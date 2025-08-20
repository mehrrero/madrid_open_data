#!/usr/bin/env python3
"""
Geography Dimension Processing Script - Step 2
Creates and populates the dim_geography table with census section geometries.
"""

import sys
from pathlib import Path
import json
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

try:
    import topojson
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "topojson"])
    import topojson

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa'          # Target for normalized data
CENSUS_SECTIONS_JSON = 'rampa/data/Secciones_Censales.json'       # Census sections geometries

def load_census_geometries():
    """Load and convert TopoJSON census sections to WKT geometries."""
    logger.info("Loading census section geometries...")
    
    try:
        # Load the TopoJSON file
        with open(CENSUS_SECTIONS_JSON, 'r', encoding='utf-8') as f:
            topo_data = json.load(f)
        
        logger.info(f"Loaded TopoJSON with {len(topo_data.get('arcs', []))} arcs")
        
        # Convert TopoJSON to GeoJSON
        geojson_data = topojson.convert(topo_data)
        
        # Extract geometries with census section details
        geography_records = []
        
        if 'features' in geojson_data:
            features = geojson_data['features']
        else:
            # Handle case where it's a FeatureCollection or direct geometry collection
            features = geojson_data.get('geometries', [])
        
        logger.info(f"Processing {len(features)} census sections...")
        
        for feature in features:
            props = feature.get('properties', {})
            geometry = feature.get('geometry', {})
            
            # Extract geographic information
            district_id = props.get('COD_DIS')
            district_name = props.get('NOM_DIS')
            neighborhood_name = props.get('NOM_BAR')
            census_section_id = props.get('COD_SECCIO')
            
            if not census_section_id:
                continue
            
            # Convert geometry to WKT format
            if geometry.get('type') == 'Polygon':
                wkt_geom = polygon_to_wkt(geometry)
            elif geometry.get('type') == 'MultiPolygon':
                wkt_geom = multipolygon_to_wkt(geometry)
            else:
                logger.warning(f"Unsupported geometry type: {geometry.get('type')} for section {census_section_id}")
                continue
            
            if wkt_geom:
                # Add SRID for web compatibility
                wkt_with_srid = f"SRID=4326;{wkt_geom}"
                
                # Create geography record
                geography_record = (
                    str(district_id) if district_id else None,
                    district_name,
                    neighborhood_name,
                    str(census_section_id),
                    wkt_with_srid
                )
                geography_records.append(geography_record)
        
        logger.info(f"✅ Processed {len(geography_records)} census section records")
        return geography_records
        
    except Exception as e:
        logger.error(f"❌ Error loading census geometries: {e}")
        return []

def polygon_to_wkt(polygon_geom):
    """Convert GeoJSON Polygon to WKT format."""
    try:
        coordinates = polygon_geom.get('coordinates', [])
        if not coordinates:
            return None
        
        # Handle exterior ring and holes
        rings = []
        for ring in coordinates:
            if len(ring) < 4:  # Need at least 4 points for a valid ring
                continue
            ring_str = ','.join([f"{coord[0]} {coord[1]}" for coord in ring])
            rings.append(f"({ring_str})")
        
        if rings:
            return f"POLYGON({','.join(rings)})"
        return None
        
    except Exception as e:
        logger.warning(f"Error converting polygon to WKT: {e}")
        return None

def multipolygon_to_wkt(multipolygon_geom):
    """Convert GeoJSON MultiPolygon to WKT format."""
    try:
        coordinates = multipolygon_geom.get('coordinates', [])
        if not coordinates:
            return None
        
        polygons = []
        for polygon_coords in coordinates:
            rings = []
            for ring in polygon_coords:
                if len(ring) < 4:
                    continue
                ring_str = ','.join([f"{coord[0]} {coord[1]}" for coord in ring])
                rings.append(f"({ring_str})")
            
            if rings:
                polygons.append(f"({','.join(rings)})")
        
        if polygons:
            return f"MULTIPOLYGON({','.join(polygons)})"
        return None
        
    except Exception as e:
        logger.warning(f"Error converting multipolygon to WKT: {e}")
        return None

def create_dim_geography_table(target_conn):
    """Create the dim_geography table with proper schema."""
    logger.info("Creating dim_geography table...")
    
    target_conn.execute("DROP TABLE IF EXISTS dim_geography")
    target_conn.execute("""
        CREATE TABLE dim_geography (
            district_id VARCHAR,
            district_name TEXT,
            neighborhood_name TEXT,
            census_section_id VARCHAR PRIMARY KEY,
            geom TEXT
        )
    """)
    logger.info("✅ dim_geography table created")

def populate_geography_table(target_conn, geography_records):
    """Populate the dim_geography table with census section data."""
    logger.info("Populating dim_geography table...")
    
    if not geography_records:
        logger.warning("No geography records to insert")
        return
    
    logger.info(f"Inserting {len(geography_records)} records into dim_geography...")
    
    target_conn.execute("BEGIN TRANSACTION")
    try:
        insert_query = """
            INSERT INTO dim_geography (
                district_id, district_name, neighborhood_name, census_section_id, geom
            ) VALUES (?, ?, ?, ?, ?)
        """
        
        batch_size = 1000
        for i in range(0, len(geography_records), batch_size):
            batch = geography_records[i:i + batch_size]
            target_conn.executemany(insert_query, batch)
            
            if (i + batch_size) % 5000 == 0:
                logger.info(f"Inserted {i + batch_size} records...")
        
        target_conn.execute("COMMIT")
        logger.info("✅ All geography records inserted successfully!")
        
    except Exception as e:
        target_conn.execute("ROLLBACK")
        logger.error(f"❌ Insert failed, transaction rolled back: {e}")
        raise

def generate_summary(target_conn):
    """Generate summary statistics for the dim_geography table."""
    logger.info("Generating summary statistics...")
    
    # Count records and check data completeness
    summary_query = """
        SELECT 
            COUNT(*) as total_sections,
            COUNT(DISTINCT district_id) as unique_districts,
            COUNT(DISTINCT neighborhood_name) as unique_neighborhoods,
            COUNT(geom) as sections_with_geometry,
            COUNT(district_name) as sections_with_district_name,
            COUNT(neighborhood_name) as sections_with_neighborhood_name
        FROM dim_geography
    """
    
    result = target_conn.execute(summary_query).fetchone()
    
    logger.info("=== DIM_GEOGRAPHY SUMMARY ===")
    logger.info(f"Total census sections: {result[0]}")
    logger.info(f"Unique districts: {result[1]}")
    logger.info(f"Unique neighborhoods: {result[2]}")
    logger.info(f"Sections with geometry: {result[3]}")
    logger.info(f"Sections with district name: {result[4]}")
    logger.info(f"Sections with neighborhood name: {result[5]}")
    
    # Show some district examples
    districts_query = """
        SELECT district_id, district_name, COUNT(*) as section_count
        FROM dim_geography
        WHERE district_name IS NOT NULL
        GROUP BY district_id, district_name
        ORDER BY section_count DESC
        LIMIT 10
    """
    
    districts = target_conn.execute(districts_query).fetchall()
    logger.info("=== TOP 10 DISTRICTS BY SECTION COUNT ===")
    for district_id, district_name, section_count in districts:
        logger.info(f"District {district_id} ({district_name}): {section_count} sections")

def main():
    """Main processing function."""
    logger.info("Starting geography dimension processing...")
    
    target_conn = None
    
    try:
        # Load census section geometries and data
        geography_records = load_census_geometries()
        
        if not geography_records:
            logger.error("No geography records found. Exiting.")
            return False
        
        # Connect to target database
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Create the dim_geography table
        create_dim_geography_table(target_conn)
        
        # Populate the geography table
        populate_geography_table(target_conn, geography_records)
        
        # Generate summary
        generate_summary(target_conn)
        
        logger.info("✅ Geography dimension processing completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    finally:
        if target_conn:
            target_conn.close()


if __name__ == "__main__":
    main()
