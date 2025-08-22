import requests
import gzip
import io
import zipfile
import pandas as pd
import geopandas as gpd
import duckdb

class GeoDataset:
    def __init__(self, name, url):
        """
        Initializes the instance with the provided URL, sets up placeholders for dataframes,
        and triggers the data download process.
        Args:
            url (str): The URL from which to download the data.
        Attributes:
            url (str): The URL for data retrieval.
            df (pandas.DataFrame or None): Placeholder for the downloaded data as a DataFrame.
            gdf (geopandas.GeoDataFrame or None): Placeholder for the downloaded data as a GeoDataFrame.
        Calls:
            download_data(): Downloads and processes the data from the specified URL.
        """
        self.name = name
        self.url = url
        self.df = None
        self.gdf = None
        self.download_data()

    def download_data(self):
        """
        Downloads data from the specified URL, reads the CSV content using the correct separator and encoding,
        and stores it as a pandas DataFrame in the `self.df` attribute.
        Raises:
            requests.HTTPError: If the HTTP request returned an unsuccessful status code.
            pandas.errors.ParserError: If the CSV parsing fails.
        """
        headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0 Safari/537.36"
                }
        # Download the file
        response = requests.get(self.url, headers=headers)
        response.raise_for_status()

        # Read CSV directly from response content with correct separator
        self.df = pd.read_csv(io.StringIO(response.content.decode('ISO-8859-1')), sep=';')
        self.df['source'] = self.name

    def to_gdf(self):
        """
        Converts the DataFrame (`self.df`) to a GeoDataFrame (`self.gdf`) with point geometries.
        The method checks if `self.df` is not None. If data is available, it creates a GeoDataFrame
        using the longitude (`LONGITUD`) and latitude (`LATITUD`) columns to generate point geometries,
        and sets the coordinate reference system to EPSG:4326. If no data is available, it prints a warning message.
        Returns:
            None
        """
        
        if self.df is not None:
            self.gdf = gpd.GeoDataFrame(self.df, geometry=gpd.points_from_xy(self.df.LONGITUD, self.df.LATITUD), crs="EPSG:4326")
        else:
            print("No data available to convert.")


class POIManager:
    def __init__(self, dict = None, db = None, store = False):
        """
        Initializes the class instance by loading geospatial data from either a provided dictionary of URLs or a DuckDB database file.
        Parameters:
            dict (dict, optional): A dictionary mapping dataset names to URLs. If provided, datasets are loaded from these URLs using the GeoDataset class.
            db (str, optional): Path to a DuckDB database file. If provided, connects to the database and loads the 'pois' table.
            store (bool, optional): If True and a database connection exists, stores the loaded dataset into the 'pois' table in the database.
        Attributes:
            dict (dict): The input dictionary of dataset URLs.
            store (bool): Indicates whether to store the dataset in the database.
            db_connection (duckdb.DuckDBPyConnection): The DuckDB database connection, if applicable.
            geo_datasets (dict): Dictionary of GeoDataset instances loaded from URLs (if dict is provided).
            dataset (pd.DataFrame): The combined dataset loaded from either the database or the provided URLs.
            gdf (gpd.GeoDataFrame): A GeoDataFrame constructed from the dataset, with geometry based on longitude and latitude columns.
        """
        
        self.dict = dict
        self.store = store
        
        if db is not None:
            if hasattr(self, "db_connection") and self.db_connection is not None:
                self.db_connection.close()
            self.db_connection = duckdb.connect(db)
            
        if dict is None:
            self.dataset = self.db_connection.execute("SELECT * FROM pois").fetchdf()
        else:
            self.geo_datasets = {key: GeoDataset(key, url) for key, url in dict.items()}
            self.dataset = pd.concat([geo_ds.df for geo_ds in self.geo_datasets.values() if geo_ds.df is not None], ignore_index=True)

        if self.store and self.db_connection is not None:
            self.db_connection.register("pois", self.dataset)
            self.db_connection.execute("CREATE OR REPLACE TABLE pois AS SELECT * FROM pois")

        self.gdf = gpd.GeoDataFrame(self.dataset, geometry=gpd.points_from_xy(self.dataset.LONGITUD, self.dataset.LATITUD), crs="EPSG:4326")
