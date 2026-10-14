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

# I tried using this method with playwright because not all entries are loaded without scrolling
# But it has not worked yet.

# LINK_SELECTOR is used to identify where the links can be found
LINK_SELECTOR = 'a[href^="/de/wanderland/route-"]'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")

    # Scroll until the number of links stops growing
    prev_count, stable_rounds = 0, 0
    while stable_rounds < 3:  # 3 unchanged rounds = done
        page.mouse.wheel(0, 5000)  # or: page.keyboard.press("End")
        page.wait_for_timeout(1500)
        count = page.locator(LINK_SELECTOR).count()
        stable_rounds = stable_rounds + 1 if count == prev_count else 0
        prev_count = count
        print("links loaded:", count)

# collecting the links to each sub page with more details per route
    links = sorted({
        urljoin(url, href)
        for href in page.locator(LINK_SELECTOR).evaluate_all(
            "els => els.map(e => e.getAttribute('href'))")
        if href
    })
    print(len(links), "unique links")

# collecting the relevant information on the subpages
    rows = []
    for url in links:
        try:
            page.goto(url, wait_until="domcontentloaded")
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
                         "condition": condition})
        except Exception as e:
            print("failed:", url, e)
        page.wait_for_timeout(500)

    browser.close()

pd.DataFrame(rows).to_csv("result.csv", index=False)

# To Do
## divide start end