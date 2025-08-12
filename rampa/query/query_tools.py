import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from arcgis.features import FeatureLayer
from rampa.duckdb.operations import write_layer_to_table, get_layer_from_table, is_key_in_table, get_all_layers
from rampa.duckdb.connection import DuckDBPyConnection
import json
import numpy as np
from datetime import datetime


class ArcGISQuery():
    """
    A class to facilitate querying ArcGIS FeatureLayers and returning results as GeoDataFrames.
    """
    
    def __init__(self, url: str, type: str = 'FeatureLayer'):
        self.url = url
        self.type = type
        self.layer = None

    def create_layer(self):
        """
        Creates a layer object based on the specified type.
        """
        if self.type == 'FeatureLayer':
            print(f"Creating FeatureLayer from URL {self.url}")
            self.layer = FeatureLayer(self.url)
        else:
            raise ValueError(f"Unsupported layer type: {self.type}")

    def query(self, where: str, out_fields: str = '*'):
        """
        Executes a query on the layer and returns results as a GeoDataFrame.
        """
        if self.layer is None:
            self.create_layer()

        features = self.layer.query(where=where, out_fields=out_fields, return_geometry=True)
        
        # Check if we have spatial data
        if hasattr(features, 'sdf') and not features.sdf.empty:
            df = features.sdf
            
            # Find the geometry column - it might be named differently
            geometry_column = None
            potential_geom_cols = ['SHAPE', 'geometry', 'geom', 'the_geom']
            
            for col in potential_geom_cols:
                if col in df.columns:
                    geometry_column = col
                    break
            
            # If we found a geometry column, create a GeoDataFrame
            if geometry_column is not None:
                try:
                    gdf = gpd.GeoDataFrame(
                        df, 
                        crs=self.layer.properties.extent.spatialReference['wkid'], 
                        geometry=geometry_column
                    )
                    return gdf
                except Exception as e:
                    print(f"Failed to create GeoDataFrame with geometry column {geometry_column}: {e}")
                    # Fall back to regular DataFrame
                    return df
            else:
                # No geometry column found, return as regular DataFrame
                print(f"No geometry column found in layer {self.url}. Available columns: {df.columns.tolist()}")
                return df
        else:
            # No data returned
            print(f"No data returned from layer {self.url}")
            return gpd.GeoDataFrame()  # Return empty GeoDataFrame
    
    def to_dict(self, data) -> dict:
        """
        Convert DataFrame or GeoDataFrame to a dictionary format suitable for storage.
        """
        # Make a copy to avoid modifying the original
        data_copy = data.copy()
        
        # Store datetime column info for reconstruction
        datetime_columns = {}
        
        # Convert datetime columns to ISO strings and track them
        for col in data_copy.columns:
            if pd.api.types.is_datetime64_any_dtype(data_copy[col]):
                datetime_columns[col] = str(data_copy[col].dtype)
                data_copy[col] = pd.to_datetime(data_copy[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
            elif data_copy[col].dtype == 'object':
                # Check if object column contains timestamps
                sample = data_copy[col].dropna().iloc[0] if not data_copy[col].dropna().empty else None
                if isinstance(sample, (pd.Timestamp, datetime)):
                    datetime_columns[col] = 'datetime64[ns]'
                    data_copy[col] = pd.to_datetime(data_copy[col]).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Handle both GeoDataFrame and regular DataFrame
        if isinstance(data_copy, gpd.GeoDataFrame):
            # Convert GeoDataFrame to GeoJSON
            try:
                geojson = data_copy.to_json()
                has_geometry = True
                bounds = data_copy.total_bounds.tolist() if not data_copy.empty else None
                crs = str(data.crs) if data.crs else None
            except TypeError:
                # If there are still serialization issues, convert all object columns to strings
                for col in data_copy.select_dtypes(include=['object']).columns:
                    if col != 'geometry':  # Don't convert geometry column
                        data_copy[col] = data_copy[col].astype(str)
                geojson = data_copy.to_json()
                has_geometry = True
                bounds = data_copy.total_bounds.tolist() if not data_copy.empty else None
                crs = str(data.crs) if data.crs else None
        else:
            # Regular DataFrame - convert to JSON
            geojson = data_copy.to_json(orient='records')
            has_geometry = False
            bounds = None
            crs = None
        
        # Add metadata including datetime column info
        layer_data = {
            'data': geojson,  # Changed from 'geojson' to 'data' for consistency
            'crs': crs,
            'layer_type': self.type,
            'url': self.url,
            'record_count': len(data),
            'columns': list(data.columns),
            'bounds': bounds,
            'dtypes': {col: str(dtype) for col, dtype in data.dtypes.items()},
            'datetime_columns': datetime_columns,
            'has_geometry': has_geometry
        }
        
        return layer_data


class Data_Collection():
    def __init__(self, url_dict: dict = None, json_file: str = None, populate: bool = True, db_connection: DuckDBPyConnection = None):
        """
        Data_Collection with DuckDB storage capabilities.
        
        Args:
            url_dict (dict): Dictionary mapping layer names to URLs
            json_file (str): Path to JSON file with layer URLs
            populate (bool): Whether to automatically populate layers
            db_connection (DuckDBPyConnection): Database connection for storing layers
        """
        if url_dict is None and json_file is None:
            raise ValueError("Either url_dict or json_file must be provided.")
        if url_dict is None:
            import json
            with open(json_file, 'r') as f:
                url_dict = json.load(f)
                
        self.url_dict = url_dict
        self.layers = {}
        self.data = {}
        self.db_connection = db_connection
        
        if populate:
            self.create_collection()

    def add_layer(self, name: str, url: str, type: str = 'FeatureLayer'):
        """
        Adds a new layer to the collection.
        """
        if name in self.layers:
            raise ValueError(f"Layer {name} already exists.")
        self.layers[name] = ArcGISQuery(url, type)
        
    def create_collection(self):
        """
        Creates a collection of layers from url_dict.
        """
        for name, url in self.url_dict.items():
            self.add_layer(name, url)

    def query_layer(self, name: str, where: str, out_fields: str = '*', store_in_db: bool = False):
        """
        Queries a layer and optionally stores the result in DuckDB.
        
        Args:
            name (str): Layer name
            where (str): SQL WHERE clause
            out_fields (str): Fields to include
            store_in_db (bool): Whether to store the result in DuckDB
            
        Returns:
            gpd.GeoDataFrame: Query results
        """
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
        
        # Check if layer is already stored in DB
        if self.db_connection and store_in_db:
            source = self.layers[name].url
            if is_key_in_table(self.db_connection, (name, source)):
                print(f"Loading layer {name} from database...")
                try:
                    stored_data = get_layer_from_table(self.db_connection, name, source)
                    
                    # Check if it has geometry
                    if stored_data.get('has_geometry', True):  # Default to True for backward compatibility
                        # Convert back to GeoDataFrame
                        data_key = 'data' if 'data' in stored_data else 'geojson'  # Handle both old and new format
                        gdf = gpd.read_file(stored_data[data_key])
                        if stored_data['crs']:
                            gdf.crs = stored_data['crs']
                        result = gdf
                    else:
                        # Convert back to regular DataFrame
                        data_key = 'data' if 'data' in stored_data else 'geojson'
                        result = pd.read_json(stored_data[data_key])
                    
                    # Restore datetime columns if they exist
                    if 'datetime_columns' in stored_data:
                        for col, dtype in stored_data['datetime_columns'].items():
                            if col in result.columns:
                                result[col] = pd.to_datetime(result[col])
                    
                    return result
                except Exception as e:
                    print(f"Error loading from DB, querying from source: {e}")
        
        # Query from source
        result = self.layers[name].query(where, out_fields)
        
        # Store in database if requested
        if self.db_connection and store_in_db:
            self.store_layer_result(name, result)
            
        return result

    def store_layer_result(self, name: str, data):
        """
        Store a layer result in DuckDB.
        
        Args:
            name (str): Layer name
            data: DataFrame or GeoDataFrame to store
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
            
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
            
        layer_data = self.layers[name].to_dict(data)
        source = self.layers[name].url
        
        write_layer_to_table(self.db_connection, name, source, layer_data)
        print(f"Stored layer {name} in database.")

    def download_data(self, params: dict = None, store_in_db: bool = False):
        """
        Downloads data from all layers and optionally stores in database.
        
        Args:
            params (dict): Query parameters (where, out_fields)
            store_in_db (bool): Whether to store results in DuckDB
        """
        for name, layer in tqdm(self.layers.items(), desc="Downloading layers"):
            where_clause = params.get('where', '1=1') if params else '1=1'
            out_fields = params.get('out_fields', '*') if params else '*'
            
            result = self.query_layer(name, where_clause, out_fields, store_in_db)
            self.data[name] = result

    def load_all_from_db(self):
        """
        Load all available layers from the database.
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
        
        stored_layers = get_all_layers(self.db_connection)
        
        loaded_data = {}
        for layer_info in stored_layers:
            name = layer_info['layer_name']
            layer_data = layer_info['layer_data']
            
            # Convert back to GeoDataFrame
            import json
            gdf = gpd.read_file(layer_data['geojson'])
            if layer_data['crs']:
                gdf.crs = layer_data['crs']
                
            loaded_data[name] = gdf
            
        self.data.update(loaded_data)
        print(f"Loaded {len(loaded_data)} layers from database.")
        
        return loaded_data

    def get_layer_info(self, name: str):
        """
        Get metadata about a stored layer.
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
            
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
            
        source = self.layers[name].url
        if is_key_in_table(self.db_connection, (name, source)):
            stored_data = get_layer_from_table(self.db_connection, name, source)
            return {
                'name': name,
                'source': source,
                'record_count': stored_data.get('record_count'),
                'columns': stored_data.get('columns'),
                'bounds': stored_data.get('bounds'),
                'crs': stored_data.get('crs')
            }
        else:
            return f"Layer {name} not found in database."