# Visualization for RQ3
# Which Swiss cantons offer the best opportunities for combining different outdoor activities, measured by the density
# of routes within each activity type (hiking, cycling, mountain biking, skating and canoeing)?

# interactive map with random data

import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go

df_index = pd.read_csv("../rq3_result_combined_index.csv")
df_dens = pd.read_csv("../rq3_result_density.csv")

# Jonining data sets

df_rq3 = df_index.merge(
    df_dens,
    on="canton",
)

# Defining the layers of the map

layers = {
    "Total": "combined_index",
    "Hiking": "wanderland",
    "Biking": "veloland",
    "Mountainbiking": "mountainbikeland",
    "Skating": "skatingland",
}

# chosing the first layer to sho
first_label, first_col = next(iter(layers.items()))

# defining a function to sort individually for each graph
def sorted_df_rq3(col):
    return  df_rq3.sort_values(col, ascending=False)

d0 = sorted_df_rq3(first_col)

# creating the figure

fig_rq3 = px.bar(d0, y='canton', x=first_col, orientation='h', text_auto='.2s',
            title="Density per Activity")

fig_rq3.update_yaxes(
    autorange="reversed",              # first row at the top
    categoryorder="array",
    categoryarray=d0["canton"].tolist(),
)


# button per layer

def sorted_df_rq3(col):
    return df_rq3.sort_values(col, ascending=False)  # largest first

d0 = sorted_df_rq3(first_col)

fig_rq3 = px.bar(
    d0, x=first_col, y="canton", orientation="h", text_auto=first_label,
    title=f"Density per Activity: {first_label}",
)
fig_rq3.update_yaxes(
    autorange="reversed",              # first row at the top
    categoryorder="array",
    categoryarray=d0["canton"].tolist(),
)

buttons = []
for label, col in layers.items():
    d = sorted_df_rq3(col)
    buttons.append(dict(
        label=label,
        method="update",
        args=[
            {"x": [d[col].tolist()], "y": [d["canton"].tolist()]},
            {"yaxis.categoryarray": d["canton"].tolist(),
             "title.text": f"Density per Activity: {label}",
             "xaxis.title.text": col},
        ],
    ))

fig_rq3.update_layout(
    updatemenus=[dict(buttons=buttons, direction="down",
                      x=0.0, y=1.15, xanchor="left")],
)

fig_rq3.show()

