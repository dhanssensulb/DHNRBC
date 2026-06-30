# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Helpers

import geopandas as gpd
from shapely.validation import make_valid
import pandas as pd
from sklearn.linear_model import LinearRegression

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

def load_dd(file_dd='hdd_cdd.csv'):
    """
    Load degree days data from a CSV file and compute trends.
    """

    hdd_cdd = (
        pd.read_csv(file_dd)
        .rename(columns={
            "gcm": "GCM",
            "year": "YEAR",
            "sum_hdd": "HDD",
            "max_hdd": "MAX_HDD",
            "sum_hdd-2": "CDD",
            "max_hdd-2": "MAX_CDD",
        })
    )

    dd_group = hdd_cdd.groupby('YEAR').agg({
        'HDD': 'mean',
        'CDD': 'mean',
        'MAX_HDD' : lambda x: x.quantile(0.95),
        'MAX_CDD' : lambda x: x.quantile(0.95)
    })

    cols = ['HDD', 'CDD', 'MAX_HDD', 'MAX_CDD']

    trend = LinearRegression().fit(
        dd_group.index.values.reshape(-1, 1),
        dd_group[cols].values
    ).predict(dd_group.index.values.reshape(-1, 1))

    dd_group[[f'{col}_trend' for col in cols]] = trend

    decades = range(2020, 2060, 10)

    df_dd = pd.DataFrame(
        {
            "HDD": [dd_group.loc[y:y+9, "HDD_trend"].mean() for y in decades],
            "CDD": [dd_group.loc[y:y+9, "CDD_trend"].mean() for y in decades],
            "MAX_HDD": [dd_group.loc[y:y+9, "MAX_HDD_trend"].max() for y in decades],
            "MAX_CDD": [dd_group.loc[y:y+9, "MAX_CDD_trend"].max() for y in decades],
        },
        index=decades
    )

    return df_dd

def compute_building_demand(gdf_b, df_dd):
    """
    Compute the building demand for space heating and domestic hot water based on degree days.
    """
    eta_sh = {
        '2020': 1.0,
        '2030': 0.9,
        '2040': 0.8,
        '2050': 0.7
    }

    eta_dhw = {
        '2020': 1.0,
        '2030': 0.95,
        '2040': 0.9,
        '2050': 0.85
    }

    gdf_b_demand = gdf_b.copy()

    for year in [2020, 2030, 2040, 2050]:
        HDD_ratio_sh = df_dd.loc[year, 'HDD'] / df_dd.loc[2020, 'HDD']
        HDD_ratio_dhw = df_dd.loc[year, 'MAX_HDD'] / df_dd.loc[2020, 'HDD']

        # Listed buildings keep their original demand (eta = 1)
        eta_sh_eff = gdf_b_demand['LISTED'].apply(lambda x: 1.0 if x else eta_sh[str(year)])
        eta_dhw_eff = gdf_b_demand['LISTED'].apply(lambda x: 1.0 if x else eta_dhw[str(year)])

        d_sh = eta_sh_eff * gdf_b_demand['SPEC_SPACE_HEAT']
        d_dhw = eta_dhw_eff * gdf_b_demand['SPEC_DHW']

        gdf_b_demand[f'HEAT_VOLUME_{year}'] = gdf_b_demand['FLOOR_AREA'] * (d_sh * HDD_ratio_sh + d_dhw) / 1e3
        gdf_b_demand[f'HEAT_CAPACITY_{year}'] = gdf_b_demand['FLOOR_AREA'] * (d_sh * HDD_ratio_dhw * 1 / 24 + d_dhw * 1 / 8760)

    return gdf_b_demand