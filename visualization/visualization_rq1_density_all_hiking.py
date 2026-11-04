from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import utils

# --- Settings ---
CSV_PATH = "../results_cantons.csv"                       # adjust path
GPKG_PATH = "swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"        # adjust path
OUTPUT_PATH = "plots/rq1_map_density_all_hiking.png"
SHOW_CITIES = True


# --- Data ---
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
df["rq1_density_all_hiking"] = (df["rq3_wanderland_routes"] / df["area_km2"]* 100).round(2)

# --- Layer: density hiking routes ---
col = "rq1_density_all_hiking"
colorbar_title = "Routes per 100km2"
map_title = "Density of hiking routes per canton"

if col not in df.columns:
    raise ValueError(f"Column '{col}' missing in CSV.\nAvailable: {df.columns.tolist()}")


# --- Map data ---
cantons = gpd.read_file(GPKG_PATH, layer="tlm_kantonsgebiet")

gdf_geo = cantons.copy()
gdf_geo["canton"] = gdf_geo["kantonsnummer"].map(utils.canton_abbreviations)
gdf_geo = gdf_geo.dropna(subset=["canton"]).to_crs(epsg=4326)
gdf_geo["geometry"] = gdf_geo.geometry.force_2d().simplify(0.005)

gdf_geo = gdf_geo[["canton", "name", "geometry"]].merge(
    df[["canton", col]],
    on="canton", how="left",
)
print(len(gdf_geo), "cantons")     # expect 26 rows
geojson = gdf_geo.geometry.__geo_interface__

# --- Create map ---
zmin, zmax = gdf_geo[col].quantile([0.05, 0.95])

fig = go.Figure()
fig.add_trace(go.Choropleth(
    geojson=geojson,
    locations=gdf_geo.index.astype(str),
    z=gdf_geo[col],
    zmin=zmin, zmax=zmax,
    colorscale=["#DCE9F4", "#B7D4EA", "#6BAED6", "#2171B5", "#08306B"],
    text=gdf_geo["name"],
    colorbar=dict(title=dict(text=colorbar_title)),
    marker_line_color="white", marker_line_width=0.5,
))

# --- Cities ---
if SHOW_CITIES:
    municipalities = gpd.read_file(GPKG_PATH, layer="tlm_hoheitsgebiet")
    cities = (municipalities
              .sort_values("einwohnerzahl", ascending=False)
              .drop_duplicates("name")
              .head(10)
              .copy())
    pts = gpd.GeoSeries(cities.geometry.representative_point(),
                        crs=cities.crs).to_crs(epsg=4326)
    cities["lon"], cities["lat"] = pts.x, pts.y

    fig.add_trace(go.Scattergeo(
        lat=cities["lat"], lon=cities["lon"], text=cities["name"],
        mode="markers+text", textposition="bottom right",
        marker=dict(size=7, color="black", line=dict(width=1, color="white")),
        showlegend=False,
    ))

# --- Layout ---
fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig.update_layout(
    width=900, height=650,
    margin=dict(l=0, r=80, t=100, b=0),
    title=map_title,
    showlegend=False,
    paper_bgcolor="white",
)

# --- Export ---
Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
fig.write_image(OUTPUT_PATH, width=900, height=650, scale=3)
print(f"Saved {OUTPUT_PATH}")