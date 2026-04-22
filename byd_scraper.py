#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BYD Costa Rica - Facebook Ads Library Scraper
=============================================
Extrae todos los anuncios activos del concesionario BYD en Costa Rica
desde la Biblioteca de Anuncios de Facebook y los exporta a Excel.

Uso:
    python byd_scraper.py

    Con opciones:
    python byd_scraper.py --max 100 --headless
    python byd_scraper.py --visible         # abre navegador visible (útil para debug)
    python byd_scraper.py --output mi_archivo.xlsx

Salida:
    byd_ads_output/
        BYD_CR_Ads_YYYYMMDD_HHMM.xlsx   ← Excel principal
        ads_raw.json                     ← JSON de respaldo
        images/                          ← Imágenes descargadas
"""

from __future__ import annotations
import argparse
import asyncio
import io
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from playwright.async_api import async_playwright

# =============================================================================
# CONFIG
# =============================================================================

PAGE_ID = "129337183749169"
PAGE_NAME = "BYD Costa Rica"

ADS_LIBRARY_URL = (
    "https://www.facebook.com/ads/library/"
    "?active_status=active"
    "&ad_type=all"
    "&country=CR"
    "&is_targeted_country=false"
    "&media_type=all"
    "&search_type=page"
    "&sort_data[direction]=desc"
    "&sort_data[mode]=total_impressions"
    f"&view_all_page_id={PAGE_ID}"
)

OUTPUT_DIR = Path("byd_ads_output")
IMAGES_DIR = OUTPUT_DIR / "images"
SCROLL_PAUSE_SEC = 3.0
LOAD_TIMEOUT_MS = 45_000
NO_CHANGE_LIMIT = 6      # stop scrolling after N scrolls with no new ads
MAX_ADS_DEFAULT = 300

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

# =============================================================================
# HELPERS
# =============================================================================

def setup_dirs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)


def log(msg: str, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"{prefix}{msg}", flush=True)


def download_image(url: str, filename_stem: str) -> str | None:
    """Download image to IMAGES_DIR. Returns local path or None."""
    if not url or not url.startswith("http"):
        return None
    try:
        headers = {"User-Agent": USER_AGENT, "Referer": "https://www.facebook.com/"}
        resp = requests.get(url, headers=headers, timeout=20, stream=True)
        if resp.status_code != 200:
            return None

        ct = resp.headers.get("content-type", "")
        ext = ".jpg"
        if "png" in ct:
            ext = ".png"
        elif "webp" in ct:
            ext = ".webp"
        elif "gif" in ct:
            ext = ".gif"

        # Sanitize filename
        safe = re.sub(r"[^\w\-]", "_", filename_stem)[:80]
        fpath = IMAGES_DIR / f"{safe}{ext}"
        with open(fpath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return str(fpath)
    except Exception as exc:
        log(f"[img] Error descargando {url[:60]}: {exc}", 2)
        return None


def thumbnail_bytes(path: str, size: tuple[int, int] = (150, 150)) -> io.BytesIO | None:
    """Return PNG thumbnail as BytesIO for openpyxl."""
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
# EXCEL EXPORT
# =============================================================================

# Column definitions: (header, width)
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
    ("URL Imagen",           50),
    ("Vista Previa",         22),
]

# BYD brand colors
COLOR_HEADER_BG   = "1A1A2E"   # dark navy
COLOR_HEADER_FG   = "FFFFFF"
COLOR_RED         = "E31837"   # BYD red
COLOR_ALT_ROW     = "F4F6F9"
COLOR_BORDER      = "CCCCCC"

_thin = Side(style="thin", color=COLOR_BORDER)
BORDER_ALL = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def _header_style() -> tuple[Font, PatternFill, Alignment]:
    return (
        Font(bold=True, color=COLOR_HEADER_FG, size=10, name="Calibri"),
        PatternFill("solid", fgColor=COLOR_HEADER_BG),
        Alignment(horizontal="center", vertical="center", wrap_text=True),
    )


def create_excel(ads: list[dict], output_path: Path) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Anuncios BYD CR"

    # ── Header row ────────────────────────────────────────────────────────────
    hfont, hfill, halign = _header_style()
    for col_idx, (title, width) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=title)
        cell.font   = hfont
        cell.fill   = hfill
        cell.alignment = halign
        cell.border = BORDER_ALL
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    # ── Data rows ─────────────────────────────────────────────────────────────
    for i, ad in enumerate(ads):
        row = i + 2
        alt = PatternFill("solid", fgColor=COLOR_ALT_ROW) if i % 2 == 0 else None

        values = [
            i + 1,
            ad.get("ad_id", ""),
            ad.get("body_text", ""),
            ad.get("headline", ""),
            ad.get("description", ""),
            ad.get("cta", ""),
            ad.get("start_date", ""),
            ad.get("status", "Activo"),
            ad.get("platforms", "Facebook"),
            ad.get("impressions", ""),
            ad.get("image_url", ""),
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col_idx, value=val)
            cell.border = BORDER_ALL
            cell.alignment = Alignment(vertical="top", wrap_text=True,
                                       horizontal="center" if col_idx <= 2 else "left")
            if alt:
                cell.fill = alt

        # Embed image thumbnail in column L (12)
        local_img = ad.get("local_image")
        cell_ref  = f"L{row}"
        if local_img and os.path.exists(local_img):
            buf = thumbnail_bytes(local_img)
            if buf:
                try:
                    xl_img = XLImage(buf)
                    xl_img.width  = 130
                    xl_img.height = 130
                    ws.add_image(xl_img, cell_ref)
                    ws.row_dimensions[row].height = 100
                except Exception as e:
                    log(f"[excel] No se pudo insertar imagen fila {row}: {e}", 2)
                    ws.row_dimensions[row].height = 55
            else:
                ws.row_dimensions[row].height = 55
        else:
            ws.row_dimensions[row].height = 55

    # ── Resumen sheet ─────────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Resumen")
    title_font = Font(bold=True, size=16, color=COLOR_RED, name="Calibri")
    bold_font  = Font(bold=True, name="Calibri")

    ws2["A1"] = f"{PAGE_NAME} – Biblioteca de Anuncios Facebook"
    ws2["A1"].font = title_font
    ws2.column_dimensions["A"].width = 38
    ws2.column_dimensions["B"].width = 55

    summary_rows = [
        ("Total anuncios extraídos",  len(ads)),
        ("Fecha de extracción",       datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Page ID Facebook",          PAGE_ID),
        ("País",                      "Costa Rica (CR)"),
        ("URL fuente",                ADS_LIBRARY_URL),
    ]
    for r, (label, val) in enumerate(summary_rows, 3):
        ws2[f"A{r}"] = label
        ws2[f"A{r}"].font = bold_font
        ws2[f"B{r}"] = str(val)

    # ── Instructions sheet ────────────────────────────────────────────────────
    ws3 = wb.create_sheet("Instrucciones")
    ws3.column_dimensions["A"].width = 90
    instructions = [
        ("Guía de columnas del reporte", Font(bold=True, size=14, color=COLOR_RED)),
        ("", None),
        ("N°              → Número secuencial del anuncio", None),
        ("ID Anuncio      → Identificador único del anuncio en Facebook", None),
        ("Texto del Anuncio → Cuerpo/copy principal del anuncio", None),
        ("Titular         → Titular o headline del anuncio", None),
        ("Descripción     → Descripción adicional o subtítulo", None),
        ("Call to Action  → Botón de acción del anuncio (Comprar, Ver más, etc.)", None),
        ("Fecha Inicio    → Fecha en que el anuncio empezó a publicarse", None),
        ("Estado          → Activo / Inactivo", None),
        ("Plataformas     → Facebook, Instagram, Messenger, etc.", None),
        ("Rango Impresiones → Estimado de impresiones (rango público de Facebook)", None),
        ("URL Imagen      → Enlace directo a la imagen del anuncio", None),
        ("Vista Previa    → Miniatura de la imagen incrustada en el Excel", None),
    ]
    for r, (text, font) in enumerate(instructions, 1):
        ws3[f"A{r}"] = text
        if font:
            ws3[f"A{r}"].font = font

    wb.save(output_path)
    return str(output_path)


# =============================================================================
# PLAYWRIGHT HELPERS
# =============================================================================

async def dismiss_cookies(page) -> None:
    """Attempt to accept/dismiss any cookie or login dialog."""
    selectors = [
        '[data-testid="cookie-policy-manage-dialog-accept-button"]',
        'button[title="Allow all cookies"]',
        'button[title="Aceptar todas las cookies"]',
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Allow essential and optional cookies")',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2500):
                await btn.click()
                log("✓ Diálogo de cookies cerrado", 1)
                await asyncio.sleep(1.5)
                return
        except Exception:
            continue


async def dismiss_login_popup(page) -> None:
    """Close Facebook login modal if it appears."""
    close_sels = [
        '[aria-label="Close"]',
        '[aria-label="Cerrar"]',
        'div[role="dialog"] [aria-label*="lose"]',
    ]
    for sel in close_sels:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                log("✓ Pop-up de login cerrado", 1)
                await asyncio.sleep(1)
                return
        except Exception:
            continue


# =============================================================================
# AD EXTRACTION
# =============================================================================

_DATE_PATTERNS = [
    r"Started running on\s+(.+?)(?:\n|$)",
    r"Inició el\s+(.+?)(?:\n|$)",
    r"Began running on\s+(.+?)(?:\n|$)",
    r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})",
    r"(\w+ \d{1,2}, \d{4})",
    r"(\d{1,2}/\d{1,2}/\d{4})",
]

_CTA_KEYWORDS = [
    "Shop Now", "Learn More", "Sign Up", "Contact Us", "Book Now",
    "Get Offer", "Watch More", "Apply Now", "Download",
    "Ver más", "Comprar ahora", "Registrarse", "Contactar",
    "Obtener oferta", "Descargar", "Solicitar",
]

_PLATFORMS = ["Facebook", "Instagram", "Messenger", "Audience Network"]

_IMPRESSION_RE = re.compile(r"[\d,.][\d,.]*\s*[-–—]\s*[\d,.][\d,.]+")


def _parse_text_block(full_text: str) -> dict:
    """Extract structured fields from raw ad text."""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    result: dict = {}

    # Body text: longest paragraph-like line
    candidates = [ln for ln in lines if len(ln) > 40]
    result["body_text"] = candidates[0] if candidates else " | ".join(lines[:4])

    # Headline: often a short bold-ish line after the body
    short = [ln for ln in lines if 5 < len(ln) <= 80 and ln not in candidates[:1]]
    result["headline"] = short[0] if short else ""

    # Date
    for pat in _DATE_PATTERNS:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            result["start_date"] = m.group(1).strip()
            break

    # CTA
    for kw in _CTA_KEYWORDS:
        if kw.lower() in full_text.lower():
            result["cta"] = kw
            break

    # Platforms
    found_platforms = [p for p in _PLATFORMS if p.lower() in full_text.lower()]
    result["platforms"] = ", ".join(found_platforms) if found_platforms else "Facebook"

    # Impressions
    m = _IMPRESSION_RE.search(full_text)
    if m:
        result["impressions"] = m.group(0).strip()

    return result


async def extract_ad(card) -> dict:
    """Extract all data from a single ad card element."""
    ad: dict = {}
    try:
        full_text = await card.inner_text()
        ad.update(_parse_text_block(full_text))

        # Ad ID
        for attr in ("data-ad-id", "id"):
            try:
                val = await card.get_attribute(attr)
                if val and val.isdigit():
                    ad["ad_id"] = val
                    break
            except Exception:
                pass

        # Images  – prefer large src, skip tiny icons
        img_urls: list[str] = []
        try:
            imgs = await card.query_selector_all("img[src]")
            for img in imgs:
                src = await img.get_attribute("src") or ""
                if src.startswith("http") and not re.search(
                    r"(emoji|icon|1[0-9]x|2[0-4]x|profile)", src, re.I
                ):
                    img_urls.append(src)
        except Exception:
            pass

        # Also capture background-image CSS
        try:
            bg_elems = await card.query_selector_all("[style*='background-image']")
            for elem in bg_elems:
                style = await elem.get_attribute("style") or ""
                for url in re.findall(r'url\(["\']?(https[^"\')\s]+)["\']?\)', style):
                    if url not in img_urls:
                        img_urls.append(url)
        except Exception:
            pass

        if img_urls:
            ad["image_url"]       = img_urls[0]
            ad["all_image_urls"]  = "; ".join(img_urls)

    except Exception as exc:
        log(f"[extract] Error: {exc}", 2)

    return ad


# Selectors to find individual ad cards on the page
_AD_CARD_SELECTORS = [
    '[data-testid="ad-archive-preview"]',
    'div._8nqq',
    'div[class*="x1n2onr6"][class*="x1ja2u2z"]',
    '._99s5',
]


async def find_ad_cards(page):
    """Try multiple selectors to locate ad cards."""
    for sel in _AD_CARD_SELECTORS:
        try:
            cards = await page.query_selector_all(sel)
            if cards:
                return cards
        except Exception:
            continue

    # Fallback: JS-based heuristic (find divs that look like ad cards)
    try:
        cards = await page.evaluate("""
            () => {
                const seen   = new Set();
                const result = [];
                for (const img of document.images) {
                    // Walk up to a container that has "Ad ID" or date text nearby
                    let el = img.parentElement;
                    for (let i = 0; i < 8; i++) {
                        if (!el) break;
                        const txt = el.innerText || "";
                        if (
                            (txt.includes("Ad ID") || txt.includes("ID del anuncio") ||
                             txt.includes("Started running") || txt.includes("Inició"))
                            && el.querySelectorAll("img").length >= 1
                            && !seen.has(el)
                        ) {
                            seen.add(el);
                            result.push(el);
                            break;
                        }
                        el = el.parentElement;
                    }
                }
                return result;
            }
        """)
        if cards:
            return cards
    except Exception:
        pass

    return []


# =============================================================================
# MAIN SCRAPER
# =============================================================================

async def scrape(max_ads: int, headless: bool, output_path: Path) -> list[dict]:
    setup_dirs()

    log("")
    log("=" * 62)
    log("  BYD Costa Rica – Facebook Ads Library Scraper")
    log("=" * 62)
    log(f"  Máx. anuncios : {max_ads}")
    log(f"  Modo          : {'headless' if headless else 'visible (navegador abierto)'}")
    log(f"  Salida        : {output_path}")
    log("=" * 62)
    log("")

    ads_collected: list[dict] = []
    seen_ids: set[str] = set()

    async with async_playwright() as pw:
        log("Iniciando navegador Chromium...", 1)
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        ctx = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="es-CR",
            timezone_id="America/Costa_Rica",
        )
        # Block fonts/icons to speed things up
        await ctx.route(
            "**/*.{woff,woff2,ttf,otf}",
            lambda route, _req: route.abort(),
        )

        page = await ctx.new_page()

        log("Navegando a Facebook Ads Library...", 1)
        try:
            await page.goto(ADS_LIBRARY_URL, wait_until="domcontentloaded",
                            timeout=LOAD_TIMEOUT_MS)
        except Exception as e:
            log(f"⚠  Timeout en carga inicial (continuando): {e}", 2)

        await asyncio.sleep(3)
        await dismiss_cookies(page)
        await dismiss_login_popup(page)

        log("Esperando que aparezcan los anuncios...", 1)
        await asyncio.sleep(5)

        processed_count = 0
        no_change = 0
        scroll_n  = 0

        while len(ads_collected) < max_ads and no_change < NO_CHANGE_LIMIT:
            cards = await find_ad_cards(page)
            log(f"Scroll {scroll_n + 1:>3} → {len(cards)} tarjetas en DOM", 1)

            new_found = 0
            for card in cards[processed_count:]:
                if len(ads_collected) >= max_ads:
                    break
                try:
                    ad = await extract_ad(card)
                    if not ad:
                        continue

                    # Deduplicate by ad_id or body fingerprint
                    key = ad.get("ad_id") or ad.get("body_text", "")[:80]
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)

                    # Download image
                    if ad.get("image_url"):
                        stem = f"ad_{len(ads_collected):04d}"
                        ad["local_image"] = download_image(ad["image_url"], stem)

                    ads_collected.append(ad)
                    new_found += 1
                    body_preview = str(ad.get("body_text", ""))[:65]
                    log(f"✓ #{len(ads_collected):>3}  {body_preview}…", 2)

                except Exception as exc:
                    log(f"✗ Error en tarjeta: {exc}", 2)

            processed_count = len(cards)
            no_change = 0 if new_found > 0 else no_change + 1

            # Scroll down to load more
            await page.evaluate("window.scrollBy(0, 1400)")
            await asyncio.sleep(SCROLL_PAUSE_SEC)
            scroll_n += 1

            # Try clicking any "See more" / "Ver más" load-more button
            for btn_text in ["See more results", "Ver más resultados", "Load more"]:
                try:
                    btn = page.locator(f'div[role="button"]:has-text("{btn_text}")').first
                    if await btn.is_visible(timeout=800):
                        await btn.click()
                        await asyncio.sleep(2)
                except Exception:
                    pass

        await browser.close()

    return ads_collected


# =============================================================================
# ENTRY POINT
# =============================================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BYD Costa Rica – Scraper de Biblioteca de Anuncios de Facebook"
    )
    p.add_argument("--max",      type=int,  default=MAX_ADS_DEFAULT,
                   help=f"Máximo de anuncios a extraer (default: {MAX_ADS_DEFAULT})")
    p.add_argument("--visible",  action="store_true",
                   help="Abrir navegador visible (útil para debug)")
    p.add_argument("--output",   type=str,  default=None,
                   help="Nombre del archivo Excel de salida")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    headless = not args.visible
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_path = Path(args.output) if args.output else \
        OUTPUT_DIR / f"BYD_CR_Ads_{timestamp}.xlsx"

    # Run async scraper
    ads = asyncio.run(scrape(
        max_ads=args.max,
        headless=headless,
        output_path=output_path,
    ))

    log("")
    log(f"Total anuncios extraídos : {len(ads)}", 1)

    if not ads:
        log("", 0)
        log("⚠  No se encontraron anuncios. Posibles causas:", 1)
        log("   1. Facebook requiere login para este contenido", 2)
        log("   2. Los selectores CSS de Facebook han cambiado", 2)
        log("   3. La página tiene protección anti-bot activa", 2)
        log("", 0)
        log("Sugerencia: prueba con --visible para ver qué pasa en el navegador.", 1)
        sys.exit(1)

    log("Generando archivo Excel...", 1)
    excel_file = create_excel(ads, output_path)

    # JSON backup
    json_path = OUTPUT_DIR / f"ads_raw_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    clean_ads = [{k: v for k, v in ad.items() if k != "local_image"} for ad in ads]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean_ads, f, ensure_ascii=False, indent=2)

    log("")
    log("=" * 62)
    log("  ✅  COMPLETADO")
    log("=" * 62)
    log(f"  Excel    : {excel_file}", 1)
    log(f"  JSON     : {json_path}", 1)
    log(f"  Imágenes : {IMAGES_DIR}", 1)
    log("=" * 62)
    log("")


if __name__ == "__main__":
    main()
