# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%%

import load

# For debugging
import importlib
importlib.reload(load)

# Fetch Macrozones from BISA WFS
file_macro = '../../Data/BISA/StatisticalMacrozones.feather'
gdf_macro = load.load_gdf(file_macro)

# Mask Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

# Fetch OSM data within the Pentagone
gdf_buildings = load.fetch_osm_building_footprints(mask_pentagone, crs=gdf_pentagone.crs, saving=True, output_folder='../../Data/OSM')
gdf_nodes, gdf_edges = load.fetch_osm_streets(mask_pentagone, crs=gdf_pentagone.crs, saving=True, output_folder='../../Data/OSM')
