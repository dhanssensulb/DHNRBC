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

# %%
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(20,20))
gdf_buildings.plot(ax=ax, color='lightgrey', edgecolor='black')
gdf_edges.plot(ax=ax, color='red')
plt.show()



# %%
import geopandas as gpd
from shapely.ops import polygonize, nearest_points
from tqdm import tqdm
from shapely.geometry import LineString

buildings = gdf_buildings[:100].copy()
edges = gdf_edges.copy()
nodes = gdf_nodes.copy()

def build_blocks(edges):
    # Street blocks (faces of the network)
    blocks = gpd.GeoDataFrame(
        geometry=list(polygonize(edges.geometry.union_all())),
        crs=edges.crs
    )
    return blocks

def valid_connection(line, building, target_edge):
    
    # If the line intersects any other building, it's not a valid connection
    touching_buildings = buildings[buildings.geometry.intersects(line)]
    touching_buildings = touching_buildings[touching_buildings.geometry != building] # Exclude the building itself
    if len(touching_buildings) > 0:
        return False

    # If the line intersects any other edge, it's not a valid connection
    touching_edges = edges[edges.geometry.intersects(line)]
    touching_edges = touching_edges[touching_edges.geometry != target_edge] # Exclude the target edge
    if len(touching_edges) > 0:
        return False

    # If the line touches any node, it's not a valid connection
    touching_nodes = nodes[nodes.geometry.touches(line)]
    if len(touching_nodes) > 0:
        return False

    return True

blocks = build_blocks(edges)
connections = []
connected_map = {} # To track which buildings are already connected

# For each building, find the nearest edge and create a connection line
for b_idx, b in tqdm(buildings.iterrows(), total=len(buildings)):
    b_geom = b.geometry
    block = blocks[blocks.contains(b_geom)] # Should be only one block

    if block.empty:
        # fallback: nearest edge
        e_idx = edges.distance(b_geom).idxmin()
        e_geom = edges.loc[e_idx].geometry
        p1, p2 = nearest_points(b_geom, e_geom)
        line = LineString([p1, p2])
        conn = {'B_ID': b_idx, 'E_ID': e_idx, 'geometry': line}
        connections.append(conn)
        connected_map[int(b_idx)] = conn
        continue

    block_geom = block.iloc[0].geometry # Get the block geometry
    candidate_edges = edges[edges.intersects(block_geom)]

    for e_idx, e in candidate_edges.iterrows():
        e_geom = e.geometry
        p1, p2 = nearest_points(b_geom, e_geom)
        line = LineString([p1, p2])
        if valid_connection(line, b_geom, e_geom):
            conn = {'B_ID': b_idx, 'E_ID': e_idx, 'geometry': line}
            connections.append(conn)
            connected_map[int(b_idx)] = conn

# For buildings with empty connections, copy the connections of the nearest connected building
for b_idx, b in buildings.iterrows():
    if int(b_idx) not in connected_map:
        nearest_connected_idx = buildings.distance(b.geometry).sort_values()
        while nearest_connected_idx.empty is False:
            nearest_idx = nearest_connected_idx.index[0]
            if int(nearest_idx) in connected_map:
                connections.append(connected_map[int(nearest_idx)])
                break
            else:
                nearest_connected_idx = nearest_connected_idx.iloc[1:]

gdf_connections = gpd.GeoDataFrame(connections, geometry='geometry', crs=buildings.crs)

fig, ax = plt.subplots(figsize=(20,20))
buildings.plot(ax=ax, color='lightgrey', edgecolor='black')
edges.plot(ax=ax, color='red')
gdf_connections.plot(ax=ax, color='blue', linewidth=1)
# zoom on the buildings boundaries (axes limit)
minx, miny, maxx, maxy = buildings.total_bounds
pad = 100
ax.set_xlim(minx - pad, maxx + pad)
ax.set_ylim(miny - pad, maxy + pad)
plt.show()

#%%

# def connect_buildings_to_streets(gdf_buildings, gdf_edges, gdf_nodes):
#     """
#     Connect buildings to the nearest street segments.
#     """
#     buildings = gdf_buildings.copy()
#     edges = gdf_edges.copy()
#     nodes = gdf_nodes.copy()

#     def build_blocks(edges):
#         # Street blocks (faces of the network)
#         blocks = gpd.GeoDataFrame(
#             geometry=list(polygonize(edges.geometry.union_all())),
#             crs=edges.crs
#         )
#         return blocks
    
#     def valid_connection(line, target_edge):
#         flag = True

#         # If the line does not cross the target edge, it's not a valid connection
#         if line.crosses(target_edge) is False:
#             flag = False
        
#         # If the line intersects any building, it's not a valid connection
#         touching_buildings = buildings.geometry.intersects(line)
#         if len(touching_buildings) > 0:
#             flag = False

#         # If the line intersects any other edge, it's not a valid connection
#         touching_edges = edges.geometry.intersects(line)
#         if len(touching_edges) > 0:
#             flag = False

#         # If the line intersects any node, it's not a valid connection
#         touching_nodes = nodes.geometry.intersects(line)
#         if len(touching_nodes) > 0:
#             flag = False

#         return flag

#     blocks = build_blocks(edges)
#     connections = []
#     connected_map = {} # To track which buildings are already connected

#     # For each building, find the nearest edge and create a connection line
#     for b_idx, b in tqdm(buildings.iterrows(), total=len(buildings)):
#         b_geom = b.geometry
#         block = blocks[blocks.contains(b_geom)] # Should be only one block

#         if block.empty:
#             # fallback: nearest edge
#             e_idx = edges.distance(b_geom).idxmin()
#             e_geom = edges.loc[e_idx].geometry
#             p1, p2 = nearest_points(b_geom, e_geom)
#             line = LineString([p1, p2])
#             conn = {'B_ID': b_idx, 'E_ID': e_idx, 'geometry': line}
#             connections.append(conn)
#             connected_map[int(b_idx)] = conn
#             continue

#         block_geom = block.iloc[0].geometry # Get the block geometry
#         candidate_edges = edges[edges.intersects(block_geom)]

#         for e_idx, e in candidate_edges.iterrows():
#             e_geom = e.geometry
#             p1, p2 = nearest_points(b_geom, e_geom)
#             line = LineString([p1, p2])
#             if valid_connection(line, e_geom):
#                 conn = {'B_ID': b_idx, 'E_ID': e_idx, 'geometry': line}
#                 connections.append(conn)
#                 connected_map[int(b_idx)] = conn

#     # For buildings with empty connections, copy the connections of the nearest connected building
#     for b_idx, b in buildings.iterrows():
#         if int(b_idx) not in connected_map:
#             nearest_connected_idx = buildings.distance(b.geometry).sort_values()
#             while nearest_connected_idx.empty is False:
#                 nearest_idx = nearest_connected_idx.index[0]
#                 if int(nearest_idx) in connected_map:
#                     connections.append(connected_map[int(nearest_idx)])
#                     break
#                 else:
#                     nearest_connected_idx = nearest_connected_idx.iloc[1:]

#     # Create a GeoDataFrame for the connections
#     # gdf_connections = gpd.GeoDataFrame(connections, geometry='geometry', crs=buildings.crs)
    
#     return connections

# gdf_connections = connect_buildings_to_streets(gdf_buildings[:100], gdf_edges, gdf_nodes)

# %%
