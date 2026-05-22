# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Helpers

import geopandas as gpd
from shapely.validation import make_valid

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

def best_overlap_match(gdf, gdf_target, id_col, target_cols, threshold):
    """
    Returns the best overlapping target attributes for each geometry in gdf based on the specified threshold.
    """
    # Compute the intersection between gdf and gdf_target
    inter = gpd.overlay(gdf, gdf_target[target_cols + ['geometry']], how='intersection')

    # Compute the area of the intersection and the area of the original geometries
    inter['overlap_area'] = inter.geometry.area
    inter['overlap_ratio'] = inter['overlap_area'] / inter['AREA']

    # Keep only significant overlaps
    inter = inter[inter["overlap_ratio"] >= threshold]

    # Keep best match per geometry
    best_match = inter.sort_values('overlap_area', ascending=False).groupby(id_col).first()[target_cols]

    return best_match


def aggregate_building_data(gdf_b, gdf_osm, gdf_sitex, association_threshold=0.5):
    """
    Aggregate building data from UrbIS and OSM based on spatial overlap.
    A building from UrbIS is associated with a building from OSM if the overlap area is at least `association_threshold` of the UrbIS building area.
    """

    gdf_b['AREA'] = gdf_b.geometry.area

    # Find the best overlapping OSM building and SitEx type for each UrbIS building
    best_osm = best_overlap_match(gdf_b, gdf_osm, id_col='BUILDING_ID', target_cols=['building'], threshold=association_threshold)
    best_sitex = best_overlap_match(gdf_b, gdf_sitex, id_col='BUILDING_ID', target_cols=['level_all', 'sp', 'type'], threshold=association_threshold)

    # Merge the best associations back to the original UrbIS building GeoDataFrame
    result = gdf_b.merge(best_osm, on='BUILDING_ID', how='left')
    result = result.merge(best_sitex, on='BUILDING_ID', how='left')

    # Clean up
    result = result.drop(columns=['AREA'])
    result = result.rename(columns={'building': 'osm_type', 'type': 'sitex_type'})

    return result

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