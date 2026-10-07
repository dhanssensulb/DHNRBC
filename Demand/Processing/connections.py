# -*- coding: utf-8 -*-
"""
Created on June 26

@author: hanssens
"""

#%%

import process

# For debugging
import importlib
importlib.reload(process)

# Load RES 
res_folder = '../Res'
file_buildings = res_folder + '/Buildings.feather'
file_edges = res_folder + '/Edges.feather'
file_nodes = res_folder + '/Nodes.feather'

gdf_buildings = process.load_gdf(file_buildings)
gdf_edges = process.load_gdf(file_edges)
gdf_nodes = process.load_gdf(file_nodes)

# Select middle scenario
gdf_b = gdf_buildings[gdf_buildings.VERSION_HEAT == 'middle']

# Create connections
gdf_connections = process.connect_buildings_to_streets(gdf_b, gdf_edges, gdf_nodes, n_length_threshold=5)

# Save dataframes in RES
gdf_connections.to_feather('../Res/Connections.feather')
# %%
