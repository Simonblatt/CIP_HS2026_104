"""
RQ3: Which cantons offer the best opportunities for different outdoor activities?
Part 1: density per activity, classified relative to the Swiss average.
Part 2: diversity of the offer (Shannon evenness), classified into categories.
"""

import numpy as np

import pandas as pd

from utils import route_canton_count

def count_routes_per_activity(routes, canton_figures):
    route_canton = route_canton_count(routes, "land")

    # Number of routes per canton (rows) and activity (columns)
    routes_per_activity = pd.crosstab(route_canton["canton"], route_canton["land"])

    print(routes_per_activity.to_string())

    routes_per_activity = routes_per_activity.reindex(canton_figures["canton"], fill_value=0)

    return routes_per_activity


def density_category(r):
    if r == 0:
        return "no offer"
    elif r < 0.75:
        return "below average"
    elif r <= 1.25:
        return "average"
    elif r <= 2:
        return "above average"
    else:
        return "high"

def density_categories(routes_per_activity, canton_figures):
    # Area of each canton, with the canton abbreviation as row name
    area = canton_figures.set_index("canton")["area_km2"]

    # Density: number of routes per 100 km², calculated separately for each activity
    density = routes_per_activity.div(area, axis=0) * 100

    # Swiss average density per activity: all routes of an activity divided by the area of Switzerland.
    # It serves as the reference value for the density categories of each canton.
    swiss_area = area.sum()
    swiss_density = routes_per_activity.sum() / swiss_area * 100

    # Ratio of each canton's density to the Swiss average of the same activity
    # (1 = exactly the Swiss average, 2 = twice as dense as the Swiss average)
    ratio = density.div(swiss_density, axis=1)

    categories = ratio.map(density_category)

    # Combine routes, density, ratio and category into one table:
    # one row per canton and activity (long format, practical for visualisations)
    rq3_density = pd.DataFrame({
        "routes": routes_per_activity.stack(),
        "density_per_100km2": density.stack().round(2),
        "ratio_to_swiss_average": ratio.stack().round(2),
        "category": categories.stack(),
    }).reset_index()

    return rq3_density

MIN_ROUTES = 5


def diversity_category(evenness_value, routes_total):
    # Cantons with fewer than MIN_ROUTES routes get no diversity category,
    # since the distribution of so few routes is largely a matter of chance.
    # Values exactly on a limit belong to the higher category.
    if routes_total == 0:
        return "no offer"
    elif routes_total < MIN_ROUTES:
        return "too few routes"
    elif evenness_value < 0.5:
        return "low"
    elif evenness_value < 0.75:
        return "medium"
    else:
        return "high"

def diversity(routes_per_activity):
    # Share of each canton in the Swiss offer of each activity (in percent).
    # Example: if 10 of all 286 mountain bike routes are in a canton, its share is 3.5 %.
    # This makes the activities comparable, although they differ strongly in size
    # (e.g. 286 mountain bike routes vs. 11 skating routes in Switzerland).
    shares = routes_per_activity / routes_per_activity.sum() * 100

    # 1. Profile of each canton: the four shares rescaled so that they add up to 1 (100 %) per canton.
    #    This removes the size of the canton; only the distribution between the activities remains.
    profile = shares.div(shares.sum(axis=1), axis=0)

    # 2. Shannon index: measures how evenly the routes are distributed between the activities.
    #    Activities without any route (share 0) are left out, as the logarithm of 0 is not defined.
    shannon = -(profile * np.log(profile.where(profile > 0))).sum(axis=1, min_count=1)

    # 3. Evenness: Shannon index divided by its maximum (log of the number of activities, here 4).
    #    0 = all routes in one activity, 1 = all four activities equally represented.
    evenness = (shannon / np.log(len(shares.columns))).round(2)

    routes_total = routes_per_activity.sum(axis=1)

    categories = pd.Series(
        {canton: diversity_category(evenness[canton], routes_total[canton]) for canton in evenness.index}
    )

    # Combine evenness, diversity category and total number of routes into one table
    rq3_diversity = pd.DataFrame({
        "evenness": evenness,
        "category": categories,
        "routes_total": routes_total,
    }).sort_values("evenness", ascending=False).reset_index()

    return rq3_diversity


