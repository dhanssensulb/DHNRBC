# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

# %% WFS Connection
from owslib.wfs import WebFeatureService

WFS_BruGIS = 'https://gis.urban.brussels/geoserver/wfs'

# Connect to the WFS
wfs_brugis = WebFeatureService(url=WFS_BruGIS, version='1.1.0', timeout=120)

features = list(wfs_brugis.contents.keys())
print('Title:', wfs_brugis.identification.title)
print('Abstract:', wfs_brugis.identification.abstract)
print('Features:', features)

# %% Layers of interest
import time
import geopandas as gpd

properties = {
    ## Map backgrounds
    'GAPD:AGDP_CAPA' : [ # Cadastral parcel data from the FPS Finance (monthly update)
        'ID', 'GEOMETRY'
    ],
    'VM_URBIS_M8_BUILDINGS' : [ # UrbIS buildings
        'INSPIRE_ID', 'GEOMETRY'       
    ],
    'URBAN_DCC_ER:region_boundary': [ # Region Boundary
        'ID', 'GEOMETRY'
    ],

    ## Public Space Manual - https://urban.brussels/public_space_fr.pdf
    'URBAN_DUP:Public_space_Programmations_segments': [ # All nodes in the BCR.
        'ORG_ID', 'PW_NAME_FR', 'ORG_TYPE', 'LARGEUR', 'PROGRAMMATION', 'ORG_EXISTING_TYPOLOGY', 'STRATEGY', 'GEOMETRY'
    ],
    'URBAN_DUP:Public_space_Programmations_nodes': [ # All segments in the BCR.
        'ORG_ID', 'PW_NAME_FR', 'ORG_TYPE', 'LARGEUR', 'PROGRAMMATION', 'ORG_EXISTING_TYPOLOGY', 'STRATEGY', 'GEOMETRY'
    ],

    ## Register of protected goods
    'URBAN_DCH_IBH:Heritage' : [ # Register of protected heritage
        'ID', 'MS', 'ML', 'BENAMING_FR', 'STATUS_FR', 'ID_BESCHERMING', 'TYPE_VRIJWARING_FR', 'BESCHERMD_ALS_FR', 'VRIJWARINGSZONE',
        'POSTCODE', 'GEMEENTE_FR', 'STRAAT_FR', 'GEOMETRY'
    ],

    ## Legal inventory
    'URBAN_DCH_NH:Legal_inventory_of_sites': [ # (CoBAT, Art. 207) - Inventory of the immovable heritage of the Region
        'TYPE', 'NAME_FR', 'ID_DPC', 'GEOMETRY'
    ],
    'URBAN_DCH_IBH:Irismonument_legal_inventory': [ # Legal inventory of monuments and ensembles
        'NOM_FR', 'CITY', 'STREET_FR', 'NUMBER', 'TYPO_FR', 'TYPO', 'STYLE_FR', 'BUILT', 'LISTED', 'UNESCO', 'GEOMETRY'
    ]
}

# Fetch each layer and store in a dictionary
gdfs = {}
for layer, props in properties.items():

    print(f'Fetching: {layer}')
    time.sleep(1)
    start = time.time()

    r = wfs_brugis.getfeature(
        typename=layer,
        propertyname=props,
        maxfeatures = None, # None if no limit
        outputFormat='application/json'
    ) # Returns BytesIO (file-like object)

    gdf = gpd.read_file(r)
    gdf.set_index('id', inplace=True)
    gdfs[layer] = gdf

    if ":" in layer:
        file_name = f'../../Data/BruGIS/{layer.split(":")[1]}.feather'
    else:
        file_name = f'../../Data/BruGIS/{layer}.feather'

    gdf.to_feather(file_name)

    end = time.time()
    print(f'Time taken: {end - start:.2f} seconds')
# %%
