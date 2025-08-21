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
from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.duckdb_tools import DataManager
from rampa.duckdb.src.run_transformations import run_transform_pipeline

# Setup logging
logger.add("setup_{time}.log")

def setup():
    """Main setup function."""
    logger.info("🚀 Starting Madrid Open Data setup...")
    
    # Create directories
    config.ensure_directories()
    
    # Setup ArcGIS data
    if config.arcgis.get("enabled", False):
        logger.info("📊 Downloading ArcGIS data...")
        arcgis_summary = setup_arcgis_data()
        logger.info(f"ArcGIS data download completed. Summary: {arcgis_summary}")
    else:
        logger.info("ArcGIS data collection is disabled in configuration")
        arcgis_summary = {'successful': 0, 'failed': 0, 'failed_details': []}
    
    # Run transformation pipeline
    logger.info("🔄 Starting data transformation pipeline...")
    transform_summary = run_transform_pipeline()
    logger.info(f"Data transformation completed. Transform summary: {transform_summary}")
    
    # Final setup summary
    logger.info("=== SETUP COMPLETE ===")
    logger.info(f"ArcGIS layers: {arcgis_summary['successful']} successful, {arcgis_summary['failed']} failed")
    logger.info(f"Transformations: {transform_summary['successful']}/{transform_summary['total_scripts']} successful")
    
    total_failed = arcgis_summary['failed'] + transform_summary['failed']
    if total_failed == 0:
        logger.success("🎉 All setup steps completed successfully!")
    else:
        logger.warning(f"⚠️ Setup completed with {total_failed} total issues - check logs above")


def setup_arcgis_data():
    """Setup ArcGIS data collection using centralized configuration."""
    logger.info("📊 Setting up ArcGIS data...")
    
    try:
        # Get configuration
        urls_file = config.arcgis["urls_file"]
        db_path = get_db_path("arcgis")
        
        with open(urls_file, 'r') as f:
            arcgis_urls = json.load(f)

        logger.info(f"Found {len(arcgis_urls)} URLs to process")
        logger.info(f"Available layer names: {list(arcgis_urls.keys())}")

        # Initialize ArcGIS data collection
        data_collection = DataManager(
            json_file=urls_file,
            db_connection=db_path,
            populate=config.arcgis["populate"]
        )
        logger.info(f"Connected to ArcGIS database: {db_path}.db")
        logger.success("✅ ArcGIS data collection completed")
        
        return {
            'successful': 1,
            'failed': 0,
            'failed_details': []
        }
        
    except Exception as e:
        logger.error(f"❌ Error setting up ArcGIS data: {e}")
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