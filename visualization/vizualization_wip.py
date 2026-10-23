# This file is to try out different visualization ideas, not done with real data
import pandas as pd
import geopandas as gpd
import plotly.express as px

print(gpd.list_layers("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"))

cantons = gpd.read_file("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_kantonsgebiet")
print(cantons.columns)
print(cantons.crs)   # Swiss data is usually EPSG:2056 (LV95)

df = pd.read_csv("random_data.csv")

# Jonining data sets

gdf = cantons.merge(
    df,
    left_on="kantonsnummer",   # column in the swissBOUNDARIES data
    right_on="KTNR",     # column in  df
    how="left",
)

gdf = gdf.drop(columns="KTNR")

# RQ 1

# density of routes above 1200m

gdf_wgs = gdf.to_crs(epsg=4326)

fig_h_1200 = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="dens_h_1200",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig_h_1200.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_h_1200.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_h_1200.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_h_1200.update_layout()
fig_h_1200.show()



# RQ 3

# density of biking routes

gdf_wgs = gdf.to_crs(epsg=4326)

fig_velo = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="dens_velo",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig_velo.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_velo.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_velo.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_velo.update_layout()
fig_velo.show()


# density of mountain biking routes

gdf_wgs = gdf.to_crs(epsg=4326)

fig_mb = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="dens_mb",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig_mb.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_mb.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_mb.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_mb.update_layout()
fig_mb.show()



# density of skating routes

gdf_wgs = gdf.to_crs(epsg=4326)

fig_sk = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="dens_sk",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig_sk.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_sk.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_sk.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_sk.update_layout()
fig_sk.show()


# density of canoeing routes

gdf_wgs = gdf.to_crs(epsg=4326)

fig_can = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="dens_can",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig_can.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_can.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_can.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_can.update_layout()
fig_can.show()

