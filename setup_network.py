from rampa.routing.route import Network
from rampa.query.duckdb_tools import ArcGISQuery
from rampa.query.madrid_api import GeoDataset, POIManager
import json
import logging
import osmnx as ox
import urllib3
from rampa.config import config

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_network():
    if config.madrid_api['populate']:
        logger.info("Downloading aceras info")
        lay = ArcGISQuery(config.madrid_api['ancho_medio_acera'])
        lay.create_layer()
        aceras = lay.query(where="1=1")
        logger.info(f"Geocoding Madrid")
        gdf = ox.geocoder.geocode_to_gdf('R5326784', by_osmid=True)
    else:
        gdf = None
        
    logger.info("Creating networks")
    net = Network(gdf, db=config.paths['grafo_db'], db_alt=config.paths['grafo_db_alt'], aceras=aceras, row='Ancho_medio', store=config.madrid_api['store'])

    logger.info("Loading POI data")
    with open('rampa/data/urls_API.json', 'r') as f:
        urls_dict = json.load(f)

    pois = POIManager(urls_dict, db=config.paths['pois_db'], store=True)

    logger.info("Everything stored in DB successfully")
if __name__ == "__main__":
    setup_network()
