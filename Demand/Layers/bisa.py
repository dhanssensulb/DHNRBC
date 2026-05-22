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

WFS_BISA = 'https://geoservices-vector.irisnet.be/geoserver/BISA/wfs'

wfs, layers = load.connect_to_wfs(WFS_BISA)

crs_lambert = 'EPSG:31370'

gdf = load.fetch_wfs_layer(
    wfs=wfs,
    layer_name=layers[0],
    srsname=crs_lambert,
    saving=True,
    output_folder='../../Data/BISA'
)