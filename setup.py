import loguru
import json
import pathlib

from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.query_tools import Data_Collection

loguru.logger.add("file_{time}.log")
urls_file =  './rampa/data/urls.json'

def setup():
    loguru.logger.info("Setting up the application...")
    loguru.logger.info("Downloading ArcGis data...")

    with open(urls_file, 'r') as f:
        arcgis_urls = json.load(f)

    loguru.logger.info(f"Found {len(arcgis_urls)} URLs to process")
    loguru.logger.info(f"Available layer names: {list(arcgis_urls.keys())}")

    # Initialize with database connection
    db_con = get_duckdb_connection("rampa/duckdb/databases/madrid_layers")
    data_collection = Data_Collection(
        url_dict=arcgis_urls,
        db_connection=db_con
    )
    data_collection.download_data(store_in_db=True)

    loguru.logger.info("ArcGis data downloaded and processed successfully.")


if __name__ == "__main__":
    setup()