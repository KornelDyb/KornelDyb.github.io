# korneldyb.github.io

Portfolio of Kornel Dybalski – CRM, process automation, business development and analytics.
Static site (HTML/CSS/vanilla JS) on GitHub Pages, bilingual (PL/EN).

## Projects

| Folder | What it is |
|---|---|
| `projects/warsaw-housing/` | Analysis of 8,665 Warsaw apartment listings – district geo-matching, regression model, interactive estimator. Pipeline: `analysis/pipeline.py`. |
| `projects/nbp-rates/` | Daily automation: GitHub Actions fetches NBP exchange rates, computes KPIs, writes `REPORT.md`, refreshes the dashboard and opens an Issue on large moves. Code: `automation/fetch_rates.py`, workflow: `.github/workflows/nbp-rates.yml`. |
| `projects/lead-scoring/` | Browser-only lead-scoring tool with editable rule weights and CSV import/export. |

## CV – one data file, every output

`data/cv.json` is the single source of truth for the CV (Polish and English).
`tools/build_cv.py` turns it into:

- the Experience, skills and courses section of `index.html` (between the `CV:*` markers),
- printable pages in `cv/` (design and ATS versions, PL/EN),
- four PDFs in `assets/cv/`: a one-page design CV and a plain ATS-friendly CV, each in PL and EN.

Edit `data/cv.json` on GitHub and commit – the `cv` workflow rebuilds everything and commits the
result. The PDFs embed real TrueType fonts (static instances in `assets/fonts/static/`) so their text
stays machine-readable for applicant-tracking systems.

## Run locally

```bash
python -m http.server 8000          # then open http://localhost:8000

# re-run the housing analysis
pip install pandas numpy shapely
python projects/warsaw-housing/analysis/pipeline.py \
  --raw projects/warsaw-housing/data/raw/Houses.csv \
  --geo projects/warsaw-housing/data/raw/warszawa-dzielnice.geojson

# run the FX automation by hand
pip install requests pytest
cd projects/nbp-rates/automation && python -m pytest -q && python fetch_rates.py

# rebuild the CV (needs: pip install playwright && python -m playwright install chromium)
python tools/build_cv.py
```

## Data sources

- Apartment listings: Kaggle “House prices in Poland” (scraped c. 2021).
- Warsaw district boundaries: GeoJSON (CARTO).
- Exchange rates: National Bank of Poland API, table A.
- Fonts: Bricolage Grotesque and Instrument Sans (SIL Open Font License, self-hosted in `assets/fonts/`).
