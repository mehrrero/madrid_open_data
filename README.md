# Madrid Open Data - Geospatial Analytics Pipeline

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

A geospatial data pipeline for analyzing Madrid's open data using ArcGIS layers, DuckDB, and Python. This project focuses on accessibility analytics, demographic analysis, and urban planning insights.

## Features

- Memory-efficient data processing optimized for large geospatial datasets
- DuckDB-powered storage with spatial extensions
- Automated download and processing of 88+ Madrid Open Data layers
- Focus on urban accessibility, demographics, and mobility analysis

## Quick Start

## Installation

Clone the repository and set up the Python environment:

```bash
git clone <repository-url>
cd madrid-open-data

# Using uv (recommended)

uv sync
uv pip install -e .

```

## Usage

Download all available Madrid Open Data layers:

```bash
python setup.py
```

This will download 88+ geospatial layers from Madrid's ArcGIS services and store them in DuckDB.

Basic usage example:

```python
from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.query_tools import Data_Collection

# Connect to database
db_con = get_duckdb_connection()

# Initialize data collection
data_collector = Data_Collection(db_con)

# Load specific layer data
accessibility_data = data_collector.get_layer_data("ACCESIBILIDAD_ACERAS_2024")
population_data = data_collector.get_layer_data("POBLACION_65_69_ANOS")
```

## Available Data

The pipeline accesses 88+ layers including:

**Demographics & Population**
- Age group distributions (0-4, 5-9, ..., 95-99, 99+) by gender
- Population density and demographic indices
- Aging and dependency ratios

**Urban Accessibility**
- Sidewalk accessibility projects (2020, 2021, 2024)
- Public facilities and services
- Transportation infrastructure

**Community Services**
- Senior centers and activities areas
- Public restrooms and facilities
- Healthcare centers (Madrid Salud)
- Religious institutions and community spaces

Data Source: [Madrid Open Data Portal](https://sigma.madrid.es/hosted/rest/services)

## Architecture

**Core Components**

- `rampa/query/`: ArcGIS API integration and data collection
- `rampa/duckdb/`: Database operations and spatial analytics
- `notebooks/`: Jupyter notebooks for analysis and examples
- `setup.py`: Automated data pipeline execution

**Database Schema**

The pipeline uses DuckDB with spatial extensions:

```sql
CREATE TABLE map_layers (
    layer_name VARCHAR PRIMARY KEY,
    source VARCHAR,
    layer_data JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Examples

**Database Inspection**
```python
from rampa.duckdb.operations import get_all_layers

layers = get_all_layers(db_connection)
print(f"Stored layers: {len(layers)}")
```

**Spatial Analysis**
```python
import duckdb

# Query sidewalk accessibility by district
query = """
SELECT 
    district,
    COUNT(*) as accessibility_projects,
    ST_Area(ST_Union(geometry)) as coverage_area
FROM map_layers 
WHERE layer_name LIKE 'ACCESIBILIDAD_ACERAS_%'
GROUP BY district;
"""

results = db_con.execute(query).fetchall()
```

**Memory Management**
```python
from rampa.query.query_tools import Data_Collection

collector = Data_Collection(db_con)
memory_info = collector.get_memory_usage_info()
print(f"Memory usage: {memory_info}")
```

## Dependencies

- `arcgis`: ArcGIS API integration
- `duckdb`: Spatial database engine
- `geopandas`: Geospatial data processing
- `pandas`: Data manipulation
- `tqdm`: Progress tracking

## Configuration

The pipeline includes:
- SSL warning suppression for ArcGIS HTTPS requests
- Comprehensive logging with timestamps
- Robust error handling and retry logic
- Memory-efficient lazy loading
- Automatic data validation and cleanup

## Testing

```bash
# Run basic database check
python -c "from rampa.duckdb.connection import get_duckdb_connection; print('Database connection successful')"

# Check available layers
python -c "
from rampa.duckdb.connection import get_duckdb_connection
from rampa.duckdb.operations import get_all_layers
db = get_duckdb_connection()
layers = get_all_layers(db)
print(f'Found {len(layers)} stored layers')
"
```

## Performance Features

- Memory efficiency with metadata-only storage and lazy data loading
- Spatial indexing using DuckDB spatial extensions for fast queries
- Batch processing with chunked downloads and progress tracking
- Error resilience with automatic retry and graceful failure handling

## Use Cases

This pipeline enables:

1. Accessibility Analysis: Map wheelchair accessibility, ramp coverage, public facility access
2. Demographic Studies: Age distribution analysis, population density mapping
3. Urban Planning: Infrastructure gaps, service coverage analysis
4. Policy Research: Evidence-based urban development insights
5. Community Services: Senior care facility optimization, public service accessibility

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project follows the Cookie Cutter Data Science template structure.

