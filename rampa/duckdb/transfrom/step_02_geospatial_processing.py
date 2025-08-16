# MISSING GEOMETRY FIELDS IN THE LAYERS! WE NEED THE MAPPING, CHECK IF THEY ARE IN THE LAYERS.

"""
Geospatial processing script to extract geographic data from SECCIONES_CENSALES layer
and create the dim_geography table.
"""

import duckdb
import json
import sys
from loguru import logger
from rampa.duckdb.operations import get_all_layers

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

SOURCE_DATABASE_PATH = 'rampa/duckdb/databases/madrid_layers.db'
TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa.db'


def extract_geography_data(feature):
    """Extract geographic data from SECCIONES_CENSALES feature"""
    # SECCIONES_CENSALES fields: COD_DIS, NOM_DIS, COD_BAR, NOM_BAR, COD_SECCION
    return {
        'district_id': str(feature.get('COD_DIS')) if feature.get('COD_DIS') is not None else None,
        'district_name': feature.get('NOM_DIS'),
        'neighborhood_name': feature.get('NOM_BAR'), 
        'census_section_id': str(feature.get('COD_SECCION')) if feature.get('COD_SECCION') is not None else None,
        'geom': json.dumps(feature.get('geometry')) if feature.get('geometry') else None
    }


def main():
    """Process geospatial data for dim_geography table"""
    logger.info("Starting geospatial processing...")
    
    source_conn = None
    target_conn = None
    try:
        # Connect to databases
        source_conn = duckdb.connect(SOURCE_DATABASE_PATH)
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Find the census layer
        all_layers = get_all_layers(source_conn)
        census_layer = None
        
        for layer in all_layers:
            if 'SECCIONES_CENSALES' in layer['layer_name'].upper():
                census_layer = layer
                logger.info(f"Found census layer: {layer['layer_name']}")
                break
        
        if not census_layer:
            logger.error("❌ No SECCIONES_CENSALES layer found!")
            return
        
        # Prepare target table
        target_conn.execute("DELETE FROM dim_geography")  # Clear existing data
        logger.info("Cleared existing dim_geography data")
        
        # Process census data
        layer_data = census_layer['layer_data']
        geojson_data = json.loads(layer_data['data']) if isinstance(layer_data['data'], str) else layer_data['data']
        features = geojson_data if isinstance(geojson_data, list) else geojson_data.get('features', [])
        
        logger.info(f"Processing {len(features)} census features...")
        
        # Extract and validate records
        records = []
        seen_ids = set()
        
        for feature in features:
            geo_data = extract_geography_data(feature)
            
            if geo_data['census_section_id'] and geo_data['census_section_id'] not in seen_ids:
                seen_ids.add(geo_data['census_section_id'])
                records.append((
                    geo_data['district_id'],
                    geo_data['district_name'],
                    geo_data['neighborhood_name'], 
                    geo_data['census_section_id'],
                    geo_data['geom']
                ))
        
        # Insert records
        if records:
            logger.info(f"Inserting {len(records):,} unique records...")
            target_conn.execute("BEGIN TRANSACTION")
            
            try:
                target_conn.executemany("""
                    INSERT INTO dim_geography (district_id, district_name, neighborhood_name, census_section_id, geom)
                    VALUES (?, ?, ?, ?, ?)
                """, records)
                
                target_conn.execute("COMMIT")
                logger.info("✅ All records inserted successfully!")
                
            except Exception as e:
                target_conn.execute("ROLLBACK")
                logger.error(f"❌ Insert failed: {e}")
                raise
        
        # Show summary
        summary = target_conn.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT district_id) as districts,
                COUNT(district_name) as has_names
            FROM dim_geography
        """).fetchone()
        
        logger.info(f"✅ Completed! {summary[0]:,} records, {summary[1]} districts, {summary[2]} with names")
        
        # Show top districts
        districts = target_conn.execute("""
            SELECT district_name, COUNT(*) as sections
            FROM dim_geography 
            WHERE district_name IS NOT NULL
            GROUP BY district_name
            ORDER BY sections DESC
            LIMIT 5
        """).fetchall()
        
        logger.info("Top districts:")
        for name, count in districts:
            logger.info(f"  {name}: {count} sections")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()


if __name__ == "__main__":
    main()
