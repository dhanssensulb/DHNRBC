# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

# %% WFS Connection - BISA
from owslib.wfs import WebFeatureService

WFS_BISA = 'https://geoservices-vector.irisnet.be/geoserver/BISA/wfs'

# Connect to the WFS
wfs_bisa = WebFeatureService(url=WFS_BISA, version='2.0.0')

features = list(wfs_bisa.contents.keys())
print('Title:', wfs_bisa.identification.title)
print('Abstract:', wfs_bisa.identification.abstract)
print('Features:', features)

# %% Layers of interest
import time
import geopandas as gpd

# Belgian Lambert 72
crs_lambert = 'EPSG:31370'

# Fetch all the properties from the layer
layer = features[0] # Macrozone

print(f'Fetching: {layer}')
time.sleep(1)
start = time.time()

r = wfs_bisa.getfeature(
    typename=layer,
    srsname=crs_lambert,
    maxfeatures = None, # None if no limit
    outputFormat='application/json'
) # Returns BytesIO (file-like object)

gdf = gpd.read_file(r)
gdf.set_index('id', inplace=True)

file_name = f'../../Data/BISA/{layer.split(":")[1]}.feather'
gdf.to_feather(file_name)

end = time.time()
print(f'Time taken: {end - start:.2f} seconds')
    
# %%