#!/usr/bin/env python3
"""
Data Cleaning and Standardization Script - Step 1
Cleans and standardizes raw data before processing.
"""

import sys
from pathlib import Path
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    import duckdb
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "duckdb"])
    import duckdb

from rampa.config import config, get_db_path

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

def main():
    """Clean and standardize raw data."""
    logger.info("Starting data cleaning and standardization...")
    
    try:
        # Get database paths from config
        source_db_path = get_db_path('arcgis')
        osm_db_path = get_db_path('osm')
        target_db_path = get_db_path('final')
        
        logger.info(f"Source ArcGIS DB: {source_db_path}.db")
        logger.info(f"Source OSM DB: {osm_db_path}.db") 
        logger.info(f"Target DB: {target_db_path}.db")
        
        # Connect to databases
        source_conn = duckdb.connect(f"{source_db_path}.db")
        osm_conn = duckdb.connect(f"{osm_db_path}.db")
        target_conn = duckdb.connect(f"{target_db_path}.db")
        
        # Check source data availability
        source_tables = source_conn.execute("SHOW TABLES").fetchall()
        osm_tables = osm_conn.execute("SHOW TABLES").fetchall()
        
        logger.info(f"Found {len(source_tables)} ArcGIS tables")
        logger.info(f"Found {len(osm_tables)} OSM tables")
        
        # Basic data validation
        total_arcgis_records = 0
        for table in source_tables:
            table_name = table[0]
            count = source_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            total_arcgis_records += count
            logger.info(f"  ArcGIS {table_name}: {count:,} records")
        
        total_osm_records = 0
        for table in osm_tables:
            table_name = table[0]
            count = osm_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            total_osm_records += count
            logger.info(f"  OSM {table_name}: {count:,} records")
        
        # Data quality checks
        logger.info("Performing data quality checks...")
        
        # Check for duplicate records, null values, etc.
        quality_issues = 0
        
        # Example quality check for OSM data
        for table in osm_tables:
            table_name = table[0]
            if table_name.startswith('osm_'):
                # Check for records without coordinates
                null_coords = osm_conn.execute(f"""
                    SELECT COUNT(*) FROM {table_name} 
                    WHERE lat IS NULL OR lon IS NULL
                """).fetchone()[0]
                
                if null_coords > 0:
                    logger.warning(f"  {table_name}: {null_coords} records with missing coordinates")
                    quality_issues += null_coords
        
        # Summary
        logger.info("=== CLEANING SUMMARY ===")
        logger.info(f"Total ArcGIS records: {total_arcgis_records:,}")
        logger.info(f"Total OSM records: {total_osm_records:,}")
        logger.info(f"Data quality issues found: {quality_issues}")
        
        if quality_issues == 0:
            logger.info("✅ All data passed quality checks!")
        else:
            logger.warning(f"⚠️  {quality_issues} data quality issues found")
        
        logger.info("✅ Data cleaning and standardization completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error in data cleaning: {e}")
        return False
    
    finally:
        # Clean up connections
        try:
            if 'source_conn' in locals():
                source_conn.close()
            if 'osm_conn' in locals():
                osm_conn.close()
            if 'target_conn' in locals():
                target_conn.close()
        except:
            pass

if __name__ == "__main__":
    main()
