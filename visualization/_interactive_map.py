import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go
import utils

# --- Data ---
df = pd.read_csv("../results_cantons.csv", encoding="utf-8-sig")   # adjust path

# --- Category order + colors per column ---
land_order  = ["no offer", "below average", "average", "above average", "high"]
land_colors = ["#898989", "#DE6B72", "#F4A582", "#92C5DE", "#5E9FCB"]
diversity_order  = ["too few routes", "low", "medium", "high"]
diversity_colors = ["#898989", "#DE6B72", "#F4A582", "#5E9FCB"]

# --- Layers: label -> category column ---
layers = {
    "All Activities": dict(
        col="rq3_diversity_category",
        order=diversity_order,
        colors=diversity_colors,
        scale_title="Route diversity",
        map_title="Route diversity",
    ),
    "Hiking": dict(
        col="rq3_wanderland_category",
        order=land_order,
        colors=land_colors,
        scale_title="Route share",
        map_title="Share of hiking routes relative to Swiss average",
    ),
    "Biking": dict(
        col="rq3_veloland_category",
        order=land_order,
        colors=land_colors,
        scale_title="Route share",
        map_title="Share of biking routes relative to Swiss average",
    ),
    "Mountainbiking": dict(
        col="rq3_mountainbikeland_category",
        order=land_order,
        colors=land_colors,
        scale_title="Route share",
        map_title="Share of mountainbiking routes relative to Swiss average",
    ),
    "Skating": dict(
        col="rq3_skatingland_category",
        order=land_order,
        colors=land_colors,
        scale_title="Route share",
        map_title="Share of skating routes relative to Swiss average",
    )
}


missing = [cfg["col"] for cfg in layers.values() if cfg["col"] not in df.columns]
if missing:
    raise ValueError(f"Columns missing in CSV: {missing}\nAvailable: {df.columns.tolist()}")

for label, cfg in layers.items():
    col, order = cfg["col"], cfg["order"]
    unknown = set(df[col].dropna()) - set(order)
    if unknown:
        print(f"WARNING {label}: categories not in order list: {unknown}")

# --- Map data: one row per canton ---
cantons = gpd.read_file("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_kantonsgebiet")


gdf_geo = cantons.copy()
gdf_geo["canton"] = gdf_geo["kantonsnummer"].map(utils.canton_abbreviations)
gdf_geo = gdf_geo.dropna(subset=["canton"]).to_crs(epsg=4326)
gdf_geo["geometry"] = gdf_geo.geometry.force_2d().simplify(0.005)

gdf_geo = gdf_geo[["canton", "name", "geometry"]].merge(
    df[["canton"] + [cfg["col"] for cfg in layers.values()]],
    on="canton", how="left",
)
print(gdf_geo.columns.tolist(), len(gdf_geo))     # expect 26 rows
geojson = gdf_geo.geometry.__geo_interface__

# --- Cities ---
municipalities = gpd.read_file("swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_hoheitsgebiet")
cities = (municipalities
          .sort_values("einwohnerzahl", ascending=False)
          .drop_duplicates("name")
          .head(10)
          .copy())
pts = gpd.GeoSeries(cities.geometry.representative_point(), crs=cities.crs).to_crs(epsg=4326)
cities["lon"], cities["lat"] = pts.x, pts.y

# --- One choropleth trace per layer ---
def make_trace(label, cfg, visible):
    col, order, colors, scale_title = cfg["col"], cfg["order"], cfg["colors"], cfg["scale_title"]
    n = len(order)
    cats = gdf_geo[col]
    codes = cats.map({c: i for i, c in enumerate(order)})

    colorscale = []
    for i, c in enumerate(colors):
        colorscale += [[i / n, c], [(i + 1) / n, c]]

    return go.Choropleth(
        geojson=geojson,
        locations=gdf_geo.index.astype(str),
        z=codes, zmin=-0.5, zmax=n - 0.5, colorscale=colorscale,
        text=cats.fillna("no data"),
        hovertext=gdf_geo["name"],
        hovertemplate="<b>%{hovertext}</b><br>%{text}<extra></extra>",
        colorbar=dict(title=dict(text=scale_title), tickvals=list(range(n)), ticktext=order),
        marker_line_color="white", marker_line_width=0.5,
        visible=visible,
    )

fig_map = go.Figure()
for i, (label, cfg) in enumerate(layers.items()):
    fig_map.add_trace(make_trace(label, cfg, visible=(i == 0)))

# cities: last trace, always visible
fig_map.add_trace(go.Scattergeo(
    lat=cities["lat"], lon=cities["lon"], text=cities["name"],
    mode="markers+text", textposition="bottom right",
    marker=dict(size=7, color="black", line=dict(width=1, color="white")),
    hovertemplate="<b>%{text}</b><extra></extra>",
    showlegend=False,
))

# --- Buttons ---
labels = list(layers)
first_label = labels[0]
buttons = []
for i, (label,cfg) in enumerate(layers.items()):
    visible = [j == i for j in range(len(layers))] + [True]
    buttons.append(dict(
        label=label,
        method="update",
        args=[{"visible": visible},
              {"title.text": cfg["map_title"]}],
    ))

fig_map.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig_map.update_layout(
    width=900, height=650, margin=dict(l=0, r=80, t=100, b=0),
    title=f"Route offer per canton: {first_label}",
    updatemenus=[dict(buttons=buttons, direction="down",
                      x=0.0, y=1.08, xanchor="left", yanchor="top")],
    showlegend=True,
    legend=dict(x=0.0, y=0.05, xanchor="left", bgcolor="rgba(255,255,255,0.7)"),
)

fig_map.show()

# --- static exports ---
from pathlib import Path
import plotly.graph_objects as go

Path("plots").mkdir(exist_ok=True)
n_layers = len(layers)

for i, (label, cfg) in enumerate(layers.items()):
    fig_static = go.Figure(fig_map)
    for j in range(n_layers):
        fig_static.data[j].visible = (j == i)
    fig_static.update_layout(title=cfg["map_title"])
    fig_static.layout.updatemenus = []
    fig_static.write_image(f"plots/rq3_map_{label.lower()}.png",
                           width=900, height=650, scale=3)

fig_map.write_html(f"plots/rq3_map_interactive.html",)