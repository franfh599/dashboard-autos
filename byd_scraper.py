#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BYD Costa Rica – Facebook Ads Library Scraper
==============================================
Extrae todos los anuncios activos del concesionario BYD en Costa Rica
desde la Biblioteca de Anuncios de Facebook y los exporta a Excel + JSON.

Uso:
    python byd_scraper.py                      # 300 anuncios, headless
    python byd_scraper.py --max 100            # límite de anuncios
    python byd_scraper.py --visible            # navegador visible (debug)
    python byd_scraper.py --output mi.xlsx     # archivo de salida específico

Salida (directorio byd_ads_output/):
    BYD_CR_Ads_YYYYMMDD_HHMM.xlsx   – Excel con thumbnails incrustados
    ads_raw_YYYYMMDD_HHMM.json      – JSON completo para la app Streamlit
    images/                          – Imágenes descargadas
"""

from __future__ import annotations
import argparse
import asyncio
import base64
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
# playwright imported lazily inside scrape() so this module can be imported
# by byd_ads_app.py even when playwright is not installed

# =============================================================================
# CONFIG
# =============================================================================

PAGE_ID  = "129337183749169"
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

OUTPUT_DIR       = Path("byd_ads_output")
IMAGES_DIR       = OUTPUT_DIR / "images"
SCROLL_PAUSE_SEC = 4.0
LOAD_TIMEOUT_MS  = 60_000
NO_CHANGE_LIMIT  = 8
MAX_ADS_DEFAULT  = 300
DEBUG_SCREENSHOTS = True   # save PNG snapshots to byd_ads_output/ for debugging

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Excel brand colours
C_NAVY   = "1A1A2E"
C_RED    = "E31837"
C_ALT    = "F4F6F9"
C_BORDER = "DDDDDD"

# =============================================================================
# SETUP / UTILITIES
# =============================================================================

def setup() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)


def log(msg: str, indent: int = 0) -> None:
    print("  " * indent + msg, flush=True)


def download_image(url: str, stem: str) -> str | None:
    if not url or not url.startswith("http"):
        return None
    try:
        r = requests.get(
            url,
            headers={"User-Agent": UA, "Referer": "https://www.facebook.com/"},
            timeout=20,
            stream=True,
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
    except Exception as e:
        log(f"[img] {e}", 3)
        return None


def thumbnail_bytes(path: str, size=(160, 160)) -> io.BytesIO | None:
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
# EXCEL EXPORT  (also imported by byd_ads_app.py)
# =============================================================================

EXCEL_COLUMNS = [
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

_thin      = Side(style="thin", color=C_BORDER)
BORDER_ALL = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def create_excel(ads: list[dict], output_path: Path) -> str:
    """Generate formatted Excel. Can be called from the Streamlit app too."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Anuncios BYD CR"

    hfont  = Font(bold=True, color="FFFFFF", size=10, name="Calibri")
    hfill  = PatternFill("solid", fgColor=C_NAVY)
    halign = Alignment(horizontal="center", vertical="center", wrap_text=True)
    alt_f  = PatternFill("solid", fgColor=C_ALT)

    for ci, (title, width) in enumerate(EXCEL_COLUMNS, 1):
        cell = ws.cell(row=1, column=ci, value=title)
        cell.font      = hfont
        cell.fill      = hfill
        cell.alignment = halign
        cell.border    = BORDER_ALL
        ws.column_dimensions[get_column_letter(ci)].width = width
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    for i, ad in enumerate(ads):
        row  = i + 2
        fill = alt_f if i % 2 == 0 else None

        row_vals = [
            i + 1,
            ad.get("ad_id",       ""),
            ad.get("body_text",   ""),
            ad.get("headline",    ""),
            ad.get("description", ""),
            ad.get("cta",         ""),
            ad.get("start_date",  ""),
            ad.get("status",      "Activo"),
            ad.get("platforms",   "Facebook"),
            ad.get("impressions", ""),
            ad.get("image_url",   ""),
        ]
        for ci, val in enumerate(row_vals, 1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.border    = BORDER_ALL
            cell.alignment = Alignment(vertical="top", wrap_text=True,
                                       horizontal="center" if ci <= 2 else "left")
            if fill:
                cell.fill = fill

        local_img = ad.get("local_image")
        if local_img and os.path.exists(local_img):
            buf = thumbnail_bytes(local_img)
            if buf:
                try:
                    xi = XLImage(buf)
                    xi.width, xi.height = 130, 130
                    ws.add_image(xi, f"L{row}")
                    ws.row_dimensions[row].height = 100
                    continue
                except Exception:
                    pass
        ws.row_dimensions[row].height = 55

    # Resumen
    ws2 = wb.create_sheet("Resumen")
    ws2["A1"] = f"{PAGE_NAME} – Biblioteca de Anuncios Facebook"
    ws2["A1"].font = Font(bold=True, size=16, color=C_RED)
    ws2.column_dimensions["A"].width = 38
    ws2.column_dimensions["B"].width = 60
    bf = Font(bold=True)
    for r, (lbl, val) in enumerate([
        ("Total anuncios",      len(ads)),
        ("Fecha extracción",    datetime.now().strftime("%d/%m/%Y %H:%M")),
        ("Page ID",             PAGE_ID),
        ("País",                "Costa Rica (CR)"),
    ], 3):
        ws2[f"A{r}"] = lbl; ws2[f"A{r}"].font = bf
        ws2[f"B{r}"] = str(val)

    wb.save(output_path)
    return str(output_path)


# =============================================================================
# PLAYWRIGHT – HELPERS
# =============================================================================

async def dismiss_overlay(page) -> None:
    """Close cookies or login dialogs - tries many known Facebook selectors."""
    selectors = [
        '[data-testid="cookie-policy-manage-dialog-accept-button"]',
        'button[title="Allow all cookies"]',
        'button[title="Aceptar todas las cookies"]',
        'button[title="Accept all"]',
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Allow all cookies")',
        'button:has-text("Allow Essential and Optional Cookies")',
        'button:has-text("Permettre tous les cookies")',
        '[data-cookiebanner="accept_button"]',
        '[data-testid="accept-btn"]',
        '[aria-label="Close"]',
        '[aria-label="Cerrar"]',
        'div[data-nosnippet] button',
    ]
    for sel in selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                log(f"  [overlay] Dismissed via: {sel}", 2)
                await asyncio.sleep(1.5)
        except Exception:
            continue


async def _screenshot(page, name: str) -> None:
    if not DEBUG_SCREENSHOTS:
        return
    try:
        p = OUTPUT_DIR / f"{name}.png"
        await page.screenshot(path=str(p), full_page=False)
        log(f"  [debug] Screenshot → {p}", 2)
    except Exception:
        pass


async def _dump_html(page) -> None:
    try:
        html = await page.content()
        p = OUTPUT_DIR / "debug_page.html"
        p.write_text(html, encoding="utf-8")
        log(f"  [debug] HTML ({len(html)//1024} kB) → {p}", 2)
    except Exception:
        pass


# Image URLs we want to skip (icons, avatars, tiny sprites)
_SKIP_IMG_RE = re.compile(
    r"(emoji|icon|static|sprite|profile|avatar|1[0-9]x|2[0-4]x|"
    r"32x32|48x48|favicon|svg\+xml)",
    re.IGNORECASE,
)

_DATE_RE = [
    re.compile(r"Started running on\s+(.+?)(?:\n|$)", re.I),
    re.compile(r"Inició el\s+(.+?)(?:\n|$)", re.I),
    re.compile(r"Began running on\s+(.+?)(?:\n|$)", re.I),
    re.compile(r"(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})"),
    re.compile(r"(\w+ \d{1,2}, \d{4})"),
    re.compile(r"(\d{1,2}/\d{1,2}/\d{4})"),
]

_IMP_RE = re.compile(r"[\d,.][\d,.]*\s*[-–—]\s*[\d,.][\d,.]+")

_CTA_KW = [
    "Shop Now", "Learn More", "Sign Up", "Contact Us", "Book Now",
    "Get Offer", "Watch More", "Apply Now", "Download", "Get Quote",
    "Ver más", "Comprar ahora", "Registrarse", "Contactar",
    "Solicitar cotización", "Descargar",
]

_PLATFORMS = ["Facebook", "Instagram", "Messenger", "Audience Network"]


def _parse_text(full: str) -> dict:
    lines = [l.strip() for l in full.splitlines() if l.strip()]
    result: dict = {}

    # Body text: longest paragraph-ish line
    cands = sorted([l for l in lines if len(l) > 30], key=len, reverse=True)
    result["body_text"] = cands[0] if cands else " | ".join(lines[:3])

    # Headline: a shorter distinct line
    short = [l for l in lines if 6 < len(l) < 90 and l != result["body_text"]]
    result["headline"] = short[0] if short else ""

    # Description: second distinct short block
    result["description"] = short[1] if len(short) > 1 else ""

    for pat in _DATE_RE:
        m = pat.search(full)
        if m:
            result["start_date"] = m.group(1).strip()
            break

    for kw in _CTA_KW:
        if kw.lower() in full.lower():
            result["cta"] = kw
            break

    plats = [p for p in _PLATFORMS if p.lower() in full.lower()]
    result["platforms"] = ", ".join(plats) if plats else "Facebook"

    m = _IMP_RE.search(full)
    if m:
        result["impressions"] = m.group(0).strip()

    return result


async def extract_ad(card) -> dict:
    ad: dict = {}
    try:
        full_text = await card.inner_text()
        ad.update(_parse_text(full_text))

        # Ad ID from data attributes or aria labels
        for attr in ("data-ad-id", "id"):
            try:
                v = await card.get_attribute(attr)
                if v and re.match(r"^\d{10,}$", v.strip()):
                    ad["ad_id"] = v.strip()
                    break
            except Exception:
                pass

        # ── Images ────────────────────────────────────────────────────────────
        img_urls: list[str] = []

        # 1. All <img src> that look like real content images
        try:
            imgs = await card.query_selector_all("img[src]")
            for img in imgs:
                src = await img.get_attribute("src") or ""
                if src.startswith("http") and not _SKIP_IMG_RE.search(src):
                    img_urls.append(src)
        except Exception:
            pass

        # 2. CSS background-image
        try:
            for elem in await card.query_selector_all("[style*='background-image']"):
                style = await elem.get_attribute("style") or ""
                for u in re.findall(r'url\(["\']?(https[^"\')\s]+)["\']?\)', style):
                    if u not in img_urls and not _SKIP_IMG_RE.search(u):
                        img_urls.append(u)
        except Exception:
            pass

        # 3. <source srcset> inside <picture> or <video poster>
        try:
            for elem in await card.query_selector_all("source[srcset], video[poster]"):
                val = (await elem.get_attribute("srcset") or
                       await elem.get_attribute("poster") or "")
                for u in re.findall(r"(https\S+)", val):
                    if u not in img_urls and not _SKIP_IMG_RE.search(u):
                        img_urls.append(u)
        except Exception:
            pass

        # Prefer largest-looking URL (often has width/height hints)
        def _img_score(u: str) -> int:
            nums = re.findall(r"[_\-](\d{3,4})[_x\-]", u)
            return max((int(n) for n in nums), default=0)

        img_urls.sort(key=_img_score, reverse=True)

        if img_urls:
            ad["image_url"]      = img_urls[0]
            ad["all_image_urls"] = img_urls[:5]  # keep up to 5

    except Exception as e:
        log(f"[extract] {e}", 3)

    return ad


# Facebook Ads Library – CSS selector strategies (kept as fast first pass)
_CARD_SELECTORS = [
    '[data-testid="ad-archive-preview"]',
    'div._8nqq',
    '._99s5',
    'div[class*="x1yztbdb"][class*="xn6708d"]',
    # 2024-2025 observed classes
    'div[class*="xh8yej3"]',
    'div[class*="x1n2onr6"][class*="x1ja2u2z"]',
]

# Text markers that appear inside every Facebook Ads Library ad card
_AD_TEXT_MARKERS = [
    "ID de la biblioteca",
    "Library ID",
    "Started running",
    "Inició",
    "Began running",
    "Se está publicando",
    "Active",
    "Activo",
    "Paused",
]

_JS_FIND_CARDS = """
() => {
    const MARKERS = [
        "ID de la biblioteca", "Library ID",
        "Started running", "Inició", "Began running",
        "Se está publicando", "En pausa"
    ];
    const seen = new WeakSet();
    const results = [];

    // Walk every text node; when we find a marker, walk up to find the card
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT, null
    );
    let node;
    while ((node = walker.nextNode())) {
        const txt = node.textContent.trim();
        if (!MARKERS.some(m => txt.includes(m))) continue;

        // Walk ancestors to find the card container
        let el = node.parentElement;
        for (let i = 0; i < 20; i++) {
            if (!el || el === document.body) break;
            const rect = el.getBoundingClientRect();
            if (rect.height > 250 && rect.width > 350 && !seen.has(el)) {
                seen.add(el);
                results.push(el);
                break;
            }
            el = el.parentElement;
        }
    }
    return results;
}
"""

_JS_COUNT_MARKERS = """
() => {
    const MARKERS = [
        "ID de la biblioteca", "Library ID",
        "Started running", "Inició", "Began running"
    ];
    let count = 0;
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT, null
    );
    let node;
    while ((node = walker.nextNode())) {
        if (MARKERS.some(m => node.textContent.includes(m))) count++;
    }
    return count;
}
"""


async def find_cards(page):
    # 1. Fast CSS selector pass
    for sel in _CARD_SELECTORS:
        try:
            cards = await page.query_selector_all(sel)
            if cards:
                log(f"  [cards] CSS selector matched ({sel}): {len(cards)}", 2)
                return cards
        except Exception:
            continue

    # 2. Text-content heuristic (works regardless of class obfuscation)
    try:
        cards = await page.evaluate(_JS_FIND_CARDS)
        if cards:
            log(f"  [cards] JS text-heuristic: {len(cards)} cards", 2)
            return cards
    except Exception as e:
        log(f"  [cards] JS heuristic error: {e}", 2)

    return []


async def page_info(page) -> dict:
    """Return diagnostic info about the current page state."""
    try:
        title = await page.title()
        url   = page.url
        h1s   = await page.evaluate(
            "() => Array.from(document.querySelectorAll('h1,h2')).map(e=>e.innerText).slice(0,5)"
        )
        marker_count = await page.evaluate(_JS_COUNT_MARKERS)
        total_text   = await page.evaluate("() => document.body.innerText.length")
        return {
            "title": title, "url": url,
            "h1s": h1s, "marker_count": marker_count,
            "total_text_chars": total_text,
        }
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# MAIN SCRAPER
# =============================================================================

async def scrape(max_ads: int, headless: bool, output_path: Path) -> list[dict]:
    setup()
    log("")
    log("=" * 64)
    log("  BYD Costa Rica – Facebook Ads Library Scraper")
    log("=" * 64)
    log(f"  Máx. anuncios : {max_ads}")
    log(f"  Modo          : {'headless' if headless else 'visible'}")
    log(f"  Salida        : {output_path}")
    log("=" * 64)

    collected: list[dict] = []
    seen: set[str] = set()

    from playwright.async_api import async_playwright  # lazy import
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1440, "height": 900},
            locale="es-CR",
            timezone_id="America/Costa_Rica",
        )
        await ctx.route("**/*.{woff,woff2,ttf,otf}",
                        lambda r, _: r.abort())

        page = await ctx.new_page()

        log("Navegando a Facebook Ads Library…", 1)
        try:
            await page.goto(ADS_LIBRARY_URL,
                            wait_until="domcontentloaded",
                            timeout=LOAD_TIMEOUT_MS)
        except Exception as e:
            log(f"⚠  Timeout inicial (continuando): {e}", 2)

        # ── Initial load: wait generously, JS-heavy page ──────────────────────
        log("Esperando carga inicial (12 s)…", 1)
        await asyncio.sleep(12)
        await _screenshot(page, "debug_01_initial")

        info = await page_info(page)
        log(f"Página cargada: {info.get('title','?')!r}", 1)
        log(f"  URL: {info.get('url','?')}", 2)
        log(f"  Marcadores de anuncio detectados: {info.get('marker_count', 0)}", 2)
        log(f"  Texto total: {info.get('total_text_chars', 0):,} chars", 2)
        if info.get("h1s"):
            log(f"  Encabezados: {info['h1s']}", 2)

        # ── Dismiss cookie / login overlays ───────────────────────────────────
        await dismiss_overlay(page)
        await asyncio.sleep(3)
        await dismiss_overlay(page)   # second pass in case of stacked dialogs
        await asyncio.sleep(5)
        await _screenshot(page, "debug_02_after_cookie")

        info2 = await page_info(page)
        log(f"Post-overlay: marcadores={info2.get('marker_count',0)}", 1)

        # ── If page is blank / login wall, dump HTML for diagnosis ────────────
        if info2.get("total_text_chars", 0) < 5000 or info2.get("marker_count", 0) == 0:
            log("⚠  Pocos datos en página – guardando HTML para diagnóstico", 1)
            await _dump_html(page)

        # ── Scroll down once to trigger lazy-load ─────────────────────────────
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(4)
        await _screenshot(page, "debug_03_after_scroll1")

        processed = 0
        no_change = 0
        scroll_n  = 0

        while len(collected) < max_ads and no_change < NO_CHANGE_LIMIT:
            cards = await find_cards(page)
            marker_n = await page.evaluate(_JS_COUNT_MARKERS)
            log(f"Scroll {scroll_n + 1:>3}  │  {len(cards)} tarjetas  │  "
                f"marcadores={marker_n}  │  {len(collected)} extraídos", 1)

            new = 0
            for card in cards[processed:]:
                if len(collected) >= max_ads:
                    break
                try:
                    ad = await extract_ad(card)
                    if not ad:
                        continue

                    key = ad.get("ad_id") or ad.get("body_text", "")[:100]
                    if not key or key in seen:
                        continue
                    seen.add(key)

                    # Download best image
                    if ad.get("image_url"):
                        stem = f"ad_{len(collected):04d}"
                        ad["local_image"] = download_image(ad["image_url"], stem)

                    ad["scraped_at"] = datetime.now().isoformat()
                    ad["status"]     = ad.get("status", "Activo")

                    collected.append(ad)
                    new += 1
                    preview = str(ad.get("body_text", ""))[:60]
                    log(f"✓ #{len(collected):>3}  {preview}…", 2)

                except Exception as e:
                    log(f"✗ {e}", 2)

            processed  = len(cards)
            no_change  = 0 if new > 0 else no_change + 1

            # Scroll
            await page.evaluate("window.scrollBy(0, 1800)")
            await asyncio.sleep(SCROLL_PAUSE_SEC)
            scroll_n += 1

            # "Load more" button
            for txt in ["See more results", "Ver más resultados", "Ver más"]:
                try:
                    btn = page.locator(
                        f'div[role="button"]:has-text("{txt}")').first
                    if await btn.is_visible(timeout=500):
                        await btn.click()
                        await asyncio.sleep(2.5)
                except Exception:
                    pass

        # Final screenshot for reference
        await _screenshot(page, "debug_final")
        await browser.close()

    return collected


# =============================================================================
# ENTRY POINT
# =============================================================================

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BYD Costa Rica – scraper de la Biblioteca de Anuncios")
    p.add_argument("--max",     type=int, default=MAX_ADS_DEFAULT)
    p.add_argument("--visible", action="store_true")
    p.add_argument("--output",  type=str, default=None)
    return p.parse_args()


def main() -> None:
    args      = _parse_args()
    headless  = not args.visible
    ts        = datetime.now().strftime("%Y%m%d_%H%M")
    out_path  = Path(args.output) if args.output else \
                OUTPUT_DIR / f"BYD_CR_Ads_{ts}.xlsx"

    ads = asyncio.run(scrape(args.max, headless, out_path))

    log(f"\n  Total extraídos: {len(ads)}", 0)

    if not ads:
        log("⚠  Sin anuncios. Prueba --visible para ver qué ocurre.", 1)
        sys.exit(1)

    log("Generando Excel…", 1)
    excel_path = create_excel(ads, out_path)

    json_path = OUTPUT_DIR / f"ads_raw_{ts}.json"
    clean = [{k: v for k, v in a.items() if k != "local_image"} for a in ads]
    # Save local_image paths too so the Streamlit app can load them
    for a_clean, a_full in zip(clean, ads):
        if a_full.get("local_image"):
            a_clean["local_image"] = a_full["local_image"]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    log("")
    log("=" * 64)
    log("  ✅  COMPLETADO")
    log("=" * 64)
    log(f"  Excel    : {excel_path}", 1)
    log(f"  JSON     : {json_path}", 1)
    log(f"  Imágenes : {IMAGES_DIR}", 1)
    log("=" * 64)


if __name__ == "__main__":
    main()
