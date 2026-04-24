# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

# %% WFS Connection
from owslib.wfs import WebFeatureService

WFS_UrbIS_vec = 'https://geoservices-vector.irisnet.be/geoserver/urbisvector/wfs'

# Connect to the WFS
wfs_urbis_vec = WebFeatureService(url=WFS_UrbIS_vec, version='2.0.0')

features = list(wfs_urbis_vec.contents.keys())
print('Title:', wfs_urbis_vec.identification.title)
print('Abstract:', wfs_urbis_vec.identification.abstract)
print('Features:', features)

# %% Layers of interest
import time
import geopandas as gpd

# Belgian Lambert 72
crs_lambert = 'EPSG:31370'

properties = {
    'urbisvector:Addresses': [
        'STRNAMEFRE', 'POLICENUM', 'BOXNUMBER', 'ZIPCODE',
        'STATNISCODE', 'CAPAKEY', 'XL72', 'YL72', 'geom'
    ],
    'urbisvector:CadastralParcels': [
        'CAPAKEY', 'TYPE', 'CADAST_DIV', 'MUNNISCODE', 'geom'
    ],
    #
    'urbisvector:StatisticalSectors': [
        'NISCODE', 'MUNNISCODE', 'MDZONE', 'geom'
    ],
    'urbisvector:MonitoringDistricts': [
        'MDZONE', 'geom'
    ],
    'urbisvector:Municipalities': [
        'NISCODE', 'POLICEZONE', 'geom'
    ],
    'urbisvector:Region': [
        'NAMEFRE', 'geom'
    ],
    #
    'urbisvector:StreetAxes': [
        'TYPE', 'HIERARCHY', 'LVL', 'STRNAMEFRE', 'SLOPE', 'LENGTH', 'geom'
    ],
    'urbisvector:StreetNodes': [
        'TYPE', 'LVL', 'XL72', 'YL72', 'geom'
    ],
    'urbisvector:StreetSurfaces': [
        'TYPE', 'STRNAMEFRE', 'MUNNISCODE', 'HIERARCHY', 'LVL', 'ADMIN', 'AREA', 'geom'
    ],
    #
    'urbisvector:Railways': [
        'TYPE', 'LVL', 'SLOPE', 'LENGTH', 'geom'
    ],
    'urbisvector:Tunnels': [
        'TYPE', 'LVL', 'AREA', 'geom'
    ],
    #
    'urbisvector:PointsOfInterest': [
        'TYPE', 'CATEGORY', 'NAMEFRE', 'XL72', 'YL72', 'geom'
    ],
}

# Fetch each layer and store in a dictionary
gdfs = {}
for layer, props in properties.items():

    print(f'Fetching: {layer}')
    time.sleep(1)
    start = time.time()

    r = wfs_urbis_vec.getfeature(
        typename=layer,
        propertyname=props,
        srsname=crs_lambert,
        maxfeatures = None, # None if no limit
        outputFormat='application/json'
    ) # Returns BytesIO (file-like object)

    gdf = gpd.read_file(r)
    gdf.set_index('id', inplace=True)
    gdfs[layer] = gdf

    file_name = f'../../Data/UrbIS/{layer.split(":")[1]}.feather'
    gdf.to_feather(file_name)

    end = time.time()
    print(f'Time taken: {end - start:.2f} seconds')    
# %%
