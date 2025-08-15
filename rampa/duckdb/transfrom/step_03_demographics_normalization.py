"""
Streamlined demographics normalization script.
"""

import duckdb
import json
import sys
from loguru import logger
from rampa.duckdb.operations import get_all_layers

# Configure minimal logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {message}")

SOURCE_DATABASE_PATH = 'rampa/duckdb/databases/madrid_layers.db'  # Source data
TARGET_DATABASE_PATH = 'rampa/duckdb/databases/rampa.db'          # Target for normalized data


def main():
    """Normalize demographics"""
    logger.info("Starting demographics normalization...")
    
    source_conn = None
    target_conn = None
    try:
        # Connect to source database (madrid_layers.db) to read data
        source_conn = duckdb.connect(SOURCE_DATABASE_PATH)
        
        # Connect to target database (rampa.db) to insert normalized data
        target_conn = duckdb.connect(TARGET_DATABASE_PATH)
        
        # Get unique demographic layers from source
        all_layers = get_all_layers(source_conn)
        layer_names = set()
        demographics_layers = []
        
        for layer in all_layers:
            name = layer['layer_name']
            if (name.startswith(('HOMBRES', 'MUJERES', 'POBLACION')) and 
                name not in layer_names):
                layer_names.add(name)
                demographics_layers.append(layer)
        
        logger.info(f"Processing {len(demographics_layers)} unique layers...")
        
        # Create table in target database with separate gender and clean age columns
        target_conn.execute("DROP TABLE IF EXISTS fact_demographics_age_groups")
        target_conn.execute("""
            CREATE TABLE fact_demographics_age_groups (
                census_section_id VARCHAR NOT NULL,
                gender VARCHAR NOT NULL,
                age_group VARCHAR NOT NULL,
                population_count INTEGER,
                PRIMARY KEY (census_section_id, gender, age_group)
            )
        """)
        
        # Process layers efficiently
        all_records = []
        for i, layer_info in enumerate(demographics_layers, 1):
            layer_name = layer_info['layer_name']
            layer_data = layer_info['layer_data']
            
            if 'data' not in layer_data:
                continue
                
            # Determine metadata
            if layer_name.startswith('HOMBRES'):
                gender = 'HOMBRE'
            elif layer_name.startswith('MUJERES'):
                gender = 'MUJER'
            else:
                gender = 'ALL'
            
            # Find data column
            columns = layer_data.get('columns', [])
            data_column = next((col for col in columns 
                              if col not in ['COD_SEC', 'OBJECTID', 'geometry']), None)
            
            if not data_column:
                continue
            
            # Clean age group - remove prefixes and "_años" suffix
            age_group = data_column.lower()
            for prefix in ['hombres_', 'mujeres_', 'poblacion_', 'ambos_sexos_', 'total_']:
                if age_group.startswith(prefix):
                    age_group = age_group.replace(prefix, '')
                    break
            
            # Remove "_años" suffix to get clean age format like "00_04", "85_89"
            if age_group.endswith('_años'):
                age_group = age_group.replace('_años', '')
            elif age_group.endswith('_más_años'):
                age_group = age_group.replace('_más_años', '+')  # Convert "100_más_años" to "100+"
            
            # Parse data
            try:
                geojson_data = layer_data['data']
                if isinstance(geojson_data, str):
                    geojson_data = json.loads(geojson_data)
                
                features = geojson_data if isinstance(geojson_data, list) else geojson_data.get('features', [])
                
                # Extract records
                layer_records = []
                for feature in features:
                    props = feature.get('properties', {})
                    data_source = feature if not props else props
                    
                    cod_censal = (data_source.get('COD_SEC') or 
                                 data_source.get('cod_sec') or 
                                 data_source.get('CODSEC'))
                    
                    pop_value = data_source.get(data_column, 0)
                    
                    if cod_censal and pop_value and pop_value != 0:
                        # Use just the census section code without combining with gender
                        layer_records.append((str(cod_censal), gender, age_group, int(pop_value)))
                
                all_records.extend(layer_records)
                
                # Progress update
                if i % 10 == 0 or i == len(demographics_layers):
                    logger.info(f"Processed {i}/{len(demographics_layers)} layers, {len(all_records):,} records so far")
                    
            except Exception as e:
                logger.warning(f"Error processing {layer_name}: {e}")
                continue
        
        # Insert records in a single transaction for maximum efficiency
        if all_records:
            logger.info(f"Inserting {len(all_records):,} records into rampa.db...")
            
            # Use a single transaction for all inserts as recommended by DuckDB docs
            target_conn.execute("BEGIN TRANSACTION")
            
            try:
                batch_size = 40000  # Smaller batches within the transaction
                total_batches = (len(all_records) + batch_size - 1) // batch_size
                
                insert_query = """
                    INSERT INTO fact_demographics_age_groups (census_section_id, gender, age_group, population_count)
                    VALUES (?, ?, ?, ?)
                """
                
                for i in range(0, len(all_records), batch_size):
                    batch = all_records[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    
                    logger.info(f"Inserting batch {batch_num}/{total_batches} ({len(batch):,} records)...")
                    target_conn.executemany(insert_query, batch)
                
                # Commit the entire transaction at once
                target_conn.execute("COMMIT")
                logger.info("✅ All records inserted and committed successfully!")
                
            except Exception as e:
                # Rollback on error
                target_conn.execute("ROLLBACK")
                logger.error(f"❌ Insert failed, transaction rolled back: {e}")
                raise
        
        # Summary from target database
        summary = target_conn.execute("""
            SELECT 
                gender,
                COUNT(*) as records, 
                SUM(population_count) as population
            FROM fact_demographics_age_groups 
            GROUP BY gender 
            ORDER BY gender
        """).fetchall()
        
        total = sum(row[1] for row in summary)
        logger.info(f"✅ Completed! {total:,} total records in rampa.db:")
        for gender, records, population in summary:
            logger.info(f"  {gender}: {records:,} records, {population:,} population")
            
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
