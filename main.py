#Control, CLI & CSV output

import argparse
import os
import pandas as pd
from playwright.sync_api import sync_playwright

from config import DEFAULT_LANDS, LANDS, FILE_ALL
from scraper import inspect_land, scrape_land

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

if __name__ == "__main__":
    main()
