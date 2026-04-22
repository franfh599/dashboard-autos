#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BYD Costa Rica - Facebook Ad Library API Scraper
=================================================
Alternativa al scraper de Playwright que usa la API pública oficial de
Facebook para obtener los anuncios de forma más confiable y sin riesgo
de bloqueo por anti-bot.

REQUISITOS PREVIOS:
  1. Crear una cuenta de desarrollador en https://developers.facebook.com
  2. Crear una App → obtener App ID y App Secret
  3. Generar un token: https://developers.facebook.com/tools/accesstoken/
     (tipo: App Token o User Token con permiso ads_read)
  4. Exportar como variable de entorno:
         export FB_ACCESS_TOKEN="your_token_here"
     O pasarlo como argumento:
         python byd_api_scraper.py --token "your_token_here"

Uso:
    python byd_api_scraper.py
    python byd_api_scraper.py --token "EAAxxxx..."
    python byd_api_scraper.py --max 500 --output mis_anuncios.xlsx

Documentación oficial de la API:
    https://developers.facebook.com/docs/marketing-api/reference/ads-archive
"""

from __future__ import annotations
import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage

# =============================================================================
# CONFIG
# =============================================================================

PAGE_ID        = "129337183749169"
PAGE_NAME      = "BYD Costa Rica"
API_VERSION    = "v21.0"
API_BASE       = f"https://graph.facebook.com/{API_VERSION}"

OUTPUT_DIR     = Path("byd_ads_output")
IMAGES_DIR     = OUTPUT_DIR / "images"
MAX_ADS_DEFAULT = 500
RESULTS_PER_PAGE = 50   # max allowed by Facebook API

# Fields to request from the API
AD_FIELDS = ",".join([
    "id",
    "ad_creative_body",
    "ad_creative_link_caption",
    "ad_creative_link_description",
    "ad_creative_link_title",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "ad_snapshot_url",
    "currency",
    "estimated_audience_size",
    "impressions",
    "page_id",
    "page_name",
    "publisher_platforms",
    "spend",
    "region_distribution",
])

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

# BYD brand colors
COLOR_HEADER_BG = "1A1A2E"
COLOR_HEADER_FG = "FFFFFF"
COLOR_RED       = "E31837"
COLOR_ALT_ROW   = "F4F6F9"
COLOR_BORDER    = "CCCCCC"

_thin      = Side(style="thin", color=COLOR_BORDER)
BORDER_ALL = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

# =============================================================================
# SETUP
# =============================================================================

def setup_dirs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)


def log(msg: str, indent: int = 0) -> None:
    print("  " * indent + msg, flush=True)


# =============================================================================
# IMAGE HELPERS
# =============================================================================

def download_image(url: str, stem: str) -> str | None:
    if not url:
        return None
    try:
        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Referer": "https://www.facebook.com/"},
            timeout=20, stream=True
        )
        if r.status_code != 200:
            return None
        ct  = r.headers.get("content-type", "")
        ext = ".png" if "png" in ct else ".webp" if "webp" in ct else ".jpg"
        safe = re.sub(r"[^\w\-]", "_", stem)[:80]
        fpath = IMAGES_DIR / f"{safe}{ext}"
        with open(fpath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return str(fpath)
    except Exception as exc:
        log(f"[img] {exc}", 2)
        return None


def thumbnail_bytes(path: str, size=(150, 150)) -> io.BytesIO | None:
    try:
        img = PILImage.open(path).convert("RGB")
        img.thumbnail(size, PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


# =============================================================================
# FACEBOOK API
# =============================================================================

def fetch_ads_page(token: str, after_cursor: str | None = None) -> dict:
    """Fetch one page of ads from the Facebook Ad Library API."""
    params = {
        "access_token":      token,
        "ad_type":           "ALL",
        "ad_reached_countries": '["CR"]',
        "search_page_ids":   PAGE_ID,
        "ad_active_status":  "ACTIVE",
        "fields":            AD_FIELDS,
        "limit":             RESULTS_PER_PAGE,
    }
    if after_cursor:
        params["after"] = after_cursor

    resp = requests.get(f"{API_BASE}/ads_archive", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_ad(raw: dict) -> dict:
    """Convert raw API ad dict into our normalized format."""
    ad: dict = {}

    ad["ad_id"]      = raw.get("id", "")
    ad["body_text"]  = raw.get("ad_creative_body", "")
    ad["headline"]   = raw.get("ad_creative_link_title", "")
    ad["description"]= raw.get("ad_creative_link_description", "")
    ad["cta"]        = raw.get("ad_creative_link_caption", "")
    ad["status"]     = "Activo" if not raw.get("ad_delivery_stop_time") else "Inactivo"
    ad["snapshot_url"] = raw.get("ad_snapshot_url", "")

    # Platforms
    platforms = raw.get("publisher_platforms", [])
    ad["platforms"] = ", ".join(p.capitalize() for p in platforms) if platforms else "Facebook"

    # Date
    start = raw.get("ad_delivery_start_time", "")
    if start:
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            ad["start_date"] = dt.strftime("%d/%m/%Y")
        except Exception:
            ad["start_date"] = start[:10]

    # Impressions range
    imp = raw.get("impressions", {})
    if imp:
        low  = imp.get("lower_bound", "")
        high = imp.get("upper_bound", "")
        if low and high:
            ad["impressions"] = f"{low} – {high}"
        elif low:
            ad["impressions"] = f"≥ {low}"

    return ad


def collect_all_ads(token: str, max_ads: int) -> list[dict]:
    ads: list[dict] = []
    cursor = None

    while len(ads) < max_ads:
        log(f"Fetching página {len(ads) // RESULTS_PER_PAGE + 1}…", 1)
        try:
            data = fetch_ads_page(token, after_cursor=cursor)
        except requests.HTTPError as exc:
            log(f"✗ Error API: {exc}", 1)
            log(f"  Respuesta: {exc.response.text[:300]}", 2)
            break

        raw_ads = data.get("data", [])
        if not raw_ads:
            log("No hay más anuncios.", 1)
            break

        for raw in raw_ads:
            if len(ads) >= max_ads:
                break
            ad = parse_ad(raw)
            ads.append(ad)
            log(f"✓ #{len(ads):>3}  {str(ad.get('body_text',''))[:65]}…", 2)

        paging = data.get("paging", {})
        cursor = paging.get("cursors", {}).get("after")
        next_page = paging.get("next")
        if not next_page or not cursor:
            log("Última página alcanzada.", 1)
            break

        time.sleep(0.5)  # be gentle with the API

    return ads


# =============================================================================
# EXCEL EXPORT  (shared structure with byd_scraper.py)
# =============================================================================

COLUMNS = [
    ("N°",                    5),
    ("ID Anuncio",           22),
    ("Texto del Anuncio",    65),
    ("Titular / Headline",   35),
    ("Descripción",          40),
    ("Call to Action",       18),
    ("Fecha Inicio",         16),
    ("Estado",               12),
    ("Plataformas",          25),
    ("Rango Impresiones",    22),
    ("URL Snapshot",         50),
    ("Vista Previa",         22),
]


def create_excel(ads: list[dict], output_path: Path) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Anuncios BYD CR"

    hfont = Font(bold=True, color=COLOR_HEADER_FG, size=10, name="Calibri")
    hfill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, (title, width) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=title)
        cell.font      = hfont
        cell.fill      = hfill
        cell.alignment = halign
        cell.border    = BORDER_ALL
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    alt_fill = PatternFill("solid", fgColor=COLOR_ALT_ROW)

    for i, ad in enumerate(ads):
        row = i + 2
        fill = alt_fill if i % 2 == 0 else None

        values = [
            i + 1,
            ad.get("ad_id",      ""),
            ad.get("body_text",  ""),
            ad.get("headline",   ""),
            ad.get("description",""),
            ad.get("cta",        ""),
            ad.get("start_date", ""),
            ad.get("status",     "Activo"),
            ad.get("platforms",  "Facebook"),
            ad.get("impressions",""),
            ad.get("snapshot_url", ad.get("image_url", "")),
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.border    = BORDER_ALL
            cell.alignment = Alignment(vertical="top", wrap_text=True,
                                       horizontal="center" if col_idx <= 2 else "left")
            if fill:
                cell.fill = fill

        # Embed thumbnail
        local_img = ad.get("local_image")
        if local_img and os.path.exists(local_img):
            buf = thumbnail_bytes(local_img)
            if buf:
                try:
                    xl_img = XLImage(buf)
                    xl_img.width  = 130
                    xl_img.height = 130
                    ws.add_image(xl_img, f"L{row}")
                    ws.row_dimensions[row].height = 100
                except Exception:
                    ws.row_dimensions[row].height = 55
            else:
                ws.row_dimensions[row].height = 55
        else:
            ws.row_dimensions[row].height = 55

    # Resumen sheet
    ws2 = wb.create_sheet("Resumen")
    ws2["A1"] = f"{PAGE_NAME} – API Oficial Facebook Ad Library"
    ws2["A1"].font = Font(bold=True, size=16, color=COLOR_RED)
    ws2.column_dimensions["A"].width = 40
    ws2.column_dimensions["B"].width = 60
    bold = Font(bold=True)
    rows = [
        ("Total anuncios",        len(ads)),
        ("Fecha de extracción",   datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Page ID",               PAGE_ID),
        ("País",                  "Costa Rica (CR)"),
        ("API Version",           API_VERSION),
        ("Fuente",                "Facebook Ad Library API (oficial)"),
    ]
    for r, (label, val) in enumerate(rows, 3):
        ws2[f"A{r}"] = label
        ws2[f"A{r}"].font = bold
        ws2[f"B{r}"] = str(val)

    wb.save(output_path)
    return str(output_path)


# =============================================================================
# ENTRY POINT
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BYD Costa Rica – Scraper vía API oficial de Facebook"
    )
    p.add_argument("--token",  type=str, default=None,
                   help="Facebook Access Token (o usar env FB_ACCESS_TOKEN)")
    p.add_argument("--max",    type=int, default=MAX_ADS_DEFAULT,
                   help=f"Máx. anuncios (default: {MAX_ADS_DEFAULT})")
    p.add_argument("--output", type=str, default=None,
                   help="Ruta del Excel de salida")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    token = args.token or os.environ.get("FB_ACCESS_TOKEN", "")
    if not token:
        log("")
        log("❌  ERROR: Se requiere un Facebook Access Token.", 0)
        log("", 0)
        log("Opciones:", 0)
        log("  1. Variable de entorno:   export FB_ACCESS_TOKEN='EAAxxxx...'", 1)
        log("  2. Argumento CLI:         python byd_api_scraper.py --token 'EAAxxxx...'", 1)
        log("", 0)
        log("Cómo obtener el token:", 0)
        log("  https://developers.facebook.com/tools/accesstoken/", 1)
        log("", 0)
        sys.exit(1)

    setup_dirs()
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M")
    out_path   = Path(args.output) if args.output else \
        OUTPUT_DIR / f"BYD_CR_Ads_API_{timestamp}.xlsx"

    log("")
    log("=" * 62)
    log("  BYD Costa Rica – Facebook Ad Library API Scraper")
    log("=" * 62)
    log(f"  API version : {API_VERSION}")
    log(f"  Máx. ads    : {args.max}")
    log(f"  Salida      : {out_path}")
    log("=" * 62)
    log("")

    ads = collect_all_ads(token, args.max)

    log("")
    log(f"Total anuncios: {len(ads)}", 1)

    if not ads:
        log("⚠  No se encontraron anuncios. Verifica que el token sea válido.", 1)
        sys.exit(1)

    # Download snapshot images (ad preview pages don't have direct images
    # via API, so we skip image download for API mode unless snapshot is accessible)
    log("Generando Excel...", 1)
    excel_file = create_excel(ads, out_path)

    json_path = OUTPUT_DIR / f"ads_api_raw_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(ads, f, ensure_ascii=False, indent=2)

    log("")
    log("=" * 62)
    log("  ✅  COMPLETADO (vía API oficial)")
    log("=" * 62)
    log(f"  Excel : {excel_file}", 1)
    log(f"  JSON  : {json_path}", 1)
    log("=" * 62)
    log("")


if __name__ == "__main__":
    main()
