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

df_dd, dd_group, hdd_cdd = process.load_dd()

eta_sh = {
    '2020': 1.0,
    '2030': 0.9,
    '2040': 0.8,
    '2050': 0.7
}

eta_dhw = {
    '2020': 1.0,
    '2030': 1.0,
    '2040': 1.0,
    '2050': 1.0
}

gdf_b_demand = process.compute_building_demand(gdf_b, df_dd, eta_sh=eta_sh, eta_dhw=eta_dhw)

# Save dataframes in RES
gdf_b_demand.to_feather('../Res/Buildings_Demand.feather')
# %%

import matplotlib.pyplot as plt

plt.rcdefaults()
plt.rc('text', usetex=True) # Use LaTeX for rendering text
plt.rc('font', family='serif')
plt.rc('savefig', directory='../Figures/Out', format='pdf', dpi=100)

plt.rcParams.update({
    "axes.titleweight": "normal",   # <-- fixes the bold-fallback issue
    "figure.titleweight": "normal", # <-- same fix for suptitle
})

fig, ax = plt.subplots(figsize=(8, 6))

for model in hdd_cdd['GCM'].unique():
    hdd_cdd_model = hdd_cdd.query(f"GCM == '{model}' & YEAR >= 2020 & YEAR <= 2050")
    hdd_cdd_model.plot(ax=ax, x='YEAR', y='HDD', alpha=0.5, label=model)

dd_group.loc[2020:2050, 'HDD'].plot(ax=ax, color='grey', alpha=1, linewidth=3, label='Mean')
df_dd['HDD'].plot(ax=ax, color='black', linewidth=2, linestyle='--', label='Trend')

ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('Annual Heating Degree Days (HDD)', fontsize=12)
ax.legend()

out_folder = '../Figures/Out/'

plt.savefig(out_folder + 'input_model_evolution.pdf', bbox_inches='tight')
plt.savefig(out_folder + 'input_model_evolution.png', bbox_inches='tight')

plt.show()

# %%

import pandas as pd

# Select a scenario

gdf_b_s = gdf_b_demand[gdf_b_demand.VERSION_HEAT == 'low']


df_sector_info = pd.DataFrame({
    'count': gdf_b_s['TYPE'].value_counts(),
    'count_percent': (gdf_b_s['TYPE'].value_counts(normalize=True) * 100).round(0),
    'spec_space_heat': gdf_b_s.groupby('TYPE')['SPEC_SPACE_HEAT'].first(),
    'heat_volume_2020': (gdf_b_s.groupby('TYPE')['HEAT_VOLUME_2020'].sum() / 1e3).round(0),
    'heat_volume_2020_percent': (gdf_b_s.groupby('TYPE')['HEAT_VOLUME_2020'].sum() / gdf_b_s['HEAT_VOLUME_2020'].sum() * 100).round(0),
    'heat_volume_2050': (gdf_b_s.groupby('TYPE')['HEAT_VOLUME_2050'].sum() / 1e3).round(0),
    'heat_volume_2050_percent': (gdf_b_s.groupby('TYPE')['HEAT_VOLUME_2050'].sum() / gdf_b_s['HEAT_VOLUME_2050'].sum() * 100).round(0),
})

df_listed_info = pd.DataFrame({
    'count': gdf_b_s['LISTED'].value_counts(),
    'count_percent': (gdf_b_s['LISTED'].value_counts(normalize=True) * 100).round(0),
    'heat_volume_2020': (gdf_b_s.groupby('LISTED')['HEAT_VOLUME_2020'].sum() / 1e3).round(0),
    'heat_volume_2020_percent': (gdf_b_s.groupby('LISTED')['HEAT_VOLUME_2020'].sum() / gdf_b_s['HEAT_VOLUME_2020'].sum() * 100).round(0),
    'heat_volume_2050': (gdf_b_s.groupby('LISTED')['HEAT_VOLUME_2050'].sum() / 1e3).round(0),
    'heat_volume_2050_percent': (gdf_b_s.groupby('LISTED')['HEAT_VOLUME_2050'].sum() / gdf_b_s['HEAT_VOLUME_2050'].sum() * 100).round(0),
})

# %%
