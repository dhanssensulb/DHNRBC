# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%%

import process

# For debugging
import importlib
importlib.reload(process)

# Fetch Macrozones from BISA WFS
folder_bisa = '../../Data/BISA'
file_macro = folder_bisa + '/StatisticalMacrozones.feather'

gdf_macro = process.load_gdf(file_macro)

# Mask Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

mask_pentagone_extended = mask_pentagone.buffer(100) # Extend by 100m

# Urbis
urbis_folder = '../../Data/UrbIS'

gdf_nodes_urbis, gdf_edges_urbis = process.load_urbis_network(urbis_folder, mask=mask_pentagone)

# OSM
osm_folder = '../../Data/OSM'

gdf_nodes_osm, gdf_edges_osm = process.load_osm_network(osm_folder, mask=mask_pentagone)

# Load RES buildings
res_folder = '../Res'
file_buildings = res_folder + '/Buildings.feather'

gdf_buildings = process.load_gdf(file_buildings)

# Clean segments
gdf_edges, gdf_nodes = process.clean_segments(gdf_edges_urbis, mask=gdf_buildings.geometry)

# Save dataframes in RES
gdf_edges.to_feather('../Res/Edges.feather')
gdf_nodes.to_feather('../Res/Nodes.feather')
# %%
