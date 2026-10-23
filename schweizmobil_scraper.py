# Scrapes route information from schweizmobil.ch for several "Länder"
# (Wanderland, Veloland, Mountainbikeland, Skatingland, optionally Kanuland).

#   python schweizmobil_scraper.py --inspect                 # step 1: look at the page structure
#   python schweizmobil_scraper.py                           # step 2: scrape the 4 land with local routes
#   python schweizmobil_scraper.py --lands veloland --limit 5  # quick test run
#   python schweizmobil_scraper.py --lands kanuland          # experimental (no local routes exist)

import argparse
import re
from urllib.parse import urljoin, urlparse

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "https://schweizmobil.ch"

# ---------------------------------------------------------------------------
# 1) CONFIGURATION: everything that differs between the "Länder" lives here
# ---------------------------------------------------------------------------
# slug      = the part of the URL that names the land
# overviews = the overview pages that list the routes (Kanuland has no local routes)
LANDS = {
    "wanderland":       {"slug": "wanderland",       "overviews": ["lokale-routen"]},
    "veloland":         {"slug": "veloland",         "overviews": ["lokale-routen"]},
    "mountainbikeland": {"slug": "mountainbikeland", "overviews": ["lokale-routen"]},
    "skatingland":      {"slug": "skatingland",      "overviews": ["lokale-routen"]},
    "kanuland":         {"slug": "kanuland",         "overviews": ["regionale-routen", "nationale-routen"]},
}
DEFAULT_LANDS = ["wanderland", "veloland", "mountainbikeland", "skatingland"]

# Names of the difficulty ratings, in the order they appear on the page.

RATING_NAMES = {
    "wanderland":       ["technical", "condition"],
    "veloland":         ["condition"],
    "mountainbikeland": ["technical", "condition"],
    "skatingland":      ["technical", "condition"],
    "kanuland":         [],
}

FACTS_SEL = "element-tour-facts .facts-list > div"
DETAILS_SEL = "div.py-details-p"


# ---------------------------------------------------------------------------

# helpers
# ---------------------------------------------------------------------------
def normalize(u):
    """Drop query string / fragment, so the same route is not collected twice."""
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}{p.path}"


def texts(locator):
    """All texts of a locator as a list (no waiting, never raises)."""
    return [locator.nth(i).inner_text().strip() for i in range(locator.count())]


def pick(items, idx):
    """items[idx] or None, instead of an IndexError that would drop the whole route."""
    return items[idx] if idx is not None and idx < len(items) else None


def num(s):
    """"2'300 m" -> 2300.0, "20 km" -> 20.0, None if there is no number."""
    if not s:
        return None
    m = re.search(r"\d[\d'\u2019]*(?:[.,]\d+)?", s)
    if not m:
        return None
    return float(m.group().replace("'", "").replace("\u2019", "").replace(",", "."))


def duration_min(s):
    """"5 h 25 min" -> 325"""
    h = re.search(r"(\d+)\s*h\b", s)
    m = re.search(r"(\d+)\s*min\b", s)
    if not (h or m):
        return None
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


RATING_RE = re.compile(r"^(sehr )?(leicht|mittel|schwer)\b", re.I)
DURATION_RE = re.compile(r"^\d+\s*(h|min)\b")
SURFACES = (("Asphaltiert", "asphalt_km"), ("Naturbelag", "natural_km"), ("Single Trail", "singletrail_km"))


def parse_details(details):
    """Sort the texts of div.py-details-p by CONTENT instead of position, because the
    fields (and their order) differ between the lands. Returns (fields, ratings)."""
    out = {"duration_min": None, "direction_note": None,
           "asphalt_km": None, "natural_km": None, "singletrail_km": None}
    ratings = []
    for t in details:
        if any(label in t for label, _ in SURFACES):
            for label, key in SURFACES:
                m = re.search(label + r":\s*([\d'\u2019.,]+)\s*km", t)
                if m:
                    out[key] = num(m.group(1))
        elif DURATION_RE.match(t):
            out["duration_min"] = duration_min(t)
        elif "Richtung" in t:
            out["direction_note"] = t
        elif RATING_RE.match(t):
            ratings.append(t)
    return out, ratings


def first_text(page, selector):
    loc = page.locator(selector)
    return loc.first.inner_text().strip() if loc.count() else None


def split_start_end(s):
    """'A – via1–via2 – B' -> start 'A', via 'via1–via2', end 'B'."""
    if not s:
        return None, None, None
    parts = [p.strip() for p in s.split(" – ")]
    if len(parts) == 1:
        return parts[0], None, None
    return parts[0], " – ".join(parts[1:-1]) or None, parts[-1]


# ---------------------------------------------------------------------------
# 2) collect the links to all routes of one overview page (lazy loading / scrolling)
# ---------------------------------------------------------------------------
def collect_links(page, overview_url, link_selector):
    links = set()

    def collect():
        hrefs = page.locator(link_selector).evaluate_all(
            "els => els.map(e => e.getAttribute('href'))")
        links.update(normalize(urljoin(overview_url, h)) for h in hrefs if h)

    page.goto(overview_url, wait_until="networkidle")
    # click away a cookie banner by hand if one appears (headless=False)

    failed_rounds = 0
    while failed_rounds < 4:
        before = len(links)
        collect()

        loc = page.locator(link_selector)
        if loc.count():
            loc.last.evaluate("el => el.scrollIntoView({block: 'start'})")

        for _ in range(24):  # wait up to ~6 s for new entries
            page.wait_for_timeout(250)
            collect()
            if len(links) > before:
                break

        if len(links) == before:  # wiggle to re-trigger the observer
            page.mouse.move(700, 450)
            page.mouse.wheel(0, -600)
            page.wait_for_timeout(500)
            page.keyboard.press("End")
            page.wait_for_timeout(1500)
            collect()

        failed_rounds = failed_rounds + 1 if len(links) == before else 0
        print("  unique links so far:", len(links))

    return sorted(links)


# ---------------------------------------------------------------------------
# 3) scrape one route page
# ---------------------------------------------------------------------------
def open_route(page, url):
    page.goto(url, wait_until="domcontentloaded")
    page.locator("h1").first.wait_for(state="visible", timeout=15_000)
    toggle = page.get_by_text("Höhenprofil anzeigen")
    if toggle.count():
        toggle.first.click()  # .first: pages with several stages have several buttons
        try:
            page.locator("element-route-profile").first.wait_for(state="visible", timeout=10_000)
        except PWTimeout:
            pass
    try:
        page.locator(DETAILS_SEL).first.wait_for(timeout=10_000)
    except PWTimeout:
        pass


def scrape_route(page, url, land):
    open_route(page, url)
    for _ in range(3):  # page may not be fully rendered yet -> re-read
        facts = texts(page.locator(FACTS_SEL))
        details = texts(page.locator(DETAILS_SEL))
        if pick(facts, 3) == "Höhenprofil":
            break
        page.wait_for_timeout(1000)
    if pick(facts, 3) != "Höhenprofil":
        print("  WARNING: unexpected page structure, check:", url)
        print("    facts:  ", facts)
        print("    details:", details)
    start, via, end = split_start_end(first_text(page, "h2"))

    # facts[] has the same order in all lands: distance, ascent, descent, (label), max, min
    row = {
        "land": land,
        "url": url,
        "title": first_text(page, "h1"),
        "start": start,
        "via": via,
        "end": end,
        "distance_km": num(pick(facts, 0)),
        "el_gain_m": num(pick(facts, 1)),
        "el_loss_m": num(pick(facts, 2)),
        "el_max_m": num(pick(facts, 4)),
        "el_min_m": num(pick(facts, 5)),
    }
    fields, ratings = parse_details(details)
    row.update(fields)
    names = RATING_NAMES.get(land, [])
    for i, r in enumerate(ratings):
        row[names[i] if i < len(names) else f"rating_{i + 1}"] = r
    row["facts_raw"] = " | ".join(facts).replace("\n", " / ")
    row["details_raw"] = " | ".join(details).replace("\n", " / ")
    return row


# ---------------------------------------------------------------------------
# 4) --inspect: print the lists with their indices for the first route of each land
# ---------------------------------------------------------------------------
def inspect_land(page, land):
    cfg = LANDS[land]
    overview = f"{BASE}/de/{cfg['slug']}/{cfg['overviews'][0]}"
    selector = f'a[href^="/de/{cfg["slug"]}/route-"]'
    page.goto(overview, wait_until="networkidle")
    page.wait_for_timeout(2000)
    hrefs = page.locator(selector).evaluate_all("els => els.map(e => e.getAttribute('href'))")
    print(f"\n===== {land}: {len(hrefs)} route links visible without scrolling =====")
    if not hrefs:
        print("No links found -> check the link selector:", selector)
        return
    url = normalize(urljoin(overview, hrefs[0]))
    print("first route:", url)
    open_route(page, url)
    print("h1:", first_text(page, "h1"))
    print("h2:", first_text(page, "h2"))
    for i, t in enumerate(texts(page.locator(FACTS_SEL))):
        print(f"  facts[{i}]   = {t!r}")
    for i, t in enumerate(texts(page.locator(DETAILS_SEL))):
        print(f"  details[{i}] = {t!r}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lands", nargs="+", default=DEFAULT_LANDS, choices=list(LANDS))
    ap.add_argument("--inspect", action="store_true", help="only print page structure, no scraping")
    ap.add_argument("--limit", type=int, default=None, help="max. routes per overview (for testing)")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    args = ap.parse_args()

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        if args.inspect:
            for land in args.lands:
                inspect_land(page, land)
            browser.close()
            return

        for land in args.lands:
            cfg = LANDS[land]
            selector = f'a[href^="/de/{cfg["slug"]}/route-"]'
            links = []
            for ov in cfg["overviews"]:
                overview_url = f"{BASE}/de/{cfg['slug']}/{ov}"
                print(f"[{land}] collecting links from {overview_url}")
                found = collect_links(page, overview_url, selector)
                links += found[: args.limit] if args.limit else found
            links = sorted(set(links))
            print(f"[{land}] {len(links)} unique routes")

            rows = []
            for url in links:
                try:
                    rows.append(scrape_route(page, url, land))
                except Exception as e:
                    print("  failed:", url, e)
                page.wait_for_timeout(500)

            if rows:
                pd.DataFrame(rows).to_csv(f"result_{land}.csv", index=False,
                                          encoding="utf-8-sig")  # save after each land
                all_rows += rows
        browser.close()

    if all_rows:
        pd.DataFrame(all_rows).to_csv("result_all.csv", index=False, encoding="utf-8-sig")
        print("saved", len(all_rows), "routes")


if __name__ == "__main__":
    main()
