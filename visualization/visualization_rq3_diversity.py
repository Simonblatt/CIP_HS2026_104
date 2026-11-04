from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import utils


# --- Settings ---
CSV_PATH = "../results_cantons.csv"                       # adjust path
GPKG_PATH = "swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"        # adjust path
OUTPUT_PATH = "plots/rq3_map_diversity.png"
SHOW_CITIES = True

# --- Layer: diversity ---
col = "rq3_diversity_category"
order = ["too few routes", "low", "medium", "high"]
colors = ["#898989", "#DE6B72", "#F4A582", "#5E9FCB"]
colorbar_title = "Route diversity"
map_title = "Diversity of routes per canton"

# --- Data ---
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")

if col not in df.columns:
    raise ValueError(f"Column '{col}' missing in CSV.\nAvailable: {df.columns.tolist()}")

unknown = set(df[col].dropna()) - set(order)
if unknown:
    print(f"WARNING: categories not in order list: {unknown}")

# --- Map data: one row per canton ---
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

# --- Choropleth trace ---
n = len(order)
cats = gdf_geo[col]
codes = cats.map({c: i for i, c in enumerate(order)})

colorscale = []
for i, c in enumerate(colors):
    colorscale += [[i / n, c], [(i + 1) / n, c]]

fig = go.Figure()
fig.add_trace(go.Choropleth(
    geojson=geojson,
    locations=gdf_geo.index.astype(str),
    z=codes, zmin=-0.5, zmax=n - 0.5, colorscale=colorscale,
    text=cats.fillna("no data"),
    colorbar=dict(title=dict(text=colorbar_title),
                  tickvals=list(range(n)), ticktext=order),
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