# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%% Libraries and config
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rc('text', usetex=True) # Use LaTeX for rendering text
plt.rc('font', family='sans-serif')

#%% Layers - UrbIS
import geopandas as gpd

file_monitoring = '../Data/UrbIS/MonitoringDistricts.feather'
gdf_monitoring = gpd.read_feather(file_monitoring)

file_cadastral = '../Data/UrbIS/CadastralParcels.feather'
gdf_cadastral = gpd.read_feather(file_cadastral)

# Mask Pentagone

pentagone = range(1, 11)
gdf_pentagone = gdf_monitoring[gdf_monitoring['MDZONE'].isin(pentagone)]
mask_geometry = gdf_pentagone.union_all()

gdf_cadastral = gdf_cadastral[gdf_cadastral.within(mask_geometry)]

# %% Graph
import osmnx as ox
import contextily as ctx

polygon = gdf_pentagone.to_crs(epsg=4326).union_all()

# Road network
G_drive = ox.graph_from_polygon(polygon, network_type='drive', simplify=True)
edges_drive = ox.graph_to_gdfs(G_drive, nodes=False, edges=True)

# %% Plot
fig, ax = plt.subplots(figsize=(20, 20))

gdf_cadastral.plot(ax=ax, color='lightblue', edgecolor='blue', alpha=0.8, linewidth=0.5)
edges_drive.to_crs(gdf_cadastral.crs).plot(ax=ax, color='k', linewidth=2)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, crs=gdf_cadastral.crs, alpha=0.8)

ax.set_axis_off()

figure_name = 'UrbIS_Pentagone'
plt.savefig(f'Figures/{figure_name}.png', dpi=300, bbox_inches='tight')

plt.show()

# %%
