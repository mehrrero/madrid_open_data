import os
import sys
project_root = os.path.dirname(os.path.abspath('.'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
__package__ = 'rampa'

import pandas as pd
import geopandas as gpd
import pandana
import osmnx as ox
from shapely.ops import unary_union
from shapely.validation import explain_validity
import duckdb
from shapely import LineString
import numpy as np
<<<<<<< HEAD
import requests
from pyproj import Transformer
import json
from shapely.geometry import LineString, mapping
=======

>>>>>>> d6db040 (routing api done)

class Network:
    """
    Network class for managing, storing, and routing over street networks.
    This class provides methods to download, construct, and store street networks using OpenStreetMap data or from a DuckDB database. It supports alternate networks with accessibility considerations and provides routing functionality.
    Attributes:
        gdf (GeoDataFrame): GeoDataFrame containing the area of interest.
        aceras (GeoDataFrame): GeoDataFrame with sidewalk data for accessibility analysis.
        row (str): Name of the column in `aceras` to use for accessibility.
        db (str): Path to the DuckDB database for the main network.
        db_alt (str): Path to the DuckDB database for the alternate network.
        store (bool): Whether to store the network in the database after creation.
        nodes (DataFrame): DataFrame of network nodes.
        edges (DataFrame): DataFrame of network edges.
        edges_alt (DataFrame): DataFrame of alternate network edges.
        network (pandana.Network): Pandana network object for routing.
        alt_network (pandana.Network): Alternate Pandana network object for accessibility-aware routing.
        db_connection (duckdb.DuckDBPyConnection): Connection to the main DuckDB database.
        db_alt_connection (duckdb.DuckDBPyConnection): Connection to the alternate DuckDB database.
    Methods:
        __init__(gdf=None, db=None, db_alt=None, aceras=None, row=None, store=False):
            Initializes the Network object, loads or downloads the network, and optionally stores it.
        __get_network():
            Loads the network from the database or downloads it from OpenStreetMap, and constructs the Pandana network.
        __store_network():
            Stores the current network nodes and edges into the DuckDB database.
        set_alternate_network():
            Constructs an alternate network with accessibility attributes, either from the database or by intersecting with sidewalk data.
        __store_alt_network():
            Stores the alternate network nodes and edges into the alternate DuckDB database.
        route(coord1, coord2, alternate=False):
            Computes the shortest path between two coordinates using the main or alternate network.
        get_linestring(row):
            Returns a LineString geometry for an edge defined by a row.
        path(node_list):
            Returns a GeoDataFrame of edges (with geometries) corresponding to a list of node IDs.
        route_gdf(coord1, coord2, alternate=False):
            Returns a GeoDataFrame representing the route between two coordinates.
    """
    def __init__(self, gdf = None, db = None, db_alt=None, aceras = None, row= None, store = False):
        self.gdf = gdf
        self.aceras = aceras
        self.row = row
        
        if gdf is not None:
            self.polygon = gdf.geometry.unary_union
            # Try to fix invalid geometries
            if not self.polygon.is_valid:
                print(f"Invalid geometry: {explain_validity(self.polygon)}")
                self.polygon = self.polygon.buffer(0)

            if not self.polygon.is_valid:
                raise ValueError("Polygon geometry is still invalid after fixing.")

        if db is not None:
            if hasattr(self, "db_connection") and self.db_connection is not None:
                self.db_connection.close()
            self.db_connection = duckdb.connect(db)

        if db_alt is not None:
            if hasattr(self, "db_alt_connection") and self.db_alt_connection is not None:
                self.db_alt_connection.close()
            self.db_alt_connection = duckdb.connect(db_alt)

        self.__get_network()
        self.set_alternate_network()
        
        if store:
            self.__store_network()
            
        if store and hasattr(self, 'alt_network'):
            self.__store_alt_network()


    def __get_network(self):
        """
        Loads or downloads the network data for routing, initializing node and edge dataframes and creating a Pandana Network.
        If `self.gdf` is None, attempts to load nodes and edges from a database connection, converting columns to appropriate types.
        If `self.gdf` is not None, downloads a network graph from OpenStreetMap within a specified polygon using osmnx, and constructs nodes and edges dataframes.
        Handles errors related to database access and network download, returning None if unsuccessful.
        Upon successful loading or downloading, initializes `self.network` as a Pandana Network object using the nodes and edges data.
        Returns:
            None. Sets `self.nodes`, `self.edges`, and `self.network` attributes.
        """
       
        print('Downloading network')
        
        if self.gdf is None:
            try:
                self.nodes = self.db_connection.execute("SELECT * FROM nodes").fetchdf()
                self.edges = self.db_connection.execute("SELECT * FROM edges").fetchdf()
                self.nodes.set_index('index', inplace=True)
                self.nodes['x'] = self.nodes['x'].astype('float64')
                self.nodes['y'] = self.nodes['y'].astype('float64')
                self.edges['from'] = self.edges['from'].astype('int64')
                self.edges['to']   = self.edges['to'].astype('int64')
                self.edges['distance'] = self.edges['distance'].astype('float64')
            except Exception as e:
                print(f"Error loading network from database: {e}")
                return None, None
        else:
            try:
                self.graph = ox.graph_from_polygon(self.polygon, network_type='walk')
            except ValueError as e:
                if "Found no graph nodes within the requested polygon" in str(e):
                    print(f"No graph nodes found. Skipping.")
                    return None, None
                else:
                    print(f"Error downloading network for: {e}")
                    return None, None


            node_positions = {node: (data['x'], data['y']) for node, data in self.graph.nodes(data=True)}
            self.nodes = pd.DataFrame.from_dict(node_positions, orient='index', columns=['x', 'y'])

            _from = [u for u, v, _ in self.graph.edges]
            _to = [v for u, v, _ in self.graph.edges]
            _distance = [data['length'] for u, v, data in self.graph.edges(data=True)]
            self.edges = pd.DataFrame({'from': _from, 'to': _to, 'distance': _distance})

        self.network = pandana.Network(
                                self.nodes['x'],
                                self.nodes['y'],
                                self.edges['from'],
                                self.edges['to'],
                                self.edges[['distance']]
                                )

    def __store_network(self):
        """
        Stores the current network's nodes and edges DataFrames into DuckDB tables.
        This method registers the `nodes` and `edges` DataFrames as temporary tables in the DuckDB
        database connection, then creates or replaces the persistent `nodes` and `edges` tables
        with their contents. It also ensures the `nodes` DataFrame index is properly managed
        before and after storage.
        Raises:
            ValueError: If the database connection (`db_connection`) is not set.
        """
        
        if self.db_connection is None:
            raise ValueError("Database connection is not set.")

        print('Storing network in DuckDB')
        self.nodes.reset_index(drop=False, inplace=True)
        self.db_connection.register("df_nodes", self.nodes)
        self.db_connection.register("df_edges", self.edges)

        self.db_connection.execute("CREATE OR REPLACE TABLE nodes AS SELECT * FROM df_nodes")
        self.db_connection.execute("CREATE OR REPLACE TABLE edges AS SELECT * FROM df_edges")
        self.nodes.set_index('index', inplace=True)   


    def set_alternate_network(self):
        """
        Sets up an alternate network for routing, either by loading edge data from an alternate database connection
        or by modifying a copy of the existing edges with accessibility information.
        If no GeoDataFrame (`self.gdf`) is present, attempts to load edge data from the alternate database connection,
        ensuring correct data types for relevant columns.
        If a GeoDataFrame is present, copies the current edges, computes new geometries, and enriches the edges with
        accessibility information based on intersections with sidewalk data (`self.aceras`). The accessibility is
        determined by the minimum width (`self.row`) of intersecting sidewalks, and an accessibility flag is set
        based on a threshold. The alternate distance is then adjusted according to accessibility.
        Finally, constructs a new `pandana.Network` object using the alternate edge data and stores it in `self.alt_network`.
        Returns:
            None. Updates instance attributes in place.
        """

        if self.gdf is None:
            try:
                self.edges_alt = self.db_alt_connection.execute("SELECT * FROM edges").fetchdf()
                self.edges_alt['from'] = self.edges_alt['from'].astype('int64')
                self.edges_alt['to']   = self.edges_alt['to'].astype('int64')
                self.edges_alt['distance'] = self.edges_alt['distance'].astype('float64')
                self.edges_alt['alt_distance'] = self.edges_alt['alt_distance'].astype('float64')
            except Exception as e:
                print(f"Error loading network from database: {e}")
                return None, None

        else:
            self.edges_alt = self.edges.copy()

            self.edges_alt['geometry'] = self.edges_alt.apply(lambda row: self.get_linestring(row), axis=1)
            self.edges_alt = gpd.GeoDataFrame(self.edges_alt, geometry='geometry', crs='EPSG:4326')

            self.aceras = self.aceras.to_crs(self.edges_alt.crs)
            self.edges_alt[self.row] = None
            sindex = self.aceras.sindex

            for i, geom in enumerate(self.edges_alt.geometry):
                # Filtrar posibles intersecciones por bounding box
                possible_idx = list(sindex.intersection(geom.bounds))
                possible_matches = self.aceras.iloc[possible_idx]
                
                # Filtrar solo las que realmente intersectan
                intersecting = possible_matches[possible_matches.geometry.intersects(geom)]
                
                # Asignar mínimo Ancho_medio (o None si no hay intersecciones)
                self.edges_alt.loc[i, self.row] = intersecting[self.row].min() if not intersecting.empty else None

            self.edges_alt[self.row] = self.edges_alt[self.row].fillna(0)
            self.edges_alt['accesibility'] = np.where(self.edges_alt[self.row] >= 1.50, 1, 0)
            
            self.edges_alt['alt_distance'] = self.edges_alt['distance']/(10**self.edges_alt['accesibility'])

        self.alt_network = pandana.Network(
                                self.nodes['x'],
                                self.nodes['y'],
                                self.edges_alt['from'],
                                self.edges_alt['to'],
                                self.edges_alt[['alt_distance']]
                                )
        
    def __store_alt_network(self):
        """
        Stores the alternative network's nodes and edges in the connected DuckDB database.
        This method resets the index of the nodes DataFrame, registers both nodes and edges DataFrames 
        (excluding the 'geometry' column from edges) as tables in DuckDB, and creates or replaces the 
        corresponding tables in the database. After storing, it restores the original index of the nodes DataFrame.
        Raises:
            ValueError: If the database connection (`db_alt_connection`) is not set.
        """
        
        if self.db_alt_connection is None:
            raise ValueError("Database connection is not set.")

        print('Storing network in DuckDB')
        self.nodes.reset_index(drop=False, inplace=True)
        self.db_alt_connection.register("df_nodes", self.nodes)
        self.db_alt_connection.register("df_edges", self.edges_alt.drop(columns=['geometry']))

        self.db_alt_connection.execute("CREATE OR REPLACE TABLE nodes AS SELECT * FROM df_nodes")
        self.db_alt_connection.execute("CREATE OR REPLACE TABLE edges AS SELECT * FROM df_edges")
        self.nodes.set_index('index', inplace=True)   

    def route(self, coord1, coord2, alternate=False):
        """
        Calculates the shortest path between two coordinates using the primary or alternate network.
        Args:
            coord1 (tuple): The (longitude, latitude) of the starting point.
            coord2 (tuple): The (longitude, latitude) of the ending point.
            alternate (bool, optional): If True and an alternate network is available, use it for routing. Defaults to False.
        Returns:
            list: The sequence of node IDs representing the shortest path between coord1 and coord2.
        """
        
        lon1, lat1 = coord1
        lon2, lat2 = coord2

        lon = pd.Series([lon1, lon2])
        lat = pd.Series([lat1, lat2])

        if alternate and hasattr(self, 'alt_network'):
            id = self.alt_network.get_node_ids(lon, lat)
            path = self.alt_network.shortest_path(id[0], id[1])
        else:
            id = self.network.get_node_ids(lon, lat)
            path = self.network.shortest_path(id[0], id[1])
        return path
    

    def get_linestring(self, row):
        """
        Creates a LineString geometry between two nodes specified in the given row.
        Args:
            row (pd.Series): A pandas Series containing at least 'from' and 'to' keys,
                             which refer to node identifiers in self.nodes.
        Returns:
            LineString: A Shapely LineString object representing the straight line
                        between the 'from' and 'to' node coordinates.
        Raises:
            KeyError: If 'from' or 'to' keys are missing in the row or if the node
                      identifiers are not present in self.nodes.
        """
        

        from_ = self.nodes.loc[row['from']]
        to_ = self.nodes.loc[row['to']]
        coords = [(from_['x'], from_['y']), (to_['x'], to_['y'])]
        
        return LineString(coords)
    
    def path(self, node_list):
        """
        Constructs a GeoDataFrame representing the path defined by a sequence of nodes.
        Given a list of node identifiers, this method finds the corresponding edges between consecutive nodes,
        computes their geometries, and returns a GeoDataFrame containing these edges with geometry information.
        Args:
            node_list (list): A list of node identifiers representing the path.
        Returns:
            geopandas.GeoDataFrame: A GeoDataFrame containing the edges along the path, each with its geometry.
        """
        
        pairs = [(node_list[i], node_list[i + 1]) for i in range(len(node_list) - 1)]
        ed = [self.edges[(self.edges['from'] == p[0]) & (self.edges['to'] == p[1])] for p in pairs]
        ed = pd.concat(ed)
        ed['geometry'] = ed.apply(lambda row: self.get_linestring(row), axis=1)
        ed = gpd.GeoDataFrame(ed, geometry='geometry', crs='EPSG:4326')

        return ed

    def route_gdf(self, coord1, coord2, alternate=False):
        """
        Generates a GeoDataFrame representing the route between two coordinates.
        Args:
            coord1 (tuple or list): The starting coordinate (e.g., (lat, lon)).
            coord2 (tuple or list): The ending coordinate (e.g., (lat, lon)).
            alternate (bool, optional): If True, computes an alternate route. Defaults to False.
        Returns:
            GeoDataFrame: A GeoDataFrame representing the computed route.
        """
        
        pat = self.route(coord1, coord2, alternate)
        ed = self.path(pat)
        return ed
    
    
import requests
from pyproj import Transformer

class GeoCoder:
    def __init__(self):
        self.address_URL = 'https://sigma.madrid.es/hosted/rest/services/GEOLOCATOR/GEOLOCALIZADOR_MADRID_VIAL_NDP/GeocodeServer'
        self.POI_URL = 'https://sigma.madrid.es/hosted/rest/services/GEOLOCATOR/POIS/GeocodeServer'
        self.transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    
    def _geocode(self, service_url, query):
        params = {
            "SingleLine": query,
            "f": "json",
            "outFields": "*",
            "maxLocations": 10
        }
        response = requests.get(f"{service_url}/findAddressCandidates", params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for candidate in data.get("candidates", []):
            x, y = candidate["location"]["x"], candidate["location"]["y"]
            lon, lat = self.transformer.transform(x, y)
            results.append({
                "address": candidate["address"],
                "lat": lat,
                "lon": lon,
                "score": candidate.get("score")
            })
        return results
    
    def __call__(self, query):
        # Llamar a ambos servicios y combinar resultados
        address_results = self._geocode(self.address_URL, query)
        poi_results = self._geocode(self.POI_URL, query)
        return address_results + poi_results

geocoder = GeoCoder()




def ruta_to_json(ruta):
    # Collect all coordinates from the route
    coords = []
    for geom in ruta.geometry:
        coords.extend(list(geom.coords))
    # Remove consecutive duplicate coordinates
    unique_coords = [coords[0]]
    for c in coords[1:]:
        if c != unique_coords[-1]:
            unique_coords.append(c)
    # Build the main geometry
    geometry = {
        "coordinates": [[round(x, 6), round(y, 6)] for x, y in unique_coords],
        "type": "LineString"
    }
    total_distance = float(ruta['distance'].sum())
    # For this example, assume duration = distance / 1.3 (walking speed ~1.3 m/s)
    total_duration = total_distance / 1.3
    # Build legs and steps (one leg, one step per segment)
    steps = []
    for idx, row in ruta.iterrows():
        step_geom = mapping(row['geometry'])
        step = {
            "distance": float(row['distance']),
            "duration": float(row['distance']) / 1.3,
            "geometry": step_geom,
            "maneuver": {
                "instruction": "Continue",
                "type": "waypoint",
                "bearing_after": None,
                "location": [round(row['geometry'].coords[0][0], 6), round(row['geometry'].coords[0][1], 6)]
            },
            "name": ""
        }
        steps.append(step)
    leg = {
        "distance": total_distance,
        "duration": total_duration,
        "steps": steps
    }
    route = {
        "geometry": geometry,
        "duration": total_duration,
        "distance": total_distance,
        "weight": total_duration,
        "weight_name": "routability",
        "legs": [leg]
    }
    # Waypoints: start point only, name left blank
    waypoint = {
        "distance": 0,
        "name": "",
        "location": [round(unique_coords[0][0], 6), round(unique_coords[0][1], 6)]
    }
    output = {
        "routes": [route],
        "waypoints": [waypoint],
        "code": "Ok"
    }
    return output

