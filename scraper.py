# Browser Automation & Scraping Logic

import re
from urllib.parse import urljoin
from playwright.sync_api import TimeoutError as PWTimeout

from config import BASE, LANDS, LEVELS, RATING_NAMES, FACTS_SEL, DETAILS_SEL, PAUSE_MS, SAVE_EVERY
from parsers import normalize, first_text, texts, pick, num, parse_details, parse_stages, split_start_end, KM_RE, N_STAGES_RE

def goto_retry(page, url, wait_until="domcontentloaded", tries=3, timeout=60_000):
    for attempt in range(1, tries + 1):
        try:
            page.goto(url, wait_until=wait_until, timeout=timeout)
            return
        except Exception as e:
            print(f"  could not load {url} (attempt {attempt}/{tries}): {type(e).__name__}")
            if attempt == tries:
                raise
            page.wait_for_timeout(5000)

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
        pass

    failed_rounds = 0
    while failed_rounds < 4:
        before = len(links)
        collect()

        loc = page.locator(link_selector)
        if loc.count():
            loc.last.evaluate("el => el.scrollIntoView({block: 'start'})")

        for _ in range(24):
            page.wait_for_timeout(250)
            collect()
            if len(links) > before:
                break

        if len(links) == before:
            page.mouse.move(700, 450)
            page.mouse.wheel(0, -600)
            page.wait_for_timeout(500)
            page.keyboard.press("End")
            page.wait_for_timeout(1500)
            collect()

        failed_rounds = failed_rounds + 1 if len(links) == before else 0
        print("  unique links so far:", len(links))

    return sorted(links)

def open_route(page, url):
    goto_retry(page, url)
    page.locator("h1").first.wait_for(state="visible", timeout=30_000)
    toggle = page.get_by_text("Höhenprofil anzeigen")
    if toggle.count():
        toggle.first.click()
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
    for _ in range(3 if has_elevation else 1):
        facts = texts(page.locator(FACTS_SEL))
        details = texts(page.locator(DETAILS_SEL))
        if not has_elevation or pick(facts, 3) == "Höhenprofil":
            break
        page.wait_for_timeout(1000)
    structure_ok = has_elevation and pick(facts, 3) == "Höhenprofil"
    if has_elevation and not structure_ok:
        print("  WARNING: unexpected page structure, elevation values left empty:", url)

    h2 = re.sub(r"^\s*Route:\s*", "", first_text(page, "h2") or "")
    start, via, end = split_start_end(h2)

    body = page.inner_text("body")
    stages = parse_stages(body)
    m = N_STAGES_RE.search(body)
    n_stages = int(m.group(1)) if m else (len(stages) or 1)

    distance = next((num(t) for t in facts + details if KM_RE.fullmatch(t)), None)

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

def dump_page(page):
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
        for i in range(min(3, len(hrefs))):
            card = page.locator(selector).nth(i)
            card_text = card.evaluate("el => (el.closest('li, article') || el.parentElement).innerText")
            print(f"  overview card {i}:", card_text.replace("\n", " / ")[:300])
        open_route(page, url)
        dump_page(page)

def scrape_land(page, land, args, done, saved_rows):
    cfg = LANDS[land]
    selector = f'a[href^="/de/{cfg["slug"]}/route-"]'
    levels = {}
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
            save_results_to_csv(saved_rows + rows) # Verweist auf CSV-Funktion in main
        page.wait_for_timeout(PAUSE_MS)

    if failed:
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