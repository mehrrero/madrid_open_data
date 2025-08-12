# OSM Wheelchair Accessibility Integration - Using OSMQuery Class
# Simple examples using the new OSMQuery class in query_tools.py

from rampa.duckdb.connection import get_duckdb_connection
from rampa.query.query_tools import Data_Collection, OSMQuery

def example_osm_with_class():
    """
    Example using the new OSMQuery class integrated with Data_Collection
    """
    print("=== OSM Integration with OSMQuery Class ===")
    
    # Get database connection
    db_con = get_duckdb_connection()
    
    # Initialize data collection (can be empty for OSM-only work)
    collector = Data_Collection(
        url_dict={},
        populate=False,
        db_connection=db_con,
        store_in_memory=False
    )
    
    # Add OSM layer for Madrid amenities
    success = collector.add_osm_layer(
        name="madrid_amenities",
        bbox=(40.3119, -3.8633, 40.5640, -3.5179),  # Madrid bounding box
        city="Madrid"
    )
    
    if success:
        # Query OSM data and store in DuckDB
        osm_data = collector.query_osm_layer(
            name="madrid_amenities",
            feature_type="amenity",
            store_in_db=True
        )
        
        if osm_data:
            print(f"Retrieved {len(osm_data.get('elements', []))} OSM amenities")
            
            # Get analysis using pure DuckDB SQL
            analysis = collector.get_osm_analysis("madrid_amenities")
            
            if analysis:
                print("\\nAccessibility Distribution:")
                for item in analysis['accessibility_distribution']:
                    print(f"  {item['wheelchair']}: {item['count']} ({item['percentage']:.1f}%)")
                
                print("\\nTop Amenity Types:")
                for item in analysis['top_amenity_types'][:5]:
                    print(f"  {item['feature_type']} ({item['wheelchair']}): {item['count']}")

def example_direct_osm_query():
    """
    Example using OSMQuery class directly for custom queries
    """
    print("\\n=== Direct OSM Query Example ===")
    
    # Create OSM query instance
    osm = OSMQuery(
        bbox=(40.4000, -3.7500, 40.4300, -3.6800),  # Central Madrid
        city="Madrid"
    )
    
    # Custom query for accessible restaurants
    custom_query = '''
    [out:json][timeout:180];
    (
      nwr["amenity"="restaurant"]["wheelchair"="yes"](40.4000,-3.7500,40.4300,-3.6800);
      nwr["amenity"="cafe"]["wheelchair"="yes"](40.4000,-3.7500,40.4300,-3.6800);
    );
    out geom;
    '''
    
    # Execute query
    result = osm.query(custom_query=custom_query)
    
    if result:
        print(f"Found {len(result.get('elements', []))} accessible restaurants/cafes")
        
        # Store in DuckDB directly
        db_con = get_duckdb_connection()
        success = osm.store_in_duckdb(result, "accessible_restaurants", db_con)
        
        if success:
            # Query results using DuckDB SQL
            summary = db_con.execute("""
                SELECT 
                    amenity,
                    COUNT(*) as count,
                    COUNT(CASE WHEN name != '' THEN 1 END) as named_count
                FROM osm_accessible_restaurants
                GROUP BY amenity
                ORDER BY count DESC
            """).fetchall()
            
            print("\\nAccessible dining options:")
            for amenity, count, named in summary:
                print(f"  {amenity}: {count} total ({named} with names)")

def example_combined_analysis():
    """
    Example combining ArcGIS accessibility data with OSM data using DuckDB
    """
    print("\\n=== Combined ArcGIS + OSM Analysis ===")
    
    db_con = get_duckdb_connection()
    
    # Check what data we have
    tables = db_con.execute("SHOW TABLES").fetchall()
    
    has_arcgis = any('map_layers' in str(table) for table in tables)
    has_osm = any('osm_madrid_amenities' in str(table) for table in tables)
    
    print(f"ArcGIS data available: {has_arcgis}")
    print(f"OSM data available: {has_osm}")
    
    if has_arcgis and has_osm:
        # Combined analysis using pure SQL
        combined_stats = db_con.execute("""
            WITH arcgis_accessibility AS (
                SELECT COUNT(*) as total_arcgis_layers
                FROM map_layers
                WHERE layer_name LIKE '%ACCESIBILIDAD%'
            ),
            osm_accessibility AS (
                SELECT 
                    COUNT(*) as total_osm_features,
                    SUM(CASE WHEN wheelchair = 'yes' THEN 1 ELSE 0 END) as accessible_features,
                    AVG(wheelchair_score) as avg_accessibility_score
                FROM osm_madrid_amenities
            )
            SELECT 
                total_arcgis_layers,
                total_osm_features,
                accessible_features,
                accessible_features * 100.0 / total_osm_features as accessibility_percentage,
                avg_accessibility_score
            FROM arcgis_accessibility, osm_accessibility
        """).fetchone()
        
        if combined_stats:
            arcgis_layers, total_osm, accessible, percentage, avg_score = combined_stats
            print(f"\\nCombined Analysis Results:")
            print(f"  ArcGIS accessibility layers: {arcgis_layers}")
            print(f"  OSM total features: {total_osm}")
            print(f"  OSM accessible features: {accessible} ({percentage:.1f}%)")
            print(f"  Average accessibility score: {avg_score:.2f}/3.0")
    
    else:
        print("Run OSM and ArcGIS data collection first to enable combined analysis")

def main():
    """
    Main function demonstrating OSM integration
    """
    try:
        example_osm_with_class()
        example_direct_osm_query() 
        example_combined_analysis()
        
        print("\\n=== Summary ===")
        print("✓ OSM wheelchair data integrated with DuckDB")
        print("✓ Pure SQL analysis for memory efficiency")
        print("✓ Compatible with existing ArcGIS pipeline")
        print("✓ Follows same architecture as query_tools.py")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure requests is installed: pip install requests")

if __name__ == "__main__":
    main()
