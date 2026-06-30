# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Helpers
import pandas as pd
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

def load_peb_public(file_peb_public, mask=None):
    """
    Clean and harmonise the PEB Public GeoDataFrame.
    """
    gdf_peb = load_gdf(file_peb_public, mask=mask)

    rename_dict = {
        'Organisation publique': 'PUBLIC_ORGA',
        'Catégorie': 'CATEGORY',
        'Nom du bâtiment': 'BUILDING_NAME',
        'Adresse': 'ADDRESS',
        'Indice d’émission de CO2 [kg éq CO2/(m².an)]': 'CO2_IDX',
        'Niveau de performance énergétique [kWhEP/(m².an)]': 'NRJ_IDX',
        'Classe': 'LABEL',
        'Surface PEB pondérée [m²]': 'PEB_AREA',
        "Date d’expiration": 'EXPIRATION_DATE',
    }

    # Rename and keep only relevant columns
    gdf_peb = gdf_peb.rename(columns=rename_dict)
    gdf_peb = gdf_peb[list(rename_dict.values()) + ['geometry']]

    # Put CO2_IDX, NRJ_IDX and PEB_AREA as float
    gdf_peb['CO2_IDX'] = gdf_peb['CO2_IDX'].astype(float)
    gdf_peb['NRJ_IDX'] = gdf_peb['NRJ_IDX'].astype(float)
    gdf_peb['PEB_AREA'] = gdf_peb['PEB_AREA'].astype(float)

    # Put EXPIRATION_DATE as datetime
    gdf_peb['EXPIRATION_DATE'] = pd.to_datetime(gdf_peb['EXPIRATION_DATE'], dayfirst='True', errors='coerce')

    # Group by geometry and take the weighted mean of CO2_IDX and NRJ_IDX, weighted by PEB_AREA, and the first value of PUBLIC_NAME, and the sum of PEB_AREA, and the more recent expiration date
    group_cols = ['PUBLIC_ORGA', 'CATEGORY', 'ADDRESS', 'geometry']

    def weighted_mean(series, weights):
        return (series * weights).sum() / weights.sum()
    
    gdf_peb = gdf_peb.groupby(group_cols).apply(lambda df: pd.Series({
        'CO2_IDX': weighted_mean(df['CO2_IDX'], df['PEB_AREA']),
        'NRJ_IDX': weighted_mean(df['NRJ_IDX'], df['PEB_AREA']),
        'BUILDING_NAME': df['BUILDING_NAME'].iloc[0],
        'PEB_AREA': df['PEB_AREA'].sum(),
        'EXPIRATION_DATE': df['EXPIRATION_DATE'].min()
    })).reset_index()

    # Convert back to GeoDataFrame
    gdf_peb = gpd.GeoDataFrame(gdf_peb, geometry='geometry')

    return gdf_peb