"""Tema visual SIPAT: CSS moderno, tarjetas, pills y helpers de estilo."""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

INDIGO = "#4f46e5"
ROJO = "#dc2626"
AZUL = "#2563eb"
VERDE = "#059669"
AMBAR = "#d97706"
MORADO = "#7c3aed"
GRIS = "#64748b"

PALETA = [INDIGO, "#f59e0b", "#10b981", ROJO, MORADO]


def nivel_riesgo(v, lo, hi):
    if v < lo:
        return "Bajo", VERDE
    if v <= hi:
        return "Medio", AMBAR
    return "Alto", ROJO


def pill(nivel):
    cls = {"Bajo": "pill-bajo", "Medio": "pill-medio", "Alto": "pill-alto"}.get(nivel, "pill-medio")
    return f'<span class="pill {cls}">{nivel}</span>'


def card(icon, num, lbl, sub="", color="#0f172a"):
    return (f'<div class="card"><span class="ic">{icon}</span>'
            f'<div class="num" style="color:{color}">{num}</div>'
            f'<div class="lbl">{lbl}</div>'
            + (f'<div class="sub">{sub}</div>' if sub else "") + "</div>")


def banner(nivel, html_interno):
    cls = {"Bajo": "ok", "Medio": "warn", "Alto": "bad"}[nivel]
    return f'<div class="banner-{cls}">{html_interno}</div>'


def estilo_plotly(fig, alto=380):
    fig.update_layout(font=dict(family="Inter, sans-serif", size=12, color="#334155"),
                      title_font=dict(color="#0f172a", size=15),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=46, b=10), height=alto,
                      legend=dict(orientation="h", y=-0.15))
    fig.update_xaxes(gridcolor="#eef2f7", title_font_color="#475569",
                     tickfont_color="#334155")
    fig.update_yaxes(gridcolor="#eef2f7", title_font_color="#475569",
                     tickfont_color="#334155")
    return fig


def hero(n_total_ev, km_red, n_pn):
    st.markdown(f"""
<div class="hero">
  <h1>🛡️ SIPAT <span style="font-weight:400;font-size:1.05rem;opacity:.8">· Viaja seguro por Perú</span></h1>
  <p>Analiza tu ruta <b>antes de salir</b>: accidentes que han ocurrido, riesgo previsto,
     clima y alertas en tiempo real.</p>
  <span class="hpill">📊 {n_total_ev:,} siniestros analizados</span>
  <span class="hpill">🛣️ {km_red:,.0f} km de red vial</span>
  <span class="hpill">⚠️ {n_pn} puntos negros</span>
  <span class="hpill">📡 ONSV + SUTRAN + OSITRAN</span>
</div>""", unsafe_allow_html=True)


def css():
    st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"], .stApp {font-family:'Inter','Segoe UI',system-ui,sans-serif;
                                           color:#0f172a;}
      .stApp h1, .stApp h2, .stApp h3, .stApp h4 {color:#0f172a;}
      .stApp a, .stApp a:visited {color:#2563eb;}
      .block-container {padding-top:.9rem; max-width:1500px;}
      #MainMenu, footer {visibility:hidden;}
      header[data-testid="stHeader"] {background:transparent;}

      section[data-testid="stSidebar"] {background:#0f172a;}
      section[data-testid="stSidebar"] hr {border-color:#1e293b !important;}
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3,
      section[data-testid="stSidebar"] p,
      section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
      section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:#e2e8f0 !important;}
      section[data-testid="stSidebar"] input,
      section[data-testid="stSidebar"] textarea,
      section[data-testid="stSidebar"] [data-baseweb="select"] > div,
      section[data-testid="stSidebar"] [data-baseweb="tag"] {color:#0f172a !important;}
      section[data-testid="stSidebar"] [data-baseweb="tag"] {background:#dbe3ef; border-color:#94a3b8;}
      section[data-testid="stSidebar"] [data-testid="stSliderTickValueBar"],
      section[data-testid="stSidebar"] [data-testid="stSliderTickValueMin"],
      section[data-testid="stSidebar"] [data-testid="stSliderTickValueMax"] {color:#cbd5e1 !important;
                                                                            background:transparent !important;}
      section[data-testid="stSidebar"] [data-baseweb="select"] svg {fill:#94a3b8;}
      section[data-testid="stSidebar"] [role="checkbox"] p,
      section[data-testid="stSidebar"] [role="radio"] p {color:#e2e8f0 !important;}
      section[data-testid="stSidebar"] .stMultiSelect label,
      section[data-testid="stSidebar"] .stSlider label {font-size:.82rem;}

      div[data-testid="stExpander"] details summary {color:#0f172a;}
      div[data-testid="stDataFrame"] {color:#0f172a;}
      [data-baseweb="select"] input::placeholder,
      input::placeholder, textarea::placeholder {color:#475569 !important; opacity:1;}

      .hero {background:linear-gradient(120deg,#0f172a 0%,#1e3a8a 55%,#4f46e5 100%);
             border-radius:20px; padding:24px 32px 20px; color:white; margin-bottom:14px;
             box-shadow:0 10px 30px -12px rgba(30,58,138,.45);}
      .hero h1 {margin:0; font-size:1.9rem; font-weight:800; letter-spacing:-.5px;}
      .hero p  {margin:6px 0 12px; opacity:.85; font-size:.98rem;}
      .hpill {display:inline-block; background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.25);
              padding:5px 14px; border-radius:999px; font-size:.8rem; font-weight:600; margin-right:8px;}

      .card {background:white; border:1px solid #e5e7eb; border-radius:16px; color:#0f172a;
             padding:16px 18px 12px; box-shadow:0 1px 3px rgba(15,23,42,.06); height:100%;}
      .card .ic {font-size:1.35rem;}
      .card .num {font-size:1.72rem; font-weight:800; letter-spacing:-.5px; line-height:1.3;}
      .card .lbl {color:#475569; font-size:.76rem; font-weight:700; text-transform:uppercase;
                  letter-spacing:.5px; margin-top:2px;}
      .card .sub {color:#64748b; font-size:.8rem; margin-top:3px;}

      .pill {display:inline-block; padding:3px 16px; border-radius:999px; color:white;
             font-weight:700; font-size:.95rem; vertical-align:middle;}
      .pill-bajo{background:#059669;} .pill-medio{background:#d97706;} .pill-alto{background:#dc2626;}

      .banner-ok   {background:linear-gradient(90deg,#ecfdf5,#d1fae5); border:1px solid #6ee7b7;
                    border-radius:14px; padding:14px 18px; margin:10px 0; color:#064e3b;}
      .banner-warn {background:linear-gradient(90deg,#fffbeb,#fef3c7); border:1px solid #fcd34d;
                    border-radius:14px; padding:14px 18px; margin:10px 0; color:#78350f;}
      .banner-bad  {background:linear-gradient(90deg,#fef2f2,#fee2e2); border:1px solid #fca5a5;
                    border-radius:14px; padding:14px 18px; margin:10px 0; color:#7f1d1d;}

      button[kind="primary"] {border-radius:12px !important; font-weight:700 !important;
             background:linear-gradient(90deg,#4f46e5,#7c3aed) !important; border:none !important;}
      button[kind="primary"]:hover {filter:brightness(1.08);}
      .stButton > button {border-radius:12px !important;}

      .stTabs [data-baseweb="tab-list"] {gap:6px;}
      .stTabs [data-baseweb="tab"] {padding:10px 18px; border-radius:12px 12px 0 0;
                                    font-weight:600; font-size:.95rem; color:#334155;}
      .stTabs [aria-selected="true"] {background:#eef2ff; color:#4338ca !important;}

      div[data-testid="stMetricValue"] {font-weight:800; color:#0f172a !important;}
      div[data-testid="stMetricLabel"] p {color:#475569 !important;}
      div[data-testid="stMetric"] {background:white; border:1px solid #eef2f7;
                                   border-radius:14px; padding:10px 14px;}
      [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
          color:#475569 !important;}
      iframe {border-radius:14px !important;}
      .mini-note {color:#64748b; font-size:.8rem;}
    </style>""", unsafe_allow_html=True)
