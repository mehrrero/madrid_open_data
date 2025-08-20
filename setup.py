import loguru
import json
import pathlib
import urllib3
import os

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from rampa.config import config, get_db_path, get_madrid_bbox, get_osm_layers
from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.duckdb_tools import DataManager
from rampa.query.osm_tools import OSMQuery
from rampa.duckdb.src.run_transformations import run_transform_pipeline

loguru.logger.add("file_{time}.log")

def setup():
    loguru.logger.info("Setting up the application...")
    
    # Ensure all directories exist
    config.ensure_directories()
    
    # Setup ArcGIS data (currently disabled)
    loguru.logger.info(config.arcgis_config["enabled"])
    if config.arcgis_config["enabled"]:
        
        loguru.logger.info("Downloading ArcGis data...")
        arcgis_summary = setup_arcgis_data()
        loguru.logger.info(f"ArcGIS data download completed. Summary: {arcgis_summary}")
    else:
        loguru.logger.info("ArcGIS data collection is disabled in configuration")
        arcgis_summary = {'successful': 0, 'failed': 0, 'failed_details': []}
    
    # Download OSM wheelchair accessibility data
    loguru.logger.info("Starting OSM wheelchair accessibility data download...")
    osm_summary = setup_osm_data()
    loguru.logger.info(f"OSM wheelchair accessibility data download completed. osm_summary: {osm_summary}")
    
    # Run transformation pipeline
    loguru.logger.info("Starting data transformation pipeline...")
    transform_summary = run_transform_pipeline()
    loguru.logger.info(f"Data transformation completed. transform_summary: {transform_summary}")
    
    # Final setup summary
    loguru.logger.info("=== SETUP COMPLETE ===")
    loguru.logger.info(f"ArcGIS layers: {arcgis_summary['successful']} successful, {arcgis_summary['failed']} failed")
    loguru.logger.info(f"OSM data: {osm_summary['successful']} successful, {osm_summary['failed']} failed")
    loguru.logger.info(f"Transformations: {transform_summary['successful']}/{transform_summary['total_scripts']} successful")
    
    total_failed = arcgis_summary['failed'] + osm_summary['failed'] + transform_summary['failed']
    if total_failed == 0:
        loguru.logger.info("🎉 All setup steps completed successfully!")
    else:
        loguru.logger.warning(f"⚠️  Setup completed with {total_failed} total issues - check logs above")


def setup_arcgis_data():
    """Setup ArcGIS data collection using centralized configuration."""
    loguru.logger.info("Setting up ArcGIS data...")
    
    try:
        # Get configuration
        urls_file = config.arcgis_config["urls_file"]
        db_path = get_db_path("arcgis")
        
        with open(urls_file, 'r') as f:
            arcgis_urls = json.load(f)

        loguru.logger.info(f"Found {len(arcgis_urls)} URLs to process")
        loguru.logger.info(f"Available layer names: {list(arcgis_urls.keys())}")

        # Initialize ArcGIS data collection
        data_collection = DataManager(
            json_file=urls_file,
            db_connection=db_path,
            populate=config.arcgis_config["populate"]
        )
        loguru.logger.info(f"Connected to ArcGIS database: {db_path}.db")
        loguru.logger.info("ArcGIS data collection completed")
        
        return {
            'successful': 1,
            'failed': 0,
            'failed_details': []
        }
        
    except Exception as e:
        loguru.logger.error(f"Error setting up ArcGIS data: {e}")
        return {
            'successful': 0,
            'failed': 1,
            'failed_details': [str(e)]
        }
    

def setup_osm_data():
    """Setup OSM wheelchair accessibility data using centralized configuration."""
    loguru.logger.info("Setting up OSM wheelchair accessibility data...")
    
    # Get OSM database connection using config
    osm_db_con = get_duckdb_connection(get_db_path("osm"))
    loguru.logger.info(f"Created OSM database: {get_db_path('osm')}.db")

    # Get configuration
    madrid_bbox = get_madrid_bbox()
    osm_layers = get_osm_layers()
    
    osm_query = OSMQuery(bbox=madrid_bbox, city="Madrid")
    successful_layers = 0
    failed_layers = []
    
    for layer_name, layer_config in osm_layers.items():
        try:
            loguru.logger.info(f"Downloading OSM {layer_name} with wheelchair accessibility data...")
            
            # Use the query type from configuration
            query_type = layer_config.get('query_type', 'accessible_pois')
            data = osm_query.query(query_type=query_type)
            
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
    
    # Download pedestrian width data if enabled
    if config.osm_config["special_collections"]["pedestrian_widths"]["enabled"]:
        loguru.logger.info("Downloading pedestrian width data for accessibility analysis...")
        try:
            width_analysis = osm_query.get_madrid_pedestrian_widths(osm_db_con)
            if width_analysis:
                loguru.logger.info("✓ Successfully collected pedestrian width data")
            else:
                failed_layers.append("pedestrian_widths: Collection failed")
                loguru.logger.warning("⚠ Failed to collect pedestrian width data")
        except Exception as e:
            failed_layers.append(f"pedestrian_widths: {str(e)}")
            loguru.logger.error(f"✗ Error collecting pedestrian width data: {e}")
    
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


def main():
    """Entry point for the rampa-setup script."""
    setup()


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()