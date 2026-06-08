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

# Load Demand Results
res_folder = '../Demand/Res'
file_buildings = res_folder + '/Buildings.feather'
file_edges = res_folder + '/Edges.feather'
file_nodes = res_folder + '/Nodes.feather'
file_connections = res_folder + '/Connections.feather'

gdf_buildings = process.load_gdf(file_buildings)
gdf_edges = process.load_gdf(file_edges)
gdf_nodes = process.load_gdf(file_nodes)
gdf_connections = process.load_gdf(file_connections)
# %%
