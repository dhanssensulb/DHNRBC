# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%%

import load

# For debugging
import importlib
importlib.reload(load)

# Import UrbIS data from WFS service
# https://datastore.brussels/web/data/dataset/f3ad5174-4a86-11ef-b009-010101010000#access

WFS_UrbIS_vec = 'https://geoservices-vector.irisnet.be/geoserver/urbisvector/wfs'

wfs, layers = load.connect_to_wfs(WFS_UrbIS_vec)

crs_lambert = 'EPSG:31370'

properties = { # Properties to fetch for each layer
    'urbisvector:Addresses': [
        'STRNAMEFRE', 'POLICENUM', 'BOXNUMBER', 'ZIPCODE',
        'STATNISCODE', 'CAPAKEY', 'XL72', 'YL72',
        'BU_ID', 'STREET_ID', 'CAPAKEY', 'geom'
    ],
    'urbisvector:Buildings': [
        'INSPIRE_ID', 'BLOCK_ID', 'geom'
    ],
    'urbisvector:Blocks': [
        'INSPIRE_ID', 'TYPE', 'NAMEFRE', 'LVL', 'geom'
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

gdfs = {}
for layer, props in properties.items():
    gdf = load.fetch_wfs_layer(
        wfs=wfs,
        layer_name=layer,
        properties=props,
        srsname=crs_lambert,
        saving=True,
        output_folder='../../Data/UrbIS'
    )
    gdfs[layer] = gdf