# Visualization for RQ1
# Which Swiss cantons provide the highest density of outdoor routes under 1200m maximum altitude that remain fully
# accessible during the spring and autumn shoulder season?

import pandas as pd
import geopandas as gpd
import plotly.express as px

print(gpd.list_layers("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"))

cantons = gpd.read_file("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_kantonsgebiet")
print(cantons.columns)
print(cantons.crs)   # Swiss data is usually EPSG:2056 (LV95)

df = pd.read_csv("../rq1_result_density_below_1200m.csv")

canton_abbreviations = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL", 9: "ZG",
    10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR", 16: "AI", 17: "SG",
    18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD", 23: "VS", 24: "NE", 25: "GE", 26: "JU"
}
canton_numbers = {abbr: num for num, abbr in canton_abbreviations.items()}

df.insert(
    df.columns.get_loc("canton") + 1,
    "kantonsnummer",
    df["canton"].map(canton_numbers),
)

# Jonining data sets

gdf = cantons.merge(
    df,
    on="kantonsnummer",
)



# density of routes above 1200m

gdf_wgs = gdf.to_crs(epsg=4326)

fig_map1 = px.choropleth(
    gdf_wgs,
    geojson=gdf_wgs.geometry.__geo_interface__,
    locations=gdf_wgs.index,
    color="density_per_100km2",
    hover_name="KTNAME",
    color_continuous_scale="YlGn",
)
fig_map1.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_map1.update_layout(width=900, height=600, margin=dict(l=0, r=80, t=40, b=0))
#manually adapt the tooltip
fig_map1.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
)
fig_map1.update_layout()
fig_map1.show()


