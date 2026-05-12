#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BYD Costa Rica – Ads Intelligence Dashboard
============================================
Visualiza y analiza los anuncios extraídos de la Biblioteca de Anuncios
de Facebook. Incluye galería de anuncios con imágenes, gráficas analíticas,
filtros y la posibilidad de lanzar el scraper directamente desde la UI.

Uso:
    streamlit run byd_ads_app.py
"""

from __future__ import annotations
import base64
import glob
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image as PILImage

# ── Import the Excel builder from the scraper module ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
try:
    from byd_scraper import create_excel
except ImportError:
    create_excel = None  # graceful degradation if scraper deps not installed

# =============================================================================
# CONSTANTS
# =============================================================================

OUTPUT_DIR = Path("byd_ads_output")
IMAGES_DIR = OUTPUT_DIR / "images"
PAGE_ID    = "129337183749169"
PAGE_SIZE  = 12   # ads per gallery page
CARD_COLS  = 3    # grid columns

BYD_RED    = "#E31837"
BYD_NAVY   = "#1A1A2E"
BYD_NAVY2  = "#2D2D5E"
BYD_LIGHT  = "#F4F6F9"
BYD_GRAY   = "#8B95A1"

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="BYD CR · Ads Intelligence",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# GLOBAL CSS
# =============================================================================

CSS = f"""
<style>
/* ── Layout ──────────────────────────────────────────────────────────────── */
.main .block-container {{
    padding: 1.5rem 2rem 3rem;
    max-width: 1500px;
}}
[data-testid="stAppViewContainer"] {{
    background: #F7F9FC;
}}

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] > div:first-child {{
    background: linear-gradient(180deg, {BYD_NAVY} 0%, {BYD_NAVY2} 100%);
    padding-top: 0;
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] span {{
    color: rgba(255,255,255,0.85) !important;
}}
section[data-testid="stSidebar"] h3 {{
    color: rgba(255,255,255,0.55) !important;
    font-size: 10px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    margin: 16px 0 4px !important;
}}
section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.12) !important;
}}
/* Sidebar inputs */
section[data-testid="stSidebar"] [data-baseweb="input"],
section[data-testid="stSidebar"] [data-baseweb="select"],
section[data-testid="stSidebar"] [data-baseweb="textarea"] {{
    background: rgba(255,255,255,0.08) !important;
    border-color: rgba(255,255,255,0.2) !important;
    color: white !important;
    border-radius: 8px !important;
}}
/* Sidebar run button */
div[data-testid="stSidebar"] .stButton:first-of-type > button {{
    background: {BYD_RED} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 0.5px !important;
    width: 100% !important;
    padding: 12px 0 !important;
    transition: filter 0.2s !important;
}}
div[data-testid="stSidebar"] .stButton:first-of-type > button:hover {{
    filter: brightness(1.15) !important;
}}

/* ── Hero header ─────────────────────────────────────────────────────────── */
.byd-hero {{
    background: linear-gradient(135deg, {BYD_NAVY} 0%, {BYD_NAVY2} 60%, #3a3a7e 100%);
    border-radius: 20px;
    padding: 28px 36px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 24px rgba(26,26,46,0.18);
}}
.byd-hero-left h1 {{
    color: white;
    font-size: 26px;
    font-weight: 800;
    margin: 0 0 4px 0;
    line-height: 1.2;
}}
.byd-hero-left .sub {{
    color: rgba(255,255,255,0.6);
    font-size: 13px;
    margin: 0;
}}
.byd-hero-right {{
    text-align: right;
}}
.byd-wordmark {{
    font-size: 48px;
    font-weight: 900;
    color: {BYD_RED};
    letter-spacing: -3px;
    line-height: 1;
}}
.byd-wordmark-sub {{
    color: rgba(255,255,255,0.4);
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: 2px;
}}

/* ── KPI cards ───────────────────────────────────────────────────────────── */
.kpi-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 28px;
}}
.kpi-card {{
    background: white;
    border-radius: 16px;
    padding: 20px 22px;
    border-left: 5px solid {BYD_RED};
    box-shadow: 0 2px 14px rgba(0,0,0,0.05);
    position: relative;
    overflow: hidden;
}}
.kpi-card::after {{
    content: attr(data-icon);
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 36px;
    opacity: 0.08;
}}
.kpi-label {{
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: {BYD_GRAY};
    margin-bottom: 8px;
}}
.kpi-value {{
    font-size: 34px;
    font-weight: 800;
    color: {BYD_NAVY};
    line-height: 1;
    margin-bottom: 4px;
}}
.kpi-sub {{
    font-size: 12px;
    color: {BYD_GRAY};
}}

/* ── Section title ───────────────────────────────────────────────────────── */
.section-heading {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 28px 0 16px;
}}
.section-heading-bar {{
    width: 5px;
    height: 22px;
    background: {BYD_RED};
    border-radius: 3px;
    flex-shrink: 0;
}}
.section-heading h2 {{
    font-size: 18px;
    font-weight: 700;
    color: {BYD_NAVY};
    margin: 0;
}}

/* ── Chart card wrapper ──────────────────────────────────────────────────── */
.chart-card {{
    background: white;
    border-radius: 16px;
    padding: 8px 8px 4px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    border: 1px solid #eef0f4;
}}

/* ── Ad card ─────────────────────────────────────────────────────────────── */
.ad-card {{
    background: white;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 2px 16px rgba(0,0,0,0.07);
    border: 1px solid #eef0f4;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    margin-bottom: 4px;
}}
.ad-card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 10px 32px rgba(26,26,46,0.14);
}}
.ad-img-wrap {{
    width: 100%;
    height: 210px;
    overflow: hidden;
    position: relative;
    background: linear-gradient(135deg, {BYD_LIGHT} 0%, #dde3ec 100%);
}}
.ad-img-wrap img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: transform 0.3s ease;
}}
.ad-card:hover .ad-img-wrap img {{
    transform: scale(1.04);
}}
.ad-img-placeholder {{
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 52px;
    color: #ccd0d8;
}}
.ad-status-badge {{
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    backdrop-filter: blur(8px);
}}
.badge-active   {{ background: rgba(0,176,155,0.9); color: white; }}
.badge-inactive {{ background: rgba(100,110,130,0.85); color: white; }}
.ad-body {{
    padding: 16px 18px 12px;
}}
.ad-headline {{
    font-size: 13px;
    font-weight: 700;
    color: {BYD_NAVY};
    margin: 0 0 7px;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.ad-text {{
    font-size: 12.5px;
    color: #556;
    line-height: 1.55;
    margin: 0 0 12px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 58px;
}}
.ad-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-bottom: 10px;
}}
.tag {{
    padding: 3px 9px;
    border-radius: 20px;
    font-size: 10.5px;
    font-weight: 600;
    white-space: nowrap;
}}
.tag-red   {{ background: {BYD_RED}1a; color: {BYD_RED}; }}
.tag-navy  {{ background: {BYD_NAVY}14; color: {BYD_NAVY}; }}
.tag-green {{ background: #00b09b1a; color: #00896c; }}
.tag-blue  {{ background: #4a90d91a; color: #2f72b5; }}
.tag-gray  {{ background: #eef0f4; color: {BYD_GRAY}; }}
.ad-footer {{
    border-top: 1px solid #f0f2f6;
    padding: 9px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.ad-id {{
    font-size: 10px;
    color: #b0b8c4;
    font-family: monospace;
}}
.ad-date {{
    font-size: 10.5px;
    color: {BYD_GRAY};
    font-weight: 500;
}}

/* ── Gallery controls ────────────────────────────────────────────────────── */
.gallery-toolbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    background: white;
    border-radius: 12px;
    padding: 10px 16px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
    border: 1px solid #eef0f4;
}}
.gallery-count {{
    font-size: 14px;
    font-weight: 700;
    color: {BYD_NAVY};
}}
.gallery-count span {{
    color: {BYD_RED};
}}

/* ── Detail modal style ──────────────────────────────────────────────────── */
.detail-section-label {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: {BYD_GRAY};
    margin-bottom: 3px;
}}
.detail-value {{
    font-size: 14px;
    color: {BYD_NAVY};
    font-weight: 500;
    margin-bottom: 12px;
}}

/* ── Pagination ──────────────────────────────────────────────────────────── */
.pagination-bar {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-top: 24px;
    padding: 12px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.04);
}}

/* ── Empty state ─────────────────────────────────────────────────────────── */
.empty-state {{
    text-align: center;
    padding: 80px 20px;
    color: {BYD_GRAY};
}}
.empty-state .icon {{ font-size: 72px; margin-bottom: 16px; }}
.empty-state h3 {{ color: {BYD_NAVY}; font-size: 22px; margin-bottom: 8px; }}
.empty-state p  {{ font-size: 15px; }}

/* ── Progress / status ───────────────────────────────────────────────────── */
[data-testid="stStatusWidget"] {{ border-radius: 12px !important; }}

/* ── Expander polish ─────────────────────────────────────────────────────── */
.streamlit-expanderHeader {{
    background: {BYD_LIGHT} !important;
    border-radius: 10px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: {BYD_NAVY} !important;
}}

/* ── Download button ─────────────────────────────────────────────────────── */
.stDownloadButton > button {{
    background: {BYD_NAVY} !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}}
.stDownloadButton > button:hover {{
    filter: brightness(1.2) !important;
}}
</style>
"""


# =============================================================================
# DATA HELPERS
# =============================================================================

@st.cache_data(ttl=30)
def _load_json_file(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_json_files() -> list[Path]:
    if not OUTPUT_DIR.exists():
        return []
    files = sorted(OUTPUT_DIR.glob("ads_raw_*.json"), reverse=True)
    return list(files)


def build_df(ads: list[dict]) -> pd.DataFrame:
    if not ads:
        return pd.DataFrame()
    df = pd.DataFrame(ads)
    for col in ["ad_id", "body_text", "headline", "description",
                "cta", "start_date", "status", "platforms",
                "impressions", "image_url", "local_image"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    df["status"] = df["status"].replace("", "Activo")
    return df


# =============================================================================
# IMAGE HELPERS
# =============================================================================

def img_to_b64(path: str) -> str | None:
    """Load local image → base64 JPEG data URI."""
    try:
        img = PILImage.open(path).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def get_display_image(ad: dict) -> str | None:
    """Return best available image src (b64 or URL)."""
    local = ad.get("local_image", "")
    if local and os.path.exists(local):
        return img_to_b64(local)
    url = ad.get("image_url", "")
    if url and url.startswith("http"):
        return url
    return None


# =============================================================================
# HTML BUILDERS
# =============================================================================

def section_heading(icon: str, title: str) -> None:
    st.markdown(
        f'<div class="section-heading">'
        f'  <div class="section-heading-bar"></div>'
        f'  <h2>{icon} {title}</h2>'
        f'</div>',
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, sub: str, icon: str) -> str:
    return (
        f'<div class="kpi-card" data-icon="{icon}">'
        f'  <div class="kpi-label">{label}</div>'
        f'  <div class="kpi-value">{value}</div>'
        f'  <div class="kpi-sub">{sub}</div>'
        f'</div>'
    )


def ad_card_html(ad: dict, idx: int) -> str:
    img_src  = get_display_image(ad)
    if img_src:
        img_html = f'<img src="{img_src}" loading="lazy" alt="Ad image">'
    else:
        img_html = '<div class="ad-img-placeholder">📷</div>'

    status     = ad.get("status", "Activo")
    status_cls = "badge-active" if "activo" in status.lower() else "badge-inactive"

    headline = ad.get("headline") or ""
    body     = (ad.get("body_text") or "")
    cta      = ad.get("cta") or ""
    date_str = ad.get("start_date") or ""
    platforms = ad.get("platforms") or "Facebook"
    impressions = ad.get("impressions") or ""
    ad_id    = ad.get("ad_id") or f"#{idx + 1}"

    # Tags
    tags = ""
    if cta:
        tags += f'<span class="tag tag-red">🎯 {cta}</span>'
    for p in platforms.split(",")[:2]:
        p = p.strip()
        if p:
            icon = {"facebook": "📘", "instagram": "📷",
                    "messenger": "💬"}.get(p.lower(), "📱")
            tags += f'<span class="tag tag-blue">{icon} {p}</span>'
    if impressions:
        tags += f'<span class="tag tag-green">👁 {impressions}</span>'

    return f"""
<div class="ad-card">
  <div class="ad-img-wrap">
    {img_html}
    <span class="ad-status-badge {status_cls}">{status}</span>
  </div>
  <div class="ad-body">
    {'<p class="ad-headline">' + headline + '</p>' if headline else ''}
    <p class="ad-text">{body}</p>
    <div class="ad-tags">{tags}</div>
  </div>
  <div class="ad-footer">
    <span class="ad-id">ID: {ad_id}</span>
    <span class="ad-date">{'📅 ' + date_str if date_str else ''}</span>
  </div>
</div>
"""


# =============================================================================
# CHARTS
# =============================================================================

_CHART_LAYOUT = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(t=46, b=12, l=12, r=12),
    font=dict(family="Inter, system-ui, sans-serif", color=BYD_NAVY),
)


def chart_platform_donut(df: pd.DataFrame) -> go.Figure:
    counts: dict[str, int] = {}
    for val in df["platforms"].dropna():
        for p in str(val).split(","):
            p = p.strip()
            if p:
                counts[p] = counts.get(p, 0) + 1
    if not counts:
        counts = {"Facebook": len(df)}

    palette = [BYD_RED, BYD_NAVY, "#4A90D9", "#00B09B", "#FFC107", "#9B59B6"]
    fig = go.Figure(go.Pie(
        labels=list(counts.keys()),
        values=list(counts.values()),
        hole=0.58,
        marker=dict(colors=palette[:len(counts)],
                    line=dict(color="white", width=2)),
        textinfo="percent+label",
        textfont=dict(size=11),
        hovertemplate="<b>%{label}</b><br>%{value} anuncios (%{percent})<extra></extra>",
    ))
    total = sum(counts.values())
    fig.update_layout(
        **_CHART_LAYOUT,
        title=dict(text="<b>Plataformas</b>", x=0.5, font=dict(size=14)),
        showlegend=False,
        height=270,
        annotations=[dict(
            text=f"<b>{total}</b><br><span style='font-size:10px'>ads</span>",
            x=0.5, y=0.5, font_size=16, showarrow=False,
            font=dict(color=BYD_NAVY),
        )],
    )
    return fig


def chart_cta_bar(df: pd.DataFrame) -> go.Figure:
    counts = df["cta"].replace("", "Sin CTA").value_counts().reset_index()
    counts.columns = ["cta", "n"]
    counts = counts.head(7)
    colors = [BYD_RED if i == 0 else "#C8D0DC" for i in range(len(counts))]

    fig = go.Figure(go.Bar(
        x=counts["n"],
        y=counts["cta"],
        orientation="h",
        marker_color=colors,
        text=counts["n"],
        textposition="outside",
        textfont=dict(size=11, color=BYD_NAVY),
        hovertemplate="<b>%{y}</b>: %{x} anuncios<extra></extra>",
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        title=dict(text="<b>Call to Action</b>", x=0.5, font=dict(size=14)),
        xaxis=dict(visible=False),
        yaxis=dict(showgrid=False, tickfont=dict(size=11)),
        height=270,
        margin=dict(t=46, b=12, l=130, r=50),
    )
    return fig


def chart_impressions(df: pd.DataFrame) -> go.Figure:
    imp = df["impressions"].replace("", pd.NA).dropna()
    if imp.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sin datos de impresiones",
                           showarrow=False, font=dict(size=13, color=BYD_GRAY),
                           x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_layout(**_CHART_LAYOUT, height=270,
                          title=dict(text="<b>Impresiones</b>", x=0.5))
        return fig

    counts = imp.value_counts().reset_index()
    counts.columns = ["rango", "n"]
    counts = counts.head(8)

    fig = go.Figure(go.Bar(
        x=counts["rango"],
        y=counts["n"],
        marker_color=BYD_NAVY,
        text=counts["n"],
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="<b>%{x}</b>: %{y} anuncios<extra></extra>",
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        title=dict(text="<b>Rango de Impresiones</b>", x=0.5, font=dict(size=14)),
        xaxis=dict(showgrid=False, tickangle=-20, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor="#F0F2F6"),
        height=270,
        margin=dict(t=46, b=70, l=40, r=20),
    )
    return fig


def chart_timeline(df: pd.DataFrame) -> go.Figure:
    # Parse dates from various formats
    raw = df["start_date"].astype(str)
    dates = pd.to_datetime(
        raw.str.extract(
            r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\w+ \d{1,2}, \d{4})"
        )[0],
        errors="coerce",
    ).dropna()

    if dates.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sin datos de fecha para la línea de tiempo",
                           showarrow=False, font=dict(size=13, color=BYD_GRAY),
                           x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_layout(**_CHART_LAYOUT, height=200,
                          title=dict(text="<b>Actividad por Mes</b>", x=0.5))
        return fig

    monthly = dates.dt.to_period("M").value_counts().sort_index()
    months  = [str(m) for m in monthly.index]
    vals    = monthly.values.tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months, y=vals,
        marker=dict(
            color=vals,
            colorscale=[[0, "#F4D0D5"], [1, BYD_RED]],
            showscale=False,
        ),
        text=vals, textposition="outside",
        textfont=dict(size=11, color=BYD_NAVY),
        hovertemplate="<b>%{x}</b>: %{y} anuncios<extra></extra>",
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        title=dict(text="<b>Anuncios iniciados por Mes</b>", x=0.5, font=dict(size=14)),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(showgrid=True, gridcolor="#F0F2F6", tickfont=dict(size=11)),
        height=220,
        margin=dict(t=46, b=50, l=40, r=20),
    )
    return fig


# =============================================================================
# SCRAPER RUNNER (subprocess)
# =============================================================================

def launch_scraper(max_ads: int, visible: bool) -> subprocess.Popen:
    cmd = [sys.executable, "byd_scraper.py", f"--max={max_ads}"]
    if visible:
        cmd.append("--visible")
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(Path(__file__).parent),
    )


# =============================================================================
# EXCEL DOWNLOAD BYTES
# =============================================================================

def make_excel_bytes(ads: list[dict]) -> bytes | None:
    if not create_excel or not ads:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        create_excel(ads, tmp_path)
        data = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        return data
    except Exception:
        return None


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar() -> dict:
    with st.sidebar:
        # ── Logo ──────────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="padding:28px 0 20px;text-align:center;
                    border-bottom:1px solid rgba(255,255,255,0.1);">
          <div style="font-size:44px;font-weight:900;
                      color:{BYD_RED};letter-spacing:-3px;line-height:1;">BYD</div>
          <div style="color:rgba(255,255,255,0.45);font-size:10px;
                      letter-spacing:3px;margin-top:2px;">ADS INTELLIGENCE</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Scraper controls ──────────────────────────────────────────────────
        st.markdown("### 🤖 Ejecutar Scraper")
        max_ads = st.slider("Máx. anuncios", 10, 500, 100, step=10,
                            key="max_ads")
        visible = st.checkbox("Abrir navegador visible", False,
                              key="visible_mode",
                              help="Útil para depurar si Facebook bloquea el scraper")
        run_btn = st.button("▶  INICIAR SCRAPER", key="run_btn",
                            use_container_width=True)

        st.markdown("---")

        # ── Data file selector ────────────────────────────────────────────────
        st.markdown("### 📂 Datos")
        files = get_json_files()
        selected_file: Path | None = None
        if files:
            labels = {f.name: f for f in files}
            chosen = st.selectbox("Archivo de resultados",
                                  list(labels.keys()), key="file_sel",
                                  label_visibility="collapsed")
            selected_file = labels[chosen]
        else:
            st.caption("Sin datos aún. Ejecuta el scraper primero.")

        st.markdown("---")

        # ── Filters ───────────────────────────────────────────────────────────
        st.markdown("### 🔍 Filtros")
        search = st.text_input("Buscar texto…", "",
                               placeholder="ej: Atto 3, precio, garantía…",
                               key="search", label_visibility="collapsed")

        plat_filter = st.multiselect(
            "Plataforma",
            ["Facebook", "Instagram", "Messenger", "Audience Network"],
            key="plat_filter",
        )
        cta_placeholder = st.empty()

        st.markdown("---")
        st.markdown(
            f'<div style="text-align:center;color:rgba(255,255,255,0.3);'
            f'font-size:10px;padding-bottom:12px;">'
            f'BYD CR · Ads Intelligence v2.0<br>'
            f'Page ID: {PAGE_ID}</div>',
            unsafe_allow_html=True,
        )

    return dict(
        run_btn=run_btn, max_ads=max_ads, visible=visible,
        selected_file=selected_file, search=search,
        plat_filter=plat_filter, cta_placeholder=cta_placeholder,
    )


# =============================================================================
# SCRAPER STATUS PANEL
# =============================================================================

def handle_scraper(sidebar: dict) -> None:
    if sidebar["run_btn"]:
        st.session_state["running"] = True
        st.session_state["proc"] = launch_scraper(
            sidebar["max_ads"], sidebar["visible"])

    if not st.session_state.get("running"):
        return

    proc: subprocess.Popen = st.session_state.get("proc")
    if not proc:
        st.session_state["running"] = False
        return

    with st.status("🔄 Scraper en ejecución…", expanded=True) as status_box:
        lines: list[str] = []
        log_area = st.empty()
        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if line:
                lines.append(line)
                log_area.code("\n".join(lines[-18:]), language=None)
        proc.wait()
        if proc.returncode == 0:
            status_box.update(label="✅ Scraper completado con éxito",
                              state="complete", expanded=False)
        else:
            status_box.update(
                label="⚠  Scraper finalizado (revisa el log para detalles)",
                state="error", expanded=True)

    st.session_state["running"] = False
    st.cache_data.clear()
    st.rerun()


# =============================================================================
# MAIN APP
# =============================================================================

def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    # Init state
    if "gallery_page" not in st.session_state:
        st.session_state["gallery_page"] = 0
    if "running" not in st.session_state:
        st.session_state["running"] = False

    sidebar = render_sidebar()
    handle_scraper(sidebar)

    # ── Load data ──────────────────────────────────────────────────────────────
    ads_raw: list[dict] = []
    source_label = ""
    if sidebar["selected_file"]:
        try:
            ads_raw = _load_json_file(str(sidebar["selected_file"]))
            source_label = sidebar["selected_file"].name
        except Exception as e:
            st.error(f"Error cargando archivo: {e}")

    df_all = build_df(ads_raw)

    # ── Hero header ────────────────────────────────────────────────────────────
    updated_txt = (
        f"Actualizado: {source_label.replace('ads_raw_','').replace('.json','').replace('_',' ')}"
        if source_label else "Sin datos cargados"
    )
    st.markdown(f"""
    <div class="byd-hero">
      <div class="byd-hero-left">
        <h1>🚗 BYD Costa Rica &nbsp;·&nbsp; Ads Intelligence</h1>
        <p class="sub">Biblioteca de Anuncios Facebook · Page ID: {PAGE_ID}
          &nbsp;·&nbsp; {updated_txt}</p>
      </div>
      <div class="byd-hero-right">
        <div class="byd-wordmark">BYD</div>
        <div class="byd-wordmark-sub">Build Your Dreams</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Empty state ────────────────────────────────────────────────────────────
    if df_all.empty:
        st.markdown("""
        <div class="empty-state">
          <div class="icon">📭</div>
          <h3>Sin datos todavía</h3>
          <p>Usa el panel izquierdo para ejecutar el scraper<br>
             y comenzar a recolectar anuncios de BYD Costa Rica.</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Apply filters ──────────────────────────────────────────────────────────
    df = df_all.copy()

    q = sidebar["search"].strip().lower()
    if q:
        mask = (
            df["body_text"].str.lower().str.contains(q, na=False)
            | df["headline"].str.lower().str.contains(q, na=False)
            | df["description"].str.lower().str.contains(q, na=False)
        )
        df = df[mask]

    if sidebar["plat_filter"]:
        mask = df["platforms"].apply(
            lambda p: any(f.lower() in str(p).lower()
                          for f in sidebar["plat_filter"])
        )
        df = df[mask]

    # CTA filter (dynamic, based on data)
    cta_opts = sorted(df_all["cta"].replace("", "Sin CTA").unique().tolist())
    cta_sel  = sidebar["cta_placeholder"].multiselect(
        "Call to Action", cta_opts, key="cta_filter")
    if cta_sel:
        df = df[df["cta"].replace("", "Sin CTA").isin(cta_sel)]

    # Reset gallery page on filter change
    if q or sidebar["plat_filter"] or cta_sel:
        st.session_state["gallery_page"] = 0

    # ── KPI row ────────────────────────────────────────────────────────────────
    n_active   = int((df["status"] == "Activo").sum())
    n_plats    = int(df["platforms"].apply(
        lambda p: [x.strip() for x in str(p).split(",")]
    ).explode().nunique())

    date_parsed = pd.to_datetime(
        df["start_date"].str.extract(
            r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})"
        )[0], errors="coerce"
    ).dropna()

    if not date_parsed.empty:
        period_str = (f"{date_parsed.min().strftime('%b %Y')} – "
                      f"{date_parsed.max().strftime('%b %Y')}")
    else:
        period_str = "N/A"

    k1, k2, k3, k4 = st.columns(4)
    for col, label, val, sub, icon in [
        (k1, "Total Anuncios",  str(len(df)),      f"de {len(df_all)} totales",     "📋"),
        (k2, "Activos",         str(n_active),      "anuncios en curso",             "🟢"),
        (k3, "Plataformas",     str(n_plats),       "canales diferentes",            "📱"),
        (k4, "Período",         period_str,         "rango de fechas detectado",     "📅"),
    ]:
        col.markdown(kpi_card(label, val, sub, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ─────────────────────────────────────────────────────────────────
    section_heading("📊", "Análisis de Anuncios")

    c1, c2, c3 = st.columns(3)
    for col, fig in [
        (c1, chart_platform_donut(df)),
        (c2, chart_cta_bar(df)),
        (c3, chart_impressions(df)),
    ]:
        with col:
            st.markdown('<div class="chart-card">', unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.plotly_chart(chart_timeline(df), use_container_width=True,
                    config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Gallery ────────────────────────────────────────────────────────────────
    section_heading("🗂", f"Galería de Anuncios")

    ads_list = df.to_dict("records")

    # Toolbar
    t_left, t_mid, t_right = st.columns([3, 3, 2])
    with t_left:
        st.markdown(
            f'<div style="padding:8px 0;font-size:14px;font-weight:700;color:{BYD_NAVY}">'
            f'Mostrando <span style="color:{BYD_RED}">{len(ads_list)}</span> anuncios</div>',
            unsafe_allow_html=True,
        )
    with t_mid:
        sort_by = st.selectbox(
            "sort",
            ["Más recientes primero", "Más antiguos primero", "Por plataforma"],
            key="sort_by", label_visibility="collapsed",
        )
    with t_right:
        xlsx = make_excel_bytes(ads_list)
        if xlsx:
            st.download_button(
                "⬇  Exportar Excel",
                data=xlsx,
                file_name=f"BYD_CR_Ads_{datetime.now():%Y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # Sort
    sort_key = {
        "Más recientes primero": lambda a: str(a.get("start_date", "")),
        "Más antiguos primero":  lambda a: str(a.get("start_date", "")),
        "Por plataforma":        lambda a: str(a.get("platforms", "")),
    }[sort_by]
    reverse = sort_by == "Más recientes primero"
    ads_list = sorted(ads_list, key=sort_key, reverse=reverse)

    # Pagination
    total_pages = max(1, (len(ads_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_idx    = min(st.session_state["gallery_page"], total_pages - 1)
    page_ads    = ads_list[page_idx * PAGE_SIZE: (page_idx + 1) * PAGE_SIZE]

    st.markdown("<br>", unsafe_allow_html=True)

    # Render cards
    for row_start in range(0, len(page_ads), CARD_COLS):
        row_ads = page_ads[row_start: row_start + CARD_COLS]
        cols    = st.columns(CARD_COLS)

        for ci, ad in enumerate(row_ads):
            global_idx = page_idx * PAGE_SIZE + row_start + ci
            with cols[ci]:
                st.markdown(ad_card_html(ad, global_idx),
                            unsafe_allow_html=True)

                # ── Detail expander ───────────────────────────────────────────
                with st.expander("🔍 Ver anuncio completo"):
                    img_src = get_display_image(ad)
                    d_img, d_info = st.columns([1, 1])

                    with d_img:
                        if img_src:
                            st.image(img_src, use_container_width=True)
                        else:
                            st.markdown(
                                '<div style="background:#f4f6f9;border-radius:12px;'
                                'padding:48px;text-align:center;font-size:40px;'
                                'color:#ccd0d8;">📷</div>',
                                unsafe_allow_html=True,
                            )
                        # Extra images
                        extras = ad.get("all_image_urls", [])
                        if isinstance(extras, list) and len(extras) > 1:
                            st.caption(f"Este anuncio tiene {len(extras)} imágenes")

                    with d_info:
                        def _row(lbl: str, val: str) -> None:
                            if val:
                                st.markdown(
                                    f'<div class="detail-section-label">{lbl}</div>'
                                    f'<div class="detail-value">{val}</div>',
                                    unsafe_allow_html=True,
                                )
                        _row("Estado",         ad.get("status", ""))
                        _row("Fecha inicio",   ad.get("start_date", ""))
                        _row("Plataformas",    ad.get("platforms", ""))
                        _row("Call to Action", ad.get("cta", ""))
                        _row("Impresiones",    ad.get("impressions", ""))
                        _row("ID del Anuncio", ad.get("ad_id", ""))

                    # Full text
                    if ad.get("headline"):
                        st.markdown(f"### {ad['headline']}")
                    if ad.get("body_text"):
                        st.markdown(ad["body_text"])
                    if ad.get("description"):
                        st.info(ad["description"])
                    if ad.get("image_url"):
                        st.caption(
                            f"[Ver imagen en Facebook]({ad['image_url']})")

    # ── Pagination controls ────────────────────────────────────────────────────
    if total_pages > 1:
        st.markdown("<br>", unsafe_allow_html=True)
        p1, p2, p3, p4, p5 = st.columns([1, 1, 3, 1, 1])
        if p1.button("⟪", disabled=page_idx == 0, use_container_width=True,
                     key="pg_first"):
            st.session_state["gallery_page"] = 0; st.rerun()
        if p2.button("‹ Ant.", disabled=page_idx == 0, use_container_width=True,
                     key="pg_prev"):
            st.session_state["gallery_page"] -= 1; st.rerun()
        p3.markdown(
            f'<div style="text-align:center;padding:8px 0;color:{BYD_GRAY};'
            f'font-size:13px;font-weight:500;">'
            f'Página <b style="color:{BYD_NAVY}">{page_idx + 1}</b> de '
            f'<b style="color:{BYD_NAVY}">{total_pages}</b> '
            f'({len(ads_list)} anuncios)</div>',
            unsafe_allow_html=True,
        )
        if p4.button("Sig. ›", disabled=page_idx >= total_pages - 1,
                     use_container_width=True, key="pg_next"):
            st.session_state["gallery_page"] += 1; st.rerun()
        if p5.button("⟫", disabled=page_idx >= total_pages - 1,
                     use_container_width=True, key="pg_last"):
            st.session_state["gallery_page"] = total_pages - 1; st.rerun()


# =============================================================================

if __name__ == "__main__":
    main()
