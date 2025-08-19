#!/usr/bin/env python3
"""
Demographics Indicators Processing Script
Processes demographic indicator layers and populates the fact_demographics table.
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

from rampa.duckdb.operations import get_all_layers

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

SOURCE_DATABASE_PATH = 'rampa/duckdb/databases/madrid_layers.db'  # Source data
TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa.db'          # Target for normalized data

# Define the expected demographic indicator layers and their mappings
DEMOGRAPHIC_INDICATORS = {
    'DENSIDAD_POBLACION': 'density',
    'EDAD_PROMEDIO': 'edad_promedio',
    'PROPORCION_JUVENTUD': 'proporcion_juventud',
    'PROPORCION_ENVEJECIMIENTO': 'proporcion_envejecimiento',
    'PROPORCION_SOBREENVEJECIMIENTO': 'proporcion_sobreenvejecimiento',
    'INDICE_ENVEJECIMIENTO': 'indice_envejecimiento',
    'INDICE_JUVENTUD': 'indice_juventud',
    'INDICE_DEPENDENCIA': 'indice_dependencia',
    'INDICE_ESTRUCTURA_POBLACION_ACTIVA': 'indice_estructura_poblacion_act',
    'INDICE_REEMPLAZO_POBLACION_ACTIVA': 'indice_reemplazo_poblacion_acti',
    'RAZON_PROGRESIVIDAD_DEMOGRAFICA': 'razon_progresividad_demografica'
}

def create_fact_demographics_table(target_conn):
    """Create the fact_demographics table with proper schema."""
    logger.info("Creating fact_demographics table...")
    
    target_conn.execute("DROP TABLE IF EXISTS fact_demographics")
    target_conn.execute("""
        CREATE TABLE fact_demographics (
            census_section_id VARCHAR PRIMARY KEY,
            total_population INTEGER,
            density DOUBLE,
            edad_promedio DOUBLE,
            proporcion_juventud DOUBLE,
            proporcion_envejecimiento DOUBLE,
            proporcion_sobreenvejecimiento DOUBLE,
            indice_envejecimiento DOUBLE,
            indice_juventud DOUBLE,
            indice_dependencia DOUBLE,
            indice_estructura_poblacion_act DOUBLE,
            indice_reemplazo_poblacion_acti DOUBLE,
            razon_progresividad_demografica DOUBLE
        )
    """)
    logger.info("✅ fact_demographics table created")

def extract_indicator_data(layer_info, indicator_name):
    """Extract data from a demographic indicator layer."""
    layer_name = layer_info['layer_name']
    layer_data = layer_info['layer_data']
    
    if 'data' not in layer_data:
        logger.warning(f"No data found in layer {layer_name}")
        return []
    
    # Find the data column (exclude standard columns)
    columns = layer_data.get('columns', [])
    data_column = next((col for col in columns 
                       if col not in ['COD_SEC', 'OBJECTID', 'geometry']), None)
    
    if not data_column:
        logger.warning(f"No data column found in layer {layer_name}")
        return []
    
    logger.info(f"Processing {layer_name} with data column: {data_column}")
    
    records = []
    try:
        geojson_data = layer_data['data']
        if isinstance(geojson_data, str):
            geojson_data = json.loads(geojson_data)
        
        features = geojson_data if isinstance(geojson_data, list) else geojson_data.get('features', [])
        
        for feature in features:
            props = feature.get('properties', {})
            data_source = feature if not props else props
            
            # Extract census section ID
            cod_censal = (data_source.get('COD_SEC') or 
                         data_source.get('cod_sec') or 
                         data_source.get('CODSEC'))
            
            # Extract indicator value
            indicator_value = data_source.get(data_column)
            
            if cod_censal and indicator_value is not None:
                try:
                    # Convert to float for numeric indicators
                    indicator_value = float(indicator_value)
                    records.append((str(cod_censal), indicator_value))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value for {indicator_name} in section {cod_censal}: {indicator_value}")
                    continue
        
        logger.info(f"Extracted {len(records)} records from {layer_name}")
        return records
        
    except Exception as e:
        logger.error(f"Error processing {layer_name}: {e}")
        return []

def populate_demographics_table(target_conn, all_indicator_data):
    """Populate the fact_demographics table with indicator data."""
    logger.info("Populating fact_demographics table...")
    
    # Get all unique census section IDs
    all_sections = set()
    for indicator_name, records in all_indicator_data.items():
        for cod_censal, value in records:
            all_sections.add(cod_censal)
    
    logger.info(f"Found {len(all_sections)} unique census sections")
    
    # Create a dictionary to hold all data for each section
    section_data = {}
    for section_id in all_sections:
        section_data[section_id] = {
            'census_section_id': section_id,
            'total_population': None,  # Will be filled separately if available
            'density': None,
            'edad_promedio': None,
            'proporcion_juventud': None,
            'proporcion_envejecimiento': None,
            'proporcion_sobreenvejecimiento': None,
            'indice_envejecimiento': None,
            'indice_juventud': None,
            'indice_dependencia': None,
            'indice_estructura_poblacion_act': None,
            'indice_reemplazo_poblacion_acti': None,
            'razon_progresividad_demografica': None
        }
    
    # Fill in the indicator data
    for indicator_name, records in all_indicator_data.items():
        column_name = DEMOGRAPHIC_INDICATORS[indicator_name]
        for cod_censal, value in records:
            if cod_censal in section_data:
                section_data[cod_censal][column_name] = value
    
    # Convert to list of tuples for insertion
    insert_records = []
    for section_id, data in section_data.items():
        record = (
            data['census_section_id'],
            data['total_population'],
            data['density'],
            data['edad_promedio'],
            data['proporcion_juventud'],
            data['proporcion_envejecimiento'],
            data['proporcion_sobreenvejecimiento'],
            data['indice_envejecimiento'],
            data['indice_juventud'],
            data['indice_dependencia'],
            data['indice_estructura_poblacion_act'],
            data['indice_reemplazo_poblacion_acti'],
            data['razon_progresividad_demografica']
        )
        insert_records.append(record)
    
    # Insert records
    if insert_records:
        logger.info(f"Inserting {len(insert_records)} records into fact_demographics...")
        
        target_conn.execute("BEGIN TRANSACTION")
        try:
            insert_query = """
                INSERT INTO fact_demographics (
                    census_section_id, total_population, density, edad_promedio,
                    proporcion_juventud, proporcion_envejecimiento, proporcion_sobreenvejecimiento,
                    indice_envejecimiento, indice_juventud, indice_dependencia,
                    indice_estructura_poblacion_act, indice_reemplazo_poblacion_acti,
                    razon_progresividad_demografica
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            batch_size = 5000
            for i in range(0, len(insert_records), batch_size):
                batch = insert_records[i:i + batch_size]
                target_conn.executemany(insert_query, batch)
                
                if (i + batch_size) % 10000 == 0:
                    logger.info(f"Inserted {i + batch_size} records...")
            
            target_conn.execute("COMMIT")
            logger.info("✅ All records inserted successfully!")
            
        except Exception as e:
            target_conn.execute("ROLLBACK")
            logger.error(f"❌ Insert failed, transaction rolled back: {e}")
            raise

def generate_summary(target_conn):
    """Generate summary statistics for the fact_demographics table."""
    logger.info("Generating summary statistics...")
    
    # Count non-null values for each indicator
    summary_query = """
        SELECT 
            COUNT(*) as total_sections,
            COUNT(density) as density_count,
            COUNT(edad_promedio) as edad_promedio_count,
            COUNT(proporcion_juventud) as proporcion_juventud_count,
            COUNT(proporcion_envejecimiento) as proporcion_envejecimiento_count,
            COUNT(proporcion_sobreenvejecimiento) as proporcion_sobreenvejecimiento_count,
            COUNT(indice_envejecimiento) as indice_envejecimiento_count,
            COUNT(indice_juventud) as indice_juventud_count,
            COUNT(indice_dependencia) as indice_dependencia_count,
            COUNT(indice_estructura_poblacion_act) as indice_estructura_poblacion_act_count,
            COUNT(indice_reemplazo_poblacion_acti) as indice_reemplazo_poblacion_acti_count,
            COUNT(razon_progresividad_demografica) as razon_progresividad_demografica_count
        FROM fact_demographics
    """
    
    result = target_conn.execute(summary_query).fetchone()
    
    logger.info("=== FACT_DEMOGRAPHICS SUMMARY ===")
    logger.info(f"Total census sections: {result[0]}")
    logger.info(f"Density: {result[1]} sections")
    logger.info(f"Edad promedio: {result[2]} sections")
    logger.info(f"Proporción juventud: {result[3]} sections")
    logger.info(f"Proporción envejecimiento: {result[4]} sections")
    logger.info(f"Proporción sobreenvejecimiento: {result[5]} sections")
    logger.info(f"Índice envejecimiento: {result[6]} sections")
    logger.info(f"Índice juventud: {result[7]} sections")
    logger.info(f"Índice dependencia: {result[8]} sections")
    logger.info(f"Índice estructura población activa: {result[9]} sections")
    logger.info(f"Índice reemplazo población activa: {result[10]} sections")
    logger.info(f"Razón progresividad demográfica: {result[11]} sections")

def main():
    """Main processing function."""
    logger.info("Starting demographic indicators processing...")
    
    source_conn = None
    target_conn = None
    
    try:
        # Connect to databases
        source_conn = duckdb.connect(SOURCE_DATABASE_PATH)
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Get all layers from source
        all_layers = get_all_layers(source_conn)
        
        # Filter for demographic indicator layers
        indicator_layers = []
        for layer in all_layers:
            layer_name = layer['layer_name']
            if layer_name in DEMOGRAPHIC_INDICATORS:
                indicator_layers.append(layer)
        
        logger.info(f"Found {len(indicator_layers)} demographic indicator layers")
        
        # Create the fact_demographics table
        create_fact_demographics_table(target_conn)
        
        # Process each indicator layer
        all_indicator_data = {}
        for layer_info in indicator_layers:
            layer_name = layer_info['layer_name']
            if layer_name in DEMOGRAPHIC_INDICATORS:
                records = extract_indicator_data(layer_info, layer_name)
                all_indicator_data[layer_name] = records
        
        # Populate the demographics table
        populate_demographics_table(target_conn, all_indicator_data)
        
        # Generate summary
        generate_summary(target_conn)
        
        logger.info("✅ Demographic indicators processing completed!")
        
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
