# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Helpers

import pandas as pd
import geopandas as gpd
from shapely.validation import make_valid
from shapely.ops import snap, unary_union, polygonize, nearest_points
from shapely.geometry import LineString
from tqdm import tqdm
import momepy
import neatnet
import networkx as nx

def load_gdf(file, layer=None, mask=None, min_overlap_ratio=0.5):
    """
    Load a GeoDataFrame from a file, optionally applying a spatial mask.
    A polygon belongs to the masked GeoDataFrame if at least `min_overlap_ratio` of its area overlaps with the mask.
    For non-polygon geometries, they are included if they are within the mask.
    """
    if file.endswith('.feather'):
        gdf = gpd.read_feather(file)
    else:
        gdf = gpd.read_file(file, layer=layer) if layer else gpd.read_file(file)
    
    # Removes null geometries and repairs invalid geometries
    gdf = gdf.dropna(subset=['geometry']).reset_index(drop=True)
    gdf.geometry = gdf.geometry.apply(make_valid)

    if mask:
        geom_type = gdf.geometry.geom_type.unique()
        if geom_type[0] in ['Polygon', 'MultiPolygon']:
            gdf = gdf.loc[lambda df: df.intersection(mask).area / df.area >= min_overlap_ratio]
        else:
            gdf = gdf.loc[lambda df: df.within(mask)]

    return gdf

def load_urbis_footprint(urbis_folder, mask=None):
    """
    Clean and harmonise the UrbIS GeoDataFrames.
    """
    # Cadastral parcels
    file_cadastral = urbis_folder + '/CadastralParcels.feather'
    gdf_cadastral = load_gdf(file_cadastral, mask=mask)
    gdf_c = (
        gdf_cadastral
        .rename(columns={"CAPAKEY": "PARCEL_ID", "TYPE": "PARCEL_TYPE"})
        .drop(columns=['MUNNISCODE'])
        .reset_index(drop=True)
    )
    # Blocks
    file_blocks = urbis_folder + '/Blocks.feather'
    gdf_blocks = load_gdf(file_blocks, mask=mask)
    gdf_B = (
        gdf_blocks
        .assign(
            INSPIRE_ID=lambda df: df["INSPIRE_ID"].str.split("/").str[-1]
        )
        .rename(columns={"INSPIRE_ID": "BLOCK_ID", "TYPE": "BLOCK_TYPE"})
        .drop(columns=['NAMEFRE', 'LVL'])
        .reset_index(drop=True)
    )
    # Buildings
    file_buildings = urbis_folder + '/Buildings.feather'
    gdf_buildings = load_gdf(file_buildings, mask=mask)
    gdf_b = (
        gdf_buildings
        .assign(
            INSPIRE_ID=lambda df: df["INSPIRE_ID"].str.split("/").str[-1],
            BLOCK_ID=lambda df: df["BLOCK_ID"].str.split("/").str[-1]
        )
        .rename(columns={"INSPIRE_ID": "BUILDING_ID"})
        .reset_index(drop=True)
    )
    # Addresses
    file_addresses = urbis_folder + '/Addresses.feather'
    gdf_addresses = load_gdf(file_addresses, mask=mask)
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

    return gdf_c, gdf_B, gdf_b, gdf_a

def load_sitex_data(file_sitex, mask=None):
    """
    Load and clean SitEx data, optionally applying a spatial mask.
    """
    gdf_s1 = load_gdf(file_sitex, layer='density_building', mask=mask)
    gdf_s2 = load_gdf(file_sitex, layer='bureau', mask=mask)
    gdf_s3 = load_gdf(file_sitex, layer='oap', mask=mask)

    gdf_s1['type'] = 'building'
    gdf_s1.loc[gdf_s1['id'].isin(gdf_s2['id']), 'type'] = 'office'
    gdf_s1.loc[gdf_s1['id'].isin(gdf_s3['id']), 'type'] = 'public'

    return gdf_s1

def load_brugis_heritage(brugis_folder, mask=None):
    """
    Clean and harmonise the BruGIS heritage GeoDataFrames.
    """
    # Heritage sites
    file_heritage = brugis_folder + '/Heritage.feather'
    gdf_heritage = load_gdf(file_heritage, mask=mask)
    mask_types = gdf_heritage['MS'].isin(['Monument', 'Ensemble'])
    gdf_h = gdf_heritage[mask_types]

    # Inventory
    file_inventory = brugis_folder + '/Irismonument_legal_inventory.feather'
    gdf_inventory = load_gdf(file_inventory, mask=mask)
    gdf_i = (
        gdf_inventory
        .assign(
            ADDRESS=lambda df: df['NUMBER'] + ' ' + df['STREET_FR'] + ', ' + df['CITY']
        )
        .reset_index(drop=True)
    )

    return gdf_h, gdf_i

def load_zonal_data(vision_folder, mask=None):
    """
    Clean and harmonise the Zonal vision GeoDataFrames.
    """
    file_common_background = vision_folder + '/00.CouchesCommunes/Parcelles_Bxl_Mu.shp'
    cols_to_keep = ['ID_Int', 'PotGeoKWh', 'BatClasses']
    gdf_common_background = load_gdf(file_common_background, mask=mask)[cols_to_keep + ['geometry']]

    # Set Lambert 72 CRS
    gdf_common_background = gdf_common_background.set_crs("EPSG:31370")
    # Fill NaN values in BatClasses
    gdf_common_background['BatClasses'] = gdf_common_background['BatClasses'].fillna(0)

    file_geothermal = vision_folder + '/01.CriteresAccessibilite/AccesGeothermie_Mu.shp'
    gdf_geothermal = load_gdf(file_geothermal, mask=mask)

    mask_geo_sup = gdf_geothermal['AccGeoSup'] == 1 # Heated Surface < 2x Unbuilt Surface
    gdf_geothermal = gdf_geothermal[mask_geo_sup]

    gdf_common_background['GEOTHERMAL_ACCESS'] = gdf_common_background['ID_Int'].isin(gdf_geothermal['ID_Int']).astype(int)

    file_aquathermal = vision_folder + '/01.CriteresAccessibilite/AccesAquathermie_Mu.shp'
    gdf_aquathermal = load_gdf(file_aquathermal, mask=mask)
    gdf_common_background['AQUATHERMAL_ACCESS'] = gdf_common_background['ID_Int'].isin(gdf_aquathermal['ID_Int']).astype(int)

    file_riothermal = vision_folder + '/01.CriteresAccessibilite/AccesRiothermie_Mu.shp'
    gdf_riothermal = load_gdf(file_riothermal, mask=mask)
    gdf_common_background['RIOTHERMAL_ACCESS'] = gdf_common_background['ID_Int'].isin(gdf_riothermal['ID_Int']).astype(int)

    file_fatal_heat = vision_folder + '/01.CriteresAccessibilite/AccesChaleurFatalePtesSources_PasdAcces_Mu.shp'
    gdf_fatal_heat = load_gdf(file_fatal_heat, mask=mask)

    mask_fatal_heat = gdf_fatal_heat['AccChFat50'] == 1 # < 50m from the fatal heat source
    gdf_fatal_heat = gdf_fatal_heat[mask_fatal_heat]

    gdf_common_background['FATAL_HEAT_ACCESS'] = gdf_common_background['ID_Int'].isin(gdf_fatal_heat['ID_Int']).astype(int)

    # Clean Up
    gdf_common_background = gdf_common_background.rename(columns={'BatClasses': 'LISTED', 'PotGeoKWh': 'POTENTIAL_KWH'})

    return gdf_common_background

def best_overlap_match(gdf, gdf_target, id_col, target_cols, threshold):
    """
    Returns the best overlapping target attributes for each geometry in gdf based on the specified threshold.
    """
    # Compute the area of each geometry in gdf
    gdf_source = gdf.copy()
    gdf_source['area'] = gdf_source.geometry.area

    # Compute the intersection between gdf_source and gdf_target
    inter = gpd.overlay(gdf_source, gdf_target[target_cols + ['geometry']], how='intersection', keep_geom_type=True)

    # Compute the area of the intersection and the area of the original geometries
    inter['overlap_area'] = inter.geometry.area
    inter['overlap_ratio'] = inter['overlap_area'] / inter['area']

    # Keep only significant overlaps
    inter = inter[inter["overlap_ratio"] >= threshold]

    # Keep best match per geometry
    best_match = inter.sort_values('overlap_area', ascending=False).groupby(id_col).first()[target_cols]

    return best_match

def aggregate_cadastral_data(gdf_c, gdf_v, association_threshold=0.5):
    """
    Aggregate cadastral data from UrbIS and Zonal vision based on spatial overlap.
    """

    # Find the best overlapping vision data for each cadastral parcel
    best_vision = best_overlap_match(gdf_c, gdf_v, id_col='PARCEL_ID', target_cols=list(gdf_v.columns.drop(['ID_Int', 'geometry'])), threshold=association_threshold)

    # Merge the best associations back to the original cadastral GeoDataFrame
    result = gdf_c.merge(best_vision, on='PARCEL_ID', how='left')

    # Clean up
    result = result.fillna(0)

    return result

def aggregate_building_data(gdf_b, gdf_osm, gdf_sitex, gdf_h, gdf_i, association_threshold=0.5):
    """
    Aggregate building data from UrbIS and OSM based on spatial overlap.
    A building from UrbIS is associated with a building from OSM if the overlap area is at least `association_threshold` of the UrbIS building area.
    """

    # Find the best overlapping OSM building and SitEx type for each UrbIS building
    best_osm = best_overlap_match(gdf_b, gdf_osm, id_col='BUILDING_ID', target_cols=['building'], threshold=association_threshold)
    best_sitex = best_overlap_match(gdf_b, gdf_sitex, id_col='BUILDING_ID', target_cols=['level_all', 'sp', 'type'], threshold=association_threshold)
    best_heritage = best_overlap_match(gdf_b, gdf_h, id_col='BUILDING_ID', target_cols=['MS'], threshold=association_threshold)

    # Merge the best associations back to the original UrbIS building GeoDataFrame
    result = gdf_b.merge(best_osm, on='BUILDING_ID', how='left')
    result = result.merge(best_sitex, on='BUILDING_ID', how='left')

    result = result.merge(best_heritage, on='BUILDING_ID', how='left')

    result['INVENTORY'] = result['BUILDING_ID'].isin(
        result.sjoin(gdf_i, how='inner', predicate='intersects')['BUILDING_ID']
    ).astype(int)

    result['HERITAGE'] = result['MS'].notna().astype(int)
    result = result.drop(columns=['MS'])

    # Clean up
    result = result.rename(columns={'building': 'osm_type', 'type': 'sitex_type', 'level_all': 'MAX_LEVEL', 'sp': 'FLOOR_AREA'})
    result['FLOOR_AREA'] = result['FLOOR_AREA'].fillna(result.geometry.area)
    result = result.fillna({'osm_type': 'yes', 'sitex_type' : 'building', 'INVENTORY': 0, 'HERITAGE': 0})

    return result

def determine_building_type(gdf_build):
    """
    Determine the building type for each building based on the OSM type and SitEx type, using the type_matching.csv file.
    """
    # Load the type matching dictionary
    type_matching = pd.read_csv('type_matching.csv')

    # Map the OSM and SitEx types to the building types
    gdf_build['TYPE'] = gdf_build['sitex_type'].map(type_matching.set_index('TAG')['TYPE'])

    # For Unknown values, use the OSM type
    gdf_build.loc[gdf_build['TYPE'] == 'Unknown', 'TYPE'] = gdf_build.loc[gdf_build['TYPE'] == 'Unknown', 'osm_type'].map(type_matching.set_index('TAG')['TYPE'])

    # Clean up
    gdf_build = gdf_build.drop(columns=['osm_type', 'sitex_type'])

    return gdf_build

def estimate_thermal_characteristics(gdf_build):
    """
    Estimate the thermal characteristics of each building based on its type.
    """
    # Load the thermal characteristics dictionary
    thermal_characteristics = pd.read_csv('thermal_characteristics.csv')

    # Map the building types to the thermal characteristics
    gdf_build = gdf_build.merge(thermal_characteristics, on='TYPE', how='left')

    return gdf_build

def infer_cadastral_data(gdf_b, gdf_c, binary_cols):
    """
    Infer cadastral data for buildings based on the cadastral parcels they intersect with.
    """
    # Compute the area of each building geometry
    gdf_b['AREA'] = gdf_b.geometry.area

    # Compute the intersection between buildings and cadastral parcels
    inter = gpd.overlay(gdf_b, gdf_c, how='intersection')

    inter['overlap_area'] = inter.geometry.area
    inter['overlap_ratio'] = inter['overlap_area'] / inter['AREA']

    # Compute the weighted average of the cadastral attributes for each building
    weighted = inter[binary_cols].multiply(inter['overlap_ratio'], axis=0)
    # Group by building and sum the weighted attributes
    inter_builds = weighted.groupby(inter['BUILDING_ID']).sum()
    # Threshold the binary attributes
    inter_builds[binary_cols] = (inter_builds[binary_cols] > 0.5).astype(int)

    gdf_b = gdf_b.merge(inter_builds[binary_cols], on='BUILDING_ID', how='left')

    # Clean up
    gdf_b[binary_cols] = gdf_b[binary_cols].fillna(0).astype(int)
    gdf_b = gdf_b.drop(columns=['AREA'])

    return gdf_b

def group_urbis_footprint(gdf_c, gdf_B, gdf_b, gdf_a):
    """
    Group the UrbIS footprint GeoDataFrames and compute building statistics.
    """
    # Group addresses and parcels geometries
    gdf_ac = gdf_a.merge(gdf_c, on='PARCEL_ID', how='left', suffixes=('_address', '_parcel'))
    # Group buildings and blocks geometries
    gdf_bb = gdf_b.merge(gdf_B, on='BLOCK_ID', how='left', suffixes=('_building', '_block'))

    # Group buildings, blocks, addresses and parcels geometries
    gdf_abc = gdf_bb.merge(gdf_ac, on='BUILDING_ID', how='left')

    # Compute buildings statistics
    gdf_buildings_stats = gdf_abc.groupby('BUILDING_ID').agg(
        PARCEL_UNIQUE_COUNT=('PARCEL_ID', 'nunique'), # Number of unique parcels associated with the building
        ADDRESS_FIRST=('ADDRESS', 'first'), # First address associated with the building
        ADDRESS_UNIQUE_COUNT=('ADDRESS', 'nunique'), # Number of unique addresses associated with the building
        MAX_BOXNUMBER_COUNT=('BOXNUMBER_COUNT', 'max'), # Maximum number of box numbers among the addresses associated with the building
    )
    
    # Merge the building statistics back to the building GeoDataFrame
    gdf = gdf_abc.merge(gdf_buildings_stats, on='BUILDING_ID', how='left')

    return gdf

def load_urbis_network(urbis_folder, mask=None):
    """
    Clean and harmonise the UrbIS GeoDataFrames.
    """
    # Street nodes
    file_nodes = urbis_folder + '/StreetNodes.feather'
    gdf_nodes = load_gdf(file_nodes, mask=mask)
    # Street edges
    file_edges = urbis_folder + '/StreetAxes.feather'
    gdf_edges = load_gdf(file_edges, mask=mask)

    return gdf_nodes, gdf_edges

def load_osm_network(osm_folder, mask=None):
    """
    Load and clean the OSM network data.
    """
    file_nodes = osm_folder + '/Nodes.feather'
    gdf_nodes = load_gdf(file_nodes, mask=mask)
    file_edges = osm_folder + '/Edges.feather'
    gdf_edges = load_gdf(file_edges, mask=mask)

    return gdf_nodes, gdf_edges

def clean_segments(gdf_edges, mask=None):

    """
    Clean and simplify the street segments.
    """

    # Explode multipart lines
    gdf_edges = gdf_edges.explode().copy()
    # Close gaps
    gdf_edges = neatnet.close_gaps(gdf_edges.geometry, tolerance=1)
    # Remove interstitial nodes
    gdf_edges = neatnet.remove_interstitial_nodes(gdf_edges)
    # Extend lines
    gdf_edges = neatnet.extend_lines(gdf_edges, tolerance=1)
    # Adaptive simplification
    gdf_edges = neatnet.neatify(gdf_edges, exclusion_mask=mask)
    # Remove the edges that cut through the mask
    if mask is not None:
        gdf_edges = gdf_edges[~gdf_edges.crosses(mask.union_all())]

    # Extract nodes from the cleaned edges
    G = momepy.gdf_to_nx(gdf_edges, directed=False)
    gdf_nodes, gdf_edges = momepy.nx_to_gdf(G)

    # Rename columns and keep only necessary ones
    gdf_nodes = gdf_nodes.rename(columns={'nodeID': 'NODE_ID'})[['NODE_ID', 'geometry']]
    gdf_edges = gdf_edges.reset_index(drop=False).rename(columns={'index': 'EDGE_ID'})
    gdf_edges = gdf_edges.rename(columns={'node_start': 'NODE_START', 'node_end': 'NODE_END'})[['EDGE_ID', 'NODE_START', 'NODE_END', 'geometry']]

    return gdf_edges, gdf_nodes

def connect_buildings_to_streets(gdf_buildings, gdf_edges, gdf_nodes, n_length_threshold=5):
    """
    Connect buildings to the nearest street segments.
    """

    buildings = gdf_buildings.copy()
    edges = gdf_edges.copy()
    nodes = gdf_nodes.copy()

    def build_blocks(edges):
        """
        Return the street blocks (faces of the network).        
        """
        blocks = gpd.GeoDataFrame(
            geometry=list(polygonize(edges.geometry.union_all())),
            crs=edges.crs
        )
        return blocks

    def valid_connection(line, building, target_edge):
        """
        Check if a connection line is valid based on the following criteria:
        - The line must not cross any other building.
        - The line must not cross any other edge.
        - The line must not touch any node.
        """
        # TODO: Check if the line is a line and not a point (in case the building is already touching the edge)
        
        touching_buildings = buildings[buildings.geometry.crosses(line)]
        touching_buildings = touching_buildings[touching_buildings.geometry != building] # Exclude the building itself
        if len(touching_buildings) > 0:
            return False

        touching_edges = edges[edges.geometry.crosses(line)]
        touching_edges = touching_edges[touching_edges.geometry != target_edge] # Exclude the target edge
        if len(touching_edges) > 0:
            return False

        touching_nodes = nodes[nodes.geometry.touches(line)]
        if len(touching_nodes) > 0:
            return False

        return True
    
    blocks = build_blocks(edges)
    connections = []

    # For each building, find the nearest edge and create a connection line
    for b_idx, b in tqdm(buildings.iterrows(), total=len(buildings)):
        b_geom = b.geometry
        block = blocks[blocks.geometry.contains(b_geom)] # Should be only one block

        if block.empty:
            # fallback: nearest edge
            print(f"No block found for building {b_idx}, using nearest edge as fallback.")
            e_idx = edges.distance(b_geom).idxmin()
            e_geom = edges.loc[e_idx].geometry
            p1, p2 = nearest_points(b_geom, e_geom)
            line = LineString([p1, p2])
            if valid_connection(line, b_geom, e_geom):
                conn = {'B_IDX': b_idx, 'BUILDING_ID': b.BUILDING_ID, 'EDGE_ID': e.EDGE_ID, 'length': line.length, 'geometry': line}
                connections.append(conn)
            continue

        block_geom = block.iloc[0].geometry # Get the block geometry

        # Find candidate edges that intersect the block bounding box (fast preselection)
        cand_e_idx = list(edges.sindex.intersection(block_geom.bounds))
        cand_edges = edges.loc[cand_e_idx]
        # Keep only edges that truly overlap boundary of the polygon block
        eps = 1e-6
        cand_edges = cand_edges[cand_edges.geometry.within(block_geom.buffer(eps))]

        for e_idx, e in cand_edges.iterrows():
            e_geom = e.geometry
            p1, p2 = nearest_points(b_geom, e_geom)
            line = LineString([p1, p2])
            if valid_connection(line, b_geom, e_geom):
                conn = {'B_IDX': b_idx, 'BUILDING_ID': b.BUILDING_ID, 'EDGE_ID': e.EDGE_ID, 'length': line.length, 'geometry': line}
                connections.append(conn)
    
    # For each buildings, remove connections that are n times longer than the shortest connection for that building
    if n_length_threshold is not None:
        for b_idx in buildings.index:
            b_connections = [conn for conn in connections if conn['B_IDX'] == b_idx]
            if b_connections:
                min_length = min(conn['length'] for conn in b_connections)
                for c in b_connections:
                    if c['length'] > n_length_threshold * min_length:
                        connections.remove(c)

    # Convert connections to GeoDataFrame
    gdf_connections = gpd.GeoDataFrame(connections, geometry='geometry', crs=buildings.crs)
    connected_buildings = set(gdf_connections['B_IDX'])

    # For buildings with empty connections, copy the connections of the nearest connected building
    for b_idx, b in buildings.iterrows():
        b_geom = b.geometry
        if b_idx in connected_buildings:
            continue
        print(f"Building {b_idx} has no valid connections, copying from nearest connected building.")
        # Find the nearest connection
        nearest_conn_idx = gdf_connections.distance(b_geom).idxmin()
        nearest_conn = gdf_connections.loc[nearest_conn_idx]
        # Copy the connection(s) and update the building index to the current building
        new_conns = nearest_conn.copy()
        new_conns['B_IDX'] = b_idx
        # Add each new connection to the connections list and GeoDataFrame
        connections.append(new_conns.to_dict())
    
    # Update the connections GeoDataFrame with the new connections
    gdf_connections = gpd.GeoDataFrame(connections, geometry='geometry', crs=buildings.crs)
    gdf_connections = gdf_connections.drop(columns=['B_IDX', 'length'])

    return gdf_connections

if __name__ == "__main__":
    # Run the code for all components
    import buildings
    import segments
    import connections