# -*- coding: utf-8 -*-
"""
Market Suite | PDF Export Module

Handles PDF generation for executive reports.
Previously in: app.py (monolithic)
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List
import pandas as pd
from fpdf import FPDF
import streamlit as st


# ==============================================================================
# PDF UTILITIES
# ==============================================================================

def human_money(x: float) -> str:
    """Format number as human-readable money."""
    try:
        if abs(x) >= 1e9:
            return f"${x/1e9:,.2f} B"
        if abs(x) >= 1e6:
            return f"${x/1e6:,.2f} M"
        return f"${x:,.0f}"
    except Exception:
        return str(x)


def pdf_sanitize(text) -> str:
    """Sanitize text for FPDF (latin-1 encoding)."""
    try:
        return str(text).encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return str(text)


# ==============================================================================
# PDF CLASS
# ==============================================================================

class ExecutivePDF(FPDF):
    """Custom PDF class with header/footer for executive reports."""
    
    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 55, 153)
        self.cell(0, 8, "Reporte de Inteligencia de Mercado - Automotriz", 0, 1, "C")
        self.ln(2)
    
    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120)
        fecha_gen = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(0, 10, f"Pag {self.page_no()} | Generado {fecha_gen} | Confidencial", 0, 0, "C")


# ==============================================================================
# PDF BUILDER
# ==============================================================================

@st.cache_data(show_spinner=False)
def build_pdf_bytes(df_dict: Dict[str, List], title: str, subtitle: str, view_mode: str) -> bytes:
    """
    Build executive PDF report from dataframe dict.
    
    Args:
        df_dict: DataFrame as dict (from df.to_dict(orient='list'))
        title: Report title
        subtitle: Report subtitle/description
        view_mode: "Full Year" or "YTD"
    
    Returns:
        PDF bytes ready for download
    """
    df = pd.DataFrame(df_dict)
    pdf = ExecutivePDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    
    # Title block
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(0)
    pdf.cell(0, 10, pdf_sanitize(title), 0, 1, "L")
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(90)
    pdf.cell(0, 7, pdf_sanitize(f"Vista Temporal: {view_mode} | {subtitle}"), 0, 1, "L")
    pdf.ln(3)
    
    # Executive KPIs box
    total_vol = float(df["CANTIDAD"].sum()) if "CANTIDAD" in df.columns else 0.0
    total_val = float(df["VALOR US$ CIF"].sum()) if "VALOR US$ CIF" in df.columns else 0.0
    ticket = (total_val / total_vol) if total_vol else 0.0
    
    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(10, 40, 190, 20, "FD")
    pdf.set_y(45)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0)
    pdf.cell(63, 8, pdf_sanitize(f"Volumen: {total_vol:,.0f}"), 0, 0, "C")
    pdf.cell(63, 8, pdf_sanitize(f"Inversión: {human_money(total_val)}"), 0, 0, "C")
    pdf.cell(63, 8, pdf_sanitize(f"Ticket: {human_money(ticket)}"), 0, 1, "C")
    pdf.ln(10)
    
    # Main ranking
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 55, 153)
    
    if "MODELO" in df.columns and df["MODELO"].nunique() > 1:
        group = "MODELO"
    elif "MARCA" in df.columns:
        group = "MARCA"
    else:
        group = "AÑO" if "AÑO" in df.columns else None
    
    if group is not None and group in df.columns and "CANTIDAD" in df.columns:
        pdf.cell(0, 8, pdf_sanitize(f"Top 15 por {group}"), 0, 1, "L")
        pdf.ln(1)
        top = df.groupby(group)["CANTIDAD"].sum().sort_values(ascending=False).head(15)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(255)
        pdf.set_fill_color(44, 62, 80)
        pdf.cell(140, 7, pdf_sanitize(group), 1, 0, "L", 1)
        pdf.cell(50, 7, "Unidades", 1, 1, "R", 1)
        
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0)
        alt = False
        for name, val in top.items():
            pdf.set_fill_color(240, 240, 240) if alt else pdf.set_fill_color(255, 255, 255)
            pdf.cell(140, 7, pdf_sanitize(str(name))[:65], 1, 0, "L", alt)
            pdf.cell(50, 7, pdf_sanitize(f"{val:,.0f}"), 1, 1, "R", alt)
            alt = not alt
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0)
        pdf.multi_cell(0, 6, pdf_sanitize("No hay columnas suficientes para construir un ranking."))
    
    # Importers block
    if "EMPRESA" in df.columns and "CANTIDAD" in df.columns:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 55, 153)
        pdf.cell(0, 8, "Top 5 Importadores", 0, 1, "L")
        top_imp = df.groupby("EMPRESA")["CANTIDAD"].sum().sort_values(ascending=False).head(5)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0)
        for name, val in top_imp.items():
            pdf.cell(140, 6, pdf_sanitize(f"- {name}")[:80], 0, 0, "L")
            pdf.cell(50, 6, pdf_sanitize(f"{val:,.0f}"), 0, 1, "R")
    
    return pdf.output(dest="S").encode("latin-1")
