# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%% Libraries and config
from ast import For

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rc('text', usetex=True) # Use LaTeX for rendering text
plt.rc('font', family='sans-serif')

def load_gdf(file, mask=None, min_overlap_ratio=0.5):
    gdf = gpd.read_feather(file) if file.endswith('.feather') else gpd.read_file(file)
    if mask:
        geom_type = gdf.geometry.geom_type.unique()
        if geom_type[0] in ['Polygon', 'MultiPolygon']:
            gdf = gdf.loc[lambda df: df.intersection(mask).area / df.area >= min_overlap_ratio]
        else:
            gdf = gdf.loc[lambda df: df.within(mask)]
    return gdf

#%% Layers - Mask Pentagone (BISA)
import geopandas as gpd

# Macrozones
file_macro = '../../Data/BISA/StatisticalMacrozones.feather'
gdf_macro = load_gdf(file_macro)

# Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

#%% Extract OSM data

import osmnx as ox

# Buildings

tags_buildings = {'building': True}
mask_pentagone_wgs84 = gdf_pentagone.geometry.to_crs(epsg=4326).union_all()

buildings = ox.features_from_polygon(mask_pentagone_wgs84, tags=tags_buildings) # WGS 84
buildings = ox.projection.project_gdf(buildings, to_crs=gdf_pentagone.crs) # Lambert 72

# Save as feather
buildings.to_feather('../../Data/OSM/Buildings.feather')

# Streets

G_streets = ox.graph_from_polygon(mask_pentagone_wgs84, network_type='all', simplify=False, truncate_by_edge=False) # WGS 84
G_streets = ox.projection.project_graph(G_streets, to_crs=gdf_pentagone.crs) # Lambert 72

nodes = ox.graph_to_gdfs(G_streets, edges=False)
edges = ox.graph_to_gdfs(G_streets, nodes=False)

# Save as feather
nodes.to_feather('../../Data/OSM/Nodes.feather')
edges.to_feather('../../Data/OSM/Edges.feather')

# %%
