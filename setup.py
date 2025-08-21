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
from rampa.query.duckdb_tools import DataManager
from rampa.duckdb.src.run_transformations import run_transform_pipeline

# Setup logging
logger.add("setup_{time}.log")

def setup():
    """Main setup function."""
    logger.info("🚀 Starting Madrid Open Data setup...")
    
    # Create directories
    config.ensure_directories()
    
    # Setup data sources
    arcgis_success = setup_arcgis() if config.arcgis.get("enabled") else True
    
    # Run transformations
    transform_success = run_transformations()
    
    # Summary
    if arcgis_success and transform_success:
        logger.success("✅ Setup completed successfully!")
    else:
        logger.warning("⚠️ Setup completed with some issues - check logs above")

def setup_arcgis():
    """Setup ArcGIS data if enabled."""
    logger.info("📊 Setting up ArcGIS data...")
    
    try:
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
            populate=config.arcgis.get("populate", True)
        )
        
        logger.success("✅ ArcGIS data setup completed")
        return True
        
    except Exception as e:
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

def main():
    """Entry point."""
    setup()

if __name__ == "__main__":
    main()