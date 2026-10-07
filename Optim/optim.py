# -*- coding: utf-8 -*-
"""
District-heating network design via Price-Collecting Steiner Tree.

Pipeline:
  1. load demand results (buildings, street edges, nodes, connections)
  2. rename ids to typed strings (B…/N…/S…)
  3. split each street at its connection points, add connection edges
  4. compute per-building VALUE (NPV of switching to geothermal) and per-edge COST
  5. solve the rooted PCST with pcst_fast
  6. inspect / plot the resulting tree

@author: jhachez
"""

# %% imports
import matplotlib.cm as cm
from collections import defaultdict
import folium
from folium.plugins import GroupedLayerControl
import geopandas as gpd
import importlib
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np
import pandas as pd
from pcst_fast import pcst_fast
import process
import re
from shapely.geometry import LineString, Point
from shapely.ops import substring
importlib.reload(process)
from scipy.interpolate import interp1d
import matplotlib.animation as animation
from itertools import product

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.size": 11,
    "axes.titleweight": "normal",   # <-- fixes the bold-fallback issue
    "figure.titleweight": "normal", # <-- same fix for suptitle
})
#%%
# import os
# import shutil
# os.environ["PATH"] += os.pathsep + "/Library/TeX/texbin"
# print(shutil.which("latex"))

#%%

def plot_html_maps(gdf_connections = None,
                   gdf_buildings = None,
                   gdf_edges = None,
                   gdf_nodes = None, 
                   filename = None):
    # create the base map yourself
    m = folium.Map(location=[50.8503, 4.3517], zoom_start=14, tiles="CartoDB positron")

    # now pass it in via m=
    if not (gdf_connections is None):
        gdf_connections.explore(
            m=m,
            color="blue",
            style_kwds=dict(weight=1.5),
            tooltip=["BUILDING_ID", "EDGE_ID"],
            name="street edges",
        )
    
    if not (gdf_buildings is None):
        gdf_buildings.explore(
            m=m,
            color = 'gray',
            tooltip=["BUILDING_ID"]
        )

    if not (gdf_edges is None):
        gdf_edges.explore(
            m=m,
            color = 'blue',
            tooltip=["EDGE_ID",'NODE_START', 'NODE_END']
        )
    if not (gdf_nodes is None):
        gdf_nodes.explore(
            m=m,
            color = 'blue',
            tooltip=["NODE_ID"]
        )
    if filename is not None:
        m.save(f'Output/html_maps/{filename}')
    else:
        m.show_in_browser()

def import_original(plot=False, plot_filename=None):

    res_folder = '../Demand/Res'
    gdf_buildings   = process.load_gdf(res_folder + '/Buildings_Demand.feather')
    gdf_edges       = process.load_gdf(res_folder + '/Edges.feather')
    gdf_nodes       = process.load_gdf(res_folder + '/Nodes.feather')
    gdf_connections = process.load_gdf(res_folder + '/Connections.feather')

    if plot:
        plot_html_maps(gdf_connections, gdf_buildings, gdf_edges, gdf_nodes, filename=plot_filename)

    return gdf_buildings, gdf_edges, gdf_nodes, gdf_connections

def split_data(gdf_buildings):
    gdf_buildings = clean_duplicate_buildings(gdf_buildings)

    # disaggregating to get only consumption
    gdf_building_cons = gdf_buildings[['BUILDING_ID', 'HEAT_VOLUME_2020', 'HEAT_CAPACITY_2020',
       'HEAT_VOLUME_2030', 'HEAT_CAPACITY_2030', 'HEAT_VOLUME_2040',
       'HEAT_CAPACITY_2040', 'HEAT_VOLUME_2050', 'HEAT_CAPACITY_2050']]
    df_long = pd.wide_to_long(
        gdf_building_cons,
        stubnames=['HEAT_VOLUME', 'HEAT_CAPACITY'],
        i='BUILDING_ID',
        j='year',
        sep='_'
    ).reset_index().rename(columns={'HEAT_VOLUME': 'volume', 'HEAT_CAPACITY': 'capacity'})
    
    df_long = df_long[['BUILDING_ID', 'year', 'capacity', 'volume']]

    # computing equivalent full load hours
    eflh = df_long[['year','volume']].groupby(by=['year']).sum()
    eflh['eflh'] = (1e3 * eflh['volume'] / df_long['capacity'].loc[df_long['year']==2030].sum())
    eflh = eflh.drop(columns=['volume']).reset_index()

    # computing acccesses
    gdf_building_prod = gdf_buildings[['BUILDING_ID', 
       'AQUATHERMAL_ACCESS', 'RIOTHERMAL_ACCESS']].rename(columns = {'AQUATHERMAL_ACCESS':'WSHP', 'RIOTHERMAL_ACCESS':'RIOTHERMAL'}, )
    
    gdf_building_prod = pd.melt(gdf_building_prod, id_vars=['BUILDING_ID'], value_vars=["WSHP",'RIOTHERMAL'])
    gdf_building_prod = gdf_building_prod[gdf_building_prod['value'] == 1].rename(columns={'variable':'tech','value':'power_MW_th'})
    
    gdf_building_prod[['power_MW_th']] = gdf_building_prod[['power_MW_th']].astype(float)
    gdf_building_prod.loc[gdf_building_prod['tech'] == 'WSHP', 'power_MW_th']               = 15.00 # MW
    gdf_building_prod.loc[gdf_building_prod['tech'] == 'RIOTHERMAL_ACCESS','power_MW_th']   = 0.05 # MW
    gdf_building_prod.loc[gdf_building_prod['tech'] == 'FATAL_HEAT_ACCESS','power_MW_th']   = 0.10 # MW

    # adding custom data
    df = pd.read_excel('tech_locations.xlsx', sheet_name='building_access')[['BUILDING_ID','tech','power (MW_th)']].rename(columns={'power (MW_th)':'power_MW_th'})
    gdf_building_prod = pd.concat([df,gdf_building_prod])

    return eflh, df_long.drop(columns=['capacity']), gdf_building_prod

def _interp_extrapolate(series):
    valid = series.dropna()
    if len(valid) < 2:
        return series  # not enough points to fit a line
    f = interp1d(valid.index, valid.values, kind='linear', fill_value='extrapolate')
    return pd.Series(f(series.index), index=series.index)

def interpolate_building_cons(df, years=None, id_col='BUILDING_ID', year_col='year', value_col='volume'):
    if years is None:
        years = range(int(df[year_col].min()), int(df[year_col].max()) + 1)

    full_index = pd.MultiIndex.from_product(
        [df[id_col].unique(), years], names=[id_col, year_col]
    )

    df_full = (
        df.set_index([id_col, year_col])
        .reindex(full_index)
        .reset_index()
    )

    # apply extrapolation per building, returns Series indexed by (BUILDING_ID, year)
    interp_result = (
        df_full.groupby(id_col)
        .apply(lambda g: _interp_extrapolate(g.set_index(year_col)[value_col]))
    )

    # interp_result is a Series with MultiIndex (BUILDING_ID, year) -> safe to map back
    interp_result = interp_result.stack() if isinstance(interp_result, pd.DataFrame) else interp_result
    interp_result.index.names = [id_col, year_col]
    interp_result = interp_result.rename(value_col).reset_index()

    df_full = df_full.drop(columns=[value_col]).merge(interp_result, on=[id_col, year_col], how='left')

    return df_full

def interpolate_eflh(eflh, years=None, year_col='year', value_col='eflh'):
    if years is None:
        years = range(int(eflh[year_col].min()), int(eflh[year_col].max()) + 1)

    eflh_full = (
        eflh.set_index(year_col)
        .reindex(years)
        .rename_axis(year_col)
        .reset_index()
    )

    eflh_full[value_col] = _interp_extrapolate(
        eflh_full.set_index(year_col)[value_col]
    ).values

    return eflh_full

def clean_duplicate_buildings(gdf_buildings):
    gdf_buildings['BUILDING_ID'][gdf_buildings['BUILDING_ID'].duplicated()]
    gdf_buildings.loc[gdf_buildings['BUILDING_ID'] == '1622342']
    gdf_buildings.drop_duplicates(subset = 'BUILDING_ID', inplace=True)
    gdf_buildings['BUILDING_ID'][gdf_buildings['BUILDING_ID'].duplicated()]
    return gdf_buildings

def compute_price_df(DISCOUNT_RATE, plot=False):
    SC_CO2 = {2030:150, 2040:175, 2050:200} # Estimated from Mimi.jl Chart (USD/tCO2)
    CCGT_emission_factor = 0.4 # taken from Gemini (tCO2/MWh)
    NG_emission_factor = 0.2 # taken from Gemini (tCO2/MWh)

    years = [2030, 2040, 2050]
    df_yearly = pd.DataFrame(index = [2030, 2040, 2050], columns=['SC_CO2','CO2_elec','elec_commodity'])

    for year in years:
        mp = pd.read_csv(f'marginal_price_results/marginal_price_t2m_co2_{year}.csv', parse_dates= True, index_col='time')
        marginal_gas = mp['AC (EUR/MWh)'] > 40
        mp.loc[marginal_gas, 'AC (EUR/MWh)'] *= 2 # gas price is closer to 80 EUR/MWh --> double the reported value
        mp.loc[marginal_gas, 'AC (EUR/MWh)'] += SC_CO2[year] * CCGT_emission_factor # adding CO2 cost
        mp['date'] = mp.index.date
        mp = mp.groupby('date').mean().reset_index()

        # mp['AC (EUR/MWh)'].plot()
        mp['HDD'] = 15 - mp['T2m (C)']
        mp.loc[mp['HDD'] < 0, 'HDD'] = 0 # rows where HDD < 0, column 'HDD'

        df_yearly.loc[year,'elec_commodity']    = (mp['HDD'] @ mp['AC (EUR/MWh)']) / mp['HDD'].sum()
        df_yearly.loc[year,'SC_CO2']            = SC_CO2[year]
        df_yearly.loc[year,'CO2_elec']          = (mp['HDD'] @ mp['grid CO2 intensity (tCO2/MWh)']) / mp['HDD'].sum()
        

    # return mp_2030
    full_index = np.arange(2030, 2060)
    df_yearly = df_yearly.apply(pd.to_numeric, errors='coerce')
    df_yearly = df_yearly.reindex(full_index)
    df_yearly = df_yearly.interpolate(method='linear')

    discount_factor = (1.0 + DISCOUNT_RATE) ** (df_yearly.index-YEAR_TODAY)
    df_yearly['elec_transport'] =      21.4 * discount_factor
    df_yearly['elec_distribution'] =   93.9 * discount_factor

    df_yearly['gas_commodity'] =       40.0 + df_yearly['SC_CO2'] * NG_emission_factor
    df_yearly['gas_transport'] =        1.6 * discount_factor
    df_yearly['gas_distribution'] =    18.8 * discount_factor
    
    if plot:
        plot_price_df(df_yearly)

    return df_yearly

def plot_price_df(df_yearly):
    fig, axs = plt.subplots(ncols=2, figsize = (10,4))


    cmap = plt.cm.Blues
    n = 3  # number of columns/areas
    colors = [cmap(x) for x in np.linspace(0.35, 0.85, n)]
    df_yearly[['elec_commodity','elec_transport','elec_distribution']].rename(columns={'elec_commodity':'Commodity','elec_transport':'Transport','elec_distribution':'Distribution'}).plot(kind='area',stacked='true', color=colors, ax = axs[0])
    axs[0].set_title('Weighted average electricity cost')

    axs[0].set_frame_on(False)
    axs[0].grid()
    axs[0].set_ylabel('Electricity cost €/MWh')
    axs[0].set_xlabel('Years')
    axs[0].set_ylim(0,450)

    cmap = plt.cm.Reds
    n = 3  # number of columns/areas
    colors = [cmap(x) for x in np.linspace(0.35, 0.85, n)]
    df_yearly[['gas_commodity','gas_transport','gas_distribution']].rename(columns={'gas_commodity':'Commodity','gas_transport':'Transport','gas_distribution':'Distribution'}).plot(kind='area',stacked='true', color=colors, ax = axs[1])
    axs[1].set_title('Gas cost evolution')
    axs[1].set_frame_on(False)
    axs[1].grid()
    axs[1].set_ylabel('Gas cost €/MWh')
    axs[1].set_xlabel('Years')
    axs[1].set_ylim(0,450)
    fig.suptitle('Evolution of energy costs for 2030-2059')

    fig.savefig('Output/Energy_prices.pdf')

def include_connections(gdf_buildings, 
                        gdf_nodes, 
                        gdf_edges, 
                        gdf_connections, 
                        plot = False, 
                        unique_conn = True):

    # keep only line connections (drop stray points/multipoints)
    gdf_connections = gdf_connections[
        ~gdf_connections.geom_type.isin(['Point', 'MultiPoint'])
    ]

    if unique_conn:
        gdf_connections = (
            gdf_connections
            .assign(_len=gdf_connections.length) # compute connection length
            .sort_values('_len') # shortest first
            .drop_duplicates('BUILDING_ID', keep='first') # keep shortest per building
            .drop(columns='_len')
            .reset_index(drop=True)
        )

    new_buildings   = gdf_buildings.copy()
    new_nodes       = gdf_nodes.copy()
    new_edges       = gdf_edges.copy()
    new_connections = gdf_connections.copy()
    new_edges['type'] = 'street'

    node_map = {old: f"N{old:05d}" for old in new_nodes["NODE_ID"]}
    edge_map = {old: f"S{old:04d}" for old in new_edges["EDGE_ID"]}

    new_buildings["BUILDING_ID"] = "B" + new_buildings["BUILDING_ID"].astype(str)

    new_nodes["NODE_ID"] = new_nodes["NODE_ID"].map(node_map)

    new_edges["EDGE_ID"]    = new_edges["EDGE_ID"].map(edge_map)
    new_edges["NODE_START"] = new_edges["NODE_START"].map(node_map)
    new_edges["NODE_END"]   = new_edges["NODE_END"].map(node_map)

    new_connections["BUILDING_ID"] = "B" + new_connections["BUILDING_ID"].astype(str)
    new_connections["EDGE_ID"]     = new_connections["EDGE_ID"].map(edge_map)
    new_connections.index = [f"C{i:05d}" for i in range(len(new_connections))]

    # Any street endpoint that didn't map is unusable downstream (would become NaN,
    # silently corrupting both the solver input and the connectivity checks). Drop it.
    _bad = new_edges["NODE_START"].isna() | new_edges["NODE_END"].isna()
    if _bad.any():
        print(f"WARNING: dropping {_bad.sum()} street edges with unmapped nodes")
        new_edges = new_edges.loc[~_bad].copy()

    next_node_id = max(int(x[1:]) for x in new_nodes["NODE_ID"]) + 1
    next_edge_id = max(int(x[1:]) for x in new_edges["EDGE_ID"]) + 1

    new_nodes_to_add = []
    new_edges_to_add = []
    edges_to_remove  = set()

    processed       = 0   # connection edges created
    skipped_no_edge = 0   # connection whose street EDGE_ID wasn't found
    skipped_split   = 0   # zero-length street segment skipped

    # ---- pass 1: group every connection by the street it lands on --------------
    # street_id -> [(distance_along_street, building_id, attach_point, building_point)]
    attachments = defaultdict(list)

    for _, conn in new_connections.iterrows():
        match = new_edges.loc[new_edges["EDGE_ID"] == conn["EDGE_ID"]]
        if len(match) == 0:
            skipped_no_edge += 1
            continue

        street_geom = match.iloc[0].geometry
        p0 = Point(conn.geometry.coords[0])
        p1 = Point(conn.geometry.coords[-1])

        # the connection endpoint nearer the street is the attach side
        if street_geom.distance(p0) <= street_geom.distance(p1):
            street_pt, building_pt = p0, p1
        else:
            street_pt, building_pt = p1, p0

        d = street_geom.project(street_pt)
        attach_pt = street_geom.interpolate(d)
        attachments[conn["EDGE_ID"]].append(
            (d, conn["BUILDING_ID"], attach_pt, building_pt)
        )

    # ---- pass 2: split each street ONCE through all its attach points ----------
    TOL = 1e-6
    for street_id, atts in attachments.items():

        edge_row = new_edges.loc[new_edges["EDGE_ID"] == street_id].iloc[0]
        street_geom = edge_row.geometry

        # --------------------------------------------------------
        # Ensure LineString orientation matches NODE_START -> NODE_END
        # --------------------------------------------------------
        start_node_geom = new_nodes.loc[
            new_nodes["NODE_ID"] == edge_row["NODE_START"],
            "geometry"
        ].iloc[0]

        end_node_geom = new_nodes.loc[
            new_nodes["NODE_ID"] == edge_row["NODE_END"],
            "geometry"
        ].iloc[0]

        start_pt = Point(street_geom.coords[0])
        end_pt = Point(street_geom.coords[-1])

        if (
            start_pt.distance(end_node_geom) <
            start_pt.distance(start_node_geom)
        ):
            # Geometry is reversed
            street_geom = LineString(list(street_geom.coords)[::-1])

        # --------------------------------------------------------
        # Recompute projected distances on the corrected geometry
        # --------------------------------------------------------
        atts2 = []

        for _, building_id, attach_pt, building_pt in atts:
            d = street_geom.project(attach_pt)
            attach_pt = street_geom.interpolate(d)
            atts2.append((d, building_id, attach_pt, building_pt))

        atts = sorted(atts2, key=lambda x: x[0])

        edges_to_remove.add(street_id)

        prev_node = edge_row["NODE_START"]
        prev_dist = 0.0

        node_at_dist = {}

        for d, building_id, attach_pt, building_pt in atts:

            key = round(d / TOL)

            if key in node_at_dist:

                node = node_at_dist[key]

            else:

                node = f"N{next_node_id:05d}"
                next_node_id += 1

                new_nodes_to_add.append({
                    "NODE_ID": node,
                    "geometry": attach_pt
                })

                node_at_dist[key] = node

                seg = substring(street_geom, prev_dist, d)

                if (
                    seg.geom_type == "LineString"
                    and seg.length > TOL
                ):

                    new_edges_to_add.append({
                        "EDGE_ID": f"S{next_edge_id:04d}",
                        "NODE_START": prev_node,
                        "NODE_END": node,
                        "geometry": seg,
                        "type": "street",
                    })

                    next_edge_id += 1

                else:
                    skipped_split += 1

                prev_node = node
                prev_dist = d

            new_edges_to_add.append({
                "EDGE_ID": f"S{next_edge_id:04d}",
                "NODE_START": node,
                "NODE_END": building_id,
                "geometry": LineString([attach_pt, building_pt]),
                "type": "connection",
            })

            next_edge_id += 1
            processed += 1

        seg = substring(street_geom, prev_dist, street_geom.length)

        if (
            seg.geom_type == "LineString"
            and seg.length > TOL
        ):

            new_edges_to_add.append({
                "EDGE_ID": f"S{next_edge_id:04d}",
                "NODE_START": prev_node,
                "NODE_END": edge_row["NODE_END"],
                "geometry": seg,
                "type": "street",
            })

            next_edge_id += 1

        else:
            skipped_split += 1

    # ---- commit additions ------------------------------------------------------
    new_nodes = pd.concat(
        [new_nodes,
        gpd.GeoDataFrame(new_nodes_to_add, geometry="geometry", crs=new_nodes.crs)],
        ignore_index=True,
    )

    new_edges = pd.concat(
        [new_edges.loc[~new_edges["EDGE_ID"].isin(edges_to_remove)].copy(),
        gpd.GeoDataFrame(new_edges_to_add, geometry="geometry", crs=new_edges.crs)],
        ignore_index=True,
    )

    assert (new_edges.geom_type == "LineString").all(), "non-line geometry in new_edges"
    if plot == True:
        plot_html_maps(gdf_buildings=new_buildings,
                       gdf_edges=new_edges,
                       gdf_nodes=new_nodes)
    return new_nodes, new_buildings, new_edges

def trench_cost(gdf_edges, 
                COST_TRENCH   = 1e3):
    e = gdf_edges.copy()
    e['Edge length m'] = (e.length) 
    e['Edge cost €'] = (e.length * COST_TRENCH) 
    return e

def optimize_network(eflh, 
                    df_building_cons, 
                    df_building_prod, 
                    df_primary_prices, 
                    gdf_intersections,
                    gdf_buildings,
                    gdf_edges,
                    benchmark, 
                    DISCOUNT_RATE, 
                    YEAR_TODAY,
                    COST_OF_HEAT,
                    COST_TRENCH,
                    ROOT,
                    indexing_heat_cost = False):
    
    connction_value = trench_cost(gdf_edges = gdf_edges, 
                                COST_TRENCH = COST_TRENCH)
    
    building_value, df_capa_profit, df_prod_opex, df_cons = define_building_value(eflh, 
                                                                    df_building_cons, 
                                                                    df_building_prod, 
                                                                    df_primary_prices, 
                                                                    benchmark = benchmark, 
                                                                    DISCOUNT_RATE = DISCOUNT_RATE, 
                                                                    YEAR_TODAY = YEAR_TODAY,
                                                                    COST_OF_HEAT = COST_OF_HEAT,
                                                                    indexing_heat_cost = indexing_heat_cost)
    

    gdf_sel_buildings, gdf_sel_connection, gdf_sel_intersections = run_pcst(connction_value,
                                                                            gdf_intersections,
                                                                            gdf_buildings,
                                                                            building_value,
                                                                            ROOT)
    
    building_value_sel =    pd.merge(building_value,gdf_sel_buildings[['BUILDING_ID','selected']])
    df_capa_profit_sel =    pd.merge(df_capa_profit,gdf_sel_buildings[['BUILDING_ID','selected']])
    df_prod_opex_sel =      pd.merge(df_prod_opex,gdf_sel_buildings[['BUILDING_ID','selected']])
    df_cons_sel =           pd.merge(df_cons,gdf_sel_buildings[['BUILDING_ID','selected']])
    # return 0,0,0,0,0,0
    return pd.merge(gdf_buildings,building_value_sel), df_capa_profit_sel, df_prod_opex_sel, df_cons_sel, gdf_sel_intersections, gdf_sel_connection
     
def define_building_value(
    eflh, 
    df_building_cons, 
    df_building_prod, 
    df_primary_prices, 
    benchmark, 
    DISCOUNT_RATE, 
    YEAR_TODAY,
    COST_OF_HEAT,
    indexing_heat_cost = True):
    

    # Computing consumption value
    if benchmark == 'ASHP':
        elec_residential = df_primary_prices[['elec_commodity','elec_transport','elec_distribution']].sum(axis = 1)
        SCOP = 2.5
        benchmark_lcoh = (elec_residential / SCOP).rename('lcoh')
    elif benchmark == 'NG':
        gas_residential = df_primary_prices[['gas_commodity','gas_transport','gas_distribution']].sum(axis = 1)
        eta_boiler = 1.06
        benchmark_lcoh = (gas_residential / eta_boiler).rename('lcoh')
    else:
        raise ValueError(f"Unknown benchmark '{benchmark}'")

    df_building_cons_interp = interpolate_building_cons(df = df_building_cons, years=range(2030,2060),id_col='BUILDING_ID',year_col='year',value_col='volume')
    expenses = pd.merge(left = benchmark_lcoh, right=df_building_cons_interp, left_index=True,right_on='year')
    
    if indexing_heat_cost:
        expenses['Expenses Heat €/MWh'] = COST_OF_HEAT * ((1 + DISCOUNT_RATE) ** (expenses['year'] - YEAR_TODAY))
    else:
        expenses['Expenses Heat €/MWh'] = COST_OF_HEAT
    expenses['Discounted difference €/MWh'] = (expenses['lcoh'] - expenses['Expenses Heat €/MWh']) / ((1 + DISCOUNT_RATE) ** (expenses['year'] - YEAR_TODAY))
    expenses['Potential consumption MWh'] = expenses['volume'] * (expenses['Discounted difference €/MWh']>0).astype(float)
    expenses['Potential savings €'] = expenses['Discounted difference €/MWh'] * expenses['Potential consumption MWh']
    

    # --- Adapt the cost to the size of the plants ---
    tech_df = pd.read_excel('tech_locations.xlsx', sheet_name='technologies')[['tech','primary','Nominal power MW','capex (MEUR/MW_th)','efficiency_th (MW_th/MW_prim)','efficiency_e (MW_e/MW_prim)','Variable o&m (€/MWh_th)','Fixed o&m (€/MW_th)']]
    
    interp_cols = [
        'efficiency_th (MW_th/MW_prim)',
        'efficiency_e (MW_e/MW_prim)',
        'Variable o&m (€/MWh_th)',
        'Fixed o&m (€/MW_th)',
        'capex (MEUR/MW_th)'
    ]

    def build_tech_curve(tech, catalogue):
        """Return sorted (x, y-dict) reference points for a given tech."""
        cat_tech = catalogue[catalogue['tech'] == tech].dropna(subset=['Nominal power MW']).copy()
        if cat_tech.empty:
            return None

        # equivalent thermal power scale for catalogue entries
        cat_tech['thermal_power_MW'] = (
            cat_tech['Nominal power MW'] * cat_tech['efficiency_th (MW_th/MW_prim)']
        )
        cat_tech = cat_tech.sort_values('thermal_power_MW')
        return cat_tech

    def interpolate_row(row, catalogue, cache={}):
        tech = row['tech']

        if tech not in cache:
            cache[tech] = build_tech_curve(tech, catalogue)
        cat_tech = cache[tech]

        if cat_tech is None:
            return pd.Series({col: np.nan for col in interp_cols})

        x_ref = cat_tech['thermal_power_MW'].values
        x_target = row['power_MW_th']

        result = {}
        for col in interp_cols:
            y_ref = cat_tech[col].values
            result[col] = np.interp(x_target, x_ref, y_ref)

        return pd.Series(result)

    interpolated = df_building_prod.apply(lambda r: interpolate_row(r, tech_df), axis=1)
    df_plants_result = pd.concat([df_building_prod, interpolated], axis=1)

    tech_opex = pd.merge(
        df_plants_result,
        df_primary_prices.index.to_frame(index=False, name="year"),
        how="cross"
    ).merge(tech_df[['tech','primary']].drop_duplicates().rename(columns={'tech':'tech'}))

    tech_operational = tech_opex[['BUILDING_ID',
                                'tech',
                                'primary',
                                'power_MW_th',
                                'year',
                                'efficiency_th (MW_th/MW_prim)',
                                'efficiency_e (MW_e/MW_prim)',
                                'Variable o&m (€/MWh_th)',
                                'Fixed o&m (€/MW_th)']]
    
    # --- Precompute price series indexed by year (source of truth for alignment) ---
    elec_full_cost   = df_primary_prices[['elec_commodity', 'elec_transport', 'elec_distribution']].sum(axis=1)
    elec_no_dist_cost = df_primary_prices[['elec_commodity', 'elec_transport']].sum(axis=1)
    elec_commodity_cost = df_primary_prices['elec_commodity']

    # --- Tech masks ---
    is_ASHP   = tech_operational['tech']    == 'ASHP'
    is_pellet = tech_operational['primary'] == 'pellet'
    is_electricity  = ~(is_ASHP | is_pellet)   # logical OR, not addition

    # --- Marginal cost, aligned explicitly by 'year' via .map() ---
    tech_operational['Cost of production €/MWh'] = 0.0

    tech_operational.loc[is_ASHP, 'Cost of production €/MWh'] = (
        tech_operational.loc[is_ASHP, 'year'].map(elec_no_dist_cost).values
        / tech_operational.loc[is_ASHP, 'efficiency_th (MW_th/MW_prim)'].astype(float).values
    )

    tech_operational.loc[is_pellet, 'Cost of production €/MWh'] = (
        40 / tech_operational.loc[is_pellet, 'efficiency_th (MW_th/MW_prim)'].astype(float).values
        # - tech_operational.loc[is_pellet, 'year'].map(elec_commodity_cost).values
        # * tech_operational.loc[is_pellet, 'efficiency_e (MW_e/MW_prim)'].astype(float).values
        # / tech_operational.loc[is_pellet, 'efficiency_th (MW_th/MW_prim)'].astype(float).values
    )

    tech_operational.loc[is_electricity, 'Cost of production €/MWh'] = (
        tech_operational.loc[is_electricity, 'year'].map(elec_full_cost).values
        / tech_operational.loc[is_electricity, 'efficiency_th (MW_th/MW_prim)'].astype(float).values
    )

    tech_operational['Revenues Electricity €/MWh'] = (tech_operational.loc[:, 'year'].map(elec_commodity_cost).values
        * tech_operational.loc[:, 'efficiency_e (MW_e/MW_prim)'].astype(float).values
        / tech_operational.loc[:, 'efficiency_th (MW_th/MW_prim)'].astype(float).values)

    if indexing_heat_cost:
        tech_operational['Revenues Heat €/MWh'] = COST_OF_HEAT * ((1 + DISCOUNT_RATE) ** (tech_operational['year'] - YEAR_TODAY))
    else:
        tech_operational['Revenues Heat €/MWh'] = COST_OF_HEAT
    

    tech_operational['Contribution Margin €/MWh'] = tech_operational['Revenues Heat €/MWh'] + tech_operational['Revenues Electricity €/MWh'] - tech_operational['Cost of production €/MWh'] - tech_operational['Variable o&m (€/MWh_th)']


    
    
    eflh = eflh.rename(columns={0: 'eflh'})
    eflh_interp = interpolate_eflh(eflh, years=range(2030, 2060))
    df_prod_opex = tech_operational.merge(eflh_interp, left_on='year', right_on='year')
    df_prod_opex['producible'] = df_prod_opex['power_MW_th'] * df_prod_opex['eflh']
    df_prod_opex['Potential Production MWh'] = df_prod_opex['producible'].astype(float) * (df_prod_opex['Contribution Margin €/MWh'] > 0).astype(float)


    df_prod_opex['Discounted Revenues Heat €'] = df_prod_opex['Potential Production MWh'].astype(float) * (df_prod_opex['Revenues Heat €/MWh']).astype(float)  / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))
    df_prod_opex['Discounted Revenues Electricity €'] = df_prod_opex['Potential Production MWh'].astype(float) * (df_prod_opex['Revenues Electricity €/MWh']).astype(float)  / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))
    df_prod_opex['Discounted Cost of production €'] = df_prod_opex['Potential Production MWh'].astype(float) * (df_prod_opex['Cost of production €/MWh']).astype(float)  / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))
    df_prod_opex['Discounted Variable o&m €'] = df_prod_opex['Potential Production MWh'].astype(float) * (df_prod_opex['Variable o&m (€/MWh_th)']).astype(float)  / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))
    df_prod_opex['Discounted Contribution Margin €'] = df_prod_opex['Potential Production MWh'].astype(float) * (df_prod_opex['Contribution Margin €/MWh']).astype(float)  / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))


    df_prod_opex['Discounted Fixed o&m €'] = df_prod_opex['Fixed o&m (€/MW_th)'] * df_prod_opex['power_MW_th'] / ((1 + DISCOUNT_RATE) ** (df_prod_opex['year'] - YEAR_TODAY))
    _grouped = df_prod_opex[['BUILDING_ID','tech','power_MW_th','Discounted Contribution Margin €', 'Discounted Fixed o&m €']].groupby(by=['BUILDING_ID','tech','power_MW_th']).sum()
    _grouped['Cumulated Discounted Contribution Margin €'] = _grouped['Discounted Contribution Margin €'] - _grouped['Discounted Fixed o&m €']
    df_prod_opex_sum = _grouped[['Cumulated Discounted Contribution Margin €']].reset_index()
    
    # Computing profit - Adding investment cost

    tech_investment = df_plants_result[['BUILDING_ID', 'tech', 'power_MW_th', 'capex (MEUR/MW_th)']]
    df_capa_profit = pd.merge(
        tech_investment,
        df_prod_opex_sum
    )
    df_capa_profit['Capacity Investment €'] = 1e6 * df_capa_profit['capex (MEUR/MW_th)'] * df_capa_profit['power_MW_th']
    df_capa_profit['Net profit €'] = df_capa_profit['Cumulated Discounted Contribution Margin €'] - df_capa_profit['Capacity Investment €']

    # Define profitable buildings
    profitable_tech = df_capa_profit.loc[df_capa_profit['Net profit €'] > 0, ['BUILDING_ID', 'tech']]
    profitable_pairs = set(map(tuple, profitable_tech.values))

    # Remove unprofitable production
    mask_prod = df_prod_opex[['BUILDING_ID', 'tech']].apply(tuple, axis=1).isin(profitable_pairs)
    df_prod_opex.loc[~mask_prod, ['Potential Production MWh','Discounted Contribution Margin €','Discounted Fixed o&m €', 'Discounted Revenues Heat €','Discounted Revenues Electricity €','Discounted Cost of production €','Discounted Variable o&m €']] *= 0
    
    # Remove unprofitable capacities
    mask_capa = df_capa_profit['Net profit €'] < 0
    df_capa_profit.loc[mask_capa, ['power_MW_th', 'Cumulated Discounted Contribution Margin €', 'Capacity Investment €', 'Net profit €']] *= 0
    
    df_profit_sum = df_capa_profit[['BUILDING_ID', 'Net profit €']].groupby(by=['BUILDING_ID']).sum()
    building_value = pd.merge(
        left = df_profit_sum,
        right = expenses[['BUILDING_ID','Potential savings €']].groupby(by=['BUILDING_ID']).sum(),
        left_index=True,
        right_index=True,
        how='outer'
    )
    building_value[building_value.isna()] = 0
    building_value['Node value €'] = building_value['Net profit €'] + building_value['Potential savings €']
    
    return building_value.reset_index(), df_capa_profit, df_prod_opex, expenses

def create_mapping(edges_df, building_df, intersections_df, root):
    assert intersections_df['NODE_ID'].is_unique, "duplicate node id in intersections table"
    assert building_df['BUILDING_ID'].is_unique, "duplicate building id in building table"
    intersections_df['Node value €'] = 0
    """Map all node/building ids to contiguous ints and attach them to edges."""
    mapping_nodes = pd.concat(
        [intersections_df[['NODE_ID','Node value €']],
         building_df[['BUILDING_ID', 'Node value €']].rename(columns={'BUILDING_ID': 'NODE_ID'})],
        ignore_index=True,
    )
    mapping_nodes['new_ID'] = mapping_nodes.index
    assert mapping_nodes['NODE_ID'].is_unique, "duplicate node id in merged table"

    nmap = dict(zip(mapping_nodes['NODE_ID'], mapping_nodes['new_ID']))

    mapping_edges = edges_df.copy()
    mapping_edges['int_NODE_START'] = mapping_edges['NODE_START'].map(nmap)
    mapping_edges['int_NODE_END']   = mapping_edges['NODE_END'].map(nmap)

    # no edge endpoint may be unmapped, or to_numpy(int64) yields garbage
    assert mapping_edges[['int_NODE_START', 'int_NODE_END']].notna().all().all(), \
        "unmapped edge endpoint (NaN) — would corrupt the solver"

    return mapping_nodes, mapping_edges, nmap[root]

def run_pcst(gdf_connection_cost,
             gdf_intersections,
             gdf_buildings,
             building_value,
             ROOT,
             plot = False):

    mapping_nodes, mapping_edges, root_map = create_mapping(
        gdf_connection_cost, building_value, gdf_intersections, ROOT
    )


    E = mapping_edges[['int_NODE_START', 'int_NODE_END']].to_numpy(np.int64)
    prizes = mapping_nodes['Node value €'].clip(lower=0).to_numpy(np.float64)  # pcst needs prizes >= 0
    costs = mapping_edges['Edge cost €'].to_numpy(np.float64)

    vertices, edges = pcst_fast(
        E, prizes, costs,
        root_map,   # root
        1,          # num_clusters
        'strong',   # pruning: 'none' | 'simple' | 'gw' | 'strong'
        0,          # verbosity
    )

    e = np.asarray(edges)
    v = np.asarray(vertices)

    mapping_nodes['selected'] = False
    mapping_nodes.loc[mapping_nodes.index.isin(vertices), 'selected'] = True

    mapping_edges['selected'] = False
    mapping_edges.loc[mapping_edges.index.isin(edges), 'selected'] = True
    
    
    gdf_sel_connection = pd.merge(gdf_connection_cost,mapping_edges[['EDGE_ID','selected']])
    gdf_sel_intersections = pd.merge(gdf_intersections, mapping_nodes[['NODE_ID','selected']])
    gdf_sel_buildings = pd.merge(gdf_buildings, mapping_nodes[['NODE_ID','selected']].rename(columns={'NODE_ID':'BUILDING_ID'}))

    assert isinstance(gdf_buildings, gpd.GeoDataFrame), 'Building is not a geodataframe'
    assert isinstance(gdf_sel_buildings, gpd.GeoDataFrame), 'Selected building is not a geodataframe'
    if plot:
        plot_html_maps(gdf_buildings=gdf_sel_buildings[gdf_sel_buildings['selected']],
                       gdf_edges=gdf_sel_connection[gdf_sel_connection['selected']],
                       gdf_nodes=gdf_sel_intersections[gdf_sel_intersections['selected']])
        
    
    return gdf_sel_buildings, gdf_sel_connection, gdf_sel_intersections

def display_tech_NPV(df_prod_opex_sel,df_capa_profit_sel):

    for tech in df_prod_opex_sel.loc[df_prod_opex_sel['selected'] * (df_prod_opex_sel['Potential Production MWh'] > 0),'tech'].unique():
        df_prod_opex = df_prod_opex_sel[df_prod_opex_sel['tech']==tech].copy()[['BUILDING_ID', 'tech','year','Discounted Revenues Heat €','Discounted Revenues Electricity €', 'Discounted Cost of production €','Discounted Variable o&m €','Discounted Fixed o&m €', 'selected']]
        # add invest
        df_prod_opex['Capacity Investment €'] = 0
        df_invest = df_capa_profit_sel[df_capa_profit_sel['tech']==tech].copy()[['tech','BUILDING_ID','Capacity Investment €','selected']].rename(columns = {'tech':'tech'})
        df_invest['year'] = YEAR_TODAY
        df_invest[['Discounted Revenues Heat €','Discounted Revenues Electricity €', 'Discounted Cost of production €','Discounted Variable o&m €','Discounted Fixed o&m €']] = 0
        df_npv = pd.concat([df_invest,df_prod_opex])
        print(df_npv)
        df_npv.loc[:,['Capacity Investment €','Discounted Cost of production €','Discounted Variable o&m €','Discounted Fixed o&m €']] *= -1

        fig, ax = plt.subplots()
        data = (df_npv.loc[df_npv['selected'],['Capacity Investment €','Discounted Revenues Heat €','Discounted Revenues Electricity €','Discounted Cost of production €','Discounted Variable o&m €','Discounted Fixed o&m €','year']]
                .groupby(by=['year']).sum()/1e6)

        years = data.index.values.astype(float)

        # Plot stacked bars manually at true numeric x positions
        bottom_pos = np.zeros(len(data))
        bottom_neg = np.zeros(len(data))
        bar_width = 0.8  # adjust if years are closely spaced

        colors = {'Capacity Investment €':        ( 90/255,200/255, 90/255),
                'Discounted Revenues Heat €':          ( 90/255, 90/255,230/255), 
                'Discounted Revenues Electricity €':          ( 45/255, 45/255,150/255), 
                'Discounted Cost of production €':(250/255, 10/255, 10/255),
                'Discounted Variable o&m €':      (200/255, 40/255, 40/255),
                'Discounted Fixed o&m €':         (150/255, 70/255, 70/255)}

        for col in data.columns:
            vals = data[col].values
            bottom = np.where(vals >= 0, bottom_pos, bottom_neg)
            ax.bar(years, vals, bottom=bottom, width=bar_width, label=col, color = colors[col])
            bottom_pos += np.where(vals >= 0, vals, 0)
            bottom_neg += np.where(vals < 0, vals, 0)

        # Plot cumulative total using the same numeric x positions
        cumulative = data.sum(axis=1).cumsum()
        breakeven_year = cumulative[cumulative>0].idxmin()
        print(f'Breakeven year {breakeven_year}')
        ax.plot(years, cumulative.values, label='Cumulative Total', color='black', marker='o', linewidth=1)

        ax.legend()
        ax.set_title(f'{tech} exhibits a ROI of {-100*cumulative.iloc[-1]/cumulative.iloc[0]:.1f}%\n Breakeven point in {breakeven_year}')
        ax.grid(True)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.set_ylabel('NPV M€')
        ax.set_xlabel('Years')
    
def progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    percent = f"{100 * (iteration / total):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='')
    
    # Print newline on completion
    if iteration == total:
        print()

def display_heat_geography(gdf_buildings, highlight_heritage=False):
    # Handle zero or missing areas
    gdf_buildings['area'] = gdf_buildings.area

    # Calculate for each year
    gdf_buildings['heat volume 2030 MWh/m2floor'] = gdf_buildings['HEAT_VOLUME_2030'] / gdf_buildings['area'].replace(0, np.nan)
    gdf_buildings['heat volume 2040 MWh/m2floor'] = gdf_buildings['HEAT_VOLUME_2040'] / gdf_buildings['area'].replace(0, np.nan)
    gdf_buildings['heat volume 2050 MWh/m2floor'] = gdf_buildings['HEAT_VOLUME_2050'] / gdf_buildings['area'].replace(0, np.nan)

    vmax = 1.0
    # Filter out invalid geometries
    gdf_buildings = gdf_buildings[gdf_buildings.area > 0]

    # Create figure and subplots (3 heat maps + 1 heritage map)
    n_subplots = 4 if highlight_heritage else 3
    fig, axes = plt.subplots(1, n_subplots, figsize=(14.5, 6) if highlight_heritage else (11, 6))

    # Define years
    years = [
        ('2030', 'heat volume 2030 MWh/m2floor'),
        ('2040', 'heat volume 2040 MWh/m2floor'),
        ('2050', 'heat volume 2050 MWh/m2floor')
    ]

    outliers = None  # will hold the last year's outliers for the legend count

    # Plot each year
    for idx, (year, col) in enumerate(years):
        ax = axes[idx]
        # Plot the main data
        gdf_buildings.plot(column=col,
                            cmap='Oranges',
                            linewidth=0,
                            vmax=vmax,
                            ax=ax,
                            legend=False)

        # Identify and plot outliers
        outliers = gdf_buildings[gdf_buildings[col] > vmax]
        if len(outliers) > 0:
            outliers.plot(ax=ax,
                           color='black',
                           markersize=10,
                           marker='o',
                           edgecolor='darkred',
                           linewidth=0.5)

        # Remove frame, ticks, and grid
        ax.set_frame_on(False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        # Anchor plotted area to the top of its cell so all maps align at the top line
        ax.set_anchor('N')
        # Set subplot title
        ax.set_title(f'{year} ({gdf_buildings[f"HEAT_VOLUME_{year}"].sum()/1e6:.2f} TWh)')

    # Extra subplot on the right: listed (heritage) buildings
    heritage_buildings = None
    if highlight_heritage:
        ax_heritage = axes[3]

        is_heritage = gdf_buildings['HERITAGE'] == True
        heritage_buildings = gdf_buildings[is_heritage]
        non_heritage_buildings = gdf_buildings[~is_heritage]

        # Gray for non-listed, blue for listed
        if len(non_heritage_buildings) > 0:
            non_heritage_buildings.plot(ax=ax_heritage, color='lightgray', linewidth=0)
        if len(heritage_buildings) > 0:
            heritage_buildings.plot(ax=ax_heritage, color='darkblue', linewidth=0)

        ax_heritage.set_frame_on(False)
        ax_heritage.set_xticks([])
        ax_heritage.set_yticks([])
        ax_heritage.grid(False)
        # Anchor to top like the other subplots
        ax_heritage.set_anchor('N')
        ax_heritage.set_title('Listed buildings')

    # Add main title
    fig.suptitle('Evolution of the Heat Demand per Land Area',
                  y=0.98, fontsize=14)

    # Reduce/control the spacing BEFORE adding the colorbar
    plt.subplots_adjust(wspace=0.05, bottom=0.16, top=0.88)

    # Create colorbar (only spans the 3 heat-map subplots)
    sm = plt.cm.ScalarMappable(cmap='Oranges', norm=plt.Normalize(vmin=0, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes[:3], orientation='horizontal',
                         pad=0.1, aspect=40, shrink=0.6)
    cbar.set_label('Heat Volume (MWh per squared meter of land area)', fontsize=12)

    # Legend for the three heat-map subplots (outliers)
    outlier_legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='black',
                   markersize=10, label=f'Buildings above {vmax:.1f} MWh per squared meter - {len(outliers)} buildings')
    ]

    outlier_legend = fig.legend(handles=outlier_legend_elements,
                                 loc='lower center',
                                 bbox_to_anchor=(0.42, 0.1) if highlight_heritage else (0.5, 0.1),
                                 ncol=1,
                                 fontsize=12,
                                 framealpha=0.9)

    # Separate legend for the heritage subplot
    if highlight_heritage:
        fig.add_artist(outlier_legend)  # keep the first legend from being overwritten

        heritage_legend_elements = [
            plt.Rectangle((0, 0), 1, 1, facecolor='darkblue', edgecolor='none',
                          label=f'Listed - {len(heritage_buildings)} buildings'),
            plt.Rectangle((0, 0), 1, 1, facecolor='lightgray', edgecolor='none',
                          label=f'Not listed - {len(gdf_buildings) - len(heritage_buildings)} buildings')
        ]

        fig.legend(handles=heritage_legend_elements,
                   loc='lower center',
                   bbox_to_anchor=(0.80, 0.1),
                   ncol=1,
                   fontsize=12,
                   framealpha=0.9)

    plt.savefig('Output/Heat_geography.pdf')

def plot_available_sources(gdf_buildings,df_building_prod, color_tech_rgb):
    capa = df_building_prod
    capa = capa[capa['power_MW_th'] > 0]
    to_plot2 = pd.merge(
        left=gdf_buildings.set_index('BUILDING_ID')[['geometry']],
        right=capa.pivot(columns='tech', index='BUILDING_ID', values='power_MW_th'),
        left_index=True, right_index=True,
        how='left'
    ).fillna(0)

    fig, (ax, lax) = plt.subplots(
        1, 2, figsize=(8, 5),
        gridspec_kw={'width_ratios': [4, 1]}
    )

    to_plot2.plot(color='lightgray', ax=ax)

    tech_cols = [c for c in to_plot2.columns if c not in ['geometry', 'selected']]
    tech_color = {key: np.array(value) / 255 for key, value in color_tech_rgb.items() if key in tech_cols}

    totals = to_plot2[tech_cols].sum(axis=1)
    max_power = totals.max()
    max_radius = 100  # map CRS units (meters if projected)

    def radius_for(power):
        return max_radius * np.sqrt(power / max_power)

    for idx, row in to_plot2.iterrows():
        total = totals.loc[idx]
        if total <= 0:
            continue
        x, y = row.geometry.centroid.x, row.geometry.centroid.y
        radius = radius_for(total)
        angle = 0
        for tech in tech_cols:
            value = row[tech]
            if value <= 0:
                continue
            theta = 360 * value / total
            wedge = mpatches.Wedge(
                (x, y), radius, angle, angle + theta,
                facecolor=tech_color[tech], edgecolor='black', linewidth=0.2
            )
            ax.add_patch(wedge)
            angle += theta

    ax.set_aspect('equal')
    ax.spines[['top', 'right', 'bottom', 'left']].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    # ============================================================
    # LEGEND AXES — positioned by axes-fraction, sized by points
    # so nothing depends on ax's or lax's data-unit scale.
    # ============================================================
    lax.axis('off')

    # --- layout must be finalized BEFORE measuring scales/positions ---
    fig.tight_layout()
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # --- legend 1: technology colors, anchored in lax's axes-fraction space ---
    tech_handles = [mpatches.Patch(color=tech_color[t], label=t) for t in tech_cols]
    tech_legend = lax.legend(
        handles=tech_handles, title='Technology',
        loc='upper left', bbox_to_anchor=(0.0, 1.0),
        frameon=False
    )
    lax.add_artist(tech_legend)
    fig.canvas.draw()  # re-render so the legend has a real bbox

    # bottom edge of the tech legend, in lax axes-fraction coords (0-1)
    bbox_px = tech_legend.get_window_extent(renderer)
    bbox_frac = lax.transAxes.inverted().transform(bbox_px)
    legend_bottom_frac = bbox_frac[0, 1]

    # --- true points-per-data-unit scale of the MAP axes ---
    # (this is what makes the legend circles match the real pies)
    p0 = ax.transData.transform((0, 0))
    p1 = ax.transData.transform((1, 0))
    pixels_per_dataunit_ax = np.hypot(*(p1 - p0))
    points_per_dataunit_ax = pixels_per_dataunit_ax * 72.0 / fig.dpi

    ref_values = np.round([max_power, max_power / 2, max_power / 4, 5], 1)
    # diameter in points, matching how these circles actually render on the map
    ref_diam_points = [2 * radius_for(v) * points_per_dataunit_ax for v in ref_values]

    # --- convert lax's pixel height to points, to space circles w/o overlap ---
    lax_bbox_px = lax.get_window_extent(renderer)
    lax_height_points = lax_bbox_px.height * 72.0 / fig.dpi

    label_buffer_points = 14      # vertical room reserved per row for the "X MW" text
    row_height_points = max(ref_diam_points) + label_buffer_points
    row_height_frac = row_height_points / lax_height_points

    x0_frac = 0.12
    y_frac = legend_bottom_frac - 0.06 - row_height_frac / 2  # first circle center

    lax.annotate(
        'Available power', (x0_frac, legend_bottom_frac - 0.03),
        xycoords='axes fraction', va='top', ha='left',
        fontsize=11, fontweight='bold'
    )

    for diam_pts, val in zip(ref_diam_points, ref_values):
        lax.plot(
            x0_frac, y_frac, transform=lax.transAxes,
            marker='o', markersize=diam_pts,   # markersize = diameter, in points
            markerfacecolor='none', markeredgecolor='black', markeredgewidth=0.8,
            clip_on=False
        )
        lax.annotate(
            f'{val:g} MW',
            (x0_frac, y_frac), xycoords='axes fraction',
            xytext=(diam_pts / 2 + 8, 0), textcoords='offset points',
            va='center', ha='left', fontsize=9
        )
        y_frac -= row_height_frac

    fig.savefig('Output/available_power.pdf')
    plt.show()

def plot_supply_demand(costs_array, production, consumption, individual_sol, indexing_heat_cost, color_tech_rgb):
    if indexing_heat_cost:
        display_euro = r'€$_{2026}$'
    else:
        display_euro = '€'

    # fig, ax = plt.subplots()
    overview_prod = pd.DataFrame(index=costs_array, data=production,columns=production[0].keys())
    overview_cons = pd.DataFrame(index=costs_array, data = consumption, columns=consumption[0].keys())

    # --- fixed technology palette, chosen for decent contrast + thematic fit ---
    # heat pumps in blues/teals (electricity-driven), CHP pellet in green (biomass),
    # riothermal in a distinct warm accent so it doesn't get lost among the blues
    color_tech = color_tech_rgb
    fig, ax = plt.subplots(figsize=(5, 5))

    # --- consumption lines: monochromatic reds, one shade per year ---
    cons_cols = list(overview_cons.columns)
    reds = reversed(cm.Reds(np.linspace(0.4, 0.9, len(cons_cols))))  # skip the near-white end
    for col, color in zip(cons_cols, reds):
        ax.plot(overview_cons.index, overview_cons[col], color=color,
                label=f'Consumption {col}', linewidth=2, marker='o', markersize=3)

    # --- production bars: stacked, colored by tech via color_tech ---
    bottom = np.zeros(len(costs_array))
    bar_width = (costs_array[1] - costs_array[0]) * 0.8

    # Define the desired order
    tech_order = ['CHP pellet', 'ASHP', 'WSHP', 'RIOTHERMAL', 'GSHP']
    colors = {k: tuple(c / 255 for c in v) for k, v in color_tech.items()}
    # Iterate through the defined order instead of overview_prod.columns
    for tech in tech_order:
        if tech in overview_prod.columns:  # Only plot if the column exists
            vals = overview_prod[tech].fillna(0).values
            ax.bar(costs_array, vals, bottom=bottom, width=bar_width,
                color=colors.get(tech, '#999999'), label=f'Production {tech}')
            bottom += vals
    # Get the equilibrium point coordinates
    eq_x = balanced['cost of heat']
    eq_y = balanced['consumption']/1000 + 200

    # Add arrow from text to equilibrium point
    ax.annotate('', 
                xy=(balanced['cost of heat'], balanced['consumption']/1000),  # Arrowhead at equilibrium point
                xytext=(eq_x, eq_y),  # Arrow starts from the text position
                arrowprops=dict(arrowstyle='->', 
                            color='black', 
                            lw=1.5,
                            connectionstyle="arc3,rad=0.0"))

    # Add text with white background and black edge
    ax.text(eq_x, eq_y,
            s=f"Equilibrium\n{balanced['consumption']/1e3:.2f} GWh \n  {balanced['cost of heat']:.2f} {display_euro}/MWh",
            ha='center', va='bottom',  # Center the text
            bbox=dict(boxstyle="round,pad=0.3",  # Rounded box
                    facecolor='white', 
                    edgecolor='black',
                    linewidth=1.5),
            fontsize=10,
            fontweight='bold')
    ax.hlines(y=gdf_buildings['HEAT_VOLUME_2030'].sum()/1e3,xmin=0,xmax=200, color='black', linestyles='dashed',label='Pentagon demand 2030')
    ax.set_xlim(cost_min-2,cost_max+2)
    ax.set_xlabel(f'Cost of heat ({display_euro}/MWh)')
    ax.set_ylabel('GWh')
    ax.set_title(f'Supply-demand curves with decentralised {individual_sol} \nas competing technology and cost of heat indexed.')
    # ax.set_ylim(0,2500)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(
        handles, labels,
        loc='upper center',
        bbox_to_anchor=(0.5, -0.2),  
        ncol=3,
        fontsize=8,
        frameon=False,
    )
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    if indexing_heat_cost:
        fig.savefig(f'Output/supply_demand_benchmark_{individual_sol}_indexed.pdf')
    else: 
        fig.savefig(f'Output/supply_demand_benchmark_{individual_sol}.pdf')

def _shade(rgb_255, amount=0.0):
    """rgb_255: (r,g,b) in 0-255. amount>0 lighten (->white), amount<0 darken (->black).
    Returns an (r,g,b) tuple in 0-1, ready for matplotlib."""
    r, g, b = (c / 255 for c in rgb_255)
    target = 1 if amount >= 0 else 0
    a = abs(amount)
    return (r + (target - r) * a, g + (target - g) * a, b + (target - b) * a)

def build_investment_frame(balanced, color_tech_rgb, year0=2026):
    if indexing_heat_cost:
        display_euro = r'€$_{2026}$'
    else:
        display_euro = '€'
    """Builds grouped_rev (tech, year) -> Revenues/Costs/Invest €, with the
    initial capacity investment injected as its own row at `year0`, then
    melted/pivoted into one stacked-bar-ready column per (tech, flux),
    plus a matching color map keyed the same way."""

    # --- network + capacity investment ---
    network_inv = balanced['gdf_sel_connection'].pipe(
        lambda d: d[d['selected']][['Edge cost €', 'Edge length m']].sum())

    df_capa = balanced['df_capa_profit_sel']
    capa_inv = (df_capa[df_capa['selected']][['tech', 'power_MW_th', 'Capacity Investment €']]
                .groupby('tech').sum())
    capa_inv = capa_inv[capa_inv['power_MW_th'] > 0]

    # --- yearly revenues / costs per tech ---
    df_opex = balanced['df_prod_opex_sel']
    grouped_rev = df_opex[df_opex['selected'] & (df_opex['Discounted Revenues Heat €'] > 0)].copy()
    grouped_rev = grouped_rev[['tech', 'year',
                                'Discounted Revenues Heat €', 'Discounted Revenues Electricity €',
                                'Discounted Cost of production €', 'Discounted Variable o&m €',
                                'Discounted Fixed o&m €']].groupby(['tech', 'year']).sum()

    grouped_rev['Revenues €'] = grouped_rev[['Discounted Revenues Heat €', 'Discounted Revenues Electricity €']].sum(axis=1)
    grouped_rev['Costs €'] = -grouped_rev[['Discounted Cost of production €', 'Discounted Variable o&m €',
                                            'Discounted Fixed o&m €']].sum(axis=1)
    grouped_rev['Invest €'] = 0.0

    # --- inject investment as its own row at year0 ---
    invest_rows = capa_inv.reset_index()[['tech', 'power_MW_th', 'Capacity Investment €']].copy()
    invest_rows['year'] = year0
    invest_rows['Invest €'] = -invest_rows['Capacity Investment €']
    for col in grouped_rev.columns:
        if col not in invest_rows.columns:
            invest_rows[col] = 0.0
    invest_rows = invest_rows.set_index(['tech', 'year'])[grouped_rev.columns]

    # year0 may already exist in grouped_rev (opex data starting at year0) -> merge by summing
    # instead of creating a duplicate (tech, year) row, which would break the pivot below.
    grouped_rev = pd.concat([invest_rows, grouped_rev]).groupby(level=['tech', 'year']).sum().sort_index()

    # --- melt/pivot to one stacked-bar-ready column per (tech, flux) ---
    melt_rev = (grouped_rev[['Revenues €', 'Costs €', 'Invest €']]
                .reset_index().melt(id_vars=['tech', 'year'], var_name='flux'))
    melt_rev['Category'] = melt_rev['tech'] + ' - ' + melt_rev['flux']
    to_plot = melt_rev.pivot(index='year', columns='Category', values='value')
    to_plot['Network - Invest €'] = 0.0
    to_plot.loc[2026, 'Network - Invest €'] = - network_inv['Edge cost €']

    to_plot['Savings €'] = balanced['df_cons_sel'][balanced['df_cons_sel']['selected']][['year','Potential savings €']].groupby(by='year').sum()

    # --- colors, one per (tech, flux), keyed the same way as `to_plot`'s columns ---
    shade_by_flux = {'Revenues €': 0.3, 'Costs €': 0.0, 'Invest €': -0.3}  # darken / lighten / base
    colors_full = {
        f"{tech} - {flux}": _shade(rgb, amount)
        for tech, rgb in color_tech_rgb.items()
        for flux, amount in shade_by_flux.items()
    }
    colors_full['Network - Invest €'] = 'darkred'
    colors_full['Savings €'] = 'orange'
    return to_plot, colors_full, network_inv, capa_inv

def plot_investment(balanced, color_tech_rgb, year0=2026, figsize=(5, 5), bar_width=0.8, individual_sol = None, indexing_heat_cost=None):
    """Stacked bar with TRUE numeric year spacing (not the equidistant
    categorical spacing you'd get from DataFrame.plot(kind='bar'))."""
    
    display_euro = r'€$_{2026}$'
    
    to_plot, colors_full, network_inv, capa_inv = build_investment_frame(balanced, color_tech_rgb, year0)
    to_plot /= 1e6
    years = to_plot.index.to_numpy()
    colors = [colors_full[col] for col in to_plot.columns]  # ordered to match columns exactly

    fig, ax = plt.subplots(figsize=figsize)
    bottom_pos = np.zeros(len(years))
    bottom_neg = np.zeros(len(years))
    
    for col, color in zip(to_plot.columns, colors):
        vals = to_plot[col].fillna(0).to_numpy()
        bottom = np.where(vals >= 0, bottom_pos, bottom_neg)
        ax.bar(years, vals, bottom=bottom, width=bar_width, color=color,
               edgecolor='white', linewidth=0.4, label=col)
        bottom_pos = np.where(vals >= 0, bottom_pos + vals, bottom_pos)
        bottom_neg = np.where(vals < 0, bottom_neg + vals, bottom_neg)
        if 'Invest' in col and not 'Network' in col:
            y = vals[0]/2+bottom[0]
            x = 2026
            ax.text(x=x, 
                    y=y, 
                    s=f'{col[0:-11]}\n{capa_inv.loc[col[0:-11],'power_MW_th']} MW\n{-vals[0]:.1f} M€',
                    ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.3",  # Rounded box
                            facecolor='white', 
                            edgecolor=color,
                            linewidth=1.5),
                    fontsize=8,
                    )
            print(col)
        elif col == 'Network - Invest €':
            y = vals[0]/2+bottom[0]
            x = 2026
            ax.text(x=x, 
                    y=y, 
                    s=f'{col[0:-11]}\n{network_inv["Edge length m"]/1e3:.2f} km\n{network_inv["Edge cost €"]/1e6:.1f} M€',
                    ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.3",  # Rounded box
                            facecolor='white', 
                            edgecolor=color,
                            linewidth=1.5),
                    fontsize=8,
                    )
            print(col)
    

    cumulative = to_plot.sum(axis=1).cumsum()
    cumulative.plot(color='black', label='NPV', ax=ax, marker='o')
    breakeven = cumulative[cumulative > 0].index[0]
    roi = -cumulative.iloc[-1]/cumulative.iloc[0]
    ax.set_title(f'The investment breakeven year is {breakeven}\n and project presents a ROI of {100*roi:.2f}% by 2060')

    to_plot['balance'] = to_plot.sum(axis=1)
    to_plot['rev'] = to_plot[to_plot>0].sum(axis=1)
    for year in [2030,2040,2050]:
        ax.text(x=year,
                y=50,#to_plot.loc[year,'rev'],
                s=f"Balance {year}\n{to_plot.loc[year,'balance']:+.2f} M{display_euro}",
                va='bottom',
                ha='center',
                fontsize=8)
    ax.axhline(0, color='black', linewidth=0.9)
    # ax.set_xticks(years)  # real numeric positions -> true spacing between years
    # ax.set_xticklabels(years)


    ax.grid(True)
    ax.set_xlabel('Year')
    ax.set_ylabel(f'M{display_euro}')
    ax.spines[['top', 'right','bottom','left']].set_visible(False)
    # Get current handles and labels
    handles, labels = ax.get_legend_handles_labels()

    # Find the handle you want to move to the end
    last_index = labels.index('NPV')
    last_handle = handles.pop(last_index)
    last_label = labels.pop(last_index)

    # Append it to the end
    handles.append(last_handle)
    labels.append(last_label)

    # Create legend with reordered handles
    # ax.legend()
    ax.legend(handles, labels,bbox_to_anchor=(0.5, -0.1), loc='upper center', fontsize=8, frameon=False, ncols = 3)
    fig.tight_layout()
    if indexing_heat_cost:
        fig.savefig(f'Output/optimal_NPV_benchmark_{individual_sol}_indexed.pdf')
    else:
        fig.savefig(f'Output/optimal_NPV_benchmark_{individual_sol}.pdf')

    return fig, ax

def plot_geography_sol(balanced, individual_sol, indexing_heat_cost, color_tech_rgb, ax = None):

    capa = balanced['df_capa_profit_sel'][balanced['df_capa_profit_sel']['selected']]
    capa = capa[capa['power_MW_th'] > 0]
    to_plot2 = pd.merge(left = balanced['building_value_sel'].set_index('BUILDING_ID')[['geometry','selected']],
                    right = capa.pivot(columns='tech',index='BUILDING_ID',values='power_MW_th'),
                    left_index=True,right_index=True,
                    how='left').fillna(0)
    
    if ax is None:
        fig, ax = plt.subplots(figsize=(5,5))
    to_plot2.plot(column='selected', ax=ax, color=to_plot2['selected'].map({False: 'lightgray', True: 'orange'}))

    balanced['gdf_sel_connection'][balanced['gdf_sel_connection']['selected']].plot(color='darkred', ax=ax, label = 'Connections')

    # tech columns are everything except 'geometry' and 'selected'
    tech_cols = [c for c in to_plot2.columns if c not in ['geometry', 'selected']]

    # consistent colors per technology
    colors = plt.cm.tab10(np.linspace(0, 1, len(tech_cols)))
    tech_color = {key:np.array(value)/255 for key, value in color_tech_rgb.items() if key in tech_cols}#dict(zip(tech_cols, colors))
    print(tech_color)
    # total power per building, used for radius scaling
    totals = to_plot2[tech_cols].sum(axis=1)
    max_power = totals.max()
    max_radius = 100  # <-- tune this: units are the same as your CRS (meters if projected)

    def radius_for(power):
        return max_radius * np.sqrt(power / max_power)

    for idx, row in to_plot2.iterrows():
        total = totals.loc[idx]
        if total <= 0:
            continue

        x, y = row.geometry.centroid.x, row.geometry.centroid.y
        radius = radius_for(total)

        angle = 0
        for tech in tech_cols:
            value = row[tech]
            if value <= 0:
                continue
            theta = 360 * value / total
            wedge = mpatches.Wedge(
                (x, y), radius, angle, angle + theta,
                facecolor=tech_color[tech], edgecolor='black', linewidth=0.2
            )
            ax.add_patch(wedge)
            angle += theta

    ax.set_aspect('equal')

    # --- legend 1: technology colors ---
    tech_handles = [mpatches.Patch(color=tech_color[t], label=t) for t in tech_cols]
    tech_legend = ax.legend(handles=tech_handles, title='Technology', loc='upper right',  bbox_to_anchor=(1.02, 1.02))
    ax.add_artist(tech_legend)

    # --- legend 2: size reference circles (drawn in data units, same scale as the pies) ---
    ref_values = np.round([max_power, max_power/2, max_power/4], 1)

    minx, miny, maxx, maxy = to_plot2.total_bounds
    x0 = maxx - 0.25 * (maxx - minx)
    y0 = miny + 0.02 * (maxy - miny)
    spacing = 1.2 * max_radius

    # --- background frame ---
    n = len(ref_values)
    box_width  = max_radius * 8   # enough room for circle + label text
    box_height = spacing * (n - 1) + 2.4 * max_radius + 50
    box_x = x0 - max_radius * 1.3
    box_y = y0 - max_radius * 1.3

    frame = mpatches.FancyBboxPatch(
        (box_x, box_y), box_width, box_height,
        boxstyle="round,pad=0.02,rounding_size=5",
        facecolor='white', edgecolor='gray', linewidth=0.8,
        zorder=3, alpha = 0.8
    )
    ax.add_patch(frame)

    for i, val in enumerate(ref_values):
        r = radius_for(val)
        cy = y0 + i * spacing
        circle = mpatches.Circle((x0, cy), r, facecolor='none', edgecolor='black', linewidth=0.8, zorder=4)
        ax.add_patch(circle)
        ax.annotate(f'{val:g} MW', (x0 + max_radius * 1.3, cy),
                    va='center', ha='left', fontsize=9)

    ax.annotate('Installed power', (x0 - 100, y0 + len(ref_values) * spacing - 65),
                va='bottom', ha='left', fontsize=12, fontweight='bold')

    ax.spines[['top', 'right', 'bottom', 'left']].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    if indexing_heat_cost:
        fig.savefig(f'Output/optimal_network_benchmark_{individual_sol}_indexed.pdf')
    else: 
        fig.savefig(f'Output/optimal_network_benchmark_{individual_sol}.pdf')
    plt.show()


#%%
YEAR_TODAY      = 2026
DISCOUNT_RATE   = 0.03
ROOT   = 'B1823663'   # single source of truth for the rooted PCST

color_tech_rgb = {
    'ASHP':        (76, 114, 176),
    'GSHP':        (90, 169, 201),
    'WSHP':        (27, 79, 114),
    'CHP pellet':  (85, 136, 59),
    'RIOTHERMAL':  (217, 142, 4),
}


if __name__ == '__main__':
    gdf_raw_buildings, gdf_raw_edges, gdf_raw_nodes, gdf_raw_connections = import_original(plot=True, plot_filename='demand_model.html')
    gdf_intersections, gdf_buildings, gdf_edges = include_connections(gdf_raw_buildings, 
                                                                        gdf_raw_nodes, 
                                                                        gdf_raw_edges, 
                                                                        gdf_raw_connections, 
                                                                        plot = False,
                                                                        unique_conn = True)
    eflh, df_building_cons, df_building_prod = split_data(gdf_buildings)
    df_primary_prices = compute_price_df(DISCOUNT_RATE=DISCOUNT_RATE)
    display_heat_geography(gdf_buildings, highlight_heritage=True)
    plot_available_sources(gdf_buildings,df_building_prod, color_tech_rgb = color_tech_rgb)

#%% DISPLAYING ROI for a given technology (discounted, non-indexed price of heat)
# building_value_sel, df_capa_profit_sel, df_prod_opex_sel, df_cons_sel, gdf_sel_intersections, gdf_sel_connection = optimize_network(eflh, 
#                                                                                                                                     df_building_cons, 
#                                                                                                                                     df_building_prod, 
#                                                                                                                                     df_primary_prices, 
#                                                                                                                                     gdf_intersections,
#                                                                                                                                     gdf_buildings,
#                                                                                                                                     gdf_edges,
#                                                                                                                                     benchmark = 'NG', 
#                                                                                                                                     DISCOUNT_RATE = DISCOUNT_RATE, 
#                                                                                                                                     YEAR_TODAY = YEAR_TODAY,
#                                                                                                                                     COST_OF_HEAT = 80,
#                                                                                                                                     COST_TRENCH = 5e3,
#                                                                                                                                     ROOT = ROOT)

# # print(f'\n\nCost of heat {cost_of_heat:.2f}')
# qp2030 = df_prod_opex_sel.loc[(df_prod_opex_sel['year'] == 2030) * df_prod_opex_sel['selected'], 'Potential Production MWh'].sum()
# print(f'Produced (2030) {qp2030/1e3:.2f} GWh')

# qc2030 = df_cons_sel.loc[(df_cons_sel['year'] == 2030) * df_cons_sel['selected'], 'Potential consumption MWh'].sum()
# print(f'Consumed (2030) {qc2030/1e3:.2f} GWh')
      
# display_tech_NPV(df_prod_opex_sel,df_capa_profit_sel)
#%%
display_NPV = False
if __name__ == '__main__':
    for individual_sol, indexing_heat_cost in product(['NG', 'ASHP'],[True, False]):
        print(f'Computing against {individual_sol} and price of heat is indexed: {indexing_heat_cost}')
        cost_min = 40
        cost_max = 90
        n_cost = int((cost_max - cost_min) / 2 + 1)
        costs_array = np.linspace(cost_min,cost_max,n_cost)
        production  = []
        consumption = []
        balanced = None
        for i, cost_of_heat in enumerate(costs_array):
            progress_bar(i,n_cost)
            building_value_sel, df_capa_profit_sel, df_prod_opex_sel, df_cons_sel, gdf_sel_intersections, gdf_sel_connection = optimize_network(eflh, 
                                                                                                                                                df_building_cons, 
                                                                                                                                                df_building_prod, 
                                                                                                                                                df_primary_prices, 
                                                                                                                                                gdf_intersections,
                                                                                                                                                gdf_buildings,
                                                                                                                                                gdf_edges,
                                                                                                                                                benchmark = individual_sol, 
                                                                                                                                                DISCOUNT_RATE = DISCOUNT_RATE, 
                                                                                                                                                YEAR_TODAY = YEAR_TODAY,
                                                                                                                                                COST_OF_HEAT = cost_of_heat,
                                                                                                                                                COST_TRENCH = 5e3,
                                                                                                                                                ROOT = ROOT,
                                                                                                                                                indexing_heat_cost = indexing_heat_cost)
            
            # print(f'\n\nCost of heat {cost_of_heat:.2f}')
            qp2030 = df_prod_opex_sel.loc[(df_prod_opex_sel['year'] == 2030) * df_prod_opex_sel['selected'], 'Potential Production MWh'].sum()
            # print(f'Produced (2030) {qp2030/1e3:.2f} GWh')

            qc2030 = df_cons_sel.loc[(df_cons_sel['year'] == 2030) * df_cons_sel['selected'], 'Potential consumption MWh'].sum()
            # print(f'Consumed (2030) {qc2030/1e3:.2f} GWh')

            consumption += [(df_cons_sel.loc[(df_cons_sel['year'].isin([2030, 2040, 2050]))* df_cons_sel['selected'],['year','Potential consumption MWh']].groupby(by=['year']).sum()['Potential consumption MWh']/1e3).to_dict()]
            production += [(df_prod_opex_sel.loc[(df_prod_opex_sel['year']==2030) * df_prod_opex_sel['selected'],['tech','Potential Production MWh']].groupby(by=['tech']).sum()['Potential Production MWh']/1e3).to_dict()]

            if (balanced == None) and (qp2030>qc2030):
                balanced = {'cost of heat':cost_of_heat,
                            'production':qp2030,
                            'consumption':qc2030,
                            'building_value_sel':building_value_sel,
                            'df_capa_profit_sel':df_capa_profit_sel,
                            'df_prod_opex_sel':df_prod_opex_sel,
                            'df_cons_sel':df_cons_sel,
                            'gdf_sel_intersections':gdf_sel_intersections,
                            'gdf_sel_connection':gdf_sel_connection}

        progress_bar(i+1,n_cost)
        plot_supply_demand(costs_array, production, consumption, individual_sol=individual_sol, indexing_heat_cost=indexing_heat_cost, color_tech_rgb = color_tech_rgb)
        # display_tech_NPV(balanced['df_prod_opex_sel'],balanced['df_capa_profit_sel'])
        plot_investment(balanced, individual_sol=individual_sol, indexing_heat_cost=indexing_heat_cost, color_tech_rgb = color_tech_rgb)
        plot_geography_sol(balanced, color_tech_rgb=color_tech_rgb, individual_sol=individual_sol, indexing_heat_cost=indexing_heat_cost)
# %%