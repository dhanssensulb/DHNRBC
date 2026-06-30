# -*- coding: utf-8 -*-
"""
Created on Apr 26

@author: hanssens
"""

#%%

import process

# For debugging
import importlib
importlib.reload(process)

import pandas as pd

# Fetch Macrozones from BISA WFS
folder_bisa = '../../Data/BISA'
file_macro = folder_bisa + '/StatisticalMacrozones.feather'

gdf_macro = process.load_gdf(file_macro)

# Mask Pentagone
gdf_pentagone = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagone = gdf_pentagone.union_all()

mask_pentagone_extended = mask_pentagone.buffer(100) # Extend by 100m

# Load PEB Public
folder_peb = '../../Data/PEB'
file_peb_public = folder_peb + '/public.gpkg'

gdf_peb = process.load_peb_public(file_peb_public, mask=mask_pentagone)


# Save dataframe in folder_peb
gdf_peb.to_feather(folder_peb + '/peb_public.feather')