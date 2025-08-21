import os
import sys
project_root = os.path.dirname(os.path.abspath('.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
__package__ = 'rampa'


from rampa.query.arcgis_tools import Data_Collection, ArcGISQuery
import duckdb
import pandas as pd
import geopandas as gpd
import logging
import datetime
from rampa.duckdb.operations import write_layer_to_table, get_layer_from_table, is_key_in_table, get_all_layers
from rampa.duckdb.connection import DuckDBPyConnection
from typing import Dict, Optional, Union, Any, Tuple
from tqdm import tqdm
import io
from datetime import datetime

# Set up logging instead of print statements
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import urllib3
# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def to_dict(data, layer_type, url) -> dict:
        """
        Converts a pandas DataFrame or GeoPandas GeoDataFrame into a serializable dictionary
        with metadata and data in JSON or GeoJSON format.
        This function processes datetime columns to ensure they are serialized as ISO strings,
        tracks which columns were originally datetime, and handles both regular and geospatial
        dataframes. For GeoDataFrames, it outputs GeoJSON and includes geometry-related metadata.
        Args:
            data (pd.DataFrame or gpd.GeoDataFrame): The input data to serialize.
            layer_type (str): A string indicating the type of layer (e.g., 'vector', 'raster').
            url (str): The source URL or identifier for the data.
        Returns:
            dict: A dictionary containing:
                - 'data': The serialized data (GeoJSON for GeoDataFrame, JSON for DataFrame).
                - 'crs': The coordinate reference system (if applicable).
                - 'layer_type': The provided layer type.
                - 'url': The provided URL.
                - 'record_count': Number of records in the data.
                - 'columns': List of column names.
                - 'bounds': Bounding box of the data (if applicable).
                - 'dtypes': Dictionary of column data types.
                - 'datetime_columns': Dictionary of columns originally detected as datetime.
                - 'has_geometry': Boolean indicating if geometry is present.
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
            'layer_type': layer_type,
            'url': url,
            'record_count': len(data),
            'columns': list(data.columns),
            'bounds': bounds,
            'dtypes': {col: str(dtype) for col, dtype in data.dtypes.items()},
            'datetime_columns': datetime_columns,
            'has_geometry': has_geometry
        }
        
        return layer_data


############################################################
############################################################
# This class wraps around the Data_Collection class to add
# database features to it.
############################################################
############################################################


class DataManager(Data_Collection):
    """
    DataManager is a class for managing collections of geospatial data layers, supporting both in-memory and DuckDB-backed storage.
    This class extends Data_Collection to provide advanced data management capabilities, including:
    - Adding, storing, and retrieving geospatial layers from a DuckDB database.
    - Loading layers into memory as pandas or GeoPandas DataFrames.
    - Managing metadata and supporting efficient access to large datasets.
    - Fallback to in-memory operations when no database connection is provided.
    Attributes:
        db_connection (duckdb.DuckDBPyConnection or None): The database connection used for persistent storage.
        url_dict (dict): Dictionary mapping layer names to their source URLs.
        json_file (str): Optional path to a JSON file with layer definitions.
        layers (dict): Dictionary of loaded ArcGISQuery layer objects.
        data (dict): Dictionary of loaded layer data (DataFrames or GeoDataFrames).
    Methods:
        __init__(db_connection=None, url_dict=None, json_file=None, populate=True):
            Initializes the DataManager, optionally connecting to a DuckDB database and populating layers.
        add_layer(name, url, type='FeatureLayer', store_in_memory=False):
            Adds a new layer from a URL, storing it in the database if connected.
        store_layer_result(name, url, data, layer_type):
        create_collection():
            Iterates over url_dict to add all layers to the collection.
        load_layer_from_db(name):
            Loads a data layer from the database by name.
        get_layer_data(name):
            Retrieves data for a specified layer, loading from the database if necessary.
        get_layer_info(name):
        query_layer(*args, **kwargs):
            Disabled when using a database; use get_layer_data instead.
        download_data(*args, **kwargs):
            Disabled when using a database.
        load_all_layers():
            Loads all layers into memory from the database.
        ValueError: If required arguments are missing or invalid operations are attempted.
        NotImplementedError: If disabled methods are called while using a database.
    Usage:
        dm = DataManager(db_connection="mydb.duckdb", url_dict=my_layers)
        dm.add_layer("roads", "https://example.com/roads")
        data = dm.get_layer_data("roads")
    """
    
    
    def __init__(self, db_connection = None, url_dict: dict = None, json_file: str = None, populate: bool = True):
        self.db_connection = None
        super().__init__(url_dict=url_dict, json_file=json_file, populate=False)
        
        if db_connection is not None:
            self.db_connection = duckdb.connect(db_connection)
            if populate:
                self.create_collection()
            else:
                layers_info = self.db_connection.execute("SELECT layer_name, source FROM map_layers").fetchall()
                for layer_name, source in layers_info:
                    self.layers[layer_name] = ArcGISQuery(source, 'FeatureLayer')

    def add_layer(self, name: str, url: str, type: str = 'FeatureLayer', store_in_memory: bool = False):
        """
        Adds a new layer to the current instance, fetching data from the specified URL.
        Args:
            name (str): The name to assign to the new layer.
            url (str): The URL from which to fetch the layer data.
            type (str, optional): The type of the layer (default is 'FeatureLayer').
            store_in_memory (bool, optional): If True, stores the layer data in memory (default is False).
        Raises:
            ValueError: If a layer with the given name already exists.
        Notes:
            - If a database connection exists, the layer is queried and optionally stored in memory.
            - If no database connection exists, the method falls back to the superclass implementation.
        """
        
        if self.db_connection is not None:
            if name in self.layers:
                raise ValueError(f"Layer {name} already exists.")
            
            layer = ArcGISQuery(url, type)
            data = layer.query(where="1=1", out_fields='*')
            self.store_layer_result(name, url, data, type)
            self.layers[name] = layer
            if store_in_memory:
                logger.info(f"Keeping layer {name} in memory.")
                self.data[name] = data
        else:
            super().add_layer(name, url, type)


    def store_layer_result(self, name: str, url: str, data: Union[pd.DataFrame, gpd.GeoDataFrame], layer_type: str) -> bool:
        """
        Stores the result of a data layer into the database.
        Args:
            name (str): The name of the layer to store.
            url (str): The source URL of the layer data.
            data (Union[pd.DataFrame, gpd.GeoDataFrame]): The data to be stored, as a pandas or geopandas DataFrame.
            layer_type (str): The type of the layer (e.g., 'vector', 'raster').
        Returns:
            bool: True if the layer was successfully stored, False otherwise.
        Logs:
            - Info message on successful storage with the number of records.
            - Error message if storage fails, including the exception details.
        """
        
        
        try:
            layer_data = to_dict(data, url=url, layer_type=layer_type)
            source = url
            
            write_layer_to_table(self.db_connection, name, source, layer_data)
            logger.info(f"Stored layer {name} in database with {len(data)} records.")
            return True
        except Exception as e:
            logger.error(f"Failed to store layer {name}: {e}")
            return False
        
    def create_collection(self):
        """
        Creates a collection of layers by iterating over the items in `self.url_dict`.
        For each (name, url) pair in `self.url_dict`, this method calls `self.add_layer(name, url)` 
        to add the corresponding layer to the collection.
        Returns:
            None
        """
        logger.info("Creating collection of layers from URL dictionary.")
        for name, url in tqdm(self.url_dict.items()):
            self.add_layer(name, url)
            
            
    def load_layer_from_db(self, name: str) -> Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]:
        """
        Loads a data layer from the database by its name.
        Retrieves the specified layer from the database connection if it exists. The layer can be either a 
        pandas DataFrame or a GeoPandas GeoDataFrame, depending on whether it contains geometry data. 
        The function restores the coordinate reference system (CRS) for geospatial data and attempts to 
        restore datetime columns if metadata is available.
        Args:
            name (str): The name of the layer to load.
        Returns:
            Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]: The loaded data as a DataFrame or GeoDataFrame,
            or None if the layer is not found or an error occurs.
        Raises:
            ValueError: If no database connection is provided or the layer does not exist in the configuration.
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
        Retrieve data for a specified layer by name.
        If the layer data is already loaded and present in the `self.data` dictionary, it is returned directly.
        Otherwise, attempts to load the layer data from the database.
        Args:
            name (str): The name of the layer to retrieve.
        Returns:
            Optional[Union[pd.DataFrame, gpd.GeoDataFrame]]: The data associated with the specified layer,
            either as a pandas DataFrame or a GeoPandas GeoDataFrame, or None if the layer cannot be found.
        """
        
        if name in self.data:
            return self.data[name]
        else:
            # Try to load from database
            self.data[name] = self.load_layer_from_db(name)
            return self.data[name]

    def get_layer_info(self, name: str) -> Union[Dict[str, Any], str]:
        """
        Retrieves metadata information for a specified layer from the database.
        Args:
            name (str): The name of the layer to retrieve information for.
        Returns:
            Union[Dict[str, Any], str]: A dictionary containing layer metadata if found,
            or an error message string if the layer is not found or an error occurs.
        Raises:
            ValueError: If no database connection is provided or if the specified layer does not exist.
        The returned dictionary may include the following keys:
            - 'name': Name of the layer.
            - 'source': Source URL or identifier of the layer.
            - 'record_count': Number of records in the layer.
            - 'columns': List of column names in the layer.
            - 'bounds': Spatial bounds of the layer.
            - 'crs': Coordinate reference system of the layer.
            - 'has_geometry': Boolean indicating if the layer has geometry data.
            - 'layer_type': Type of the layer.
            - 'dtypes': Data types of the columns.
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
        
    def load_all_layers(self):
        """
        Loads data for all layers into the `self.data` dictionary if not already loaded.
        Iterates over all layers defined in `self.layers`. For each layer, if its name is not present in `self.data`,
        retrieves the layer data using `get_layer_data(name)`. Requires an active database connection (`self.db_connection`).
        If no database connection is available, logs a warning message.
        Returns:
            None
        """
         
        if self.db_connection:
            for name, layer in tqdm(self.layers.items()):
                if name not in self.data:
                    _ = self.get_layer_data(name)
        else:
            logger.warning("This method requires a database connection.")
        
        
    ###### Methods to deactivate if using the database connection
    
    def query_layer(self, *args, **kwargs):
        if self.db_connection is not None:
            raise NotImplementedError("This method is disabled when using a database. Use get_layer_data instead.")
        else:
            return super().query_layer(*args, **kwargs)
    
    def download_data(self, *args, **kwargs):
        if self.db_connection is not None:
            raise NotImplementedError("This method is disabled when using a database")
        else:
            return super().download_data(*args, **kwargs)
        
    
