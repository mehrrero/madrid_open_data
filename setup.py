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

if __name__ == "__main__":
    main()