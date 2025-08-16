"""
Index layers processing script to extract demographic indices and create fact_demographics table.
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

# Layer mappings: layer_name -> (field_name, target_column)
LAYERS = {
    'DENSIDAD_POBLACION': ('Densidad', 'density'),
    'EDAD_PROMEDIO': ('Edad_Promedio', 'edad_promedio'),
    'PROPORCION_JUVENTUD': ('Proporcion_juventud', 'proporcion_juventud'),
    'PROPORCION_ENVEJECIMIENTO': ('Proporcion_envejecimiento', 'proporcion_envejecimiento'),
    'PROPORCION_SOBREENVEJECIMIENTO': ('Proporcion_sobreenvejecimiento', 'proporcion_sobreenvejecimiento'),
    'INDICE_ENVEJECIMIENTO': ('Indice_envejecimiento', 'indice_envejecimiento'),
    'INDICE_JUVENTUD': ('Indice_juventud', 'indice_juventud'),
    'INDICE_DEPENDENCIA': ('Indice_dependencia', 'indice_dependencia'),
    'INDICE_ESTRUCTURA_POBLACION_ACTIVA': ('Indice_estructura_poblacion_act', 'indice_estructura_poblacion_act'),
    'INDICE_REEMPLAZO_POBLACION_ACTIVA': ('Indice_reemplazo_poblacion_acti', 'indice_reemplazo_poblacion_acti'),
    'RAZON_PROGRESIVIDAD_DEMOGRAFICA': ('Razon_progresividad_demografica', 'razon_progresividad_demografica'),
    'TOTAL_AMBOS_SEXOS': ('ambos_sexos_total', 'total_population')
}


def extract_layer_data(layer, field_name):
    """Extract census_id -> value mapping from layer"""
    layer_data = layer['layer_data']
    geojson_data = json.loads(layer_data['data']) if isinstance(layer_data['data'], str) else layer_data['data']
    features = geojson_data if isinstance(geojson_data, list) else geojson_data.get('features', [])
    
    data = {}
    for feature in features:
        census_id = str(feature.get('COD_SEC')) if feature.get('COD_SEC') is not None else None
        value = feature.get(field_name)
        
        if census_id and value is not None:
            data[census_id] = float(value) if isinstance(value, (int, float, str)) else None
    
    return data


def main():
    """Process demographic index layers for fact_demographics table"""
    logger.info("Starting demographic indices processing...")
    
    source_conn = None
    target_conn = None
    try:
        # Connect to databases
        source_conn = duckdb.connect(SOURCE_DATABASE_PATH)
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Find target layers
        all_layers = get_all_layers(source_conn)
        found_layers = {}
        
        for layer in all_layers:
            if layer['layer_name'] in LAYERS:
                found_layers[layer['layer_name']] = layer
                logger.info(f"Found layer: {layer['layer_name']}")
        
        logger.info(f"Processing {len(found_layers)} demographic layers...")
        
        # Create table
        target_conn.execute("DROP TABLE IF EXISTS fact_demographics")
        target_conn.execute("""
            CREATE TABLE fact_demographics (
                census_section_id VARCHAR PRIMARY KEY NOT NULL,
                total_population INTEGER, density FLOAT, edad_promedio FLOAT,
                proporcion_juventud FLOAT, proporcion_envejecimiento FLOAT, proporcion_sobreenvejecimiento FLOAT,
                indice_envejecimiento FLOAT, indice_juventud FLOAT, indice_dependencia FLOAT,
                indice_estructura_poblacion_act FLOAT, indice_reemplazo_poblacion_acti FLOAT,
                razon_progresividad_demografica FLOAT,
                FOREIGN KEY (census_section_id) REFERENCES dim_geography(census_section_id)
            )
        """)
        
        # Extract and merge data
        all_data = {}
        for layer_name, layer in found_layers.items():
            field_name, target_col = LAYERS[layer_name]
            logger.info(f"Processing {layer_name}...")
            
            layer_data = extract_layer_data(layer, field_name)
            for census_id, value in layer_data.items():
                if census_id not in all_data:
                    all_data[census_id] = {'census_section_id': census_id}
                all_data[census_id][target_col] = value
            
            logger.info(f"  Extracted {len(layer_data)} records")
        
        # Get valid census IDs and filter
        valid_ids = set(row[0] for row in target_conn.execute("SELECT census_section_id FROM dim_geography").fetchall())
        logger.info(f"Found {len(valid_ids)} valid census sections in dim_geography")
        
        # Build records and track missing IDs
        records = []
        missing_ids = []
        
        for census_id, data in all_data.items():
            if census_id in valid_ids:
                record = (
                    census_id,
                    int(data.get('total_population')) if data.get('total_population') is not None else None,
                    data.get('density'), data.get('edad_promedio'), data.get('proporcion_juventud'),
                    data.get('proporcion_envejecimiento'), data.get('proporcion_sobreenvejecimiento'),
                    data.get('indice_envejecimiento'), data.get('indice_juventud'), data.get('indice_dependencia'),
                    data.get('indice_estructura_poblacion_act'), data.get('indice_reemplazo_poblacion_acti'),
                    data.get('razon_progresividad_demografica')
                )
                records.append(record)
            else:
                missing_ids.append(census_id)
        
        # Log missing census IDs
        if missing_ids:
            logger.info(f"Skipped {len(missing_ids)} records with missing census IDs:")
            for missing_id in sorted(missing_ids)[:10]:  # Show first 10
                logger.info(f"  Missing: {missing_id}")
            if len(missing_ids) > 10:
                logger.info(f"  ... and {len(missing_ids) - 10} more")
        
        # Insert records
        if records:
            logger.info(f"Inserting {len(records):,} records...")
            target_conn.execute("BEGIN TRANSACTION")
            
            try:
                target_conn.executemany("""
                    INSERT INTO fact_demographics (
                        census_section_id, total_population, density, edad_promedio,
                        proporcion_juventud, proporcion_envejecimiento, proporcion_sobreenvejecimiento,
                        indice_envejecimiento, indice_juventud, indice_dependencia,
                        indice_estructura_poblacion_act, indice_reemplazo_poblacion_acti,
                        razon_progresividad_demografica
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
                
                target_conn.execute("COMMIT")
                logger.info("✅ All records inserted successfully!")
                
            except Exception as e:
                target_conn.execute("ROLLBACK")
                logger.error(f"❌ Insert failed: {e}")
                raise
        
        # Summary
        summary = target_conn.execute("""
            SELECT COUNT(*) as total, AVG(total_population) as avg_pop, AVG(density) as avg_density
            FROM fact_demographics
        """).fetchone()
        
        logger.info(f"✅ Completed! {summary[0]:,} records")
        logger.info(f"  Average population: {summary[1]:.1f}" if summary[1] else "  Average population: N/A")
        logger.info(f"  Average density: {summary[2]:.1f}" if summary[2] else "  Average density: N/A")
        
        # Top sections
        samples = target_conn.execute("""
            SELECT census_section_id, total_population, density, edad_promedio
            FROM fact_demographics WHERE total_population IS NOT NULL
            ORDER BY total_population DESC LIMIT 3
        """).fetchall()
        
        logger.info("Top census sections:")
        for census_id, pop, density, age in samples:
            logger.info(f"  {census_id}: {pop:,} people, density {density:.1f}, age {age:.1f}")
            
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
