import geopandas as gpd
import pandas as pd
from rampa.config import config
import duckdb


def lines_in_polygons(polygons_gdf, lines_gdf, polygon_id_col=None, line_id_col=None, crs='EPSG:3857'):
    """
    Returns lines intersecting polygons with the ratio of each line's length inside the polygon.
    """

    # Ensure same projected CRS
    polygons = polygons_gdf.to_crs(crs).copy()
    lines = lines_gdf.to_crs(crs).copy()

    # If no ID column is provided, create one
    if polygon_id_col is None or polygon_id_col not in polygons.columns:
        polygons['poly_id'] = polygons.index
        polygon_id_col = 'poly_id'

    if line_id_col is None or line_id_col not in lines.columns:
        lines['line_id'] = lines.index
        line_id_col = 'line_id'

    # Keep IDs
    polygons = polygons[[polygon_id_col, 'COD_SECCIO', 'NOM_BAR', 'NOM_DIS', 'geometry']]
    lines = lines[[line_id_col, 'accesibility', 'geometry']]

    # Get intersection geometries
    line_segments = gpd.overlay(lines, polygons, how='intersection')

    # Compute lengths
    line_segments['length_inside'] = line_segments.geometry.length

    # Total line lengths
    lines['length_total'] = lines.geometry.length
    lines['accesibility'] = lines['accesibility']

    # Merge total length
    line_segments = line_segments.merge(lines[[line_id_col, 'length_total']], on=line_id_col)

    # Ratio inside
    line_segments['ratio_inside'] = line_segments['length_inside'] / line_segments['length_total']

    return line_segments



def analysis(network):
    print('Loading data...')
    sc = gpd.read_file(config.data_analysis['secciones_censales'])
    edges = network.edges
    edges['geometry'] = edges.apply(lambda row: network.get_linestring(row), axis=1)
    edges = gpd.GeoDataFrame(edges, geometry='geometry', crs='EPSG:4326')

    print('Computing line-polygon intersections...')
    res = lines_in_polygons(sc, edges)
    res_acc = res[res['accesibility'] ==1]
    res_no_acc = res[res['accesibility'] ==0]

    acc = res_acc.groupby('poly_id').agg({
        'COD_SECCIO': 'first',
        'length_inside': 'sum',
        'NOM_BAR': 'first',
        'NOM_DIS': 'first'
    }).reset_index()
    
    no_acc = res_no_acc.groupby('poly_id').agg({
        'COD_SECCIO': 'first',
        'length_inside': 'sum',
        'NOM_BAR': 'first',
        'NOM_DIS': 'first'
    }).reset_index()
    
    cs = acc.merge(no_acc, on=['poly_id', 'COD_SECCIO'], how='outer', suffixes=('_acc', '_no_acc')).fillna(0)
    cs['ratio'] =100 * cs['length_inside_acc'] /(cs['length_inside_no_acc']+cs['length_inside_acc'])
    
    print('Generating outputs...')
    seccion = cs.merge(sc[['COD_SECCIO', 'geometry']], on='COD_SECCIO')
    seccion = gpd.GeoDataFrame(seccion, geometry='geometry', crs='EPSG:25830')
    seccion.loc[seccion['NOM_DIS_no_acc'] == 0, 'NOM_DIS_no_acc'] = seccion.loc[seccion['NOM_DIS_no_acc'] == 0, 'NOM_DIS_acc']
    seccion.loc[seccion['NOM_BAR_no_acc'] == 0, 'NOM_BAR_no_acc'] = seccion.loc[seccion['NOM_BAR_no_acc'] == 0, 'NOM_BAR_acc']
    barrio = seccion.dissolve(by='NOM_BAR_no_acc', as_index=False)
    distrito = seccion.dissolve(by='NOM_DIS_no_acc', as_index=False)
    
    seccion = seccion[['COD_SECCIO', 'length_inside_acc', 'length_inside_no_acc', 'ratio', 'NOM_BAR_no_acc', 'NOM_DIS_no_acc', 'geometry']]
    seccion = seccion.rename(columns={
        'NOM_BAR_no_acc': 'NOM_BAR',
        'NOM_DIS_no_acc': 'NOM_DIS'
    })
    barrio = barrio[['NOM_BAR_no_acc', 'NOM_DIS_no_acc', 'length_inside_acc', 'length_inside_no_acc', 'ratio', 'geometry']]
    barrio = barrio.rename(columns={
        'NOM_BAR_no_acc': 'NOM_BAR',
        'NOM_DIS_no_acc': 'NOM_DIS'
    })
    
    distrito = distrito[['NOM_DIS_no_acc', 'length_inside_acc', 'length_inside_no_acc', 'ratio', 'geometry']]
    distrito = distrito.rename(columns={
        'NOM_DIS_no_acc': 'NOM_DIS',
    })

    seccion.to_file(config.paths['data_dir']+'/seccion.geojson', driver='GeoJSON')
    barrio.to_file(config.paths['data_dir']+'/barrio.geojson', driver='GeoJSON')
    distrito.to_file(config.paths['data_dir']+'/distrito.geojson', driver='GeoJSON')

    print('Done.')