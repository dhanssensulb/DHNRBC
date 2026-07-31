# -*- coding: utf-8 -*-
"""
Created on May 26

@author: hanssens
"""

#%% Helpers
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.validation import make_valid

plt.rc('text', usetex=True) # Use LaTeX for rendering text
plt.rc('font', family='serif', size=20)
plt.rc('figure', figsize=(20, 20), dpi=100)
plt.rc('savefig', directory='/Out', format='pdf', dpi=100)
plt.rc('axes', facecolor='white', edgecolor='none', titlesize=35)
plt.rc('xtick', bottom=False, top=False, labelbottom=False)
plt.rc('ytick', left=False, right=False, labelleft=False)

plt.rcParams.update({
    "axes.titleweight": "normal",   # <-- fixes the bold-fallback issue
    "figure.titleweight": "normal", # <-- same fix for suptitle
})

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