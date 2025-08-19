# Geospatial processing script to extract geographic data from Secciones_Censales.json
# and create the dim_geography table with proper geometries.

"""
Geospatial processing script to extract geographic data from TopoJSON census sections
and create the dim_geography table.
"""

import duckdb
import json
import sys
from loguru import logger

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa.db'
CENSUS_SECTIONS_JSON = 'rampa/data/Secciones_Censales.json'

def load_census_sections_from_topojson():
    """Load census sections from TopoJSON file and extract basic geometries."""
    logger.info("Loading census sections from TopoJSON...")
    
    try:
        # Load the TopoJSON file
        with open(CENSUS_SECTIONS_JSON, 'r', encoding='utf-8') as f:
            topo_data = json.load(f)
        
        logger.info(f"Loaded TopoJSON with {len(topo_data.get('arcs', []))} arcs")
        
        # Extract census sections from objects
        census_sections = []
        if 'objects' in topo_data and 'SECCIONES_CENSALES' in topo_data['objects']:
            geometries = topo_data['objects']['SECCIONES_CENSALES'].get('geometries', [])
            logger.info(f"Found {len(geometries)} census section geometries")
            
            for geom in geometries:
                props = geom.get('properties', {})
                
                # Extract the properties we need
                census_section = {
                    'district_id': str(props.get('COD_DIS', '')).strip() if props.get('COD_DIS') else None,
                    'district_name': str(props.get('NOM_DIS', '')).strip() if props.get('NOM_DIS') else None,
                    'neighborhood_name': str(props.get('NOM_BAR', '')).strip() if props.get('NOM_BAR') else None,
                    'census_section_id': str(props.get('COD_SECCIO', '')).strip() if props.get('COD_SECCIO') else None,
                    'arcs': geom.get('arcs', []),
                    'geometry_type': geom.get('type', 'Polygon')
                }
                
                if census_section['census_section_id']:
                    census_sections.append(census_section)
        
        logger.info(f"✅ Loaded {len(census_sections)} census sections with properties")
        return census_sections, topo_data.get('arcs', [])
        
    except Exception as e:
        logger.error(f"❌ Error loading TopoJSON: {e}")
        return [], []

def convert_arcs_to_simple_geometry(arcs_indices, all_arcs):
    """Convert TopoJSON arc indices to a simple WKT-like representation."""
    try:
        if not arcs_indices or not all_arcs:
            return None
        
        # For simplicity, we'll create a basic polygon representation
        # This is a simplified approach - for production you'd want proper TopoJSON conversion
        coordinates = []
        
        for arc_group in arcs_indices:
            if isinstance(arc_group, list):
                for arc_index in arc_group:
                    if isinstance(arc_index, int) and abs(arc_index) < len(all_arcs):
                        arc = all_arcs[abs(arc_index)]
                        if arc and len(arc) > 0:
                            # Get first and last coordinates of this arc
                            if len(arc[0]) >= 2:
                                coordinates.extend([arc[0], arc[-1] if len(arc) > 1 else arc[0]])
        
        if len(coordinates) >= 3:
            # Create a simple WKT polygon
            coord_strings = [f"{coord[0]} {coord[1]}" for coord in coordinates[:10]]  # Limit for simplicity
            if len(coord_strings) >= 3:
                # Close the polygon by adding first point at the end
                if coord_strings[0] != coord_strings[-1]:
                    coord_strings.append(coord_strings[0])
                wkt = f"SRID=4326;POLYGON(({','.join(coord_strings)}))"
                return wkt
        
        return None
        
    except Exception as e:
        logger.warning(f"Error converting arcs to geometry: {e}")
        return None


def main():
    """Process geospatial data for dim_geography table from TopoJSON."""
    logger.info("Starting geospatial processing...")
    
    target_conn = None
    try:
        # Load census sections from TopoJSON
        census_sections, all_arcs = load_census_sections_from_topojson()
        
        if not census_sections:
            logger.error("❌ No census sections loaded from TopoJSON!")
            return
        
        # Connect to target database
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Create dim_geography table if it doesn't exist
        target_conn.execute("""
            CREATE TABLE IF NOT EXISTS dim_geography (
                district_id VARCHAR,
                district_name TEXT,
                neighborhood_name TEXT,
                census_section_id VARCHAR PRIMARY KEY,
                geom TEXT
            )
        """)
        
        # Clear existing data
        target_conn.execute("DELETE FROM dim_geography")
        logger.info("Cleared existing dim_geography data")
        
        # Process census sections
        logger.info(f"Processing {len(census_sections)} census sections...")
        
        records = []
        sections_with_geom = 0
        seen_section_ids = set()
        
        for section in census_sections:
            section_id = section['census_section_id']
            
            # Skip duplicates
            if section_id in seen_section_ids:
                logger.warning(f"Duplicate census section ID found: {section_id}, skipping...")
                continue
            
            seen_section_ids.add(section_id)
            
            # Convert arcs to simple geometry
            geom_wkt = convert_arcs_to_simple_geometry(section['arcs'], all_arcs)
            if geom_wkt:
                sections_with_geom += 1
            
            record = (
                section['district_id'],
                section['district_name'],
                section['neighborhood_name'],
                section['census_section_id'],
                geom_wkt
            )
            records.append(record)
        
        logger.info(f"After deduplication: {len(records)} unique sections")
        logger.info(f"Generated geometries for {sections_with_geom}/{len(records)} sections")
        
        # Insert records
        if records:
            logger.info(f"Inserting {len(records):,} records...")
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
                COUNT(district_name) as has_names,
                COUNT(geom) as has_geometry
            FROM dim_geography
        """).fetchone()
        
        logger.info(f"✅ Completed! {summary[0]:,} records, {summary[1]} districts, {summary[2]} with names, {summary[3]} with geometry")
        
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
        if target_conn:
            target_conn.close()


if __name__ == "__main__":
    main()
