"""
RQ1: Which cantons have the highest density of outdoor routes
with a maximum altitude below 1200 m (accessible in the shoulder seasons)?
"""
import pandas as pd

from utils import route_canton_count



def run_rq1(routes, canton_figures):
    # Keep only routes whose highest point is below 1200 m
    # (assumed to be accessible in spring and autumn, see RQ1)
    low_routes = routes[routes["el_max_m"] < 1200]

    # Check: number of routes before and after the filter
    print("All routes:", len(routes))
    print("Routes below 1200 m:", len(low_routes))
    print("Routes without altitude information:", routes["el_max_m"].isna().sum())

    route_canton = route_canton_count(low_routes)
    routes_per_canton = route_canton["canton"].value_counts()

    # Combine the number of routes with the area of each canton.
    # The canton table is the base (how="left"), so all 26 cantons are included,
    # also those without any route below 1200 m (e.g. Zug); their count is set to 0.
    rq1 = canton_figures[["canton", "KTNAME", "area_km2"]].merge(
        routes_per_canton.rename("routes").reset_index(),
        on="canton",
        how="left"
    )
    rq1["routes"] = rq1["routes"].fillna(0).astype(int)

    # Density: number of routes per 100 km² of canton area
    rq1["density_per_100km2"] = (rq1["routes"] / rq1["area_km2"] * 100).round(2)

    # Sort from highest to lowest density
    rq1 = rq1.sort_values("density_per_100km2", ascending=False).reset_index(drop=True)

    return rq1