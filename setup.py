#!/usr/bin/env python3
"""
Simple setup script for Madrid Open Data project.
"""

import json
from pathlib import Path
import urllib3
from loguru import logger

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

<<<<<<< HEAD
from rampa.config import config, get_db_path
<<<<<<< HEAD
=======
from rampa.duckdb.connection import get_duckdb_connection
>>>>>>> 037475f (Refactor: Remove ArcGIS and OSM data setup from setup.py)
from rampa.query.duckdb_tools import DataManager
from rampa.duckdb.src.run_transformations import run_transform_pipeline

# Setup logging
logger.add("setup_{time}.log")

def setup():
    """Main setup function."""
    logger.info("🚀 Starting Madrid Open Data setup...")
    
    # Create directories
    config.ensure_directories()
    
<<<<<<< HEAD
    # Setup data sources
    arcgis_success = setup_arcgis() if config.arcgis.get("enabled") else True
    
    # Run transformations
    transform_success = run_transformations()
    
    # Summary
    if arcgis_success and transform_success:
        logger.success("✅ Setup completed successfully!")
    else:
        logger.warning("⚠️ Setup completed with some issues - check logs above")
=======
    # Setup ArcGIS data
    if config.arcgis.get("enabled", False):
        loguru.logger.info("Downloading ArcGIS data...")
        arcgis_summary = setup_arcgis_data()
        loguru.logger.info(f"ArcGIS data download completed. Summary: {arcgis_summary}")
    else:
        loguru.logger.info("ArcGIS data collection is disabled in configuration")
        arcgis_summary = {'successful': 0, 'failed': 0, 'failed_details': []}
    
    # Run transformation pipeline
    loguru.logger.info("Starting data transformation pipeline...")
    transform_summary = run_transform_pipeline()
    loguru.logger.info(f"Data transformation completed. transform_summary: {transform_summary}")
    
    # Final setup summary
    loguru.logger.info("=== SETUP COMPLETE ===")
    loguru.logger.info(f"ArcGIS layers: {arcgis_summary['successful']} successful, {arcgis_summary['failed']} failed")
    loguru.logger.info(f"Transformations: {transform_summary['successful']}/{transform_summary['total_scripts']} successful")
    
    total_failed = arcgis_summary['failed'] + transform_summary['failed']
    if total_failed == 0:
        loguru.logger.info("🎉 All setup steps completed successfully!")
    else:
        loguru.logger.warning(f"⚠️  Setup completed with {total_failed} total issues - check logs above")
>>>>>>> 037475f (Refactor: Remove ArcGIS and OSM data setup from setup.py)

def setup_arcgis():
    """Setup ArcGIS data if enabled."""
    logger.info("📊 Setting up ArcGIS data...")
    
=======
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
>>>>>>> 433b687 (Refactor geospatial processing and demographics scripts; improve error handling and logging)
    try:
<<<<<<< HEAD
=======
        # Get configuration
>>>>>>> 037475f (Refactor: Remove ArcGIS and OSM data setup from setup.py)
        urls_file = config.arcgis["urls_file"]
        db_path = get_db_path("arcgis")
        
        # Load URLs
        with open(urls_file, 'r') as f:
            urls = json.load(f)
        
        logger.info(f"Found {len(urls)} ArcGIS layers to process")
        
        # Initialize data manager
        DataManager(
            json_file=urls_file,
            db_connection=db_path,
<<<<<<< HEAD
            populate=config.arcgis.get("populate", True)
=======
            populate=config.arcgis["populate"]
>>>>>>> 037475f (Refactor: Remove ArcGIS and OSM data setup from setup.py)
        )
        
        logger.success("✅ ArcGIS data setup completed")
        return True
        
    except Exception as e:
<<<<<<< HEAD
        logger.error(f"❌ ArcGIS setup failed: {e}")
        return False

def run_transformations():
    """Run the data transformation pipeline."""
    logger.info("🔄 Running data transformations...")
    
    try:
        result = run_transform_pipeline()
        
        if result['failed'] == 0:
            logger.success(f"✅ All {result['successful']} transformations completed")
            return True
        else:
            logger.warning(f"⚠️ {result['successful']}/{result['total_scripts']} transformations succeeded")
            return False
            
    except Exception as e:
        logger.error(f"❌ Transformation pipeline failed: {e}")
        return False
=======
        loguru.logger.error(f"Error setting up ArcGIS data: {e}")
        return {
            'successful': 0,
            'failed': 1,
            'failed_details': [str(e)]
        }


>>>>>>> 037475f (Refactor: Remove ArcGIS and OSM data setup from setup.py)

def main():
    """Entry point."""
    setup()

def main():
    """Entry point for the rampa-setup script."""
    setup()


if __name__ == "__main__":
<<<<<<< HEAD
=======
    main()

if __name__ == "__main__":
>>>>>>> 433b687 (Refactor geospatial processing and demographics scripts; improve error handling and logging)
    main()