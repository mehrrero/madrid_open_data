import loguru
import json
import pathlib
import urllib3
import os

# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from rampa.config import config, get_db_path
from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.duckdb_tools import DataManager
from rampa.duckdb.src.run_transformations import run_transform_pipeline

loguru.logger.add("file_{time}.log")

def setup():
    loguru.logger.info("Setting up the application...")
    
    # Ensure all directories exist
    config.ensure_directories()
    
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


def setup_arcgis_data():
    """Setup ArcGIS data collection using centralized configuration."""
    loguru.logger.info("Setting up ArcGIS data...")
    
    try:
        # Get configuration
        urls_file = config.arcgis["urls_file"]
        db_path = get_db_path("arcgis")
        
        with open(urls_file, 'r') as f:
            arcgis_urls = json.load(f)

        loguru.logger.info(f"Found {len(arcgis_urls)} URLs to process")
        loguru.logger.info(f"Available layer names: {list(arcgis_urls.keys())}")

        # Initialize ArcGIS data collection
        data_collection = DataManager(
            json_file=urls_file,
            db_connection=db_path,
            populate=config.arcgis["populate"]
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



def main():
    """Entry point for the rampa-setup script."""
    setup()


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()