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

# Import BruGIS data from WFS service
# https://gis.urban.brussels/brugis/#/

WFS_BruGIS = 'https://gis.urban.brussels/geoserver/wfs'

wfs, layers = load.connect_to_wfs(WFS_BruGIS, version='1.1.0')

crs_lambert = 'EPSG:31370'

properties = { # Properties to fetch for each layer
    ## Map backgrounds
    'GAPD:AGDP_CAPA' : [ # Cadastral parcel data from the FPS Finance (monthly update)
        'ID', 'GEOMETRY'
    ],
    'URBAN_DCC_ER:VM_URBIS_M8_BUILDINGS' : [ # UrbIS buildings
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
    'URBAN_DCH_IBH:Classified_or_protected_built_heritage': [ # Classified or protected built heritage
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

gdfs = {}
for layer, props in properties.items():
    gdf = load.fetch_wfs_layer(
        wfs=wfs,
        layer_name=layer,
        properties=props,
        saving=True,
        output_folder='../../Data/BruGIS'
    )
    gdfs[layer] = gdf