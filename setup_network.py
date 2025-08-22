from rampa.routing.route import Network
from rampa.query.duckdb_tools import ArcGISQuery
from rampa.query.madrid_api import GeoDataset, POIManager
import json
import logging
import osmnx as ox
import urllib3

with open("config.json", "r", encoding="utf-8") as f:
    json_config = json.load(f)

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup():
    logger.info("Downloading aceras info")
    lay = ArcGISQuery(json_config['ancho_medio_acera'])
    lay.create_layer()
    aceras = lay.query(where="1=1")
    logger.info(f"Geocoding Madrid")
    madrid = ox.geocoder.geocode_to_gdf('R5326784', by_osmid=True)
    logger.info("Creating networks")
    net = Network(madrid, db=json_config['db'], db_alt=json_config['db_alt'], aceras=aceras, row='Ancho_medio', store=True)

    logger.info("Loading POI data")
    with open('rampa/data/urls_API.json', 'r') as f:
        urls_dict = json.load(f)

    pois = POIManager(urls_dict, db=json_config['pois_db'], store=True)

    logger.info("Everything stored in DB successfully")
if __name__ == "__main__":
    setup()
