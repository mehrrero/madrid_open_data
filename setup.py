import loguru
import json
import pathlib
import urllib3
import os

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.duckdb_tools import DataManager
from rampa.query.osm_tools import OSMQuery

loguru.logger.add("file_{time}.log")
project_root = os.path.dirname(os.path.abspath('.'))
urls_file =  './rampa/data/urls.json'

def setup():
    loguru.logger.info("Setting up the application...")
    loguru.logger.info("Downloading ArcGis data...")

    with open(urls_file, 'r') as f:
        arcgis_urls = json.load(f)

    loguru.logger.info(f"Found {len(arcgis_urls)} URLs to process")
    loguru.logger.info(f"Available layer names: {list(arcgis_urls.keys())}")

    # Ensure database directory exists
    db_path = pathlib.Path("rampa/duckdb/databases")
    db_path.mkdir(parents=True, exist_ok=True)

    '''# Initialize ArcGIS data with separate database
    data_collection = DataManager(
        json_file=urls_file,
        db_connection=db_path / "madrid_layers.db",
        populate=True
    )'''
    loguru.logger.info("Connected to ArcGIS database: rampa/duckdb/databases/madrid_layers.db")
    loguru.logger.info("Downloading ArcGIS data and getting summary...")

    
    # Download OSM wheelchair accessibility data
    loguru.logger.info("Starting OSM wheelchair accessibility data download...")
    osm_summary = setup_osm_data()
    loguru.logger.info(f"OSM wheelchair accessibility data download completed. osm_summary: {osm_summary}")
    

def setup_osm_data():
    """
    Setup OSM wheelchair accessibility data in separate database
    """
    loguru.logger.info("Setting up OSM wheelchair accessibility data...")
    
    # Ensure database directory exists
    osm_db_path = pathlib.Path("rampa/duckdb/databases")
    osm_db_path.mkdir(parents=True, exist_ok=True)
    
    # Create separate OSM database
    osm_db_con = get_duckdb_connection("rampa/duckdb/databases/madrid_osm.db")
    loguru.logger.info("Created OSM database: rampa/duckdb/databases/madrid_osm.db")
    
    # Madrid bounding box
    madrid_bbox = (40.3119, -3.8633, 40.5640, -3.5179)
    
    # Define OSM layers to collect
    osm_layers = {
        'amenities': ['amenity'],
        'shops': ['shop'], 
        'transport': ['public_transport', 'highway'],
        'tourism': ['tourism'],
        'leisure': ['leisure'],
        'routing_infrastructure': ['routing']  # New layer for routing infrastructure
    }
    
    osm_query = OSMQuery(bbox=madrid_bbox, city="Madrid")
    successful_layers = 0
    failed_layers = []
    
    for layer_name, feature_types in osm_layers.items():
        try:
            loguru.logger.info(f"Downloading OSM {layer_name} with wheelchair accessibility data...")
            
            # For POI features, use accessible_pois query type
            if layer_name in ['amenities', 'shops', 'tourism', 'leisure']:
                data = osm_query.query(query_type="accessible_pois")
            elif layer_name == 'transport':
                data = osm_query.query(query_type="accessible_pois")  # Transport stations are also POIs
            elif layer_name == 'routing_infrastructure':
                data = osm_query.query(query_type="accessibility_routing")  # Routing infrastructure
            else:
                # For other types, use the new comprehensive query
                data = osm_query.query(query_type="accessibility_routing")
            
            if data and 'elements' in data:
                # Store in OSM database
                success = osm_query.store_in_duckdb(data, layer_name, osm_db_con)
                
                if success:
                    successful_layers += 1
                    loguru.logger.info(f"✓ Successfully stored OSM {layer_name}: {len(data['elements'])} features")
                else:
                    failed_layers.append(f"{layer_name}: Storage failed")
                    loguru.logger.error(f"✗ Failed to store OSM {layer_name}")
            else:
                failed_layers.append(f"{layer_name}: No data retrieved")
                loguru.logger.warning(f"⚠ No OSM data found for {layer_name}")
                
        except Exception as e:
            failed_layers.append(f"{layer_name}: {str(e)}")
            loguru.logger.error(f"✗ Error processing OSM {layer_name}: {e}")
    
    # Log OSM summary
    loguru.logger.info(f"OSM download completed. Successful: {successful_layers}, Failed: {len(failed_layers)}")
    
    if failed_layers:
        loguru.logger.warning("Failed OSM layers:")
        for failure in failed_layers:
            loguru.logger.warning(f"  - {failure}")
    
    # Generate OSM database summary
    try:
        tables = osm_db_con.execute("SHOW TABLES").fetchall()
        total_records = 0
        
        for table in tables:
            table_name = table[0]
            if table_name.startswith('osm_'):
                count = osm_db_con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                total_records += count
                loguru.logger.info(f"OSM table {table_name}: {count} records")
        
        loguru.logger.info(f"Total OSM records stored: {total_records}")
        
    except Exception as e:
        loguru.logger.error(f"Error generating OSM summary: {e}")
    
    return {
        'successful': successful_layers,
        'failed': len(failed_layers),
        'failed_details': failed_layers
    }


if __name__ == "__main__":
    setup()