"""
RQ2: Does the percentage of hiking routes per difficulty level
relate to the mean elevation of a canton?
"""

import pandas as pd

from scipy.stats import spearmanr

from utils import route_canton_count

def run_rq2(routes, canton_figures):
    # Only hiking routes are relevant for RQ2
    hiking_routes = routes[routes["land"] == "wanderland"]

    route_canton = route_canton_count(hiking_routes, ["technical", "condition"])

    # Number of routes per canton and difficulty level
    # crosstab counts the routes for each combination of canton and difficulty level.
    technical_count = pd.crosstab(route_canton["canton"], route_canton["technical"]).add_prefix("technical_")
    condition_count = pd.crosstab(route_canton["canton"], route_canton["condition"]).add_prefix("condition_")

    # Percentage of each difficulty level per canton
    # crosstab counts the routes for each combination of canton and difficulty level;
    # normalize="index" turns the counts into shares per canton (each row adds up to 100 %).

    difficulty_share = (pd.crosstab(route_canton["canton"], route_canton["technical"], normalize="index") * 100).round(
        1)

    # Combine the counts and share with the mean elevation of each canton.
    # Only cantons with hiking routes are included (AG, BS and ZG have none).
    rq2 = (
        difficulty_share
        .join(technical_count, how="left")
        .join(condition_count, how="left")
        .reset_index()
        .merge(canton_figures[["canton", "Z_AVG"]], on="canton", how="left")
    )


    #Delete
    from scipy.stats import spearmanr
    # scipy: library for scientific calculations.
    # spearmanr calculates the Spearman correlation together with its p-value.

    result = spearmanr(rq2["Z_AVG"], rq2["mittel (Bergwanderweg)"])
    print("Spearman correlation:", round(result.statistic, 2))
    print("p-value:", result.pvalue)
    
    return rq2, result
