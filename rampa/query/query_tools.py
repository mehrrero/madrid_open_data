import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from arcgis.features import FeatureLayer
from rampa.duckdb.operations import write_layer_to_table, get_layer_from_table, is_key_in_table, get_all_layers
from rampa.duckdb.connection import DuckDBPyConnection
import json
import numpy as np
import io
from datetime import datetime
from typing import Dict, Optional, Union, Any, Tuple
import logging
import urllib3

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging instead of print statements
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            logger.info(f"Creating FeatureLayer from URL {self.url}")
            self.layer = FeatureLayer(self.url)
        else:
            raise ValueError(f"Unsupported layer type: {self.type}")

    def query(self, where: str, out_fields: str = '*') -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        """
        Executes a query on the layer and returns results as a GeoDataFrame.
        """
        if self.layer is None:
            self.create_layer()

        try:
            features = self.layer.query(where=where, out_fields=out_fields, return_geometry=True)
        except Exception as e:
            logger.error(f"Error querying layer {self.url}: {e}")
            # Try with simpler parameters
            try:
                logger.info(f"Retrying with basic parameters...")
                features = self.layer.query(where="1=1", return_geometry=True)
            except Exception as e2:
                logger.error(f"Second attempt failed: {e2}")
                return gpd.GeoDataFrame()  # Return empty GeoDataFrame
        
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
                    logger.warning(f"Failed to create GeoDataFrame with geometry column {geometry_column}: {e}")
                    # Fall back to regular DataFrame
                    return df
            else:
                # No geometry column found, return as regular DataFrame
                logger.warning(f"No geometry column found in layer {self.url}. Available columns: {df.columns.tolist()}")
                return df
        else:
            # No data returned
            logger.warning(f"No data returned from layer {self.url}")
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
    def __init__(self, 
                 url_dict: Optional[Dict[str, str]] = None, 
                 json_file: Optional[str] = None, 
                 populate: bool = True, 
                 db_connection: Optional[DuckDBPyConnection] = None,
                 store_in_memory: bool = False):
        """
        Data_Collection with DuckDB storage capabilities and improved memory management.
        
        Args:
            url_dict: Dictionary mapping layer names to URLs
            json_file: Path to JSON file with layer URLs
            populate: Whether to automatically populate layers
            db_connection: Database connection for storing layers
            store_in_memory: Whether to keep data in memory (default: False for better memory management)
        """
        if url_dict is None and json_file is None:
            raise ValueError("Either url_dict or json_file must be provided.")
        if url_dict is None and json_file is not None:
            with open(json_file, 'r') as f:
                url_dict = json.load(f)
        
        if url_dict is None:
            raise ValueError("Failed to load URL dictionary")
                
        self.url_dict = url_dict
        self.layers = {}
        self.data = {}  # Only stores metadata by default
        self.db_connection = db_connection
        self.store_in_memory = store_in_memory
        
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

    def query_layer(self, 
                    name: str, 
                    where: str, 
                    out_fields: str = '*', 
                    store_in_db: bool = False) -> Union[pd.DataFrame, gpd.GeoDataFrame]:
        """
        Queries a layer and optionally stores the result in DuckDB.
        
        Args:
            name: Layer name
            where: SQL WHERE clause
            out_fields: Fields to include
            store_in_db: Whether to store the result in DuckDB
            
        Returns:
            Query results as DataFrame or GeoDataFrame
        """
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
        
        # Check if layer is already stored in DB
        if self.db_connection and store_in_db:
            source = self.layers[name].url
            if is_key_in_table(self.db_connection, (name, source)):
                logger.info(f"Loading layer {name} from database...")
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
                        result = pd.read_json(io.StringIO(stored_data[data_key]), orient='records')
                    
                    # Restore datetime columns if they exist
                    if 'datetime_columns' in stored_data:
                        for col, dtype in stored_data['datetime_columns'].items():
                            if col in result.columns:
                                result[col] = pd.to_datetime(result[col])
                    
                    return result
                except Exception as e:
                    logger.warning(f"Error loading from DB, querying from source: {e}")
        
        # Query from source
        result = self.layers[name].query(where, out_fields)
        
        # Store in database if requested
        if self.db_connection and store_in_db:
            self.store_layer_result(name, result)
            
        return result

    def store_layer_result(self, name: str, data: Union[pd.DataFrame, gpd.GeoDataFrame]) -> bool:
        """
        Store a layer result in DuckDB.
        
        Args:
            name: Layer name
            data: DataFrame or GeoDataFrame to store
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
            
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
        
        try:
            layer_data = self.layers[name].to_dict(data)
            source = self.layers[name].url
            
            write_layer_to_table(self.db_connection, name, source, layer_data)
            logger.info(f"Stored layer {name} in database with {len(data)} records.")
            return True
        except Exception as e:
            logger.error(f"Failed to store layer {name}: {e}")
            return False

    def download_data(self, 
                      params: Optional[Dict[str, str]] = None, 
                      store_in_db: bool = True) -> Dict[str, Any]:
        """
        Downloads data from all layers with improved memory management.
        
        Args:
            params: Query parameters (where, out_fields)
            store_in_db: Whether to store results in DuckDB (recommended: True)
            
        Returns:
            Dictionary with download statistics
        """
        successful_downloads = 0
        failed_downloads = []
        
        for name, layer in tqdm(self.layers.items(), desc="Downloading layers"):
            where_clause = params.get('where', '1=1') if params else '1=1'
            out_fields = params.get('out_fields', '*') if params else '*'
            
            try:
                result = self.query_layer(name, where_clause, out_fields, store_in_db)
                
                # Check if we got valid data
                if result is not None and not result.empty:
                    # Memory management: only store in memory if explicitly requested
                    if self.store_in_memory:
                        self.data[name] = result
                    else:
                        # Store only metadata for memory efficiency
                        self.data[name] = {
                            'stored_in_db': store_in_db,
                            'table_name': f'layer_{name}',
                            'record_count': len(result),
                            'columns': list(result.columns),
                            'last_updated': datetime.now().isoformat()
                        }
                    
                    successful_downloads += 1
                    logger.info(f"✓ Successfully processed layer: {name} ({len(result)} records)")
                    
                    # Clear result from memory immediately if not storing
                    if not self.store_in_memory:
                        del result
                else:
                    failed_downloads.append(f"{name}: No data returned")
                    logger.warning(f"⚠ Warning: No data for layer: {name}")
                    
            except Exception as e:
                failed_downloads.append(f"{name}: {str(e)}")
                logger.error(f"✗ Failed to process layer {name}: {e}")
                continue  # Skip this layer and continue with the next one
        
        # Log summary
        logger.info(f"\n=== DOWNLOAD SUMMARY ===")
        logger.info(f"Successful downloads: {successful_downloads}")
        logger.info(f"Failed downloads: {len(failed_downloads)}")
        
        if failed_downloads:
            logger.warning(f"Failed layers:")
            for failure in failed_downloads:
                logger.warning(f"  - {failure}")
        
        return {
            'successful': successful_downloads,
            'failed': len(failed_downloads),
            'failed_details': failed_downloads,
            'memory_mode': 'full' if self.store_in_memory else 'metadata_only'
        }

    def load_layer_from_db(self, name: str) -> Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Load a specific layer from database (lazy loading for memory efficiency).
        
        Args:
            name: Layer name to load
            
        Returns:
            DataFrame/GeoDataFrame if found, None otherwise
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
            
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
        
        source = self.layers[name].url
        if is_key_in_table(self.db_connection, (name, source)):
            try:
                stored_data = get_layer_from_table(self.db_connection, name, source)
                
                # Check if it has geometry
                if stored_data.get('has_geometry', True):
                    data_key = 'data' if 'data' in stored_data else 'geojson'
                    gdf = gpd.read_file(stored_data[data_key])
                    if stored_data['crs']:
                        gdf.crs = stored_data['crs']
                    result = gdf
                else:
                    data_key = 'data' if 'data' in stored_data else 'geojson'
                    result = pd.read_json(io.StringIO(stored_data[data_key]), orient='records')
                
                # Restore datetime columns if they exist
                if 'datetime_columns' in stored_data:
                    for col, dtype in stored_data['datetime_columns'].items():
                        if col in result.columns:
                            result[col] = pd.to_datetime(result[col])
                
                logger.info(f"Loaded layer {name} from database: {len(result)} records")
                return result
                
            except Exception as e:
                logger.error(f"Error loading layer {name} from database: {e}")
                return None
        else:
            logger.warning(f"Layer {name} not found in database")
            return None

    def get_layer_data(self, name: str) -> Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Get layer data with smart loading (from memory if available, otherwise from DB).
        
        Args:
            name: Layer name
            
        Returns:
            Layer data or None if not found
        """
        if name in self.data:
            # Check if we have actual data or just metadata
            if isinstance(self.data[name], dict) and 'stored_in_db' in self.data[name]:
                # We have metadata, load from DB
                return self.load_layer_from_db(name)
            else:
                # We have actual data in memory
                return self.data[name]
        else:
            # Try to load from database
            return self.load_layer_from_db(name)

    def load_all_from_db(self) -> Dict[str, Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Load all available layers from the database.
        
        Returns:
            Dictionary of loaded layers (only if store_in_memory=True)
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
        
        stored_layers = get_all_layers(self.db_connection)
        
        loaded_data = {}
        for layer_info in stored_layers:
            name = layer_info['layer_name']
            layer_data = layer_info['layer_data']
            
            try:
                # Convert back to GeoDataFrame/DataFrame
                if layer_data.get('has_geometry', True):
                    data_key = 'data' if 'data' in layer_data else 'geojson'
                    gdf = gpd.read_file(layer_data[data_key])
                    if layer_data['crs']:
                        gdf.crs = layer_data['crs']
                    result = gdf
                else:
                    data_key = 'data' if 'data' in layer_data else 'geojson'
                    result = pd.read_json(io.StringIO(layer_data[data_key]), orient='records')
                
                # Restore datetime columns
                if 'datetime_columns' in layer_data:
                    for col, dtype in layer_data['datetime_columns'].items():
                        if col in result.columns:
                            result[col] = pd.to_datetime(result[col])
                
                if self.store_in_memory:
                    loaded_data[name] = result
                    self.data[name] = result
                else:
                    # Store only metadata for memory efficiency
                    self.data[name] = {
                        'stored_in_db': True,
                        'table_name': f'layer_{name}',
                        'record_count': len(result),
                        'columns': list(result.columns),
                        'last_loaded': datetime.now().isoformat()
                    }
                    loaded_data[name] = f"Metadata stored (use get_layer_data('{name}') to load)"
                
            except Exception as e:
                logger.error(f"Error loading layer {name}: {e}")
                continue
                
        logger.info(f"Processed {len(loaded_data)} layers from database.")
        if not self.store_in_memory:
            logger.info("Metadata stored for memory efficiency. Use get_layer_data(name) to load specific layers.")
        
        return loaded_data

    def get_layer_info(self, name: str) -> Union[Dict[str, Any], str]:
        """
        Get metadata about a stored layer.
        
        Args:
            name: Layer name
            
        Returns:
            Layer metadata dictionary or error message
        """
        if not self.db_connection:
            raise ValueError("No database connection provided.")
            
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
            
        source = self.layers[name].url
        if is_key_in_table(self.db_connection, (name, source)):
            try:
                stored_data = get_layer_from_table(self.db_connection, name, source)
                return {
                    'name': name,
                    'source': source,
                    'record_count': stored_data.get('record_count'),
                    'columns': stored_data.get('columns'),
                    'bounds': stored_data.get('bounds'),
                    'crs': stored_data.get('crs'),
                    'has_geometry': stored_data.get('has_geometry', True),
                    'layer_type': stored_data.get('layer_type'),
                    'dtypes': stored_data.get('dtypes')
                }
            except Exception as e:
                logger.error(f"Error getting info for layer {name}: {e}")
                return f"Error retrieving layer {name} info: {e}"
        else:
            return f"Layer {name} not found in database."
    
    def get_memory_usage_info(self) -> Dict[str, Any]:
        """
        Get information about current memory usage and data storage.
        
        Returns:
            Dictionary with memory usage statistics
        """
        memory_layers = 0
        metadata_layers = 0
        total_records_in_memory = 0
        
        for name, data in self.data.items():
            if isinstance(data, dict) and 'stored_in_db' in data:
                metadata_layers += 1
            else:
                memory_layers += 1
                if hasattr(data, '__len__'):
                    total_records_in_memory += len(data)
        
        return {
            'store_in_memory_mode': self.store_in_memory,
            'layers_in_memory': memory_layers,
            'layers_metadata_only': metadata_layers,
            'total_layers': len(self.layers),
            'total_records_in_memory': total_records_in_memory,
            'recommendation': 'Memory efficient' if not self.store_in_memory else 'Full memory mode'
        }