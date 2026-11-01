#Control, CLI & CSV output

import argparse
import os
import pandas as pd
from playwright.sync_api import sync_playwright

from config import DEFAULT_LANDS, LANDS, FILE_ALL, GEO_FILES
from scraper import inspect_land, scrape_land
from utils import load_canton_figures
from canton_assignment import load_cantons, assign_cantons
from rq1 import run_rq1
from rq2 import run_rq2
from rq3 import count_routes_per_activity, density_categories, diversity

def save_results_to_csv(rows):
    """Saves all scraped routes into a single CSV file."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(FILE_ALL, index=False, encoding="utf-8-sig")

# Provide the save function to the scraper module
import scraper
scraper.save_results_to_csv = save_results_to_csv

def load_existing():
    """--resume: load rows from a previous (possibly interrupted) run."""
    if not os.path.exists(FILE_ALL):
        return []
    return pd.read_csv(FILE_ALL).to_dict("records")

def build_results_table(canton_figures, rq1, rq2, rq3_density, rq3_diversity):
    """Combines the results of RQ1 to RQ3 into one table with one row per canton."""

    # Base: all 26 cantons with name, area and mean elevation (BFS)
    results = canton_figures[["canton", "KTNAME", "area_km2", "Z_AVG"]].rename(
        columns={"KTNAME": "name", "Z_AVG": "mean_elevation_m"}
    )

    # RQ1: routes below 1200 m and their density
    results = results.merge(
        rq1[["canton", "routes", "density_per_100km2"]].rename(columns={
            "routes": "rq1_routes_below_1200m",
            "density_per_100km2": "rq1_density_per_100km2",
        }),
        on="canton", how="left"
    )

    # RQ2: share of each difficulty level (in %) and number of hiking routes.
    # The mean elevation is already in the table, so it is not added again.
    rq2_columns = rq2.drop(columns=["Z_AVG"]).set_index("canton").add_prefix("rq2_").reset_index()
    results = results.merge(rq2_columns, on="canton", how="left")

    # RQ3, part 1: density per activity.
    # The density table has one row per canton and activity; pivot turns the activities into columns,
    # e.g. "rq3_wanderland_density_per_100km2", "rq3_wanderland_category".
    density_wide = rq3_density.pivot(
        index="canton", columns="land",
        values=["routes", "density_per_100km2", "ratio_to_swiss_average", "category"]
    )
    density_wide.columns = [f"rq3_{land}_{value}" for value, land in density_wide.columns]
    results = results.merge(density_wide.reset_index(), on="canton", how="left")

    # RQ3, part 2: diversity (evenness, diversity category, total number of routes)
    diversity_columns = rq3_diversity.rename(columns={"index": "canton"})
    diversity_columns = diversity_columns.set_index("canton").add_prefix("rq3_diversity_").reset_index()
    results = results.merge(diversity_columns, on="canton", how="left")

    return results

def run_analysis(all_rows):
    """Assigns cantons to the scraped routes and answers RQ1 to RQ3."""
    # Scraped routes as a table
    scraped = pd.DataFrame(all_rows)

    # Canton boundaries, loaded once for all activities
    cantons = load_cantons()

    # Assign cantons separately for each activity, each with its own route geometries.
    # Activities without geodata (Kanuland) are skipped.
    tables = []
    for land, geo_file in GEO_FILES.items():
        land_routes = scraped[scraped["land"] == land]
        if land_routes.empty:
            continue
        print(f"\n=== Canton assignment: {land} ===")
        tables.append(assign_cantons(land_routes, geo_file, cantons))

    # All activities together in one table
    routes = pd.concat(tables, ignore_index=True)
    routes.to_csv("routes_cantons.csv", index=False, encoding="utf-8-sig")
    # BFS key figures of the cantons (area, mean elevation), used by all research questions
    canton_figures = load_canton_figures()

    # RQ1: density of routes below 1200 m
    print("\n=== RQ1 ===")
    rq1 = run_rq1(routes, canton_figures)

    # RQ2: share of difficulty levels and mean elevation
    print("\n=== RQ2 ===")
    rq2, rq2_correlation = run_rq2(routes, canton_figures)

    # RQ3: density per activity and diversity
    print("\n=== RQ3 ===")
    routes_per_activity = count_routes_per_activity(routes, canton_figures)
    rq3_density = density_categories(routes_per_activity, canton_figures)
    rq3_diversity = diversity(routes_per_activity)

    # One table with all results per canton, saved as the final output
    results = build_results_table(canton_figures, rq1, rq2, rq3_density, rq3_diversity)
    results.to_csv("results_cantons.csv", index=False, encoding="utf-8-sig")
    print(f"\nSaved results for {len(results)} cantons in results_cantons.csv")

    # The RQ2 correlation is a single value for all of Switzerland and is not part of the canton table
    print(f"RQ2 Spearman correlation: {rq2_correlation.statistic:.2f}, p-value: {rq2_correlation.pvalue:.2g}")

    return results

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lands", nargs="+", default=DEFAULT_LANDS, choices=list(LANDS))
    ap.add_argument("--inspect", action="store_true", help="only print page structure, no scraping")
    ap.add_argument("--limit", type=int, default=None, help="max. routes per overview (for testing)")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--resume", action="store_true",
                    help="keep the rows already in the result file and scrape only missing routes")
    args = ap.parse_args()

    all_rows = load_existing() if args.resume else []
    done = {r["url"] for r in all_rows}
    if args.resume:
        print(f"resume: {len(all_rows)} routes already in {FILE_ALL}")
    failed_lands, still_failed = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        if args.inspect:
            for land in args.lands:
                inspect_land(page, land)
            browser.close()
            return

        for land in args.lands:
            try:
                rows, failed = scrape_land(page, land, args, done, all_rows)
            except Exception as e:
                print(f"[{land}] ABORTED: {type(e).__name__}: {str(e).splitlines()[0]}")
                failed_lands.append(land)
                continue
            all_rows += rows
            still_failed += failed
            save_results_to_csv(all_rows)
        browser.close()

    print("saved", len(all_rows), "routes in", FILE_ALL)
    if failed_lands:
        print("lands that failed completely:", ", ".join(failed_lands))
        print("-> run again: python main.py --resume --lands", " ".join(failed_lands))
    if still_failed:
        print(f"{len(still_failed)} routes could not be read:")
        for u in still_failed:
            print("  ", u)
    # Analysis: canton assignment and research questions, based directly on the scraped routes
    results = run_analysis(all_rows)

if __name__ == "__main__":
    main()

