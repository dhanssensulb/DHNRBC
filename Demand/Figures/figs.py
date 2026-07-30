# -*- coding: utf-8 -*-
"""
Created on June 26

@author: hanssens
"""

#%%

import settings
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import matplotlib.colors as colors
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import cartopy
import cartopy.crs as ccrs

# For debugging
import importlib
importlib.reload(settings)

# Fetch Macrozones from BISA WFS
folder_bisa = '../../Data/BISA'
file_macro = folder_bisa + '/StatisticalMacrozones.feather'

gdf_macro = settings.load_gdf(file_macro)

# Mask Pentagon
gdf_pentagon = gdf_macro[gdf_macro.ma_code == 1]
mask_pentagon = gdf_pentagon.union_all()

mask_pentagon_extended = mask_pentagon.buffer(100) # Extend by 100m

# Load Data
data_folder = '../../Data'
file_canal = data_folder + '/Vision_Zonee/01.CriteresAccessibilite/Canal_200m_split.shp'
file_senne = data_folder + '/Vision_Zonee/01.CriteresAccessibilite/Zenne_open_and_covered.shp'
file_sewers = data_folder + '/Vision_Zonee/01.CriteresAccessibilite/riothermie.shp'

gdf_canal = settings.load_gdf(file_canal, mask=mask_pentagon_extended)
gdf_senne = settings.load_gdf(file_senne, mask=mask_pentagon_extended)
gdf_sewers = settings.load_gdf(file_sewers, mask=mask_pentagon_extended)

# Load RES 
res_folder = '../Res'
file_buildings = res_folder + '/Buildings.feather'
file_buildings_demand = res_folder + '/Buildings_Demand.feather'
file_edges = res_folder + '/Edges.feather'
file_nodes = res_folder + '/Nodes.feather'
file_connections = res_folder + '/Connections.feather'

gdf_buildings = settings.load_gdf(file_buildings)
gdf_buildings_demand = settings.load_gdf(file_buildings_demand)
gdf_edges = settings.load_gdf(file_edges)
gdf_nodes = settings.load_gdf(file_nodes)
gdf_connections = settings.load_gdf(file_connections)

def add_cbar(ax, color, values, label):
    sm = plt.cm.ScalarMappable(cmap=color, norm=plt.Normalize(vmin=values.min(), vmax=values.max()))
    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal', fraction=0.03, pad=0.0)
    cbar.set_label(label, fontsize=35)
    cbar.ax.tick_params(labelsize=25)
    cbar.outline.set_edgecolor('black')
    cbar.outline.set_linewidth(1)

def binary_cmap(color):
    return ListedColormap([
        "lightgrey",
        color
    ])

out_folder = 'Out/'
save = True

#%%

fig = plt.figure(figsize=(5, 5))

bcr = gdf_macro.dissolve().to_crs(epsg=4326)  # Convert to WGS84 (EPSG:4326) for plotting

ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent([2.2, 6.8, 49.2, 51.8], crs=ccrs.PlateCarree())

ax.add_feature(cartopy.feature.OCEAN, facecolor='lightblue')
ax.add_feature(cartopy.feature.LAND, facecolor='white')
ax.add_feature(cartopy.feature.BORDERS, edgecolor='black', linewidth=1)
ax.coastlines(linewidth=1.5)

gl = ax.gridlines(draw_labels=True, linewidth=1, color='gray', alpha=0.5, linestyle='--')
gl.top_labels = False
gl.right_labels = False

gl.xlabel_style = {'size': 10}
gl.ylabel_style = {'size': 10}

bcr.plot(ax=ax, facecolor='chocolate', alpha=0.5, transform=ccrs.PlateCarree())
bcr.plot(ax=ax, facecolor='none', edgecolor='black', linewidth=0.5, transform=ccrs.PlateCarree())

inset_rect = (0.5, 0.17, 0.38, 0.38)  # (x0, y0, width, height)

bg_ax = fig.add_axes(inset_rect, transform=ax.transAxes, facecolor='white', zorder=9)
for spine in bg_ax.spines.values():
    spine.set_visible(True)
    spine.set_edgecolor('black')
    spine.set_linewidth(1.5)

pentagon = gdf_macro.query("ma_id == 1")
macro = gdf_macro.copy()
bcr = gdf_macro.dissolve()

macro.plot(ax=bg_ax, facecolor='chocolate', edgecolor='black', linewidth=0.5, alpha=0.5)
pentagon.plot(ax=bg_ax, facecolor='chocolate', edgecolor='black', linewidth=1, alpha=1)
bcr.plot(ax=bg_ax, facecolor='none', edgecolor='black', linewidth=1.5)

if save:
    plt.savefig(out_folder + 'brussels_belgium.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
    plt.savefig(out_folder + 'brussels_belgium.pdf', bbox_inches='tight')
plt.show()

#%%

# Buildings Raw - UrbIS
fig, ax = plt.subplots(figsize=(5, 5))

gdf_buildings.plot(ax=ax, color='lightgrey', edgecolor='black', linewidth=0.2)

if save:
    plt.savefig(out_folder + 'buildings_raw.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()

# Buildings Type - OSM + SitEx
fig, ax = plt.subplots(figsize=(5, 5))

gdf_buildings.plot(ax=ax, column='TYPE', cmap='tab10')

if save:
    plt.savefig(out_folder + 'buildings_type.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()

# Buildings Floor area - SitEx
fig, ax = plt.subplots(figsize=(5, 5))

gdf_buildings.plot(ax=ax, column='FLOOR_AREA', cmap='Purples')

if save:
    plt.savefig(out_folder + 'buildings_area.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()

# Buildings Listed - BruGIS
fig, ax = plt.subplots(figsize=(5, 5))

gdf_buildings.plot(ax=ax, column='LISTED', cmap=binary_cmap('orange'))

if save:
    plt.savefig(out_folder + 'buildings_listed.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()

# Buildings Resources
fig, ax = plt.subplots(figsize=(5, 5))

gdf_buildings.plot(ax=ax, column='RIOTHERMAL_ACCESS', cmap=binary_cmap('green'))
gdf_sewers.plot(ax=ax, color='darkgreen', linewidth=1, label='Sewers')

if save:
    plt.savefig(out_folder + 'buildings_access.png', format='png', dpi=300, bbox_inches='tight', transparent=True)
plt.show()
#%%

# Building network
fig, ax = plt.subplots()

gdf_buildings.plot(ax=ax, color='lightgrey', edgecolor='grey', linewidth=0.2)
gdf_connections.plot(ax=ax, color='blue', alpha=0.5, linewidth=0.7)
gdf_edges.plot(ax=ax, color='red', linewidth=1)
gdf_nodes.plot(ax=ax, color='k', markersize=2, zorder=10)

# Legend
red_patch = plt.Line2D([0], [0], color='red', lw=2, label='Street Network')
blue_patch = plt.Line2D([0], [0], color='blue', lw=2, label='Building-Street Connections')
plt.legend(handles=[red_patch, blue_patch], loc='upper right')

if save:
    plt.savefig(out_folder + 'building_network.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_network.png', bbox_inches='tight')
plt.show()

# Building demand
fig, axs = plt.subplots(1, 3, figsize=(60, 20))
plt.subplots_adjust(wspace=-0.3)

lw = 0.5

gdf_buildings.plot(ax=axs[0], column='SPEC_DHW', cmap='Oranges', edgecolor='black', linewidth=lw)
axs[0].set_title('Domestic Hot Water Demand')
add_cbar(axs[0], 'Oranges', gdf_buildings['SPEC_DHW'], r'$\frac{kWh}{m^2 \cdot year}$')

gdf_buildings.plot(ax=axs[1], column='SPEC_SPACE_HEAT', cmap='Reds', edgecolor='black', linewidth=lw)
axs[1].set_title('Space Heating Demand')
add_cbar(axs[1], 'Reds', gdf_buildings['SPEC_SPACE_HEAT'], r'$\frac{kWh}{m^2 \cdot year}$')

gdf_buildings.plot(ax=axs[2], column='SPEC_SPACE_COOL', cmap='Blues', edgecolor='black', linewidth=lw)
axs[2].set_title('Space Cooling Demand')
add_cbar(axs[2], 'Blues', gdf_buildings['SPEC_SPACE_COOL'], r'$\frac{kWh}{m^2 \cdot year}$')

if save:
    plt.savefig(out_folder + 'building_demand.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_demand.png', bbox_inches='tight')
plt.show()

# Building resources
fig, axs = plt.subplots(1, 4, figsize=(80, 20))
plt.subplots_adjust(wspace=-0.3)

gdf_buildings.plot(ax=axs[0], column='GEOTHERMAL_ACCESS', cmap=binary_cmap('orange'))
axs[0].set_title('Geothermal Access')

gdf_buildings.plot(ax=axs[1], column='AQUATHERMAL_ACCESS', cmap=binary_cmap('blue'))
gdf_canal.plot(ax=axs[1], color='lightblue', label='Canal')
gdf_senne.plot(ax=axs[1], color='lightblue', label='Senne')
axs[1].set_title('Aquathermal Access')

gdf_buildings.plot(ax=axs[2], column='RIOTHERMAL_ACCESS', cmap=binary_cmap('green'))
gdf_sewers.plot(ax=axs[2], color='darkgreen', linewidth=2, label='Sewers')
axs[2].set_title('Riothermal Access')

gdf_buildings.plot(ax=axs[3], column='FATAL_HEAT_ACCESS', cmap=binary_cmap('red'))
axs[3].set_title('Fatal Heat Access')

if save:
    plt.savefig(out_folder + 'building_resources.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_resources.png', bbox_inches='tight')
plt.show()

# Geothermal access
fig, ax = plt.subplots()
gdf_buildings.plot(ax=ax, column='GEOTHERMAL_ACCESS', cmap=binary_cmap('orange'))
if save:
    plt.savefig(out_folder + 'building_geothermal_access.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_geothermal_access.png', bbox_inches='tight')
plt.show()

# Aquathermal access
fig, ax = plt.subplots()
gdf_buildings.plot(ax=ax, column='AQUATHERMAL_ACCESS', cmap=binary_cmap('blue'))
gdf_canal.plot(ax=ax, color='lightblue', label='Canal')
gdf_senne.plot(ax=ax, color='lightblue', label='Senne')
canal_patch = mpatches.Patch(color='lightblue', label='Canal')
senne_line = mlines.Line2D([], [], color='lightblue', label='Senne')
ax.legend(handles=[canal_patch, senne_line], loc='upper right')
if save:
    plt.savefig(out_folder + 'building_aquathermal_access.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_aquathermal_access.png', bbox_inches='tight')
plt.show()

# Riothermal access
fig, ax = plt.subplots()
gdf_buildings.plot(ax=ax, column='RIOTHERMAL_ACCESS', cmap=binary_cmap('green'))
gdf_sewers.plot(ax=ax, color='darkgreen', linewidth=2, label='Sewers')
ax.legend(loc='upper right')
if save:
    plt.savefig(out_folder + 'building_riothermal_access.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_riothermal_access.png', bbox_inches='tight')
plt.show()

# Fatal heat access
fig, ax = plt.subplots()
gdf_buildings.plot(ax=ax, column='FATAL_HEAT_ACCESS', cmap=binary_cmap('red'))
if save:
    plt.savefig(out_folder + 'building_fatal_heat_access.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_fatal_heat_access.png', bbox_inches='tight')
plt.show()

# Building features
fig, axs = plt.subplots(1, 2, figsize=(40, 20))
plt.subplots_adjust(wspace=-0.2)

gdf_buildings.plot(ax=axs[1], column='LISTED', cmap=binary_cmap('purple'))
axs[1].set_title('Listed Buildings')

gdf_buildings.plot(ax=axs[0], column='TYPE', cmap='tab10', legend=True)
axs[0].set_title('Building Type')

legend = axs[0].get_legend()
handles = legend.legend_handles
labels = [t.get_text() for t in legend.get_texts()]
legend.remove()

fig.legend(handles, labels, loc='lower right', bbox_to_anchor=(0.58, 0.12), fontsize=25, ncol=2)

if save:
    plt.savefig(out_folder + 'building_architecture.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_architecture.png', bbox_inches='tight')
plt.show()
# %%

# Building demand evolution
fig, axs = plt.subplots(1, 2, figsize=(40, 20))
plt.subplots_adjust(wspace=-0.3)

lw = 0.5
lw_listed = 3.5*lw

vmin = min(gdf_buildings_demand['HEAT_VOLUME_2020'].min(), gdf_buildings_demand['HEAT_VOLUME_2050'].min())
vmax = max(gdf_buildings_demand['HEAT_VOLUME_2020'].max(), gdf_buildings_demand['HEAT_VOLUME_2050'].max())

cmap = plt.cm.Reds
norm = colors.Normalize(vmin=vmin, vmax=vmax)

gdf_buildings_demand.plot(ax=axs[0], column='HEAT_VOLUME_2020', cmap=cmap, norm=norm, edgecolor='black', linewidth=lw)
gdf_buildings_demand.query("LISTED == 1").plot(ax=axs[0], facecolor='none', edgecolor='k', linewidth=lw_listed)
axs[0].set_title('Heating Demand 2020')

gdf_buildings_demand.plot(ax=axs[1], column='HEAT_VOLUME_2050', cmap=cmap, norm=norm, edgecolor='black', linewidth=lw)
gdf_buildings_demand.query("LISTED == 1").plot(ax=axs[1], facecolor='none', edgecolor='k', linewidth=lw_listed)
axs[1].set_title('Heating Demand 2050')

cbar = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axs, orientation='horizontal', fraction=0.03, pad=0.0)
cbar.set_label(r'Heating Demand $\left[\frac{MWh}{year}\right]$', fontsize=30)
cbar.ax.tick_params(labelsize=25)
cbar.outline.set_edgecolor('black')
cbar.outline.set_linewidth(1)

listed_patch = plt.Line2D([0], [0], color='k', lw=lw_listed, label='Listed Buildings')
plt.legend(handles=[listed_patch], loc='upper right', fontsize=25)

if save:
    plt.savefig(out_folder + 'building_demand_evolution.pdf', bbox_inches='tight')
    plt.savefig(out_folder + 'building_demand_evolution.png', bbox_inches='tight')
plt.show()

# %%
