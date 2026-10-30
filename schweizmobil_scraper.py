# This script extracts the information from all routes in Wanderland > Lokale Routen

# INFO: PROBLEM, DASS NICHT ALLE ROUTEN GELADEN WERDEN KONNTE GELÖST WERDEN.
# INFORMATIONEN AUS DEM HÖHENPROFIL SIND JETZT AUCH ENTHALTEN.

# OFFENES PROBLEM: DIE SEITEN DER ROUTEN MIT MEHREREN ETAPPEN SCHEINEN EINE ANDERE STRUKTUR ZU HABEN.

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import pandas as pd
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

url = 'https://schweizmobil.ch/de/wanderland/lokale-routen'
print(url)

# We start on the overview page where only limited information on each route is available.
# Here, we only collect the URLs leading to the subpages with more information for each route.

# LINK_SELECTOR is used to identify where the links to the subpages can be found
LINK_SELECTOR = 'a[href^="/de/wanderland/route-"]'

# Define a function to collect all links to subpages on the overview page
def collect(page, links):
    hrefs = page.locator(LINK_SELECTOR).evaluate_all(
        "els => els.map(e => e.getAttribute('href'))")
    links.update(urljoin(url, h) for h in hrefs if h)


# When loading the page not all routes are shown immediately.
# Therefore, we need to simulate scrolling.

# ACHTUNG: DIESER PROZESS ENTHÄLT JETZT VIELLEICHT ELEMENTE, DIE NICHT NOTWENDIG SIND UND KÖNNTE MIT AUSPROBIEREN EVTL. NOCH EFFIZIENTER GESTALTET WERDEN.

with (sync_playwright() as p):
    browser = p.chromium.launch(headless=True)     # watch it once, switch back later
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(url, wait_until="networkidle")
    #page.wait_for_timeout(3000)                     # click away a cookie banner by hand if one appears

    links = set()
    failed_rounds = 0

    while failed_rounds < 4:
        before = len(links)
        collect(page, links)

        loc = page.locator(LINK_SELECTOR)
        if loc.count():
            # last entry to the top of the viewport -> the area below it is visible
            loc.last.evaluate("el => el.scrollIntoView({block: 'start'})")

        # wait up to ~6 s for new entries
        for _ in range(24):
            page.wait_for_timeout(250)
            collect(page, links)
            if len(links) > before:
                break

        if len(links) == before:
            # wiggle to re-trigger the observer
            page.mouse.move(700, 450)
            page.mouse.wheel(0, -600)
            page.wait_for_timeout(500)
            page.keyboard.press("End")
            page.wait_for_timeout(1500)
            collect(page, links)

        failed_rounds = failed_rounds + 1 if len(links) == before else 0
        print("unique links so far:", len(links))

    links = sorted(links)
    print(len(links), "unique links")

# collecting the relevant information on the subpages
    rows = []
    for url in links:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.get_by_text("Höhenprofil anzeigen").click() # click on that text, otherwise not all information is displayed
            profile = page.locator("element-route-profile")
            profile.wait_for(state = "visible")
            info = page.locator("element-tour-facts .facts-list > div")
            el_max = info.nth(4).inner_text()
            el_min = info.nth(5).inner_text()
            title = page.locator("h1").first.inner_text()
            start_end = page.locator("h2").first.inner_text()
            distance = page.locator('div[class="flex flex-col"]').first.inner_text()
            details = page.locator("div.py-details-p")
            el_gain = details.nth(2).inner_text()
            el_loss = details.nth(3).inner_text()
            duration = details.nth(5).inner_text()
            technical = details.nth(6).inner_text()
            condition = details.nth(7).inner_text()
            rows.append({"url": url,
                         "title": title,
                         "start_end": start_end,
                         "distance": distance,
                         "el_gain": el_gain,
                         "el_loss": el_loss,
                         "duration": duration,
                         "technical": technical,
                         "condition": condition,
                         "el_max": el_max,
                         "el_min": el_min})
        except Exception as e:
            print("failed:", url, e)
        page.wait_for_timeout(500)

    browser.close()

results = pd.DataFrame(rows)

# split the column containing the start and end point
results[["start", "end"]] = results["start_end"].str.split(" – ", n=1, expand=True)

# remove whitespace
results["start"] = results["start"].str.strip()
results["end"] = results["end"].str.strip()

results = results.drop(columns=["start_end"])   # optional: remove the original column
results.to_csv("result.csv", index=False)