# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%% Helpers

import time
import os
import geopandas as gpd
from owslib.wfs import WebFeatureService
import osmnx as ox
from shapely.validation import make_valid

def connect_to_wfs(url, version='2.0.0', verbose=True):
    """
    Connect to a Web Feature Service (WFS) and return the service object.
    If verbose is True, print the service title, abstract, and available features.
    """
    wfs = WebFeatureService(url=url, version=version, timeout=120)
    layers = list(wfs.contents.keys())

    if verbose:
        print('Title:', wfs.identification.title)
        print('Abstract:', wfs.identification.abstract)
        print('Layers:', layers)

    return wfs, layers

def fetch_wfs_layer(wfs, layer_name, properties=None, srsname=None, maxfeatures=None, saving=False, output_folder=None):
    """
    Fetch a specific layer from a WFS service and return it as a GeoDataFrame.
    """
    print(f'Fetching: {layer_name}')
    start = time.time()

    try:
        r = wfs.getfeature(
            typename=layer_name,
            propertyname=properties, # Fetch all properties
            srsname=srsname, # Coordinate Reference System (CRS)
            maxfeatures=maxfeatures,
            outputFormat='application/json'
        ) # BytesIO (file-like object)
    
        gdf = gpd.read_file(r)
        gdf.set_index('id', inplace=True)
    except Exception as e:
        print(f"Error fetching layer {layer_name}: {e}\n")
        return None

    if saving:
        print(f'Saving: {layer_name}')
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        if ':' in layer_name:
            file_name = f'{output_folder}/{layer_name.split(":")[1]}.feather'
        else:
            file_name = f'{output_folder}/{layer_name}.feather'

        gdf.to_feather(file_name)

    end = time.time()
    print(f'Time taken: {end - start:.2f} seconds\n')

    return gdf

def fetch_osm_building_footprints(mask, crs='EPSG:4326', missing_threshold=0.5, saving=False, output_folder=None):
    """
    Fetch building footprints from OSM.
    """
    tags_buildings = {'building': True}

    mask_wgs84 = gpd.GeoSeries(mask, crs=crs).to_crs(epsg=4326).union_all()

    print(f'Fetching: OSM Building Footprints')
    start = time.time()

    buildings = ox.features_from_polygon(mask_wgs84, tags=tags_buildings) # WGS 84
    buildings = ox.projection.project_gdf(buildings, to_crs=crs) # Reproject to specified CRS

    # Keep then only columns with less than {missing_threshold*100}% missing values
    columns_to_keep = [col for col in buildings.columns if buildings[col].isna().mean() < missing_threshold]
    buildings = buildings[columns_to_keep]

    # Keep only polygons and multipolygons
    buildings = buildings[buildings.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    if saving:
        print(f'Saving: OSM Building Footprints')
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        buildings.to_feather(f'{output_folder}/Buildings.feather')

    end = time.time()
    print(f'Time taken: {end - start:.2f} seconds\n')

    return buildings

def fetch_osm_streets(mask, crs='EPSG:4326', missing_threshold=0.5, saving=False, output_folder=None):
    """
    Fetch street data from OSM.
    """
    mask_wgs84 = gpd.GeoSeries(mask, crs=crs).to_crs(epsg=4326).union_all()

    print(f'Fetching: OSM Streets')
    start = time.time()

    G_streets = ox.graph_from_polygon(mask_wgs84, network_type='all', simplify=False, truncate_by_edge=False) # WGS 84
    G_streets = ox.projection.project_graph(G_streets, to_crs=crs) # Reproject to specified CRS

    nodes = ox.graph_to_gdfs(G_streets, edges=False)
    edges = ox.graph_to_gdfs(G_streets, nodes=False)

    # Keep only columns with less than {missing_threshold*100}% missing values
    columns_to_keep_nodes = [col for col in nodes.columns if nodes[col].isna().mean() < missing_threshold]
    columns_to_keep_edges = [col for col in edges.columns if edges[col].isna().mean() < missing_threshold]
    nodes = nodes[columns_to_keep_nodes]
    edges = edges[columns_to_keep_edges]

    if saving:
        print(f'Saving: OSM Streets')
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        nodes.to_feather(f'{output_folder}/Nodes.feather')
        edges.to_feather(f'{output_folder}/Edges.feather')

    end = time.time()
    print(f'Time taken: {end - start:.2f} seconds\n')

    return nodes, edges

def load_gdf(file, layer=None, mask=None, min_overlap_ratio=0.5):
    """
    Load a GeoDataFrame from a file, optionally applying a spatial mask.
    A polygon belongs to the masked GeoDataFrame if at least `min_overlap_ratio` of its area overlaps with the mask.
    For non-polygon geometries, they are included if they are within the mask.
    """
    if file.endswith('.feather'):
        gdf = gpd.read_feather(os.path.abspath(file))
    else:
        gdf = gpd.read_file(os.path.abspath(file), layer=layer) if layer else gpd.read_file(os.path.abspath(file))
    
    # Removes null geometries and repairs invalid geometries
    gdf = gdf.dropna(subset=['geometry']).reset_index(drop=True)
    gdf.geometry = gdf.geometry.apply(make_valid)

    if mask:
        geom_type = gdf.geometry.geom_type.unique()
        if geom_type[0] in ['Polygon', 'MultiPolygon']:
            gdf = gdf.loc[lambda df: df.intersection(mask).area / df.area >= min_overlap_ratio]
        else:
            gdf = gdf.loc[lambda df: df.within(mask)]

    return gdf

if __name__ == "__main__":
    # Run the code for all layers
    import bisa
    import urbis
    import brugis
    import osm # OSM must be run after BISA as it requires the Pentagon mask
# %%
