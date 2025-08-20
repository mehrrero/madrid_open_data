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
    
    def build_query(self, query_type: str = "accessibility_routing") -> str:
        """
        Build Overpass QL query for wheelchair routing and accessibility data.
        
        Args:
            query_type: Type of accessibility query:
                - "accessibility_routing": Infrastructure for routing (kerbs, crossings, paths)
                - "accessible_pois": All wheelchair-accessible points of interest
                - "barriers": Obstacles and barriers that affect accessibility
                - "complete": All accessibility-related data
            
        Returns:
            Overpass QL query string
        """
        south, west, north, east = self.bbox
        
        if query_type == "accessibility_routing":
            # Infrastructure critical for wheelchair routing
            query = f"""
            [out:json][timeout:300];
            (
              // Kerbs and curb cuts - critical for wheelchair routing
              nwr["barrier"="kerb"]({south},{west},{north},{east});
              nwr["kerb"]({south},{west},{north},{east});
              
              // Crossings and pedestrian infrastructure
              nwr["highway"="crossing"]({south},{west},{north},{east});
              nwr["highway"="footway"]({south},{west},{north},{east});
              nwr["highway"="path"]["foot"!="no"]({south},{west},{north},{east});
              nwr["highway"="pedestrian"]({south},{west},{north},{east});
              nwr["highway"="steps"]({south},{west},{north},{east});
              
              // Sidewalks and walkways
              nwr["sidewalk"]({south},{west},{north},{east});
              nwr["footway"]({south},{west},{north},{east});
              
              // Tactile paving and guidance systems
              nwr["tactile_paving"]({south},{west},{north},{east});
              
              // Ramps and accessibility infrastructure
              nwr["highway"="footway"]["ramp"]({south},{west},{north},{east});
              nwr["ramp"]({south},{west},{north},{east});
            );
            out geom;
            """
            
        elif query_type == "accessible_pois":
            # All wheelchair-accessible points of interest
            query = f"""
            [out:json][timeout:300];
            (
              // All amenities with wheelchair accessibility
              nwr["amenity"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Shops with wheelchair accessibility
              nwr["shop"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Tourism and leisure with wheelchair accessibility
              nwr["tourism"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              nwr["leisure"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Healthcare facilities
              nwr["healthcare"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Public transport with accessibility
              nwr["public_transport"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              nwr["railway"="station"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              nwr["highway"="bus_stop"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Government and public services
              nwr["office"="government"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              nwr["amenity"="townhall"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
              
              // Educational facilities
              nwr["amenity"~"school|university|college"]["wheelchair"~"yes|limited"]({south},{west},{north},{east});
            );
            out geom;
            """
            
        elif query_type == "barriers":
            # Barriers and obstacles that affect accessibility
            query = f"""
            [out:json][timeout:300];
            (
              // Physical barriers
              nwr["barrier"]({south},{west},{north},{east});
              
              // Steps and level changes
              nwr["highway"="steps"]({south},{west},{north},{east});
              
              // Surfaces that may be difficult for wheelchairs
              nwr["surface"~"grass|gravel|sand|unpaved"]({south},{west},{north},{east});
              
              // Narrow passages
              nwr["width"]({south},{west},{north},{east});
              
              // Incline information
              nwr["incline"]({south},{west},{north},{east});
              
              // Obstacles
              nwr["obstacle"]({south},{west},{north},{east});
            );
            out geom;
            """
            
        elif query_type == "complete":
            # Comprehensive accessibility data
            query = f"""
            [out:json][timeout:600];
            (
              // ROUTING INFRASTRUCTURE
              nwr["barrier"="kerb"]({south},{west},{north},{east});
              nwr["kerb"]({south},{west},{north},{east});
              nwr["highway"="crossing"]({south},{west},{north},{east});
              nwr["highway"="footway"]({south},{west},{north},{east});
              nwr["highway"="path"]["foot"!="no"]({south},{west},{north},{east});
              nwr["tactile_paving"]({south},{west},{north},{east});
              nwr["ramp"]({south},{west},{north},{east});
              
              // ACCESSIBLE POIS
              nwr["wheelchair"~"yes|limited|no"]({south},{west},{north},{east});
              
              // BARRIERS AND OBSTACLES
              nwr["barrier"]({south},{west},{north},{east});
              nwr["highway"="steps"]({south},{west},{north},{east});
              nwr["incline"]({south},{west},{north},{east});
              
              // SURFACE INFORMATION
              nwr["surface"]({south},{west},{north},{east});
              nwr["smoothness"]({south},{west},{north},{east});
            );
            out geom;
            """
        else:
            # Default to accessibility routing
            return self.build_query("accessibility_routing")
            
        return query
    
    def query(self, query_type: str = "accessibility_routing", custom_query: Optional[str] = None) -> Optional[Dict]:
        """
        Execute OSM query and return raw JSON data.
        
        Args:
            query_type: Type of accessibility query:
                - "accessibility_routing": Infrastructure for routing (kerbs, crossings, paths)
                - "accessible_pois": All wheelchair-accessible points of interest
                - "barriers": Obstacles and barriers that affect accessibility
                - "complete": All accessibility-related data
            custom_query: Custom Overpass QL query (overrides query_type)
            
        Returns:
            Raw OSM JSON data or None if failed
        """
        try:
            if custom_query:
                query = custom_query
            else:
                query = self.build_query(query_type)
            
            logger.info(f"Executing OSM query for {query_type} accessibility data...")
            response = requests.post(self.overpass_url, data=query, timeout=600)
            
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
        Store OSM accessibility data directly in DuckDB using SQL operations.
        
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
            # Create comprehensive table for accessibility data
            table_name = f"osm_{layer_name}"
            
            # Drop table if it exists to recreate with correct schema
            db_con.execute(f"DROP TABLE IF EXISTS {table_name}")
            
            db_con.execute(f"""
                CREATE TABLE {table_name} (
                    osm_id BIGINT,
                    osm_type VARCHAR,
                    
                    -- Wheelchair accessibility
                    wheelchair VARCHAR,
                    wheelchair_score INTEGER,
                    
                    -- Feature types
                    amenity VARCHAR,
                    shop VARCHAR,
                    tourism VARCHAR,
                    leisure VARCHAR,
                    highway VARCHAR,
                    barrier VARCHAR,
                    
                    -- Routing infrastructure
                    kerb VARCHAR,
                    crossing VARCHAR,
                    tactile_paving VARCHAR,
                    ramp VARCHAR,
                    surface VARCHAR,
                    smoothness VARCHAR,
                    incline VARCHAR,
                    width FLOAT,
                    
                    -- Basic info
                    name VARCHAR,
                    lat DOUBLE,
                    lon DOUBLE,
                    geometry VARCHAR,
                    
                    -- Metadata
                    data_type VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Clear existing data for this layer
            # db_con.execute(f"DELETE FROM {table_name}")
            
            # Process and insert data in batches
            batch_size = 1000
            elements = osm_data['elements']
            
            for i in range(0, len(elements), batch_size):
                batch = elements[i:i + batch_size]
                values = []
                
                for element in batch:
                    osm_id = element.get('id')
                    osm_type = element.get('type')
                    tags = element.get('tags', {})
                    
                    # Extract accessibility and routing tags
                    wheelchair = tags.get('wheelchair', 'unknown')
                    kerb = tags.get('kerb', tags.get('barrier') if tags.get('barrier') == 'kerb' else '')
                    crossing = tags.get('crossing', '')
                    tactile_paving = tags.get('tactile_paving', '')
                    ramp = tags.get('ramp', '')
                    surface = tags.get('surface', '')
                    smoothness = tags.get('smoothness', '')
                    incline = tags.get('incline', '')
                    
                    # Width handling with improved parsing
                    width_str = tags.get('width', '')
                    width = self.parse_width(width_str) if width_str else None
                    
                    # Feature types
                    amenity = tags.get('amenity', '')
                    shop = tags.get('shop', '')
                    tourism = tags.get('tourism', '')
                    leisure = tags.get('leisure', '')
                    highway = tags.get('highway', '')
                    barrier = tags.get('barrier', '')
                    
                    # Basic info
                    name = tags.get('name', '')
                    
                    # Score wheelchair accessibility
                    wheelchair_score = {
                        'yes': 3,
                        'limited': 2, 
                        'no': 1,
                        'unknown': 0
                    }.get(wheelchair, 0)
                    
                    # Determine data type for categorization
                    if kerb or crossing or highway in ['crossing', 'footway', 'path']:
                        data_type = 'routing_infrastructure'
                    elif wheelchair in ['yes', 'limited']:
                        data_type = 'accessible_poi'
                    elif barrier or highway == 'steps':
                        data_type = 'barrier'
                    else:
                        data_type = 'other'
                    
                    # Handle geometry
                    if osm_type == 'node':
                        lat = element.get('lat')
                        lon = element.get('lon')
                        geometry = f"POINT({lon} {lat})" if lat and lon else None
                    else:
                        lat = lon = None
                        geometry = None  # Could be enhanced to handle ways/relations
                    
                    values.append([
                        osm_id, osm_type, wheelchair, wheelchair_score,
                        amenity, shop, tourism, leisure, highway, barrier,
                        kerb, crossing, tactile_paving, ramp, surface, smoothness, incline, width,
                        name, lat, lon, geometry, data_type
                    ])
                
                # Batch insert
                if values:
                    placeholders = ",".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(values))
                    flattened_values = [item for sublist in values for item in sublist]
                    
                    db_con.execute(f"""
                        INSERT INTO {table_name} 
                        (osm_id, osm_type, wheelchair, wheelchair_score,
                         amenity, shop, tourism, leisure, highway, barrier,
                         kerb, crossing, tactile_paving, ramp, surface, smoothness, incline, width,
                         name, lat, lon, geometry, data_type)
                        VALUES {placeholders}
                    """, flattened_values)
            
            # Log summary by data type
            summary = db_con.execute(f"""
                SELECT data_type, COUNT(*) as count 
                FROM {table_name} 
                GROUP BY data_type 
                ORDER BY count DESC
            """).fetchall()
            
            logger.info(f"Stored {len(elements)} OSM features in DuckDB table {table_name}:")
            for data_type, count in summary:
                logger.info(f"  {data_type}: {count} features")
            
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
    
    def build_pedestrian_width_query(self) -> str:
        """
        Build Overpass QL query specifically for pedestrian areas with width information.
        
        Returns:
            Overpass QL query string for pedestrian width data
        """
        south, west, north, east = self.bbox
        
        query = f"""
        [out:json][timeout:300];
        (
          // Pedestrian streets and areas with width information
          nwr["highway"="pedestrian"]["width"]({south},{west},{north},{east});
          
          // Footways with width (including pedestrian-only footways)
          nwr["highway"="footway"]["width"]({south},{west},{north},{east});
          
          // Pedestrian paths with width
          nwr["highway"="path"]["foot"="designated"]["width"]({south},{west},{north},{east});
          nwr["highway"="path"]["foot"="yes"]["width"]({south},{west},{north},{east});
          
          // Pedestrian areas (squares, plazas) with width
          nwr["area:highway"="pedestrian"]["width"]({south},{west},{north},{east});
          
          // Living streets (shared spaces) with width
          nwr["highway"="living_street"]["width"]({south},{west},{north},{east});
          
          // Also get all pedestrian areas even without explicit width
          // to see coverage
          nwr["highway"="pedestrian"]({south},{west},{north},{east});
        );
        out geom;
        """
        
        return query

    def parse_width(self, width_str: str) -> Optional[float]:
        """
        Parse width string from OSM tags, handling various formats.
        
        Args:
            width_str: Width string from OSM (e.g., "3.5", "3.5 m", "3,5", "3.5;4.0", "~3")
            
        Returns:
            Parsed width in meters as float, or None if unparseable
        """
        if not width_str or width_str.strip() == '':
            return None
            
        try:
            # Clean the string
            width_clean = width_str.strip().lower()
            
            # Remove common units
            width_clean = width_clean.replace(' m', '').replace('m', '').replace(' meters', '').replace('meters', '')
            width_clean = width_clean.replace(' ft', '').replace('ft', '').replace(' feet', '').replace('feet', '')
            
            # Handle approximate values
            width_clean = width_clean.replace('~', '').replace('ca.', '').replace('approx', '').replace('about', '')
            
            # Replace comma with dot for European decimal notation
            width_clean = width_clean.replace(',', '.')
            
            # Handle ranges (take average)
            if ';' in width_clean:
                # Multiple values separated by semicolon
                values = [v.strip() for v in width_clean.split(';') if v.strip()]
                parsed_values = []
                for v in values:
                    try:
                        parsed_values.append(float(v))
                    except ValueError:
                        continue
                if parsed_values:
                    return sum(parsed_values) / len(parsed_values)
            
            if '-' in width_clean:
                # Range like "3-4" or "3.5-4.5"
                parts = width_clean.split('-')
                if len(parts) == 2:
                    try:
                        min_width = float(parts[0].strip())
                        max_width = float(parts[1].strip())
                        return (min_width + max_width) / 2
                    except ValueError:
                        pass
            
            # Handle feet conversion (if ft was in original)
            multiplier = 1.0
            if 'ft' in width_str.lower() or 'feet' in width_str.lower():
                multiplier = 0.3048  # Convert feet to meters
            
            # Try direct float conversion
            width_float = float(width_clean) * multiplier
            
            # Sanity check: reasonable width values (0.1m to 100m)
            if 0.1 <= width_float <= 100:
                return round(width_float, 2)
            else:
                logger.warning(f"Width value outside reasonable range: {width_float}m from '{width_str}'")
                return None
                
        except (ValueError, TypeError):
            logger.warning(f"Could not parse width: '{width_str}'")
            return None

    def analyze_pedestrian_widths(self, db_con) -> Dict:
        """
        Analyze pedestrian width data stored in DuckDB.
        
        Args:
            db_con: DuckDB connection
            
        Returns:
            Dictionary with width analysis results
        """
        try:
            # Query pedestrian areas with width data
            width_data = db_con.execute("""
                SELECT 
                    osm_id,
                    highway,
                    width,
                    name,
                    lat,
                    lon,
                    CASE 
                        WHEN width IS NULL THEN 'No width data'
                        WHEN width < 2 THEN 'Narrow (< 2m)'
                        WHEN width >= 2 AND width < 4 THEN 'Medium (2-4m)'
                        WHEN width >= 4 AND width < 8 THEN 'Wide (4-8m)'
                        WHEN width >= 8 THEN 'Very wide (>= 8m)'
                    END as width_category
                FROM osm_amenities 
                WHERE highway IN ('pedestrian', 'footway', 'path', 'living_street')
                ORDER BY width DESC NULLS LAST
            """).fetchall()
            
            # Summary statistics
            summary = db_con.execute("""
                SELECT 
                    highway,
                    COUNT(*) as total_count,
                    COUNT(width) as with_width_count,
                    ROUND(AVG(width), 2) as avg_width,
                    ROUND(MIN(width), 2) as min_width,
                    ROUND(MAX(width), 2) as max_width,
                    ROUND(COUNT(width) * 100.0 / COUNT(*), 1) as width_coverage_percent
                FROM osm_amenities 
                WHERE highway IN ('pedestrian', 'footway', 'path', 'living_street')
                GROUP BY highway
                ORDER BY with_width_count DESC
            """).fetchall()
            
            # Width distribution for pedestrian areas specifically
            pedestrian_widths = db_con.execute("""
                SELECT 
                    width,
                    COUNT(*) as count
                FROM osm_amenities 
                WHERE highway = 'pedestrian' AND width IS NOT NULL
                GROUP BY width
                ORDER BY width DESC
            """).fetchall()
            
            return {
                'detailed_data': width_data,
                'summary_by_type': summary,
                'pedestrian_width_distribution': pedestrian_widths
            }
            
        except Exception as e:
            logger.error(f"Error analyzing pedestrian widths: {e}")
            return {}

    def query_pedestrian_widths(self, db_con) -> bool:
        """
        Execute query specifically for pedestrian width data and store in DuckDB.
        
        Args:
            db_con: DuckDB connection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build and execute pedestrian width query
            query = self.build_pedestrian_width_query()
            logger.info("Querying OSM for pedestrian width data...")
            
            response = requests.post(self.overpass_url, data=query, timeout=600)
            
            if response.status_code == 200:
                osm_data = response.json()
                logger.info(f"Retrieved {len(osm_data.get('elements', []))} pedestrian features")
                
                # Store in DuckDB
                success = self.store_in_duckdb(osm_data, "pedestrian_widths", db_con)
                
                if success:
                    # Analyze the width data
                    analysis = self.analyze_pedestrian_widths(db_con)
                    
                    # Log summary
                    logger.info("Pedestrian width data summary:")
                    for highway_type, total, with_width, avg_width, min_w, max_w, coverage in analysis.get('summary_by_type', []):
                        logger.info(f"  {highway_type}: {with_width}/{total} have width data ({coverage}% coverage)")
                        if with_width > 0:
                            logger.info(f"    Width range: {min_w}m - {max_w}m (avg: {avg_width}m)")
                    
                    return True
                else:
                    logger.error("Failed to store pedestrian width data in DuckDB")
                    return False
                
            else:
                logger.error(f"OSM pedestrian width query failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error querying pedestrian width data: {e}")
            return False
        
    def get_madrid_pedestrian_widths(self, db_con) -> Optional[Dict]:
        """
        Get pedestrian width data specifically for Madrid.
        
        Args:
            db_con: DuckDB connection
            
        Returns:
            Analysis results dictionary or None if failed
        """
        logger.info("Getting pedestrian width data for Madrid...")
        
        # Query pedestrian width data
        success = self.query_pedestrian_widths(db_con)
        
        if success:
            # Analyze the results
            analysis = self.analyze_pedestrian_widths(db_con)
            
            # Log key findings
            if analysis:
                logger.info("=== MADRID PEDESTRIAN WIDTH ANALYSIS ===")
                summary = analysis.get('summary_by_type', [])
                
                total_pedestrian_areas = 0
                total_with_width = 0
                
                for highway_type, total, with_width, avg_width, min_w, max_w, coverage in summary:
                    total_pedestrian_areas += total
                    total_with_width += with_width
                    
                    logger.info(f"{highway_type.upper()}: {with_width}/{total} with width data ({coverage}%)")
                    if with_width > 0:
                        logger.info(f"  Width range: {min_w}m - {max_w}m (average: {avg_width}m)")
                
                coverage_percent = (total_with_width / total_pedestrian_areas * 100) if total_pedestrian_areas > 0 else 0
                logger.info(f"Overall coverage: {total_with_width}/{total_pedestrian_areas} ({coverage_percent:.1f}%)")
                
                # Show some examples of wide pedestrian areas
                wide_areas = [item for item in analysis.get('pedestrian_width_distribution', []) if item[0] >= 5]
                if wide_areas:
                    logger.info("Wide pedestrian areas (≥5m):")
                    for width, count, name in wide_areas[:5]:  # Top 5
                        name_info = f" ({name})" if name else ""
                        logger.info(f"  {width}m width: {count} areas{name_info}")
            
            return analysis
        else:
            logger.error("Failed to get pedestrian width data")
            return None
