# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the Streamlit dashboard (dev)
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false

# Install all dependencies
pip install -r requirements.txt

# Install Playwright browsers (required once for the BYD scraper)
playwright install chromium

# Run the BYD ads scraper (Playwright headless browser)
python byd_scraper.py
python byd_scraper.py --max 100 --visible      # open visible browser for debugging
python byd_scraper.py --output my_file.xlsx

# Run the BYD ads scraper via Facebook's official API
export FB_ACCESS_TOKEN="EAAxxxx..."
python byd_api_scraper.py
python byd_api_scraper.py --token "EAAxxxx..." --max 500
```

The devcontainer auto-runs the Streamlit app on port 8501 via `postAttachCommand` in `.devcontainer/devcontainer.json`.

## Architecture

### Dashboard (`app.py` + `market_suite/`)

`app.py` is a self-contained Streamlit monolith with four pages (Home, Macro, Benchmark, Deep Dive) and sidebar navigation. The `market_suite/` package contains modular helpers that were extracted from the original monolith (preserved in `app_monolito_backup.py`):

| Module | Responsibility |
|---|---|
| `market_suite/data.py` | Parquet load, column canonicalization, date/price filtering |
| `market_suite/state.py` | `st.session_state` initialization, figure registry for PDF export |
| `market_suite/ui.py` | Sidebar with date-range/export/theme controls, reusable KPI cards, page headers |
| `market_suite/pdf_export.py` | `ExecutivePDF` (FPDF subclass) + `build_pdf_bytes()` cached builder |
| `market_suite/config.py` | App-wide constants (title, icon, data paths, brand colors) |

> **Note:** `market_suite/state.py` and `market_suite/ui.py` are physically stored as directories (e.g., `state.py/state.py`) — a filesystem quirk. Import them normally; Python resolves through the `__init__.py`.

### Data Flow

```
historial_lite.parquet (334 k rows, 35 cols)
  → data.load_data_flow()          # cached @st.cache_data TTL=1h
  → data.ensure_required_columns() # rename via CANON_COLS dict
  → data.etl_clean()               # drop nulls/dupes, enforce dtypes
  → data.apply_time_view()         # date-range filter from sidebar
  → Plotly charts in each page
  → state.register_figure()        # adds to figure_registry in session state
  → pdf_export.build_pdf_bytes()   # reads figure_registry → FPDF document
```

**Column canonicalization (`CANON_COLS` in `data.py`):** Raw parquet column names (e.g. `MARCA`, `PRECIO_VENTA`, `AÑO`) are lowercased to `marca`, `precio`, `año`. Always use canonical names in any new analysis code.

**Key parquet columns after canonicalization:** `fecha` (datetime), `año` (int), `marca`, `modelo`, `precio` (float), `empresa`, `distribuidor`, `combustible`, `categoria`, `cantidad` (int), `valor us$ cif` (float).

### BYD Ads Scrapers

Two standalone CLI scripts — no Streamlit dependency:

**`byd_scraper.py`** — Playwright (headless Chromium). Navigates to the public Facebook Ads Library page for `PAGE_ID=129337183749169`, scrolls to trigger dynamic loading, extracts ad cards via CSS selectors with a JS heuristic fallback, downloads images, and produces:
- `byd_ads_output/BYD_CR_Ads_<timestamp>.xlsx` — formatted Excel with embedded image thumbnails
- `byd_ads_output/ads_raw_<timestamp>.json` — raw backup
- `byd_ads_output/images/` — downloaded ad images

**`byd_api_scraper.py`** — Facebook Graph API (`/v21.0/ads_archive`). Requires a Facebook Access Token (from `FB_ACCESS_TOKEN` env var or `--token` arg). More reliable than the browser scraper but needs manual token setup at `developers.facebook.com`. Outputs the same Excel/JSON format.

Both scrapers share the same Excel column layout (N°, ID Anuncio, Texto, Titular, Descripción, CTA, Fecha Inicio, Estado, Plataformas, Rango Impresiones, URL Imagen, Vista Previa) and write to `byd_ads_output/`.

### Session State Keys

All keys are initialized by `state.init_session_state()`:

| Key | Values | Purpose |
|---|---|---|
| `theme_mode` | `SYSTEM` / `DARK_FORCE` / `LIGHT_FORCE` | CSS injection in `ui.inject_custom_css()` |
| `time_view` | `FULL` / `YTD` | Passed to `data.apply_time_view()` |
| `figure_registry` | list of dicts | Accumulates Plotly figs for PDF export |
| `menu` | page name string | Active sidebar page |
| `data_source_mode` | `AUTO` | Controls whether to load from local parquet or URL |
| `uploaded_parquet` | bytes or None | User-uploaded parquet from sidebar |
