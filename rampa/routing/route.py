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


class Network:
    def __init__(self, gdf = None, db = None, store = False):
        self.gdf = gdf
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

        self.__get_network()
        
        if store:
            self.__store_network()

    def __get_network(self):
        """
        Downloads the street network from OpenStreetMap for the given GeoDataFrame and returns a Pandana network object.
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
        if self.db_connection is None:
            raise ValueError("Database connection is not set.")

        print('Storing network in DuckDB')
        self.nodes.reset_index(drop=False, inplace=True)
        self.db_connection.register("df_nodes", self.nodes)
        self.db_connection.register("df_edges", self.edges)

        self.db_connection.execute("CREATE OR REPLACE TABLE nodes AS SELECT * FROM df_nodes")
        self.db_connection.execute("CREATE OR REPLACE TABLE edges AS SELECT * FROM df_edges")
        self.nodes.set_index('index', inplace=True)   
        

    def route(self, coord1, coord2):
        lon1, lat1 = coord1
        lon2, lat2 = coord2

        lon = pd.Series([lon1, lon2])
        lat = pd.Series([lat1, lat2])

        id = self.network.get_node_ids(lon, lat)

        path = self.network.shortest_path(id[0], id[1])
        return path
    

    def get_linestring(self, row):

        from_ = self.nodes.loc[row['from']]
        to_ = self.nodes.loc[row['to']]
        coords = [(from_['x'], from_['y']), (to_['x'], to_['y'])]
        
        return LineString(coords)
    
    def path(self, node_list):
        pairs = [(node_list[i], node_list[i + 1]) for i in range(len(node_list) - 1)]
        ed = [self.edges[(self.edges['from'] == p[0]) & (self.edges['to'] == p[1])] for p in pairs]
        ed = pd.concat(ed)
        ed['geometry'] = ed.apply(lambda row: self.get_linestring(row), axis=1)
        ed = gpd.GeoDataFrame(ed, geometry='geometry')

        return ed

    def route_gdf(self, coord1, coord2):
        pat = self.route(coord1, coord2)
        ed = self.path(pat)
        return ed