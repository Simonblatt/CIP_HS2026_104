# SchweizMobil route scraper

Collects route information from [schweizmobil.ch](https://schweizmobil.ch) for five activity types
(Wanderland, Veloland, Mountainbikeland, Skatingland, Kanuland).

## Setup

```
pip install -r requirements.txt
playwright install chromium
```

## Usage

```
python schweizmobil_scraper.py --inspect --lands wanderland   # print the page structure of one route (diagnosis)
python schweizmobil_scraper.py --lands veloland --limit 3      # quick test run
python schweizmobil_scraper.py                                 # all lands -> the two result files below
python schweizmobil_scraper.py --resume                        # continue an interrupted run (see below)
```

Options: `--lands` (one or more lands), `--limit N` (max. routes per overview, for testing),
`--show` (show the browser window), `--inspect` (no scraping, only print the page structure),
`--resume` (keep the rows already in the result file and scrape only the routes that are missing).

A full run takes a long time. The result files are saved every 25 routes and after every land. If a land fails
or the run is interrupted, start again with `--resume` (add `--lands ...` for the lands that are missing).
Routes that cannot be read are retried once and listed at the end of the run.

## Result files

One scraping run writes one file:

| File | Content |
|---|---|
| `result_lokal_regional.csv` | local and regional routes of all five lands |

National routes are not included. Kanuland is only available as regional routes.

Data retrieved on: 30.10.2026. Source: schweizmobil.ch.

## Columns

`land`, `route_level` (lokal / regional), `url`, `title`, `start`, `via`, `end`,
`distance_km`, `n_etappen`, `etappen_detail`, `el_gain_m`, `el_loss_m`, `el_max_m`, `el_min_m`,
`duration_min`, `asphalt_km`, `natural_km`, `singletrail_km`, `direction_note`, and the difficulty ratings
(`technical`, `condition`; for Kanuland `rating_1`, `rating_2`). The raw texts are kept in `facts_raw` and
`details_raw` for checking.

## How it works

- One script for all lands. Differences between the lands (URL name, overview pages, elevation data
  available or not) are set in the `LANDS` dictionary at the top of the file.
- Values that differ between the lands are recognised by their **content** (e.g. "5 h 25 min" = duration,
  "Asphaltiert: 7 km" = surface) and not by their position on the page.
- Multi-stage routes (regional routes): the number of stages and a text with all stages are stored; the route
  length is the value shown for the whole route, not the sum of the stages.

## Known limitations
-Regional routes: `duration_min` is empty (the page shows no total duration); the stage lengths in
  `etappen_detail` were not verified on all lands.
- The ratings of Mountainbikeland and Skatingland are assumed to be in the order technical, condition.
- Pages with an unexpected structure produce a warning and leave the elevation columns empty.

