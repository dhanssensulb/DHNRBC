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
file_macro = '../../Data/BISA/StatisticalMacrozones.feather'
gdf_macro = process.load_gdf(file_macro)

# Mask Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

mask_pentagone_extended = mask_pentagone.buffer(100) # Extend by 100m

# Urbis
urbis_folder = '../../Data/UrbIS'

gdf_c, gdf_B, gdf_b, gdf_a = process.load_urbis_footprint(urbis_folder, mask=mask_pentagone)

gdf_nodes, gdf_edges = process.load_urbis_network(urbis_folder, mask=mask_pentagone)

# OSM
osm_folder = '../../Data/OSM'
file_osm_buildings = osm_folder + '/Buildings.feather'

gdf_osm_buildings = process.load_gdf(file_osm_buildings, mask=mask_pentagone)

# SitEx
sitex_folder = '../../Data/SitEx'
file_sitex = sitex_folder + '/sitex_data.gpkg'
gdf_sitex = process.load_sitex_data(file_sitex, mask=mask_pentagone)


# Group and harmonise footprint data
gdf_b = process.aggregate_building_data(gdf_b, gdf_osm_buildings, gdf_sitex)

gdf = process.group_urbis_footprint(gdf_c, gdf_B, gdf_b, gdf_a)
