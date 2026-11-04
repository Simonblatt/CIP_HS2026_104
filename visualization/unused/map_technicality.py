import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

# --- Data ---
df = pd.read_csv("../../results_cantons.csv", encoding="utf-8-sig")   # adjust path

for label, col in layers.items():
    order, _ = styles[col]
    unknown = set(df[col].dropna()) - set(order)
    if unknown:
        print(f"WARNING {label}: categories not in order list: {unknown}")

# --- Map data: one row per canton ---
cantons = gpd.read_file("../swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_kantonsgebiet")

canton_abbreviations = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL", 9: "ZG",
    10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR", 16: "AI", 17: "SG",
    18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD", 23: "VS", 24: "NE", 25: "GE", 26: "JU"
}

gdf_geo = cantons.copy()
gdf_geo["canton"] = gdf_geo["kantonsnummer"].map(canton_abbreviations)
gdf_geo = gdf_geo.dropna(subset=["canton"]).to_crs(epsg=4326)
gdf_geo["geometry"] = gdf_geo.geometry.force_2d().simplify(0.005)

gdf_geo = gdf_geo[["canton", "name", "geometry"]].merge(
    df[["canton"] + list(layers.values())],
    on="canton", how="left",
)
print(gdf_geo.columns.tolist(), len(gdf_geo))     # expect 26 rows
geojson = gdf_geo.geometry.__geo_interface__

# --- Cities ---
municipalities = gpd.read_file("../swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_hoheitsgebiet")
cities = (municipalities
          .sort_values("einwohnerzahl", ascending=False)
          .drop_duplicates("name")
          .head(10)
          .copy())
pts = gpd.GeoSeries(cities.geometry.representative_point(), crs=cities.crs).to_crs(epsg=4326)
cities["lon"], cities["lat"] = pts.x, pts.y

# --- One choropleth trace per layer ---
def make_trace(label, col, visible):
    order, colors = styles[col]
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
        colorbar=dict(title=label, tickvals=list(range(n)), ticktext=order),
        marker_line_color="white", marker_line_width=0.5,
        visible=visible,
    )

fig_map = go.Figure()
for i, (label, col) in enumerate(layers.items()):
    fig_map.add_trace(make_trace(label, col, visible=(i == 0)))

# cities: last trace, always visible
fig_map.add_trace(go.Scattergeo(
    lat=cities["lat"], lon=cities["lon"], text=cities["name"],
    mode="markers+text", textposition="bottom right",
    marker=dict(size=7, color="black", line=dict(width=1, color="white")),
    hovertemplate="<b>%{text}</b><extra></extra>",
    name="Biggest cities",
))

# --- Buttons ---
labels = list(layers)
first_label = labels[0]
buttons = []
for i, label in enumerate(labels):
    visible = [j == i for j in range(len(labels))] + [True]
    buttons.append(dict(
        label=label,
        method="update",
        args=[{"visible": visible},
              {"title.text": f"Route offer per canton: {label}"}],
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