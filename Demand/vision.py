# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Libraries and config
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rc('text', usetex=True) # Use LaTeX for rendering text
plt.rc('font', family='sans-serif')

#%% Layers - BISA
import geopandas as gpd

# Macrozones
file_macro = '../Data/BISA/StatisticalMacrozones.feather'
gdf_macro = gpd.read_feather(file_macro)

# Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

mask_pentagone_extended = mask_pentagone.buffer(100) # Extend by 100m

# %% Layers - Vision
import geopandas as gpd

file_common_background = '../Data/Vision_Zonee/00.CouchesCommunes/Parcelles_Bxl_Mu.shp'
gdf_common_background = gpd.read_file(file_common_background).loc[
    lambda df: df.within(mask_pentagone)
]

# %%

file_aquathermie = '../Data/Vision_Zonee/01.CriteresAccessibilite/AccesAquathermie_Mu.shp'
gdf_aquathermie = gpd.read_file(file_aquathermie).loc[
    lambda df: df.within(mask_pentagone)
]
file_canal = '../Data/Vision_Zonee/01.CriteresAccessibilite/Canal_200m_split.shp'
gdf_canal = gpd.read_file(file_canal).loc[
    lambda df: df.within(mask_pentagone_extended)
]

file_geothermal = '../Data/Vision_Zonee/01.CriteresAccessibilite/AccesGeothermie_Mu.shp'
gdf_geothermal = gpd.read_file(file_geothermal).loc[
    lambda df: df.within(mask_pentagone)
]

file_riothermie = '../Data/Vision_Zonee/01.CriteresAccessibilite/AccesRiothermie_Mu.shp'
gdf_riothermie = gpd.read_file(file_riothermie).loc[
    lambda df: df.within(mask_pentagone)
]
file_riothermie_layout = '../Data/Vision_Zonee/01.CriteresAccessibilite/riothermie.shp'
gdf_riothermie_layout = gpd.read_file(file_riothermie_layout).loc[
    lambda df: df.within(mask_pentagone)
]

file_transport = '../Data/Vision_Zonee/01.CriteresAccessibilite/specialisation_tp.shp'
gdf_transport = gpd.read_file(file_transport).loc[
    lambda df: df.within(mask_pentagone_extended)
]

file_fatal_heat = '../Data/Vision_Zonee/01.CriteresAccessibilite/AccesChaleurFatalePtesSources_PasdAcces_Mu.shp'
gdf_fatal_heat = gpd.read_file(file_fatal_heat).loc[
    lambda df: df.within(mask_pentagone)
]

# %%

file_zonal_view = '../Data/Vision_Zonee/06.VisionZonee/VisionZonee.shp'
gdf_zonal_view = gpd.read_file(file_zonal_view).loc[
    lambda df: df.within(mask_pentagone)
]

file_block = '../Data/Vision_Zonee/06.VisionZonee/UrbisVector-Blocks.shp'
gdf_block = gpd.read_file(file_block).loc[
    lambda df: df.within(mask_pentagone)
]

file_geothermal_source = '../Data/Vision_Zonee/09.SourceGeothermie/BuidlingBlocs_Ilots_RBC_SansBati.shp'
gdf_geothermal_source = gpd.read_file(file_geothermal_source).loc[
    lambda df: df.within(mask_pentagone)
]

# %%

# plot ConsoChKWh from gdf_common_background
fig, ax = plt.subplots(figsize=(7, 7))
gdf_common_background.plot(column='ConsoChKWh', ax=ax, cmap='OrRd', edgecolor='grey', linewidth=0.5, legend=True)
ax.set_axis_off()
# %%
