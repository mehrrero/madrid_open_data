import loguru
import json
import pathlib
import urllib3

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.arcgis_tools import Data_Collection, OSMQuery

loguru.logger.add("file_{time}.log")
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

    # Initialize ArcGIS data with separate database
    arcgis_db_con = get_duckdb_connection("rampa/duckdb/databases/madrid_layers")
    loguru.logger.info("Connected to ArcGIS database: rampa/duckdb/databases/madrid_layers.db")
    data_collection = Data_Collection(
        url_dict=arcgis_urls,
        db_connection=arcgis_db_con
    )
    
    # Download ArcGIS data and get summary
    download_summary = data_collection.download_data(store_in_db=True)
    
    loguru.logger.info("ArcGis data download process completed.")
    loguru.logger.info(f"Successfully processed: {download_summary['successful']} layers")
    loguru.logger.info(f"Failed to process: {download_summary['failed']} layers")
    
    if download_summary['failed'] > 0:
        loguru.logger.warning("Some layers failed to download. Check the output for details.")
    
    # Download OSM wheelchair accessibility data
    loguru.logger.info("Starting OSM wheelchair accessibility data download...")
    osm_summary = setup_osm_data()
    
    # Combined summary
    total_summary = {
        'arcgis': download_summary,
        'osm': osm_summary,
        'total_successful': download_summary['successful'] + osm_summary['successful'],
        'total_failed': download_summary['failed'] + osm_summary['failed']
    }
    
    loguru.logger.info(f"Setup completed. Total successful: {total_summary['total_successful']}, Total failed: {total_summary['total_failed']}")
    
    return total_summary

def setup_osm_data():
    """
    Setup OSM wheelchair accessibility data in separate database
    """
    loguru.logger.info("Setting up OSM wheelchair accessibility data...")
    
    # Ensure database directory exists
    osm_db_path = pathlib.Path("rampa/duckdb/databases")
    osm_db_path.mkdir(parents=True, exist_ok=True)
    
    # Create separate OSM database
    osm_db_con = get_duckdb_connection("rampa/duckdb/databases/madrid_osm")
    loguru.logger.info("Created OSM database: rampa/duckdb/databases/madrid_osm.db")
    
    # Madrid bounding box
    madrid_bbox = (40.3119, -3.8633, 40.5640, -3.5179)
    
    # Define OSM layers to collect
    osm_layers = {
        'amenities': ['amenity'],
        'shops': ['shop'], 
        'transport': ['public_transport', 'highway'],
        'tourism': ['tourism'],
        'leisure': ['leisure']
    }
    
    osm_query = OSMQuery(bbox=madrid_bbox, city="Madrid")
    successful_layers = 0
    failed_layers = []
    
    for layer_name, feature_types in osm_layers.items():
        try:
            loguru.logger.info(f"Downloading OSM {layer_name} with wheelchair accessibility data...")
            
            # Query each feature type and combine
            all_data = {'elements': []}
            
            for feature_type in feature_types:
                data = osm_query.query(feature_type=feature_type)
                if data and 'elements' in data:
                    all_data['elements'].extend(data['elements'])
            
            if all_data['elements']:
                # Store in OSM database
                success = osm_query.store_in_duckdb(all_data, layer_name, osm_db_con)
                
                if success:
                    successful_layers += 1
                    loguru.logger.info(f"✓ Successfully stored OSM {layer_name}: {len(all_data['elements'])} features")
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