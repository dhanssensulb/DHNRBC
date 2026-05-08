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
file_macro = '../Data/BISA/StatisticalMacrozones.feather'
gdf_macro = load_gdf(file_macro)

# Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all() # Extend by 5m to include parcels that are just outside the boundary

mask_pentagone_extended = mask_pentagone.buffer(100) # Extend by 100m

#%% Layers - BrugIS / UrbIS

# Cadastral parcels
file_cadastral = '../Data/UrbIS/CadastralParcels.feather'
gdf_cadastral = load_gdf(file_cadastral, mask=mask_pentagone)

# Buildings
file_buildings = '../Data/UrbIS/Buildings.feather'
gdf_buildings = load_gdf(file_buildings, mask=mask_pentagone)

# Blocks
file_blocks = '../Data/UrbIS/Blocks.feather'
gdf_blocks = load_gdf(file_blocks, mask=mask_pentagone)

# Addresses
file_addresses = '../Data/UrbIS/Addresses.feather'
gdf_addresses = load_gdf(file_addresses, mask=mask_pentagone)

# Heritage
file_heritage = '../Data/BrugIS/Heritage.feather'
gdf_heritage = load_gdf(file_heritage, mask=mask_pentagone)

# Legal inventory
file_inventory = '../Data/BrugIS/Irismonument_legal_inventory.feather'
gdf_inventory = load_gdf(file_inventory, mask=mask_pentagone)

# Segments and nodes
file_axes = '../Data/UrbIS/StreetAxes.feather'
gdf_axes = load_gdf(file_axes, mask=mask_pentagone)

file_nodes = '../Data/UrbIS/StreetNodes.feather'
gdf_nodes = load_gdf(file_nodes, mask=mask_pentagone)

file_segments = '../Data/BrugIS/Public_space_Programmations_segments.feather'
gdf_segments = load_gdf(file_segments, mask=mask_pentagone) # ORG_TYPE (Noeud, Tronçon)

#%% Preprocessing

# Cadastral parcels
gdf_c = (
    gdf_cadastral
    .rename(columns={"CAPAKEY": "PARCEL_ID", "TYPE": "PARCEL_TYPE"})
    .drop(columns=['MUNNISCODE'])
    .reset_index(drop=True)
)

# Buildings
gdf_b = (
    gdf_buildings
    .assign(
        INSPIRE_ID=lambda df: df["INSPIRE_ID"].str.split("/").str[-1],
        BLOCK_ID=lambda df: df["BLOCK_ID"].str.split("/").str[-1]
    )
    .rename(columns={"INSPIRE_ID": "BUILDING_ID"})
    .reset_index(drop=True)
)

# Blocks
gdf_B = (
    gdf_blocks
    .assign(
        INSPIRE_ID=lambda df: df["INSPIRE_ID"].str.split("/").str[-1]
    )
    .rename(columns={"INSPIRE_ID": "BLOCK_ID", "TYPE": "BLOCK_TYPE"})
    .drop(columns=['NAMEFRE', 'LVL'])
    .reset_index(drop=True)
)

# Addresses
gdf_a = (
    gdf_addresses
    .assign(
        STREET_ID=lambda df: df['STREET_ID'].str.split("/").str[-1],
        BU_ID=lambda df: df['BU_ID'].str.split("/").str[-1],
        ADDRESS=lambda df: df['POLICENUM'] + ' ' + df['STRNAMEFRE'] + ', ' + df['ZIPCODE']
    )
    .rename(columns={'CAPAKEY': 'PARCEL_ID', 'BU_ID': 'BUILDING_ID'})
    .drop(columns=['XL72', 'YL72', 'STATNISCODE'])
    .reset_index(drop=True)
)
# Group by address and count unique box numbers
gdf_a = gdf_a.groupby('ADDRESS').agg(
    **{col: (col, 'first') for col in gdf_a.columns if col not in ['BOXNUMBER', 'ADDRESS']},
    BOXNUMBER_COUNT=('BOXNUMBER', 'nunique')
).reset_index()

gdf_a = gpd.GeoDataFrame(gdf_a, geometry="geometry", crs=gdf_addresses.crs)

# Inventory
gdf_i = (
    gdf_inventory
    .assign(
        ADDRESS=lambda df: df['NUMBER'] + ' ' + df['STREET_FR'] + ', ' + df['CITY']
    )
    .reset_index(drop=True)
)

# Heritage
mask_types = gdf_heritage['MS'].isin(['Monument', 'Ensemble'])
gdf_h = gdf_heritage[mask_types].copy()

# %% Processing

# Addresses to parcels
gdf_ac = gdf_a.merge(gdf_c, on='PARCEL_ID', how='left', suffixes=('_address', '_parcel'))
# Buildings to blocks
gdf_bb = gdf_b.merge(gdf_B, on='BLOCK_ID', how='left', suffixes=('_building', '_block'))

# Buildings to addresses and parcels
gdf_abc = gdf_bb.merge(gdf_ac, on='BUILDING_ID', how='left')

# Buildings statistics
df_bu_stats = gdf_abc.groupby('BUILDING_ID').agg(
    PARCEL_UNIQUE_COUNT=('PARCEL_ID', 'nunique'),
    ADDRESS_FIRST=('ADDRESS', 'first'),
    ADDRESS_UNIQUE_COUNT=('ADDRESS', 'nunique'),
    MAX_BOXNUMBER_COUNT=('BOXNUMBER_COUNT', 'max')    
)
gdf_abc = gdf_abc.merge(df_bu_stats, on='BUILDING_ID', how='left')

# %% Filtering

gdf = gdf_abc.copy()

# Area
gdf['BUILDING_AREA'] = gdf.set_geometry('geometry_building').area

# Inventory
inventory_geom = gdf_i.union_all()

gdf['INVENTORY'] = (
    gdf['ADDRESS'].isin(gdf_i['ADDRESS']) | # Is the address of gdf in gdf_i ?
    gdf.set_geometry('geometry_building').intersects(inventory_geom) # Is the building intersecting with a building in gdf_i ?
)

# If one address of the building is in the inventory, then the building is in the inventory
gdf['INVENTORY'] = gdf.groupby('BUILDING_ID')['INVENTORY'].transform('max')

# Heritage
heritage_geom = gdf_h.union_all()
intersection_heritage = gdf.set_geometry('geometry_building').intersection(heritage_geom)

gdf['HERITAGE'] = intersection_heritage.area / gdf.set_geometry('geometry_building').area >= 0.5

# %% Plotting

import matplotlib.patches as mpatches
import matplotlib.lines as mlines

fig, ax = plt.subplots(figsize=(12, 12))

# Parcel
gdf.set_geometry('geometry_parcel').groupby('PARCEL_ID').first().plot(ax=ax, color='lightgrey', edgecolor='none')

# Building
gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
gdf_b_plot.plot(
    # make choropleth map
    ax=ax, column='BUILDING_AREA', cmap=plt.cm.Reds, scheme='quantiles', k=5,
    edgecolor='none',
    legend=True, legend_kwds={'title': 'Building Area (m²)', 'fmt': '{:.0f}'},
    missing_kwds={'color': 'grey', 'label': 'Missing'}
)

legend1 = ax.get_legend()

# Blocks
gdf_B_plot = gdf_B.set_geometry('geometry').groupby('BLOCK_ID').first()
gdf_B_plot.plot(ax=ax, color='none', edgecolor='black', linewidth=0.5)

# Legend handles
parcel_handle = mpatches.Patch(facecolor='lightgrey', edgecolor='none', label='Parcels')
block_handle = mlines.Line2D([], [], color='black', linewidth=1, label='Blocks')

legend2 = ax.legend(handles=[parcel_handle, block_handle], title='Map Layers', loc='upper left'
)

ax.add_artist(legend1)
ax.add_artist(legend2)

plt.axis('off')
plt.show()
# %%

fig, ax = plt.subplots(figsize=(12, 12))

# Parcel
gdf.set_geometry('geometry_parcel').groupby('PARCEL_ID').first().plot(ax=ax, color='lightgrey', edgecolor='none')

# Building
gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
# Plot in green if not in inventory, red if in inventory
color_inventory = gdf_b_plot['INVENTORY'].map({True: 'lightcoral', False: 'steelblue'})

gdf_b_plot.plot(
    ax=ax, color=color_inventory,
    edgecolor='none'
)

legend_handle = [
    mpatches.Patch(color='lightcoral', label='True'),
    mpatches.Patch(color='steelblue', label='False')
]

legend1 = ax.legend(handles=legend_handle, title='Inventory', loc='upper right')

# Blocks
gdf_B_plot = gdf_B.set_geometry('geometry').groupby('BLOCK_ID').first()
gdf_B_plot.plot(ax=ax, color='none', edgecolor='black', linewidth=0.5)

# Legend handles
parcel_handle = mpatches.Patch(facecolor='lightgrey', edgecolor='none', label='Parcels')
block_handle = mlines.Line2D([], [], color='black', linewidth=1, label='Blocks')

legend2 = ax.legend(handles=[parcel_handle, block_handle], title='Map Layers', loc='upper left'
)

ax.add_artist(legend1)
ax.add_artist(legend2)

plt.axis('off')
plt.show()

# %%
fig, ax = plt.subplots(figsize=(12, 12))

# Parcel
gdf.set_geometry('geometry_parcel').groupby('PARCEL_ID').first().plot(ax=ax, color='lightgrey', edgecolor='none')

# Building
gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
# Plot in green if not in inventory, red if in inventory
color_inventory = gdf_b_plot['HERITAGE'].map({True: 'lightcoral', False: 'steelblue'})

gdf_b_plot.plot(
    ax=ax, color=color_inventory,
    edgecolor='none'
)

legend_handle = [
    mpatches.Patch(color='lightcoral', label='True'),
    mpatches.Patch(color='steelblue', label='False')
]

legend1 = ax.legend(handles=legend_handle, title='Heritage', loc='upper right')

# Blocks
gdf_B_plot = gdf_B.set_geometry('geometry').groupby('BLOCK_ID').first()
gdf_B_plot.plot(ax=ax, color='none', edgecolor='black', linewidth=0.5)

# Legend handles
parcel_handle = mpatches.Patch(facecolor='lightgrey', edgecolor='none', label='Parcels')
block_handle = mlines.Line2D([], [], color='black', linewidth=1, label='Blocks')

legend2 = ax.legend(handles=[parcel_handle, block_handle], title='Map Layers', loc='upper left'
)

ax.add_artist(legend1)
ax.add_artist(legend2)

plt.axis('off')
plt.show()


# %%

# share of buildings in inventory
gdf['INVENTORY'].mean()

# share of areas of buildings in inventory
gdf['INVENTORY_AREA'] = gdf['INVENTORY'] * gdf['BUILDING_AREA']
gdf['INVENTORY_AREA'].sum() / gdf['BUILDING_AREA'].sum()
# %%

# share of buildings in inventory
gdf['HERITAGE'].mean()

# # share of areas of buildings in inventory
# gdf['HERITAGE_AREA'] = gdf['HERITAGE'] * gdf['BUILDING_AREA']
# gdf['HERITAGE_AREA'].sum() / gdf['BUILDING_AREA'].sum()

# %%
