# Scrapes route information from schweizmobil.ch for several "Länder"
# (Wanderland, Veloland, Mountainbikeland, Skatingland, Kanuland).

import argparse
import os
import re
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "https://schweizmobil.ch"

# ---------------------------------------------------------------------------
# 1) CONFIGURATION: everything that differs between the "Länder" lives here
# ---------------------------------------------------------------------------
# slug      = the part of the URL that names the land
# overviews = the overview pages that list the routes (Kanuland has no local routes)
# elevation = False: the pages of this land show no elevation data (Kanuland); default is True
LANDS = {
    "wanderland":       {"slug": "wanderland",       "overviews": ["lokale-routen", "regionale-routen"]},
    "veloland":         {"slug": "veloland",         "overviews": ["lokale-routen", "regionale-routen"]},
    "mountainbikeland": {"slug": "mountainbikeland", "overviews": ["lokale-routen", "regionale-routen"]},
    "skatingland":      {"slug": "skatingland",      "overviews": ["lokale-routen", "regionale-routen"]},
    "kanuland":         {"slug": "kanuland",         "overviews": ["regionale-routen"], "elevation": False},
}
DEFAULT_LANDS = ["wanderland", "veloland", "mountainbikeland", "skatingland", "kanuland"]

# name of the route level in the output, nationale routen are not scraped
LEVELS = {"lokale-routen": "lokal", "regionale-routen": "regional", "nationale-routen": "national"}

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

def first_text(page, selector):
    """Text of first element or None."""
    loc = page.locator(selector)
    if loc.count() > 0:
        return loc.first.inner_text().strip()
    return None


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


# --- multi-stage routes (regional / national): "Etappe 1/8" and a list "Etappe 1: A – B ... 13 km" ---
N_STAGES_RE = re.compile(r"Etappe\s+\d+\s*/\s*(\d+)")
KM_RE = re.compile(r"[\d'\u2019]+(?:[.,]\d+)?\s*km")
STAGE_RE = re.compile(
    r"Etappe\s+(\d+):\s*([^\n]+)\n(?:(?!Etappe\s+\d+:).){0,80}?([\d'\u2019]+(?:[.,]\d+)?)\s*km",
    re.S,
)


def parse_stages(body):
    """Return [(number, name, length_km), ...]; the first occurrence of each stage number wins."""
    stages = {}
    for m in STAGE_RE.finditer(body):
        nr = int(m.group(1))
        if nr not in stages:
            stages[nr] = (m.group(2).strip(), num(m.group(3)))
    return [(nr, name, km) for nr, (name, km) in sorted(stages.items())]


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
PAUSE_MS = 1000        # pause between two route pages
SAVE_EVERY = 25        # save the result files after this many routes


def goto_retry(page, url, wait_until="domcontentloaded", tries=3, timeout=60_000):
    """page.goto with retries: a single slow page load must not stop a long run."""
    for attempt in range(1, tries + 1):
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout)
            return
        except Exception as e:
            print(f"  could not load {url} (attempt {attempt}/{tries}): {type(e).__name__}")
            if attempt == tries:
                raise
            page.wait_for_timeout(5000 * attempt)


def collect_links(page, overview_url, link_selector):
    links = set()

    def collect():
        hrefs = page.locator(link_selector).evaluate_all(
            "els => els.map(e => e.getAttribute('href'))")
        links.update(normalize(urljoin(overview_url, h)) for h in hrefs if h)

    goto_retry(page, overview_url)
    try:
        page.locator(link_selector).first.wait_for(timeout=30_000)
    except PWTimeout:
        pass                                     # no routes (or wrong URL): the loop below ends with an empty list
    # click away a cookie banner by hand if one appears (headless=False)

    failed_rounds = 0
    while failed_rounds < 4:
        before = len(links)
        collect()

        loc = page.locator(link_selector)
        if loc.count():
            loc.last.evaluate("el => el.scrollIntoView({block: 'start'})")

        for _ in range(24):                      # wait up to ~6 s for new entries
            page.wait_for_timeout(250)
            collect()
            if len(links) > before:
                break

        if len(links) == before:                 # wiggle to re-trigger the observer
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
    goto_retry(page, url)
    page.locator("h1").first.wait_for(state="visible", timeout=30_000)
    toggle = page.get_by_text("Höhenprofil anzeigen")
    if toggle.count():
        toggle.first.click()                     # .first: pages with several stages have several buttons
        try:
            page.locator("element-route-profile").first.wait_for(state="visible", timeout=10_000)
        except PWTimeout:
            pass
    try:
        page.locator(DETAILS_SEL).first.wait_for(timeout=10_000)
    except PWTimeout:
        pass


def scrape_route(page, url, land, level="lokal"):
    open_route(page, url)
    has_elevation = LANDS[land].get("elevation", True)
    for _ in range(3 if has_elevation else 1):   # page may not be fully rendered yet -> re-read
        facts = texts(page.locator(FACTS_SEL))
        details = texts(page.locator(DETAILS_SEL))
        if not has_elevation or pick(facts, 3) == "Höhenprofil":
            break
        page.wait_for_timeout(1000)
    structure_ok = has_elevation and pick(facts, 3) == "Höhenprofil"
    if has_elevation and not structure_ok:
        print("  WARNING: unexpected page structure, elevation values left empty:", url)
        print("    facts:  ", facts)
        print("    details:", details)

    # multi-stage pages have a "Route: " prefix in the h2 that single-stage pages do not have
    h2 = re.sub(r"^\s*Route:\s*", "", first_text(page, "h2") or "")
    start, via, end = split_start_end(h2)

    body = page.inner_text("body")
    stages = parse_stages(body)
    m = N_STAGES_RE.search(body)
    n_stages = int(m.group(1)) if m else (len(stages) or 1)
    if stages and n_stages != len(stages):
        print(f"  WARNING: {n_stages} stages announced but {len(stages)} parsed: {url}")

    # length of the whole route: first "<n> km" entry (facts[0] on all pages seen so far)
    distance = next((num(t) for t in facts + details if KM_RE.fullmatch(t)), None)

    # facts[] has the same order in all lands: distance, ascent, descent, (label), max, min
    # -> positions are only trusted if the structure check passed
    row = {
        "land": land,
        "route_level": level,
        "url": url,
        "title": first_text(page, "h1"),
        "start": start,
        "via": via,
        "end": end,
        "distance_km": distance,
        "n_etappen": n_stages,
        "etappen_detail": " | ".join(
            f"{nr}: {name}" + (f" ({km:g} km)" if km is not None else "") for nr, name, km in stages) or None,
        "el_gain_m": num(pick(facts, 1)) if structure_ok else None,
        "el_loss_m": num(pick(facts, 2)) if structure_ok else None,
        "el_max_m": num(pick(facts, 4)) if structure_ok else None,
        "el_min_m": num(pick(facts, 5)) if structure_ok else None,
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
def dump_page(page):
    """Print what a route/stage page contains (used by --inspect)."""
    print("  h1:", first_text(page, "h1"))
    print("  h2:", first_text(page, "h2"))
    print("  'Höhenprofil anzeigen' buttons:", page.get_by_text("Höhenprofil anzeigen").count())
    for i, t in enumerate(texts(page.locator(FACTS_SEL))):
        print(f"  facts[{i}]   = {t!r}")
    for i, t in enumerate(texts(page.locator(DETAILS_SEL))):
        print(f"  details[{i}] = {t!r}")

def inspect_land(page, land):
    cfg = LANDS[land]
    selector = f'a[href^="/de/{cfg["slug"]}/route-"]'
    for ov in cfg["overviews"]:
        overview = f"{BASE}/de/{cfg['slug']}/{ov}"
        page.goto(overview, wait_until="networkidle")
        page.wait_for_timeout(2000)
        hrefs = page.locator(selector).evaluate_all("els => els.map(e => e.getAttribute('href'))")
        print(f"\n===== {land} / {ov}: {len(hrefs)} route links visible without scrolling =====")
        if not hrefs:
            print("No links found -> check the link selector:", selector)
            continue
        print("all visible links:", sorted({normalize(urljoin(overview, h)) for h in hrefs if h}))
        url = normalize(urljoin(overview, hrefs[0]))
        print("first route:", url)
        for i in range(min(3, len(hrefs))):          # what does the overview show for a route?
            card = page.locator(selector).nth(i)
            card_text = card.evaluate("el => (el.closest('li, article') || el.parentElement).innerText")
            print(f"  overview card {i}:", card_text.replace("\n", " / ")[:300])
            card_imgs = card.evaluate(
                "el => [...(el.closest('li, article') || el.parentElement).querySelectorAll('img')]"
                ".map(i => (i.currentSrc || i.src) + ' | alt=' + i.alt)")
            print(f"  overview card {i} images:", card_imgs)
        open_route(page, url)
        dump_page(page)

        # multi-stage pages: show the stage list and the links to the stages
        stages = page.get_by_text(re.compile(r"^\s*Etappe\s+\d")).all_inner_texts()
        if stages:
            print("  stage texts:", [t.replace("\n", " / ") for t in stages[:20]])
            site_links = page.locator(f'a[href^="/de/{cfg["slug"]}/"]').evaluate_all(
                "els => els.map(e => e.getAttribute('href'))")
            print("  links on this page:", sorted(set(h for h in site_links if h))[:40])
            stage_link = page.get_by_role("link", name=re.compile("zur Etappe", re.I))
            if stage_link.count():
                href = stage_link.first.get_attribute("href")
                stage_url = normalize(urljoin(url, href))
                print("\n  --- first stage page:", stage_url)
                try:
                    open_route(page, stage_url)
                    dump_page(page)
                except Exception as e:
                    print("  stage page could not be read:", type(e).__name__)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
FILE_ALL = "result_lokal_regional.csv"


def save_results(rows):
    """Saves all scraped routes into a single CSV file."""
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(FILE_ALL, index=False, encoding="utf-8-sig")


def load_existing():
    """--resume: the rows of an earlier (possibly interrupted) run."""
    if not os.path.exists(FILE_ALL):
        return []
    return pd.read_csv(FILE_ALL).to_dict("records")


def scrape_land(page, land, args, done, saved_rows):
    """Scrape all routes of one land that are not in `done` yet. Returns (rows, urls that failed)."""
    cfg = LANDS[land]
    selector = f'a[href^="/de/{cfg["slug"]}/route-"]'
    levels = {}                                  # url -> route level (from the overview it was found on)
    for ov in cfg["overviews"]:
        overview_url = f"{BASE}/de/{cfg['slug']}/{ov}"
        print(f"[{land}] collecting links from {overview_url}")
        found = collect_links(page, overview_url, selector)
        if not found:
            print("  no routes found here - check the URL in LANDS")
        for u in (found[: args.limit] if args.limit else found):
            levels.setdefault(u, LEVELS.get(ov, ov))
    links = sorted(levels)
    todo = [u for u in links if u not in done]
    print(f"[{land}] {len(links)} unique routes, {len(links) - len(todo)} already scraped, {len(todo)} to do")

    rows, failed = [], []
    for i, url in enumerate(todo, 1):
        try:
            rows.append(scrape_route(page, url, land, levels[url]))
        except Exception as e:
            print("  failed:", url, str(e).splitlines()[0])
            failed.append(url)
        if i % SAVE_EVERY == 0:
            save_results(saved_rows + rows)
        page.wait_for_timeout(PAUSE_MS)

    if failed:                                   # second pass for the routes that failed
        print(f"[{land}] retrying {len(failed)} failed routes")
        page.wait_for_timeout(5000)
        for url in list(failed):
            try:
                rows.append(scrape_route(page, url, land, levels[url]))
                failed.remove(url)
            except Exception as e:
                print("  failed again:", url, str(e).splitlines()[0])
            page.wait_for_timeout(PAUSE_MS)

    print(f"[{land}] {len(rows)} routes scraped")
    return rows, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lands", nargs="+", default=DEFAULT_LANDS, choices=list(LANDS))
    ap.add_argument("--inspect", action="store_true", help="only print page structure, no scraping")
    ap.add_argument("--limit", type=int, default=None, help="max. routes per overview (for testing)")
    ap.add_argument("--show", action="store_true", help="show the browser window")
    ap.add_argument("--resume", action="store_true",
                    help="keep the rows already in the result file and scrape only the routes that are missing")
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
            except Exception as e:               # one broken land must not stop the others
                print(f"[{land}] ABORTED: {type(e).__name__}: {str(e).splitlines()[0]}")
                failed_lands.append(land)
                continue
            all_rows += rows
            still_failed += failed
            save_results(all_rows)               # also saved every few routes (crash protection)
        browser.close()

    print("saved", len(all_rows), "routes in", FILE_ALL)
    if failed_lands:
        print("lands that failed completely:", ", ".join(failed_lands))
        print("-> run again:  python schweizmobil_scraper.py --resume --lands", " ".join(failed_lands))
    if still_failed:
        print(f"{len(still_failed)} routes could not be read (check them in the browser):")
        for u in still_failed:
            print("  ", u)


if __name__ == "__main__":
    main()