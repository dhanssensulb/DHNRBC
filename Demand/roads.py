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

def load_gdf(file, mask=None, min_overlap_ratio=0.5):
    gdf = gpd.read_feather(file) if file.endswith('.feather') else gpd.read_file(file)
    if mask:
        geom_type = gdf.geometry.geom_type.unique()
        if geom_type[0] in ['Polygon', 'MultiPolygon']:
            gdf = gdf.loc[lambda df: df.intersection(mask).area / df.area > min_overlap_ratio]
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
mask_pentagone = gdf_pentagone.union_all()

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
gdf_segments = load_gdf(file_segments, mask=mask_pentagone, min_overlap_ratio=0) # ORG_TYPE (Noeud, Tronçon)

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


#%%

from shapely.ops import snap
import networkx as nx
import momepy
import neatnet

# MULTILINESTRING -> LINESTRING
gdf_axes_clean = gdf_axes.explode(index_parts=False).copy()

# Snap nearby vertices together
axes_union = gdf_axes_clean.geometry.union_all()
gdf_axes_clean['geometry'] = gdf_axes_clean.geometry.apply(lambda geom: snap(geom, axes_union, 1))
axes_union_snapped = gdf_axes_clean.geometry.union_all()
gdf_axes_clean = gpd.GeoDataFrame(geometry=[axes_union_snapped], crs=gdf_axes.crs).explode(index_parts=False)

# Keep only the largest connected component
G = momepy.gdf_to_nx(gdf_axes_clean)

# Back to GeoDataFrames
gdf_nodes_clean, gdf_axes_clean = momepy.nx_to_gdf(G)

# group gdf by building with the geometry building and the crs
mask_builds = gdf.set_geometry('geometry_building').dissolve(by='BUILDING_ID').geometry

# Simplify the single graph
gdf_axes_simplified = neatnet.neatify(
    gdf_axes_clean,
    exclusion_mask=mask_builds, 
    # artifact_threshold=12,
)

G = momepy.gdf_to_nx(gdf_axes_simplified)
gdf_nodes_simplified, gdf_axes_simplified = momepy.nx_to_gdf(G)

fig, ax = plt.subplots(figsize=(18, 18))

gdf_axes.plot(ax=ax, color='r', alpha=0.5)
gdf_nodes_simplified.plot(ax=ax, color='b', markersize=5)

gdf.set_geometry('geometry_building').dissolve(by='BUILDING_ID').plot(ax=ax, color='b', alpha=0.1)

gdf_axes_simplified.plot(ax=ax, color='k')

plt.axis('off')
plt.show()

#%%

from shapely.ops import polygonize, nearest_points
from shapely.geometry import LineString
import geopandas as gpd
from tqdm import tqdm

def connect_buildings_to_streets(gdf_axes, gdf_buildings):
    streets = gdf_axes.reset_index(drop=True).copy()
    buildings = gdf_buildings.reset_index(drop=True).copy()

    # Build street blocks (faces of the network)
    blocks = gpd.GeoDataFrame(
        geometry=list(polygonize(streets.geometry.union_all())),
        crs=gdf_axes.crs
    )

    # Build all spatial indices upfront
    buildings_sindex = buildings.sindex
    blocks_sindex = blocks.sindex
    streets_sindex = streets.sindex

    connections = []

    for bld_idx, bld in tqdm(buildings.iterrows(), total=len(buildings)):
        bld_geom = bld.geometry

        # Find the smallest enclosing block around the building, using sindex
        candidate_idx = list(blocks_sindex.intersection(bld_geom.bounds)) # should be only one, but we have several of them
        candidate_blocks  = blocks.iloc[containing_block_idx]
        print(len(containing_block))
        if containing_block.empty:  
            continue 

        enclosing_block = containing_block.loc[containing_block.area.idxmin()].geometry  

        # Find streets that form the boundary of this block
        boundary_streets_idx = list(streets_sindex.intersection(enclosing_block.bounds))
        boundary_streets = streets.iloc[boundary_streets_idx]

        # Remove streets that are not linestrings
        boundary_streets = boundary_streets[boundary_streets.geometry.geom_type.isin(['LineString', 'MultiLineString'])]

        for ax_idx, ax_row in boundary_streets.iterrows():
            nearest_on_building, nearest_on_street = nearest_points(bld_geom, ax_row.geometry)
            connection = LineString([nearest_on_building, nearest_on_street])

            candidates = buildings.iloc[list(buildings_sindex.intersection(connection.bounds))]
            if candidates.drop(index=bld_idx, errors='ignore').intersects(connection).any():
                continue

            connections.append({
                'street_idx': ax_idx,
                'building_idx': bld_idx,
                'connection_length': connection.length,
                'geometry': connection
            })

    return gpd.GeoDataFrame(connections, geometry='geometry', crs=gdf_axes.crs)


gdf_connections = connect_buildings_to_streets(gdf_axes_simplified, gdf_b)

# print buildings that doesn't appear in gdf_connections
connected_buildings = gdf_b.loc[gdf_connections['building_idx'].unique()]
unconnected_buildings = gdf_b.loc[~gdf_b.index.isin(gdf_connections['building_idx'].unique())]

#%%

fig, ax = plt.subplots(figsize=(30, 30))

# Buildings
gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
# plot in blue buildings that are connected, and in red buildings that are not connected
connected_buildings.plot(ax=ax, color='blue', alpha=0.3)
unconnected_buildings.plot(ax=ax, color='red', alpha=0.3)

# Connections - with lines in tab10 and extremities in blue
gdf_connections.plot(ax=ax, cmap='tab10', linewidth=1, alpha=1)

# Network
gdf_axes_simplified.plot(ax=ax, color='k')
gdf_nodes_simplified.plot(ax=ax, color='r', markersize=5)


plt.axis('off')
plt.show()


# %%

fig, ax = plt.subplots(figsize=(25, 25))

gdf_B_plot = gdf.set_geometry('geometry_block').groupby('BLOCK_ID').first()
gdf_B_plot.plot(ax=ax, column='BLOCK_TYPE', alpha=0.3)

gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
gdf_b_plot.plot(ax=ax, alpha=0.3)

gdf_pentagone.plot(ax=ax, color='none', edgecolor='black', linewidth=2)

gdf_axes.plot(ax=ax, color='k', alpha=0.5)

plt.axis('off')
plt.show()

#%%

fig, ax = plt.subplots(figsize=(15, 15))

# # Buildings
# gdf_b_plot = gdf.set_geometry('geometry_building').groupby('BUILDING_ID').first()
# gdf_b_plot.plot(ax=ax, alpha=0.3)

# Network
gdf_axes.plot(ax=ax, column='TYPE', cmap='tab20', legend=True, alpha=0.5)
gdf_nodes.plot(ax=ax, color='r', markersize=5)

# # Connections
# gdf_connections.plot(ax=ax, color='blue', linewidth=2, alpha=0.5)

plt.axis('off')
plt.show()


# %%
