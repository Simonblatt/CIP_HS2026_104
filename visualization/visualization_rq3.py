# Visualization for RQ3
# Which Swiss cantons offer the best opportunities for combining different outdoor activities, measured by the density
# of routes within each activity type (hiking, cycling, mountain biking, skating and canoeing)?

# interactive map with random data

import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go


df = pd.read_csv("../results_cantons.csv")

# Defining the layers of the map
layers = {
    "Total": "rq3_diversity_category",
    "Hiking": "rq3_wanderland_category",
    "Biking": "rq3_veloland_category",
    "Mountainbiking": "rq3_mountainbikeland_category",
    "Skating": "rq3_skatingland_category",
}

# chosing the first layer to sho
first_label, first_col = next(iter(layers.items()))

# defining a function to sort individually for each graph
def sorted_df(col):
    return  df.sort_values(col, ascending=False)

d0 = sorted_df(first_col)

# creating the figure

fig_rq3 = px.bar(d0, y='canton', x=first_col, orientation='h', text_auto='.2s',
            title="Density per Activity")

fig_rq3.update_yaxes(
    autorange="reversed",              # first row at the top
    categoryorder="array",
    categoryarray=d0["canton"].tolist(),
)


# button per layer

def sorted_df(col):
    return df.sort_values(col, ascending=False)  # largest first

d0 = sorted_df(first_col)

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
    d = sorted_df(col)
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



# Idee Kategorisierung der Kanton
# in verschiedene Kategorien statt
# die Density.

# Verschiedene Fragen, zu denen wir Hilfestellungen
# geben wollen und mit welcher Karte wir sie
# beantworten wollen.

# Grosse Städte / Flughafen
# Erschlossenheitsindex

# Fragen beantworten. Wir müssen
# nicht begründen wieso geändert.

