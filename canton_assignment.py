"""
This file assigns cantons to the start and end point of each route
and finds the cantons a route passes through.
"""

import pandas as pd
# pandas: works with tables (DataFrames).
# Used to load the scraped route data (result.csv) and to clean and merge tables.

import geopandas as gpd
# geopandas: extends pandas with a column for shapes (lines, areas, points).
# Used to read the shapefiles (route lines, canton areas) and to find
# the canton in which a point lies.

from shapely.geometry import Point
# shapely: the library geopandas uses to calculate shapes.
# Point represents a single location (east and north coordinate).
# Used to create the start point and end point of each route.

from utils import canton_abbreviations

# Source 3: canton boundaries from swissBOUNDARIES3D, edition 2026 (swisstopo)
# One row per canton with the canton number, name and the area of the canton as a shape.
def load_cantons(file = "Geodaten/Kantonsgrenzen/swissBOUNDARIES3D_1_5_TLM_KANTONSGEBIET.shp"):
    cantons = gpd.read_file(file)
    # Add the canton abbreviation via the official canton number
    cantons["canton_abbr"] = cantons["KANTONSNUM"].map(canton_abbreviations)

    return cantons

def assign_cantons(scraped_routes, geo_file, cantons):

    # This function assigns the start canton and the end canton to each route,
    # as well as every canton the route passes through in between.
    # Data loading: This paragraph loads the two data sources.
    # Source 1: routes scraped from schweizmobil.ch
    # One row per route with title, distance, elevation, difficulty, start and end point.
    # Source 2: route geometries from the matching Schweiz mobil dataset (FEDRO / SchweizMobil)
    # One row per route with the route number and the line of the route as coordinates.
    coordinates = gpd.read_file(geo_file)
    print("Scraped routes:", len(scraped_routes))
    print("coordinates:", len(coordinates))


    # Data loading: Shows the column names of the scraped routes
    print(scraped_routes.columns.tolist())


    #  Data cleaning: This paragraph extracts the route number from the URL of each scraped route.
    # Example: ".../wanderland/route-101" -> 101
    # The route number is needed to link the scraped routes with the route geometries.
    scraped_routes["route_nr"] = (
        scraped_routes["url"]
        .str.extract(r"route-(\d+)")[0]   # take the digits after "route-"
        .astype(int)                      # convert the text "101" into the number 101
    )


    # Data cleaning: This paragraph converts the route number in the route geometries from text to a number.
    # In the shapefile, the route number (column "NrR") is stored as text, e.g. "101".
    # To compare it with the route numbers of the scraped routes, it must be a number as well.
    # A few internal entries have no valid route number (e.g. "SWL249.RT");
    # errors="coerce" turns them into empty values instead of causing an error.
    coordinates["route_nr"] = pd.to_numeric(coordinates["NrR"], errors="coerce")
    # Check: how many entries could not be converted
    print("Entries without a valid route number:", coordinates["route_nr"].isna().sum())

    # Data cleaning: This paragraph removes duplicate route geometries.
    # Some datasets (e.g. Veloland) store a route several times:
    # as outward and return way ("Hinweg" / "Rückweg"), or as variants and side routes.
    # Only the main route ("Touristische Route") in one direction is kept;
    # start and end point are the same for both directions.
    coordinates = coordinates[
        (coordinates["Routenart"] == "Touristische Route")
        & (coordinates["Abwicklung"] != "Rückweg")
    ]
    print("Route geometries after removing duplicates:", len(coordinates))

    # Data cleaning: This paragraph checks whether the two tables can be linked correctly before merging them.
    # 1. How many scraped routes find a matching route number in the route geometries?
    found = scraped_routes["route_nr"].isin(coordinates["route_nr"])
    print("Scraped routes:", len(scraped_routes))
    print("With matching geometry:", found.sum())
    # 2. Do any of the scraped route numbers appear more than once in the route geometries?
    relevant = coordinates[coordinates["route_nr"].isin(scraped_routes["route_nr"])]
    print("Duplicate route numbers:", relevant["route_nr"].duplicated().sum())


    # merging: This paragraph links the scraped routes with the route geometries via the route number.
    # Only the columns needed are taken from the route geometries:
    # - geometry: the line of the route (used to find the start and end point)
    # - AOrt, ZOrt: start and end location according to the geodataset (used for checking)
    # how="left" keeps all scraped routes, even if no geometry were found.
    routes_linked = scraped_routes.merge(
        coordinates[["route_nr", "AOrt", "ZOrt", "geometry"]],
        on="route_nr",
        how="left"
    )
    # Check: the number of rows must be the same as the number of scraped routes
    print("Rows after linking:", len(routes_linked))


    # Controlling: This paragraph checks how the route lines are stored.
    # LineString: one continuous line -> first point = start, last point = end
    # MultiLineString: several separate line pieces -> order of the pieces is not guaranteed
    print(routes_linked["geometry"].apply(lambda g: g.geom_type).value_counts())


    # merging: This paragraph creates the start point and the end point of each route.
    # Each route line consists of many points with coordinates (east, north, height).
    # The first point of the line is the start, the last point is the end.
    # [:2] keeps only east and north; the height is not needed to find the canton.
    routes_linked["start_point"] = routes_linked["geometry"].apply(lambda line: Point(line.coords[0][:2]))
    routes_linked["end_point"] = routes_linked["geometry"].apply(lambda line: Point(line.coords[-1][:2]))


    # merging: This paragraph determines the canton of each start point.
    # A spatial join (sjoin) links two tables by location instead of by a common column:
    # each start point receives the canton abbreviation of the canton area it lies within.
    # Points outside Switzerland (e.g. Liechtenstein) lie within no canton and are marked "abroad".
    # 1. Turn the start points into a geo table with the same coordinate system as the cantons
    start_points = gpd.GeoDataFrame(geometry=routes_linked["start_point"], crs=cantons.crs)
    # 2. Spatial join: which canton area contains each point?
    start_join = gpd.sjoin(start_points, cantons[["canton_abbr", "geometry"]], how="left", predicate="within")
    # 3. Write the result into a new column; points without a canton are marked "abroad"
    routes_linked["start_canton"] = start_join["canton_abbr"].fillna("abroad")
    # Check: total number of start points, number abroad, and full list of all cantons
    print("Total:", routes_linked["start_canton"].notna().sum())
    print("Abroad:", (routes_linked["start_canton"] == "abroad").sum())
    print(routes_linked["start_canton"].value_counts().to_string())


    # This paragraph determines the canton of each end point.
    # Same method as for the start points: spatial join of the end points with the canton areas.
    # 1. Turn the end points into a geo table with the same coordinate system as the cantons
    end_points = gpd.GeoDataFrame(geometry=routes_linked["end_point"], crs=cantons.crs)
    # 2. Spatial join: which canton area contains each point?
    end_join = gpd.sjoin(end_points, cantons[["canton_abbr", "geometry"]], how="left", predicate="within")
    # 3. Write the result into a new column; points without a canton are marked "abroad"
    routes_linked["end_canton"] = end_join["canton_abbr"].fillna("abroad")
    # Check: total number of end points, number abroad, and full list of all cantons
    print("Total:", routes_linked["end_canton"].notna().sum())
    print("Abroad:", (routes_linked["end_canton"] == "abroad").sum())
    print(routes_linked["end_canton"].value_counts().to_string())


    # merging: This paragraph determines all cantons a route passes through.
    # Instead of a point, the whole line of the route is used.
    # predicate="intersects" finds every canton area the line touches or crosses.
    # A route can pass through several cantons, so the join returns one row per route and canton;
    # these rows are then combined into one text per route, e.g. "BE, NW, OW".
    # 1. Turn the route lines into a geo table with the same coordinate system as the cantons
    route_lines = gpd.GeoDataFrame(geometry=routes_linked["geometry"], crs=cantons.crs)
    # 2. Spatial join: which canton areas does each line touch or cross?
    line_join = gpd.sjoin(route_lines, cantons[["canton_abbr", "geometry"]], how="left", predicate="intersects")
    # 3. For each route: all cantons the line touches, minus the start and end canton
    #    -> only the cantons the route passes through in between remain
    touched = line_join.groupby(level=0)["canton_abbr"].apply(lambda abbrs: set(abbrs.dropna()))
    def cantons_in_between(row):
        in_between = touched[row.name] - {row["start_canton"], row["end_canton"]}
        return ", ".join(sorted(in_between)) if in_between else None
    # 4. Write the result into a new column; routes without a canton in between stay empty
    routes_linked["crossed_cantons"] = routes_linked.apply(cantons_in_between, axis=1)
    # Check: routes passing through at least one canton in between
    has_crossed = routes_linked["crossed_cantons"].notna()
    print("Routes with cantons in between:", has_crossed.sum())


    # This paragraph creates the final table and saves it as a CSV file.
    # Coordinates of start and end point as plain numbers (LV95: east "e" and north "n"),
    # so they can be saved in a CSV file and used later for maps
    routes_linked["start_e"] = routes_linked["start_point"].apply(lambda p: round(p.x))
    routes_linked["start_n"] = routes_linked["start_point"].apply(lambda p: round(p.y))
    routes_linked["end_e"] = routes_linked["end_point"].apply(lambda p: round(p.x))
    routes_linked["end_n"] = routes_linked["end_point"].apply(lambda p: round(p.y))
    # Final table: all original columns of the scraped routes + route number, cantons and coordinates
    new_columns = ["route_nr", "start_canton", "end_canton", "crossed_cantons",
               "start_e", "start_n", "end_e", "end_n"]
    original_columns = [col for col in scraped_routes.columns if col != "route_nr"]

    routes_cantons = routes_linked[original_columns + new_columns]
    # Check: number of rows and columns of the final table
    print("Rows:", len(routes_cantons))
    print("Columns:", routes_cantons.columns.tolist())

    return routes_cantons

