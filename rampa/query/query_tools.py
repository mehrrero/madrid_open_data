import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from arcgis.features import FeatureLayer




class ArcGISQuery():
    """
    A class to facilitate querying ArcGIS FeatureLayers and returning results as GeoDataFrames.
    Attributes:
        url (str): The URL of the ArcGIS layer to query.
        type (str): The type of the ArcGIS layer (default is 'FeatureLayer').
        layer: The instantiated ArcGIS layer object.
    Methods:
        __init__(url: str, type: str = 'FeatureLayer'):
            Initializes the ArcGISQuery with the given layer URL and type.
        create_layer():
            Instantiates the ArcGIS layer object based on the specified type.
            Currently supports only 'FeatureLayer'.
        query(where: str, out_fields: str = '*'):
            Executes a query on the ArcGIS layer using the specified SQL where clause and output fields.
            Returns:
                gpd.GeoDataFrame: A GeoDataFrame containing the queried features with geometry.
            Raises:
                ValueError: If the specified layer type is not supported.
    """
    
    
    def __init__(self, url: str, type: str = 'FeatureLayer'):
        self.url = url
        self.type = type
        self.layer = None

    def create_layer(self):
        """
        Creates a layer object based on the specified type.
        If the layer type is 'FeatureLayer', initializes a FeatureLayer instance using the provided URL.
        Otherwise, raises a ValueError for unsupported layer types.
        Raises:
            ValueError: If the layer type is not supported.
        """
        
        if self.type == 'FeatureLayer':
            print(f"Creating FeatureLayer from URL {self.url}")
            self.layer = FeatureLayer(self.url)
        else:
            raise ValueError(f"Unsupported layer type: {self.type}")


    def query(self, where: str, out_fields: str = '*'):
        """
        Executes a query on the layer using the specified SQL WHERE clause and returns the results as a GeoDataFrame.
        Parameters:
            where (str): SQL WHERE clause to filter features in the layer.
            out_fields (str, optional): Comma-separated list of fields to include in the result. Defaults to '*', which returns all fields.
        Returns:
            geopandas.GeoDataFrame: A GeoDataFrame containing the queried features with geometry and specified fields.
        Raises:
            AttributeError: If the layer is not initialized and cannot be created.
        """
        
        
        if self.layer is None:
            self.create_layer()

        features = self.layer.query(where=where, out_fields=out_fields, return_geometry=True)
        gdf = gpd.GeoDataFrame(features.sdf, crs=self.layer.properties.extent.spatialReference['wkid'], geometry='SHAPE')

        return gdf
    
    

class Data_Collection():
    def __init__(self, url_dict: dict = None, json_file: str = None, populate: bool = True):

        """
        Data_Collection is a class for managing and querying multiple ArcGIS FeatureLayers.
        This class allows you to initialize a collection of ArcGIS layers from a dictionary of URLs or a JSON file,
        add new layers, query specific layers, and download data from all layers.
        Attributes:
            url_dict (dict): Dictionary mapping layer names to their ArcGIS service URLs.
            layers (dict): Dictionary mapping layer names to ArcGISQuery objects.
            data (dict): Dictionary to store queried data for each layer.
            populate (bool): If True, automatically populates the collection with layers from url_dict.
        Methods:
            __init__(url_dict: dict = None, json_file: str = None):
                Initializes the Data_Collection with a dictionary of URLs or a JSON file.
                Raises ValueError if neither is provided.
            add_layer(name: str, url: str, type: str = 'FeatureLayer'):
                Adds a new layer to the collection.
                Raises ValueError if the layer already exists.
            create_collection():
                Populates the collection with layers from url_dict.
            query_layer(name: str, where: str, out_fields: str = '*'):
                Queries a specific layer with a SQL-like where clause and specified output fields.
                Raises ValueError if the layer does not exist.
                Returns the query result.
            download_data(params: dict = None):
                Downloads data from all layers in the collection.
                Optionally accepts query parameters (where, out_fields).
                Stores the results in the data attribute.
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
        if populate:
            self.create_collection()


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
        
        if name in self.layers:
            raise ValueError(f"Layer {name} already exists.")
        self.layers[name] = ArcGISQuery(url, type)
        
    def create_collection(self):
        """
        Creates a collection of layers by iterating over the items in `self.url_dict`.
        For each (name, url) pair in `self.url_dict`, this method calls `self.add_layer(name, url)` 
        to add the corresponding layer to the collection.
        Returns:
            None
        """
        
        for name, url in self.url_dict.items():
            self.add_layer(name, url)

    def query_layer(self, name: str, where: str, out_fields: str = '*'):
        """
        Queries a specified layer with a given SQL-like where clause and returns the results.
        Args:
            name (str): The name of the layer to query.
            where (str): The SQL-like WHERE clause to filter the query.
            out_fields (str, optional): Comma-separated list of fields to include in the result. Defaults to '*'.
        Returns:
            Any: The result of the query operation on the specified layer.
        Raises:
            ValueError: If the specified layer name does not exist in the layers collection.
        """
        
        if name not in self.layers:
            raise ValueError(f"Layer {name} does not exist.")
        return self.layers[name].query(where, out_fields)

    def download_data(self, params: dict = None):
        """
        Downloads data from all layers and stores the results in the `self.data` dictionary.
        For each layer in `self.layers`, performs a query using the provided parameters if given,
        otherwise uses default query parameters. The result of each query is stored in `self.data`
        with the layer's name as the key.
        Args:
            params (dict, optional): A dictionary of query parameters. Supported keys are:
                - 'where' (str): SQL-like WHERE clause to filter results. Defaults to '1=1' (no filter).
                - 'out_fields' (str): Comma-separated list of fields to include in the result. Defaults to '*'.
        Returns:
            None
        """
        
        for name, layer in tqdm(self.layers.items()):
            if params:
                layer.query(where=params.get('where', '1=1'), out_fields=params.get('out_fields', '*'))
            else:
                layer.query(where="1=1", out_fields='*')
            self.data[name] = layer.query(where="1=1", out_fields='*')