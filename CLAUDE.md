# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install all dependencies
pip install -r requirements.txt
playwright install chromium   # one-time: install headless browser for the scraper

# ── EV Market dashboard ───────────────────────────────────────────────────────
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false

# ── BYD Ads Intelligence UI (scraper + viewer in one) ─────────────────────────
streamlit run byd_ads_app.py --server.enableCORS false --server.enableXsrfProtection false

# ── Run the BYD scraper standalone (Playwright headless browser) ──────────────
python byd_scraper.py                          # 300 ads, headless
python byd_scraper.py --max 100 --visible      # visible browser (debug)
python byd_scraper.py --output my_file.xlsx    # custom output path

# ── Run the BYD scraper via Facebook's official API ──────────────────────────
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

### BYD Ads Intelligence (`byd_ads_app.py` + `byd_scraper.py` + `byd_api_scraper.py`)

**`byd_ads_app.py`** — Streamlit app that is the main UI for the entire BYD ads workflow:
- Sidebar panel to trigger `byd_scraper.py` as a subprocess and stream live output
- Analytics charts: platform donut, CTA bar, impressions distribution, monthly timeline
- Ad gallery grid (3 columns, paginated 12/page) — each card shows the actual ad image, headline, body text, and metadata badges (CTA, platform, impressions, date)
- "Ver anuncio completo" expander on each card with full detail + large image
- Filters: text search, platform multi-select, CTA multi-select
- One-click Excel export of the current filtered view
- Reads from `byd_ads_output/ads_raw_*.json` (auto-selects latest; dropdown to choose older runs)

**`byd_scraper.py`** — Playwright (headless Chromium). Navigates to the public Facebook Ads Library page for `PAGE_ID=129337183749169`, scrolls to trigger dynamic loading, extracts ad cards via CSS selectors with a JS heuristic fallback, downloads ad images immediately (before CDN tokens expire), and produces:
- `byd_ads_output/BYD_CR_Ads_<timestamp>.xlsx` — formatted Excel with embedded thumbnails
- `byd_ads_output/ads_raw_<timestamp>.json` — structured JSON read by the Streamlit app
- `byd_ads_output/images/` — downloaded ad images
- `create_excel()` is a public function imported by `byd_ads_app.py` for the in-app download button

**`byd_api_scraper.py`** — Facebook Graph API (`/v21.0/ads_archive`). Requires a Facebook Access Token (from `FB_ACCESS_TOKEN` env var or `--token` arg). More reliable than the browser scraper. Outputs the same Excel/JSON format.

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
