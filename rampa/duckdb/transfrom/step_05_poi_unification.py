#!/usr/bin/env python3
"""
POI Unification Script - Step 5
Consolidates OSM data into unified POI and routing infrastructure tables.
"""

import sys
from pathlib import Path
import json
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from rampa.duckdb.connection import get_duckdb_connection

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

SOURCE_OSM_DB = 'rampa/duckdb/databases/madrid_osm.db'
TARGET_DB = 'rampa/duckdb/databases/rampa.db'

def format_geometry_for_web(lat, lon, geometry_wkt=None):
    """
    Format geometry in web-readable standards (WGS84/EPSG:4326).
    Returns tuple of (wkt_with_srid, lat, lon)
    """
    if lat is None or lon is None:
        return None, None, None
    
    try:
        # Ensure coordinates are float
        lat_f = float(lat)
        lon_f = float(lon)
        
        # Validate coordinates are reasonable for Madrid area
        if not (39.0 <= lat_f <= 41.0 and -5.0 <= lon_f <= -2.0):
            logger.warning(f"Coordinates outside Madrid area: lat={lat_f}, lon={lon_f}")
        
        # Create WKT with explicit SRID (4326 = WGS84)
        wkt_with_srid = f"POINT({lon_f} {lat_f})"
        
        return wkt_with_srid, lat_f, lon_f
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid coordinates: lat={lat}, lon={lon}, error={e}")
        return None, None, None

def create_unified_tables():
    """Create tables based on db_models schema."""
    try:
        with get_duckdb_connection(TARGET_DB) as conn:
            # Drop existing tables to recreate with correct schema
            conn.execute("DROP TABLE IF EXISTS fact_points_of_interest")
            conn.execute("DROP TABLE IF EXISTS routing_infrastructure")
            
            # Create fact_points_of_interest table (from your db_models)
            conn.execute("""
                CREATE TABLE fact_points_of_interest (
                    poi_id INTEGER,
                    osm_id BIGINT,
                    source VARCHAR NOT NULL,
                    name TEXT,
                    description TEXT,
                    category TEXT,
                    wheelchair_accessible VARCHAR,
                    address TEXT,
                    latitude DOUBLE,
                    longitude DOUBLE,
                    geom TEXT
                )
            """)
            
            # Create routing_infrastructure table (from your new db_models)
            conn.execute("""
                CREATE TABLE routing_infrastructure (
                    infra_id INTEGER,
                    osm_id BIGINT NOT NULL,
                    osm_type VARCHAR,
                    wheelchair VARCHAR,
                    wheelchair_score INTEGER,
                    highway VARCHAR,
                    barrier VARCHAR,
                    kerb VARCHAR,
                    crossing VARCHAR,
                    tactile_paving VARCHAR,
                    ramp VARCHAR,
                    surface VARCHAR,
                    smoothness VARCHAR,
                    incline VARCHAR,
                    width FLOAT,
                    name TEXT,
                    lat FLOAT NOT NULL,
                    lon FLOAT NOT NULL,
                    geom TEXT,
                    data_type VARCHAR,
                    created_at VARCHAR
                )
            """)
            
            logger.info("Created unified tables with correct schema")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

def process_osm_pois():
    """Extract POIs from OSM data."""
    try:
        with get_duckdb_connection(SOURCE_OSM_DB) as osm_conn, \
             get_duckdb_connection(TARGET_DB) as target_conn:
            
            # Get available OSM tables
            tables = [row[0] for row in osm_conn.execute("SHOW TABLES").fetchall()]
            osm_tables = [t for t in tables if t.startswith('osm_')]
            
            logger.info(f"Found OSM tables: {osm_tables}")
            
            all_pois = []
            
            for table_name in osm_tables:
                try:
                    # Get POIs with accessibility info
                    query = f"""
                        SELECT 
                            osm_id, name, amenity, shop, tourism, leisure,
                            wheelchair, lat, lon, geometry
                        FROM {table_name}
                        WHERE (amenity IS NOT NULL AND amenity != '') 
                           OR (shop IS NOT NULL AND shop != '')
                           OR (tourism IS NOT NULL AND tourism != '')
                           OR (leisure IS NOT NULL AND leisure != '')
                        AND lat IS NOT NULL AND lon IS NOT NULL
                    """
                    
                    rows = osm_conn.execute(query).fetchall()
                    
                    for row in rows:
                        osm_id, name, amenity, shop, tourism, leisure, wheelchair, lat, lon, geometry = row
                        
                        # Determine category
                        if amenity:
                            category = f"amenity_{amenity}"
                        elif shop:
                            category = f"shop_{shop}"
                        elif tourism:
                            category = f"tourism_{tourism}"
                        elif leisure:
                            category = f"leisure_{leisure}"
                        else:
                            category = "other"
                        
                        # Format geometry for web standards
                        wkt_geom, lat_clean, lon_clean = format_geometry_for_web(lat, lon, geometry)
                        
                        if wkt_geom is None:  # Skip if coordinates are invalid
                            continue
                        
                        # Create POI record with sequential ID
                        poi_record = (
                            len(all_pois) + 1,  # Sequential poi_id
                            int(osm_id) if osm_id and str(osm_id).isdigit() else None,  # Convert to int or None
                            'OSM',
                            name or category,
                            f"OSM {category}",
                            category,
                            wheelchair or 'unknown',
                            None,  # address
                            lat_clean,  # latitude
                            lon_clean,  # longitude
                            wkt_geom    # WKT with SRID
                        )
                        all_pois.append(poi_record)
                    
                    logger.info(f"Processed {len(rows)} POIs from {table_name}")
                    
                except Exception as e:
                    logger.warning(f"Error processing POI table {table_name}: {e}")
                    continue
            
            # Insert POIs in batches
            if all_pois:
                logger.info(f"Inserting {len(all_pois)} POIs...")
                
                target_conn.execute("BEGIN TRANSACTION")
                try:
                    insert_query = """
                        INSERT INTO fact_points_of_interest 
                        (poi_id, osm_id, source, name, description, category, wheelchair_accessible, address, latitude, longitude, geom)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    
                    batch_size = 1000
                    for i in range(0, len(all_pois), batch_size):
                        batch = all_pois[i:i + batch_size]
                        target_conn.executemany(insert_query, batch)
                        
                        if (i + batch_size) % 5000 == 0:
                            logger.info(f"Inserted {i + batch_size} POIs...")
                    
                    target_conn.execute("COMMIT")
                    logger.info(f"✅ Successfully inserted {len(all_pois)} POIs")
                    
                except Exception as e:
                    target_conn.execute("ROLLBACK")
                    logger.error(f"Failed to insert POIs: {e}")
                    return False
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to process OSM POIs: {e}")
        return False

def process_osm_routing_infrastructure():
    """Extract routing infrastructure from OSM data."""
    try:
        with get_duckdb_connection(SOURCE_OSM_DB) as osm_conn, \
             get_duckdb_connection(TARGET_DB) as target_conn:
            
            # Check if we have the routing infrastructure table
            tables = [row[0] for row in osm_conn.execute("SHOW TABLES").fetchall()]
            
            if 'osm_routing_infrastructure' in tables:
                logger.info("Processing routing infrastructure from osm_routing_infrastructure table")
                
                # Get routing infrastructure data
                rows = osm_conn.execute("""
                    SELECT 
                        osm_id, osm_type, wheelchair, wheelchair_score,
                        highway, barrier, kerb, crossing, tactile_paving, ramp,
                        surface, smoothness, incline, width, name,
                        lat, lon, geometry, data_type, created_at
                    FROM osm_routing_infrastructure
                    WHERE lat IS NOT NULL AND lon IS NOT NULL
                """).fetchall()
                
                # Convert rows to ensure proper data types and add sequential IDs
                converted_rows = []
                for i, row in enumerate(rows):
                    osm_id = row[0]
                    # Convert osm_id to int if possible, otherwise skip this row
                    try:
                        osm_id_int = int(osm_id) if osm_id else None
                        if osm_id_int is None:
                            continue
                        
                        # Extract coordinates from the row
                        lat, lon = row[15], row[16]  # lat, lon are at positions 15, 16
                        
                        # Format geometry for web standards
                        wkt_geom, lat_clean, lon_clean = format_geometry_for_web(lat, lon, row[17])
                        
                        if wkt_geom is None:  # Skip if coordinates are invalid
                            continue
                        
                        # Add sequential infra_id at the beginning and format geometry
                        converted_row = (
                            i + 1,     # infra_id
                            osm_id_int, # osm_id
                            row[1],    # osm_type
                            row[2],    # wheelchair
                            row[3],    # wheelchair_score
                            row[4],    # highway
                            row[5],    # barrier
                            row[6],    # kerb
                            row[7],    # crossing
                            row[8],    # tactile_paving
                            row[9],    # ramp
                            row[10],   # surface
                            row[11],   # smoothness
                            row[12],   # incline
                            row[13],   # width
                            row[14],   # name
                            lat_clean, # lat
                            lon_clean, # lon
                            wkt_geom,  # geom (WKT with SRID)
                            row[18],   # data_type
                            row[19]    # created_at
                        )
                        converted_rows.append(converted_row)
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"Error processing row {i}: {e}")
                        continue
                
                rows = converted_rows
                
                logger.info(f"Found {len(rows)} routing infrastructure records")
                
                if rows:
                    logger.info("Inserting routing infrastructure...")
                    
                    target_conn.execute("BEGIN TRANSACTION")
                    try:
                        insert_query = """
                            INSERT INTO routing_infrastructure 
                            (infra_id, osm_id, osm_type, wheelchair, wheelchair_score,
                             highway, barrier, kerb, crossing, tactile_paving, ramp,
                             surface, smoothness, incline, width, name,
                             lat, lon, geom, data_type, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        
                        batch_size = 5000
                        for i in range(0, len(rows), batch_size):
                            batch = rows[i:i + batch_size]
                            target_conn.executemany(insert_query, batch)
                            
                            if (i + batch_size) % 20000 == 0:
                                logger.info(f"Inserted {i + batch_size} infrastructure records...")
                        
                        target_conn.execute("COMMIT")
                        logger.info(f"✅ Successfully inserted {len(rows)} routing infrastructure records")
                        
                    except Exception as e:
                        target_conn.execute("ROLLBACK")
                        logger.error(f"Failed to insert routing infrastructure: {e}")
                        return False
                        
            else:
                logger.warning("No osm_routing_infrastructure table found, skipping routing data")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to process routing infrastructure: {e}")
        return False

def generate_summary():
    """Generate summary statistics."""
    try:
        with get_duckdb_connection(TARGET_DB) as conn:
            # POI summary
            poi_stats = conn.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    SUM(CASE WHEN wheelchair_accessible = 'yes' THEN 1 ELSE 0 END) as accessible,
                    SUM(CASE WHEN wheelchair_accessible = 'limited' THEN 1 ELSE 0 END) as limited
                FROM fact_points_of_interest
                WHERE source = 'OSM'
                GROUP BY category
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            
            logger.info("=== TOP 10 POI CATEGORIES ===")
            for category, count, accessible, limited in poi_stats:
                logger.info(f"{category}: {count} total, {accessible} accessible, {limited} limited")
            
            # Infrastructure summary
            infra_stats = conn.execute("""
                SELECT 
                    data_type,
                    COUNT(*) as total,
                    SUM(CASE WHEN wheelchair = 'yes' THEN 1 ELSE 0 END) as accessible
                FROM routing_infrastructure
                GROUP BY data_type
                ORDER BY total DESC
            """).fetchall()
            
            logger.info("=== ROUTING INFRASTRUCTURE SUMMARY ===")
            for data_type, total, accessible in infra_stats:
                logger.info(f"{data_type}: {total} total, {accessible} accessible")
            
            # Detailed routing features
            features = conn.execute("""
                SELECT 
                    'kerb' as feature, COUNT(*) as count FROM routing_infrastructure WHERE kerb IS NOT NULL AND kerb != ''
                UNION ALL
                SELECT 'crossing', COUNT(*) FROM routing_infrastructure WHERE crossing IS NOT NULL AND crossing != ''
                UNION ALL
                SELECT 'tactile_paving', COUNT(*) FROM routing_infrastructure WHERE tactile_paving IS NOT NULL AND tactile_paving != ''
                UNION ALL
                SELECT 'surface', COUNT(*) FROM routing_infrastructure WHERE surface IS NOT NULL AND surface != ''
                UNION ALL
                SELECT 'smoothness', COUNT(*) FROM routing_infrastructure WHERE smoothness IS NOT NULL AND smoothness != ''
                ORDER BY count DESC
            """).fetchall()
            
            logger.info("=== ROUTING FEATURES ===")
            for feature, count in features:
                logger.info(f"{feature}: {count} records")
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return False

def main():
    """Main execution function."""
    logger.info("Starting OSM POI and routing infrastructure unification...")
    
    # Step 1: Create tables
    if not create_unified_tables():
        return False
    
    # Step 2: Process OSM POIs
    if not process_osm_pois():
        logger.warning("Failed to process OSM POIs")
    
    # Step 3: Process OSM routing infrastructure
    if not process_osm_routing_infrastructure():
        logger.warning("Failed to process routing infrastructure")
    
    # Step 4: Generate summary
    if not generate_summary():
        logger.warning("Failed to generate summary")
    
    logger.info("✅ OSM unification completed!")
    return True

if __name__ == "__main__":
    main()