# Geospatial processing script to extract geographic data from TopoJSON
# and create the dim_geography table with proper geometries.

"""
Geospatial processing script to extract geographic data from TopoJSON census sections
and create the dim_geography table with proper WGS84 geometries.
"""

import duckdb
import geopandas as gpd
import sys
from pathlib import Path
from loguru import logger

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa'
TOPOJSON_PATH = 'rampa/data/Secciones_Censales.json'

def load_census_sections_from_topojson():
    """Load census sections from TopoJSON file using GeoPandas."""
    logger.info("Loading census sections from TopoJSON file...")
    
    try:
        # Read the TopoJSON file directly with GeoPandas
        gdf = gpd.read_file(TOPOJSON_PATH)
        
        logger.info(f"Loaded {len(gdf)} features from TopoJSON")
        logger.info(f"CRS: {gdf.crs}")
        logger.info(f"Columns: {list(gdf.columns)}")
        
        # Check coordinate bounds
        bounds = gdf.total_bounds
        logger.info(f"Coordinate bounds: {bounds}")
        
        # Verify coordinates are in Madrid area
        if bounds[0] < -4 or bounds[0] > -3 or bounds[1] < 40 or bounds[1] > 41:
            logger.warning("Coordinates may not be in Madrid area")
        else:
            logger.info("✅ Coordinates are in Madrid area")
        
        return gdf
        
    except Exception as e:
        logger.error(f"Error loading TopoJSON file: {e}")
        raise

def create_dim_geography_table(conn):
    """Create the dim_geography table with proper schema."""
    logger.info("Creating dim_geography table...")
    
    conn.execute("DROP TABLE IF EXISTS dim_geography")
    conn.execute("""
        CREATE TABLE dim_geography (
            census_section_id VARCHAR PRIMARY KEY,
            district_id VARCHAR,
            district_name VARCHAR,
            neighborhood_id VARCHAR,
            neighborhood_name VARCHAR,
            geom VARCHAR
        )
    """)
    logger.info("✅ dim_geography table created")

def populate_dim_geography_table(conn, gdf):
    """Populate the dim_geography table with data from GeoDataFrame."""
    logger.info("Populating dim_geography table...")
    
    # Prepare data for insertion
    records = []
    for idx, row in gdf.iterrows():
        # Extract properties
        census_section_id = str(row['COD_SECCIO']) if row['COD_SECCIO'] else None
        district_id = str(row['COD_DIS']) if row['COD_DIS'] else None
        district_name = str(row['NOM_DIS']) if row['NOM_DIS'] else None
        neighborhood_id = str(row['COD_BAR']) if row['COD_BAR'] else None
        neighborhood_name = str(row['NOM_BAR']) if row['NOM_BAR'] else None
        
        # Convert geometry to WKT
        geom_wkt = row.geometry.wkt if row.geometry else None
        
        if census_section_id and geom_wkt:
            records.append((
                census_section_id,
                district_id,
                district_name,
                neighborhood_id,
                neighborhood_name,
                geom_wkt
            ))
    
    # Insert records
    if records:
        conn.executemany("""
            INSERT OR REPLACE INTO dim_geography 
            (census_section_id, district_id, district_name, neighborhood_id, neighborhood_name, geom)
            VALUES (?, ?, ?, ?, ?, ?)
        """, records)
        
        logger.info(f"✅ Inserted {len(records)} census sections")
        
        # Print summary statistics
        total_sections = conn.execute("SELECT COUNT(*) FROM dim_geography").fetchone()[0]
        sections_with_geom = conn.execute("SELECT COUNT(*) FROM dim_geography WHERE geom IS NOT NULL").fetchone()[0]
        
        logger.info(f"Total census sections: {total_sections}")
        logger.info(f"Sections with geometry: {sections_with_geom}")
        
        # Print district distribution
        district_dist = conn.execute("""
            SELECT district_name, COUNT(*) as sections 
            FROM dim_geography 
            GROUP BY district_name 
            ORDER BY sections DESC
        """).fetchall()
        
        logger.info("District distribution:")
        for district, count in district_dist[:5]:  # Show top 5
            logger.info(f"  {district}: {count} sections")
        
    else:
        logger.warning("No records to insert")

def main():
    """Main function to process geospatial data."""
    logger.info("🚀 Starting geospatial processing...")
    
    try:
        # Load data from TopoJSON
        gdf = load_census_sections_from_topojson()
        
        # Connect to database
        conn = duckdb.connect(f"{TARGET_DATABASE_PATH}.db")
        
        # Create and populate table
        create_dim_geography_table(conn)
        populate_dim_geography_table(conn, gdf)
        
        conn.close()
        logger.info("✅ Geospatial processing completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during geospatial processing: {e}")
        raise

if __name__ == "__main__":
    main()
