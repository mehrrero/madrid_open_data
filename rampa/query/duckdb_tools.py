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

# Set up logging instead of print statements
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def to_dict(self, data) -> dict:
        """
        Serializes a pandas DataFrame or GeoPandas GeoDataFrame to a dictionary suitable for JSON export,
        including metadata and handling of datetime and geometry columns.
        Args:
            data (pd.DataFrame or gpd.GeoDataFrame): The input data to serialize.
        Returns:
            dict: A dictionary containing:
                - 'data': JSON string of the data (GeoJSON for GeoDataFrame, records for DataFrame).
                - 'crs': Coordinate Reference System (CRS) of the data, if available.
                - 'layer_type': The type of the layer (from self.type).
                - 'url': The URL associated with the layer (from self.url).
                - 'record_count': Number of records in the data.
                - 'columns': List of column names.
                - 'bounds': Bounding box of the geometry (if GeoDataFrame), else None.
                - 'dtypes': Dictionary mapping column names to their data types.
                - 'datetime_columns': Dictionary of datetime columns and their original dtypes.
                - 'has_geometry': Boolean indicating if the data has geometry information.
        Notes:
            - Datetime columns are converted to ISO string format for serialization.
            - Geometry columns in GeoDataFrames are serialized as GeoJSON.
            - Object columns containing datetime-like objects are also converted to strings.
            - Handles serialization issues by converting problematic object columns to strings.
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


############################################################
############################################################
# This class wraps around the Data_Collection class to add
# database features to it.
############################################################
############################################################


class DataManager(Data_Collection):
    def __init__(self, db_connection = None, *args, **kwargs):
        self.db_connection = None
        super().__init__(*args, **kwargs)
        if db_connection is not None:
            self.db_connection = duckdb.connect(db_connection)
            self.layers = []
            if not self.populate:
                pass # Here we should try to read the layers from the DB

    def add_layer(self, name: str, url: str, type: str = 'FeatureLayer'):
        """
        Adds a new layer to the collection.
        Args:
            name (str): The unique name for the layer.
            url (str): The URL of the layer to be added.
            type (str, optional): The type of the layer. Defaults to 'FeatureLayer'.
        Raises:
            ValueError: If a layer with the given name already exists.
        """
        if self.db_connection is not None:
            if name in self.layers:
                raise ValueError(f"Layer {name} already exists.")
            
            layer = ArcGISQuery(url, type)
            data = layer.query(where="1=1", out_fields='*')
            self.store_layer_result(name, url, data)
        else:
            super().add_layer(name, url, type)


    def store_layer_result(self, name: str, url: str, data: Union[pd.DataFrame, gpd.GeoDataFrame]) -> bool:
        """
        Store a layer result in DuckDB.
        
        Args:
            name: Layer name
            data: DataFrame or GeoDataFrame to store
            
        Returns:
            True if successful, False otherwise
        """
        
        try:
            layer_data = to_dict(data)
            source = url
            
            write_layer_to_table(self.db_connection, name, source, layer_data)
            logger.info(f"Stored layer {name} in database with {len(data)} records.")
            return True
        except Exception as e:
            logger.error(f"Failed to store layer {name}: {e}")
            return False