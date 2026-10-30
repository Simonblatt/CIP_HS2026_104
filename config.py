# Configuration & Constants

BASE = "https://schweizmobil.ch"

LANDS = {
    "wanderland":       {"slug": "wanderland",       "overviews": ["lokale-routen", "regionale-routen"]},
    "veloland":         {"slug": "veloland",         "overviews": ["lokale-routen", "regionale-routen"]},
    "mountainbikeland": {"slug": "mountainbikeland", "overviews": ["lokale-routen", "regionale-routen"]},
    "skatingland":      {"slug": "skatingland",      "overviews": ["lokale-routen", "regionale-routen"]},
    "kanuland":         {"slug": "kanuland",         "overviews": ["regionale-routen"], "elevation": False},
}
DEFAULT_LANDS = ["wanderland", "veloland", "mountainbikeland", "skatingland", "kanuland"]

LEVELS = {"lokale-routen": "lokal", "regionale-routen": "regional", "nationale-routen": "national"}

RATING_NAMES = {
    "wanderland":       ["technical", "condition"],
    "veloland":         ["condition"],
    "mountainbikeland": ["technical", "condition"],
    "skatingland":      ["technical", "condition"],
    "kanuland":         [],
}

FACTS_SEL = "element-tour-facts .facts-list > div"
DETAILS_SEL = "div.py-details-p"

FILE_ALL = "schweizmobil_routen.csv"
PAUSE_MS = 1000
SAVE_EVERY = 25