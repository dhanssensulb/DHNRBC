# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%%

import process
import pandas as pd

# For debugging
import importlib
importlib.reload(process)

# Fetch Macrozones from BISA WFS
folder_bisa = '../../Data/BISA'
file_macro = folder_bisa + '/StatisticalMacrozones.feather'

gdf_macro = process.load_gdf(file_macro)

# Mask Pentagon
gdf_pentagon = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagon = gdf_pentagon.union_all()

mask_pentagon_extended = mask_pentagon.buffer(100) # Extend by 100m

# Urbis
urbis_folder = '../../Data/UrbIS'

gdf_c, gdf_B, gdf_b, gdf_a = process.load_urbis_footprint(urbis_folder, mask=mask_pentagon)

# OSM
osm_folder = '../../Data/OSM'
file_osm_buildings = osm_folder + '/Buildings.feather'

gdf_osm_buildings = process.load_gdf(file_osm_buildings, mask=mask_pentagon)

# SitEx
sitex_folder = '../../Data/SitEx'
file_sitex = sitex_folder + '/sitex_data.gpkg'

gdf_sitex = process.load_sitex_data(file_sitex, mask=mask_pentagon)

# BruGIS
brugis_folder = '../../Data/BruGIS'

gdf_h, gdf_i = process.load_brugis_heritage(brugis_folder, mask=mask_pentagon)

# Zonal Vision
vision_folder = '../../Data/Vision_Zonee'

gdf_v = process.load_zonal_data(vision_folder, mask=mask_pentagon_extended) # Extend to capture all cadastral parcels that intersect the pentagon

# # PEB
# peb_folder = '../../Data/PEB'
# file_peb_public = peb_folder + '/peb_public.feather'
# file_peb_res = peb_folder + '/peb_residential.feather'

# # Concatenate both public and residential PEB data (only take NRJ_IDX)
# gdf_peb = pd.concat([
#     process.load_gdf(file_peb_public, mask=mask_pentagon),
#     process.load_gdf(file_peb_res, mask=mask_pentagon)
# ], ignore_index=True)[['NRJ_IDX', 'geometry']]

# Group and aggregate data

gdf_cad = process.aggregate_cadastral_data(gdf_c, gdf_v)
gdf_build = process.aggregate_building_data(
    gdf_b, gdf_osm_buildings, gdf_sitex,
    gdf_h, gdf_i #, gdf_peb
)

gdf_build = process.determine_building_type(gdf_build)
gdf_build = process.estimate_thermal_characteristics(gdf_build)

gdf_build = process.infer_cadastral_data(gdf_build, gdf_cad, binary_cols=['LISTED_CAD', 'GEOTHERMAL_ACCESS', 'AQUATHERMAL_ACCESS', 'RIOTHERMAL_ACCESS', 'FATAL_HEAT_ACCESS'])

# A building is considered listed if it is either in the inventory or a heritage site.
gdf_build['LISTED'] = gdf_build['LISTED_CAD'] | gdf_build['HERITAGE']

# Remove unhabited buildings
# Minimum habitable floor area is 18 m² (https://be.brussels/fr/logement/nouvelles-normes-minimales-de-qualite-partir-de-2026)
mask_unhabited = (gdf_build.TYPE.isna()) | (gdf_build.FLOOR_AREA < 18)
gdf_build = gdf_build[~mask_unhabited]

gdf = process.group_urbis_footprint(gdf_cad, gdf_B, gdf_build, gdf_a)
gdf = gdf.set_geometry('geometry_building')

# Building scenarios

scenarios = { "low": 0.5, "middle": 1.0, "high": 1.5} # + 50 % / - 50 %
gdf_build_scenarios = []

for version, factor in scenarios.items():
    gdf = gdf_build.copy()
    mask = gdf.TYPE == 'Unknown'
    gdf.loc[mask, ['SPEC_SPACE_HEAT', 'SPEC_DHW']] *= factor
    gdf['VERSION_HEAT'] = version
    gdf_build_scenarios.append(gdf)

gdf_build = pd.concat(gdf_build_scenarios, ignore_index=True)

# Save dataframes in RES
gdf_build.to_feather('../Res/Buildings.feather')
gdf_cad.to_feather('../Res/Cadastral.feather')

# %%
