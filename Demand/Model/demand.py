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

# Load RES 
res_folder = '../Res'
file_buildings = res_folder + '/Buildings.feather'

gdf_b = process.load_gdf(file_buildings)

df_dd = process.load_dd()

gdf_b_demand = process.compute_building_demand(gdf_b, df_dd)

# Save dataframes in res

gdf_b_demand.to_feather('../Res/Buildings_Demand.feather')
# %%
