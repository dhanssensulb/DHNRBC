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

gdf_c, gdf_B, gdf_b, gdf_a = process.load_urbis_footprint(urbis_folder, mask=mask_pentagone)

# OSM
osm_folder = '../../Data/OSM'
file_osm_buildings = osm_folder + '/Buildings.feather'

gdf_osm_buildings = process.load_gdf(file_osm_buildings, mask=mask_pentagone)

# SitEx
sitex_folder = '../../Data/SitEx'
file_sitex = sitex_folder + '/sitex_data.gpkg'

gdf_sitex = process.load_sitex_data(file_sitex, mask=mask_pentagone)

# BruGIS
brugis_folder = '../../Data/BruGIS'

gdf_h, gdf_i = process.load_brugis_heritage(brugis_folder, mask=mask_pentagone)

# Vision
vision_folder = '../../Data/Vision_Zonee'

gdf_v = process.load_zonal_data(vision_folder, mask=mask_pentagone_extended) # Extend to capture all cadastral parcels that intersect the pentagone

# PEB
peb_folder = '../../Data/PEB'
file_peb_public = peb_folder + '/peb_public.feather'

gdf_peb = process.load_gdf(file_peb_public)

# Group and aggregate data

gdf_cad = process.aggregate_cadastral_data(gdf_c, gdf_v)
gdf_build = process.aggregate_building_data(
    gdf_b, gdf_osm_buildings, gdf_sitex,
    gdf_h, gdf_i, gdf_peb
)

gdf_build = process.determine_building_type(gdf_build)
gdf_build = process.estimate_thermal_characteristics(gdf_build)

gdf_build = process.infer_cadastral_data(gdf_build, gdf_cad, binary_cols=['LISTED', 'GEOTHERMAL_ACCESS', 'AQUATHERMAL_ACCESS', 'RIOTHERMAL_ACCESS', 'FATAL_HEAT_ACCESS'])

# Remove unhabited buildings
mask_unhabited = (gdf_build.TYPE.isna()) | (gdf_build.FLOOR_AREA < 18)
gdf_build = gdf_build[~mask_unhabited]

gdf = process.group_urbis_footprint(gdf_cad, gdf_B, gdf_build, gdf_a)
gdf = gdf.set_geometry('geometry_building')

# Save dataframes in res

gdf_build.to_feather('../Res/Buildings.feather')
gdf_cad.to_feather('../Res/Cadastral.feather')

# %%
