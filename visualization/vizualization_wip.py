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

# interactive map
gdf_wgs = gdf.to_crs(epsg=4326)

fig = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="routes_h_tot",
    hover_name="name",
    color_continuous_scale="Viridis",
)
fig.update_geos(fitbounds="locations", visible=False)
fig.show()




