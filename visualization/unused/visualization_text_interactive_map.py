# interactive map with random data

import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go

print(gpd.list_layers("../swissBOUNDARIES3D_1_5_LV95_LN02.gpkg"))

cantons = gpd.read_file("../swissBOUNDARIES3D_1_5_LV95_LN02.gpkg", layer="tlm_kantonsgebiet")
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

gdf_wgs = gdf.to_crs(epsg=4326)

# Defining the layers of the map

layers = {
    "hiking_1200": "dens_h_1200",
    "biking": "dens_velo",
    "mountain_biking": "dens_mb",
    "skating": "dens_sk",
    "canoeing": "dens_can",
}

# chosing the first layer to sho
first_label, first_col = next(iter(layers.items()))

# creating the figure

fig = go.Figure(
    go.Choropleth(
        #gdf_wgs,
        geojson=gdf_wgs.geometry.__geo_interface__,
        locations=gdf_wgs.index,
        z = gdf_wgs[first_col],
        text=gdf_wgs["name"],
        colorscale ="Viridis",
        zmin = 0,
        zmax = 1,
        colorbar_title=f"Density {first_label.lower()}",
        hovertemplate="<b>%{hovertext}</b><br>Density: %{z:.1f}<extra></extra>"
    )
)

# button per layer

buttons = [
    dict(
        label=label,
        method="restyle",
        args=[{
            "z": [gdf_wgs[col].tolist()],
            "zmin": [gdf_wgs[col].min()],
            "zmax": [gdf_wgs[col].max()],
            "colorbar.title.text": f"Density {label.lower()}",
        }],
    )
    for label, col in layers.items()
]

fig.update_layout(
    updatemenus=[dict(
        buttons=buttons,
        direction="down",
        x=0.01, xanchor="left",
        y=1.0, yanchor="top",
    )],
    width=900,
    height=600,
    margin=dict(l=0, r=80, t=40, b=0),
)
fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
fig.show()