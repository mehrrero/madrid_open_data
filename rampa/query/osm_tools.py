import os
import sys
project_root = os.path.dirname(os.path.abspath('.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
__package__ = 'rampa'


import logging
import datetime
from rampa.duckdb.operations import write_layer_to_table
from rampa.duckdb.connection import DuckDBPyConnection
from typing import Dict, Optional, Any, Tuple
from datetime import datetime
import requests
import json

# Set up logging instead of print statements
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import urllib3
# Suppress urllib3 SSL warnings globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class OSMQuery():
    """
    A class to facilitate querying OpenStreetMap wheelchair accessibility data using DuckDB-first approach.
    """
    
    def __init__(self, bbox: Optional[Tuple[float, float, float, float]] = None, city: str = "Madrid"):
        """
        Initialize OSM query for wheelchair accessibility data.
        
        Args:
            bbox: Bounding box (south, west, north, east) in decimal degrees
            city: City name for queries
        """
        self.bbox = bbox or (40.3119, -3.8633, 40.5640, -3.5179)  # Madrid default
        self.city = city
        self.overpass_url = "http://overpass-api.de/api/interpreter"
        self.type = "OSM"
    
    def build_query(self, feature_type: str = "amenity") -> str:
        """
        Build Overpass QL query for wheelchair accessibility features.
        
        Args:
            feature_type: OSM feature type ('amenity', 'shop', 'tourism', etc.)
            
        Returns:
            Overpass QL query string
        """
        south, west, north, east = self.bbox
        
        query = f"""
        [out:json][timeout:180];
        (
          nwr["{feature_type}"]["wheelchair"~"yes|no|limited"]({south},{west},{north},{east});
        );
        out geom;
        """
        return query
    
    def query(self, feature_type: str = "amenity", custom_query: Optional[str] = None) -> Optional[Dict]:
        """
        Execute OSM query and return raw JSON data.
        
        Args:
            feature_type: Type of features to query
            custom_query: Custom Overpass QL query (overrides feature_type)
            
        Returns:
            Raw OSM JSON data or None if failed
        """
        try:
            if custom_query:
                query = custom_query
            else:
                query = self.build_query(feature_type)
            
            logger.info(f"Executing OSM query for {feature_type} wheelchair data...")
            response = requests.post(self.overpass_url, data=query, timeout=300)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Retrieved {len(data.get('elements', []))} OSM features")
                return data
            else:
                logger.error(f"OSM query failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error querying OSM data: {e}")
            return None
    
    def store_in_duckdb(self, osm_data: Dict, layer_name: str, db_con: DuckDBPyConnection) -> bool:
        """
        Store OSM data directly in DuckDB using SQL operations.
        
        Args:
            osm_data: Raw OSM JSON data
            layer_name: Name for the DuckDB table
            db_con: DuckDB connection
            
        Returns:
            True if successful, False otherwise
        """
        if not osm_data or 'elements' not in osm_data:
            logger.warning("No OSM data to store")
            return False
        
        try:
            # Create table for OSM data
            table_name = f"osm_{layer_name}"
            db_con.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    osm_id BIGINT,
                    osm_type VARCHAR,
                    wheelchair VARCHAR,
                    amenity VARCHAR,
                    shop VARCHAR,
                    tourism VARCHAR,
                    name VARCHAR,
                    lat DOUBLE,
                    lon DOUBLE,
                    geometry VARCHAR,
                    wheelchair_score INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Clear existing data for this layer
            db_con.execute(f"DELETE FROM {table_name}")
            
            # Process and insert data in batches for efficiency
            batch_size = 1000
            elements = osm_data['elements']
            
            for i in range(0, len(elements), batch_size):
                batch = elements[i:i + batch_size]
                values = []
                
                for element in batch:
                    osm_id = element.get('id')
                    osm_type = element.get('type')
                    tags = element.get('tags', {})
                    
                    # Extract relevant tags
                    wheelchair = tags.get('wheelchair', 'unknown')
                    amenity = tags.get('amenity', '')
                    shop = tags.get('shop', '')
                    tourism = tags.get('tourism', '')
                    name = tags.get('name', '')
                    
                    # Score wheelchair accessibility
                    wheelchair_score = {
                        'yes': 3,
                        'limited': 2, 
                        'no': 1,
                        'unknown': 0
                    }.get(wheelchair, 0)
                    
                    # Handle geometry
                    if osm_type == 'node':
                        lat = element.get('lat')
                        lon = element.get('lon')
                        geometry = f"POINT({lon} {lat})" if lat and lon else None
                    else:
                        lat = lon = None
                        geometry = None  # Simplified for now
                    
                    values.append([osm_id, osm_type, wheelchair, amenity, shop, tourism, 
                                 name, lat, lon, geometry, wheelchair_score])
                
                # Batch insert
                if values:
                    placeholders = ",".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(values))
                    flattened_values = [item for sublist in values for item in sublist]
                    
                    db_con.execute(f"""
                        INSERT INTO {table_name} 
                        (osm_id, osm_type, wheelchair, amenity, shop, tourism, 
                         name, lat, lon, geometry, wheelchair_score)
                        VALUES {placeholders}
                    """, flattened_values)
            
            logger.info(f"Stored {len(elements)} OSM features in DuckDB table {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OSM data in DuckDB: {e}")
            return False
    
    def to_dict(self, osm_data: Dict, layer_name: str) -> Dict[str, Any]:
        """
        Convert OSM data to dictionary format compatible with existing storage system.
        
        Args:
            osm_data: Raw OSM JSON data
            layer_name: Layer name
            
        Returns:
            Dictionary suitable for database storage
        """
        if not osm_data or 'elements' not in osm_data:
            elements = []
        else:
            elements = osm_data['elements']
        
        # Process elements to extract key information
        processed_data = []
        for element in elements:
            tags = element.get('tags', {})
            processed_element = {
                'osm_id': element.get('id'),
                'osm_type': element.get('type'),
                'wheelchair': tags.get('wheelchair', 'unknown'),
                'amenity': tags.get('amenity', ''),
                'name': tags.get('name', ''),
                'lat': element.get('lat'),
                'lon': element.get('lon')
            }
            processed_data.append(processed_element)
        
        layer_data = {
            'data': json.dumps(processed_data),
            'crs': 'EPSG:4326',
            'layer_type': 'OSM',
            'url': f'OSM_{layer_name}_{self.city}',
            'record_count': len(elements),
            'columns': ['osm_id', 'osm_type', 'wheelchair', 'amenity', 'name', 'lat', 'lon'],
            'bounds': list(self.bbox),
            'dtypes': {'osm_id': 'int64', 'wheelchair': 'object', 'amenity': 'object'},
            'datetime_columns': {},
            'has_geometry': True,
            'query_bbox': self.bbox
        }
        
        return layer_data

    def add_osm_layer(self, 
                     name: str, 
                     bbox: Optional[Tuple[float, float, float, float]] = None,
                     city: str = "Madrid") -> bool:
        """
        Add an OSM wheelchair accessibility layer to the collection.
        
        Args:
            name: Layer name for storage
            bbox: Bounding box (south, west, north, east)
            city: City name
            
        Returns:
            True if successful, False otherwise
        """
        if name in self.layers:
            logger.warning(f"Layer {name} already exists. Use a different name.")
            return False
        
        try:
            # Create OSM query instance
            osm_query = OSMQuery(bbox=bbox, city=city)
            self.layers[name] = osm_query
            logger.info(f"Added OSM layer: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add OSM layer {name}: {e}")
            return False
    
    def query_osm_layer(self, 
                       name: str, 
                       feature_type: str = "amenity",
                       custom_query: Optional[str] = None,
                       store_in_db: bool = True) -> Optional[Dict]:
        """
        Query an OSM layer and optionally store in DuckDB.
        
        Args:
            name: OSM layer name
            feature_type: Type of features to query
            custom_query: Custom Overpass QL query
            store_in_db: Whether to store results in database
            
        Returns:
            Raw OSM data dictionary or None
        """
        if name not in self.layers:
            raise ValueError(f"OSM layer {name} does not exist. Add it first with add_osm_layer().")
        
        layer = self.layers[name]
        if not isinstance(layer, OSMQuery):
            raise ValueError(f"Layer {name} is not an OSM layer.")
        
        # Query from OSM
        osm_data = layer.query(feature_type=feature_type, custom_query=custom_query)
        
        # Store in DuckDB if requested and we got data
        if self.db_connection and store_in_db and osm_data:
            success = layer.store_in_duckdb(osm_data, name, self.db_connection)
            if success:
                # Also store in the map_layers table for consistency
                layer_dict = layer.to_dict(osm_data, name)
                source = f"OSM_{feature_type}_{layer.city}"
                write_layer_to_table(self.db_connection, name, source, layer_dict)
                
                # Store metadata
                if not self.store_in_memory:
                    self.data[name] = {
                        'stored_in_db': True,
                        'table_name': f'osm_{name}',
                        'record_count': len(osm_data.get('elements', [])),
                        'last_updated': datetime.now().isoformat(),
                        'data_type': 'OSM',
                        'feature_type': feature_type
                    }
        
        return osm_data
    