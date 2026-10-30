"""
This file stores helper functions used for several scripts:
canton abbreviations, loading the BFS canton figures and counting routes per canton.
"""

import pandas as pd
# pandas: works with tables (DataFrames).
# Used to load the routes, count them per canton and activity, and calculate percentile ranks.

# Canton abbreviation for each official canton number (order of the Federal Constitution)
canton_abbreviations = {
    1: "ZH", 2: "BE", 3: "LU", 4: "UR", 5: "SZ", 6: "OW", 7: "NW", 8: "GL", 9: "ZG",
    10: "FR", 11: "SO", 12: "BS", 13: "BL", 14: "SH", 15: "AR", 16: "AI", 17: "SG",
    18: "GR", 19: "AG", 20: "TG", 21: "TI", 22: "VD", 23: "VS", 24: "NE", 25: "GE", 26: "JU"
}

# Load the geographic key figures of the cantons (BFS, as of 01.01.2026)
def load_canton_figures(file="Geographische_Kennzahlen.xlsx"):
    canton_figures = pd.read_excel(file, sheet_name="Daten")

    # Add the canton abbreviation via the official canton number
    canton_figures["canton"] = canton_figures["KTNR"].map(canton_abbreviations)



    # Convert the area from hectares to square kilometres (1 km² = 100 ha)
    canton_figures["area_km2"] = canton_figures["AREA_HA"] / 100

    return canton_figures

# One row per route and canton: a route counts for every canton in which it starts or ends.
# A route that starts and ends in the same canton counts only once for that canton.
# Routes abroad are not counted.
# extra_column: optional column to keep, e.g. "technical" (RQ2) or "land" (RQ3).
def route_canton_count(routes, extra_column = None):
    columns = [extra_column] if extra_column else []

    route_canton = pd.concat([
        routes[["start_canton", "land"]].rename(columns={"start_canton": "canton"}),
        routes[["end_canton", "land"]].rename(columns={"end_canton": "canton"}),
    ])

    # A route that starts and ends in the same canton counts only once for that canton
    route_canton = route_canton.reset_index().drop_duplicates()

    # Routes abroad are not counted
    route_canton = route_canton[route_canton["canton"] != "abroad"]

    return route_canton

