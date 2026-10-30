# Helpers and Parsing-Functions

import re
from urllib.parse import urlparse

RATING_RE = re.compile(r"^(sehr )?(leicht|mittel|schwer)\b", re.I)
DURATION_RE = re.compile(r"^\d+\s*(h|min)\b")
SURFACES = (("Asphaltiert", "asphalt_km"), ("Naturbelag", "natural_km"), ("Single Trail", "singletrail_km"))

N_STAGES_RE = re.compile(r"Etappe\s+\d+\s*/\s*(\d+)")
KM_RE = re.compile(r"[\d'\u2019]+(?:[.,]\d+)?\s*km")
STAGE_RE = re.compile(
    r"Etappe\s+(\d+):\s*([^\n]+)\n(?:(?!Etappe\s+\d+:).){0,80}?([\d'\u2019]+(?:[.,]\d+)?)\s*km",
    re.S,
)

def normalize(u):
    p = urlparse(u)
    return f"{p.scheme}://{p.netloc}{p.path}"

def first_text(page, selector):
    loc = page.locator(selector)
    if loc.count() > 0:
        return loc.first.inner_text().strip()
    return None

def texts(locator):
    return [locator.nth(i).inner_text().strip() for i in range(locator.count())]

def pick(items, idx):
    return items[idx] if idx is not None and idx < len(items) else None

def num(s):
    if not s:
        return None
    m = re.search(r"\d[\d'\u2019]*(?:[.,]\d+)?", s)
    if not m:
        return None
    return float(m.group().replace("'", "").replace("\u2019", "").replace(",", "."))

def duration_min(s):
    h = re.search(r"(\d+)\s*h\b", s)
    m = re.search(r"(\d+)\s*min\b", s)
    if not (h or m):
        return None
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)

def parse_details(details):
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

def parse_stages(body):
    stages = {}
    for m in STAGE_RE.finditer(body):
        nr = int(m.group(1))
        if nr not in stages:
            stages[nr] = (m.group(2).strip(), num(m.group(3)))
    return [(nr, name, km) for nr, (name, km) in sorted(stages.items())]

def split_start_end(s):
    if not s:
        return None, None, None
    parts = [p.strip() for p in s.split(" – ")]
    if len(parts) == 1:
        return parts[0], None, None
    return parts[0], " – ".join(parts[1:-1]) or None, parts[-1]