"""
SolarPro-FinModelling | PV Module Financial Intelligence
Upload 2-5 datasheets, enter financials, generate comparison PDF report.
"""
import streamlit as st
import os, io, json, tempfile, sys, re, hashlib
import urllib.request
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from pdf_parser import extract_module_specs, format_specs_for_display, extract_text_from_pdf, parse_specs
from financial_engine import run_analysis
from report_generator import generate_report as gen_report
from scoring import compute_scores, get_default_weights, format_scoring_table
from weather_data import fetch_nasa_power_monthly, fetch_pvgis_monthly, compute_annual_solar_metrics, get_weather_summary
from currency import currency_options, code_from_option, get_currency, make_formatter


def _check_internet():
    """Quick connectivity check against a known endpoint."""
    try:
        urllib.request.urlopen("https://httpbin.org/get", timeout=5)
        return True
    except Exception:
        return False


st.set_page_config(page_title="SolarPro | PV Module Financial Intelligence", page_icon="☀️", layout="wide")

# ---------------------------------------------------------------------------
# THEMES
# ---------------------------------------------------------------------------
THEMES = {
    "Midnight Ocean": {
        "bg": "#071b31", "card": "#0d2b4a", "border": "rgba(255,255,255,0.06)",
        "accent": "#f0c040", "accent2": "#e8923a", "text": "#e8edf2",
        "muted": "#7a9bb5", "dim": "#5a7a94", "heading": "#e8edf2",
        "success": "#4ade80", "link": "#6b9bc0",
    },
    "Arctic Frost": {
        "bg": "#f0f4f8", "card": "#ffffff", "border": "rgba(0,0,0,0.08)",
        "accent": "#2563eb", "accent2": "#7c3aed", "text": "#1e293b",
        "muted": "#64748b", "dim": "#94a3b8", "heading": "#0f172a",
        "success": "#16a34a", "link": "#2563eb",
    },
    "Solar Flare": {
        "bg": "#1a1a2e", "card": "#16213e", "border": "rgba(255,255,255,0.08)",
        "accent": "#e94560", "accent2": "#f5a623", "text": "#eaeaea",
        "muted": "#a0a0b0", "dim": "#6c6c80", "heading": "#ffffff",
        "success": "#00d68f", "link": "#e94560",
    },
    "Emerald Dark": {
        "bg": "#0d1f1d", "card": "#132e2b", "border": "rgba(255,255,255,0.06)",
        "accent": "#34d399", "accent2": "#6ee7b7", "text": "#ecfdf5",
        "muted": "#6ee7b7", "dim": "#34d399", "heading": "#ffffff",
        "success": "#34d399", "link": "#34d399",
    },
    "Royal Purple": {
        "bg": "#1e1033", "card": "#2a1a42", "border": "rgba(255,255,255,0.07)",
        "accent": "#c084fc", "accent2": "#a855f7", "text": "#f3e8ff",
        "muted": "#c4b5fd", "dim": "#8b5cf6", "heading": "#ffffff",
        "success": "#34d399", "link": "#c084fc",
    },
    "Warm Sunset": {
        "bg": "#1c1917", "card": "#292524", "border": "rgba(255,255,255,0.07)",
        "accent": "#fb923c", "accent2": "#f97316", "text": "#fafaf9",
        "muted": "#a8a29e", "dim": "#78716c", "heading": "#ffffff",
        "success": "#4ade80", "link": "#fb923c",
    },
    "Clean White": {
        "bg": "#ffffff", "card": "#f8fafc", "border": "rgba(0,0,0,0.1)",
        "accent": "#0369a1", "accent2": "#0284c7", "text": "#1e293b",
        "muted": "#64748b", "dim": "#94a3b8", "heading": "#0c4a6e",
        "success": "#15803d", "link": "#0369a1",
    },
    "Neon Tech": {
        "bg": "#0a0a0f", "card": "#12121a", "border": "1px solid rgba(0,255,136,0.15)",
        "accent": "#00ff88", "accent2": "#00ccff", "text": "#e0e0e0",
        "muted": "#888899", "dim": "#555566", "heading": "#ffffff",
        "success": "#00ff88", "link": "#00ccff",
    },
}

def _get_theme():
    return THEMES.get(st.session_state.get("theme", ""), THEMES["Midnight Ocean"])

def _theme_css(t):
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400,500&family=Manrope:wght@400,500,600,700,800&family=Playfair+Display:wght@600,700&display=swap');
* {{ box-sizing: border-box; }}
html, body, .stApp {{ background: {t['bg']}; color: {t['text']}; font-family: 'Manrope', sans-serif; }}
.stApp > header {{ display: none; }}
section.main > div {{ padding-top: 0; max-width: 1200px; margin: 0 auto; }}
.block-container {{ padding: 0 !important; max-width: 1200px !important; }}
.solarpro-header {{ display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1.5rem; border-bottom: 1px solid {t['border']}; background: {t['bg']}; }}
.solarpro-brand {{ font-family: 'Playfair Display', serif; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem; color: {t['text']}; }}
.solarpro-brand .sun-mark {{ color: {t['accent']}; font-size: 1rem; }}
.solarpro-brand span span {{ color: {t['link']}; }}
.solarpro-tag {{ font-family: 'DM Mono', monospace; font-size: 0.6rem; color: {t['muted']}; letter-spacing: 0.08em; display: flex; align-items: center; gap: 0.4rem; }}
.dot {{ width: 6px; height: 6px; border-radius: 50%; background: {t['success']}; display: inline-block; animation: pulse 2s infinite; }}
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
.step-nav {{ display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1.5rem; background: {t['bg']}; border-bottom: 1px solid {t['border']}; }}
.step-nav .step-label {{ font-family: 'DM Mono', monospace; font-size: 0.7rem; color: {t['accent']}; letter-spacing: 0.08em; }}
.step-nav .step-desc {{ font-size: 0.65rem; color: {t['muted']}; margin-left: 0.8rem; }}
.progress-wrap {{ padding: 0.5rem 1.5rem; }}
.progress-label {{ display: flex; justify-content: space-between; font-family: 'DM Mono', monospace; font-size: 0.6rem; color: {t['muted']}; }}
.progress-label .stat {{ color: {t['text']}; }}
.progress-track {{ height: 3px; background: {t['border']}; border-radius: 2px; overflow: hidden; margin-top: 0.3rem; }}
.progress-fill {{ height: 100%; background: linear-gradient(90deg, {t['accent']}, {t['accent2']}); border-radius: 2px; transition: width .4s; }}
.step-panel {{ padding: 1.5rem; }}
.section-eyebrow {{ font-family: 'DM Mono', monospace; font-size: 0.6rem; color: {t['accent']}; letter-spacing: 0.12em; }}
.section-heading h2 {{ font-family: 'Playfair Display', serif; font-size: 1.3rem; color: {t['heading']}; margin: 0.2rem 0; }}
.section-heading p {{ font-size: 0.75rem; color: {t['text']}; margin: 0 0 1.2rem; opacity: 0.7; }}
.stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div, .stTextArea textarea {{ background: {t['card']} !important; border: 1px solid {t['border']} !important; border-radius: 6px !important; color: {t['text']} !important; font-family: 'Manrope',sans-serif !important; font-size: 0.8rem !important; padding: 0.4rem 0.7rem !important; }}
.stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus {{ border-color: {t['accent']} !important; box-shadow: 0 0 0 1px {t['accent']} !important; }}
.stSelectbox>div>div {{ background: {t['card']} !important; border: 1px solid {t['border']} !important; border-radius: 6px !important; }}
label {{ color: {t['text']} !important; font-size: 0.75rem !important; font-weight: 500 !important; }}
.stRadio>div {{ flex-direction: row !important; gap: 0.4rem !important; }}
.stRadio>div label {{ background: {t['card']} !important; padding: 0.2rem 0.7rem !important; border-radius: 5px !important; border: 1px solid {t['border']} !important; font-size: 0.7rem !important; color: {t['text']} !important; }}
div[data-testid="stMarkdownContainer"] p {{ font-size: 0.8rem; color: {t['text']}; }}
.stSlider>div>div>div {{ background: {t['dim']} !important; }}
div[data-testid="stThumb"] {{ background: {t['accent']} !important; }}
.mod-card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 1rem; margin-bottom: 0.8rem; }}
.mod-card.done {{ border-color: {t['success']}40; }}
.mod-card h4 {{ font-size: 0.8rem; color: {t['text']}; margin: 0 0 0.5rem; display: flex; align-items: center; gap: 0.5rem; }}
.mod-card .tag {{ font-size: 0.55rem; background: {t['accent']}20; color: {t['accent']}; padding: 0.1rem 0.4rem; border-radius: 3px; letter-spacing: 0.04em; }}
.stButton>button, div[data-testid="stDownloadButton"]>button {{ background: linear-gradient(135deg,{t['accent']},{t['accent2']}) !important; color: {t['bg']} !important; border: none !important; font-weight: 600 !important; padding: 0.4rem 1.2rem !important; border-radius: 6px !important; font-size: 0.78rem !important; }}
.stButton>button[kind="secondary"] {{ background: transparent !important; color: {t['text']} !important; border: 1px solid {t['border']} !important; }}
.stButton>button[kind="secondary"]:hover {{ border-color: {t['accent']} !important; color: {t['accent']} !important; }}
div[data-testid="metric-container"] {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 8px; padding: 0.7rem; }}
div[data-testid="metric-container"] > div:first-child {{ color: {t['text']} !important; font-size: 0.65rem !important; font-weight: 500 !important; }}
div[data-testid="metric-container"] > div:nth-child(2) {{ font-size: 1.2rem !important; font-weight: 700 !important; color: {t['accent']} !important; }}
.stTable table {{ background: {t['card']} !important; }}
.stTable th {{ background: {t['dim']}40 !important; color: {t['text']} !important; font-size: 0.65rem !important; }}
.stTable td {{ color: {t['text']} !important; font-size: 0.7rem !important; }}
.wiz-actions {{ display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.5rem; border-top: 1px solid {t['border']}; background: {t['bg']}; }}
.stAlert {{ border-radius: 6px !important; font-size: 0.75rem !important; }}
.st-cb {{ color: {t['text']} !important; }}
.st-b8 {{ color: {t['text']} !important; }}
@media (max-width:768px){{ .form-grid, .form-grid.three {{ grid-template-columns: 1fr; }} }}
footer {{ display: none; }}
</style>
"""

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
if "theme" in st.session_state and st.session_state.theme:
    st.markdown(_theme_css(_get_theme()), unsafe_allow_html=True)
else:
    st.markdown(_theme_css(THEMES["Midnight Ocean"]), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SESSION
# ---------------------------------------------------------------------------
for k in ("step",):
    if k not in st.session_state:
        st.session_state[k] = 0
for k,v in {"results":None,"chart_paths":None,"project_info":None,"mod_list":None,
            "weather_data":None,"project_params":None,"module_specs_list":[],
            "module_pdf_bytes":{},"module_filenames":{},
            "compliances":{},"_n_mod":2,
            "report_generated":False}.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "theme" not in st.session_state:
    st.session_state.theme = ""
if "report_generated" not in st.session_state:
    st.session_state.report_generated = False
if "inputs_dirty" not in st.session_state:
    st.session_state.inputs_dirty = False

STEP_NAMES = ["Project", "Modules", "Priorities", "Finance", "Compliances", "Report"]
STEP_EYEBROWS = ["01 / PROJECT BRIEF", "02 / CANDIDATE MODULES", "03 / DECISION PRIORITIES",
                 "04 / ECONOMIC CASE", "05 / STATUTORY COMPLIANCES", "06 / ANALYSIS"]
STEP_DESCS = [
    "Frame the solar asset — location, scale, and site conditions anchor every calculation.",
    "Upload PDF datasheets; specs are auto-extracted and editable below.",
    "Weight what matters. Weights are normalised automatically.",
    "Set costs, tariff, and financing structure.",
    "Track statutory approvals and environmental clearances.",
    "",
]
PCT = lambda s: int((s+1)/6*100)

# ======================================================================
# NAVIGATION FUNCTIONS
# ======================================================================
def _go_back():
    st.session_state.step = st.session_state.step - 1
    st.session_state.inputs_dirty = True

def _go_forward():
    st.session_state.step = st.session_state.step + 1
    st.session_state.inputs_dirty = True

# ---------------------------------------------------------------------------
# THEME SELECTION SCREEN (shown on first visit)
# ---------------------------------------------------------------------------
if not st.session_state.theme:
    st.markdown(f"""
<div class="solarpro-header" style="background:{THEMES['Midnight Ocean']['bg']}">
    <div class="solarpro-brand" style="color:{THEMES['Midnight Ocean']['text']}">
        <span class="sun-mark" style="color:{THEMES['Midnight Ocean']['accent']}">&#9728;</span>
        <span>SOLAR<span style="color:{THEMES['Midnight Ocean']['link']}">PRO</span></span>
    </div>
    <div class="solarpro-tag" style="color:{THEMES['Midnight Ocean']['muted']}">THEME SETUP</div>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="padding:1.5rem;background:{THEMES['Midnight Ocean']['bg']}">
    <div style="font-family:'Playfair Display',serif;font-size:1.6rem;color:{THEMES['Midnight Ocean']['heading']}">Choose Your Theme</div>
    <p style="font-size:0.85rem;color:{THEMES['Midnight Ocean']['muted']};margin:0.3rem 0 1.5rem">
        Select a visual theme for SolarPro. You can change this later from Settings.
    </p>
</div>
""", unsafe_allow_html=True)

    # Theme grid - 4 columns
    theme_names = list(THEMES.keys())
    for row_start in range(0, len(theme_names), 4):
        cols = st.columns(4)
        for idx, col in enumerate(cols):
            t_idx = row_start + idx
            if t_idx >= len(theme_names):
                break
            name = theme_names[t_idx]
            t = THEMES[name]
            with col:
                st.markdown(f"""
<div style="background:{t['card']};border:1px solid {t['border']};border-radius:10px;padding:0.8rem;min-height:130px">
    <div style="display:flex;gap:5px;margin-bottom:8px">
        <div style="width:18px;height:18px;border-radius:50%;background:{t['accent']}"></div>
        <div style="width:18px;height:18px;border-radius:50%;background:{t['accent2']}"></div>
        <div style="width:18px;height:18px;border-radius:50%;background:{t['text_muted'] if 'text_muted' in t else t['muted']}"></div>
        <div style="width:18px;height:18px;border-radius:50%;background:{t['dim']}"></div>
    </div>
    <div style="font-size:0.75rem;font-weight:600;color:{t['text']};font-family:Manrope,sans-serif">{name}</div>
    <div style="font-size:0.55rem;color:{t['muted']};margin-top:2px;font-family:DM Mono,monospace">{t['bg']}</div>
</div>
""", unsafe_allow_html=True)
                if st.button(f"Select {name}", key=f"theme_{name}", use_container_width=True):
                    st.session_state.theme = name
                    st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# HEADER (only shown after theme is selected)
# ---------------------------------------------------------------------------
t = _get_theme()
st.markdown(f"""
<div class="solarpro-header">
    <div class="solarpro-brand"><span class="sun-mark">&#9728;</span><span>SOLAR<span>PRO</span></span></div>
    <div class="solarpro-tag"><span class="dot"></span>PV Module Financial Intelligence</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR - Theme Switcher
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"<p style='font-size:0.7rem;color:{t['muted']};margin-bottom:0.5rem'>THEME</p>", unsafe_allow_html=True)
    theme_options = list(THEMES.keys())
    current_idx = theme_options.index(st.session_state.theme) if st.session_state.theme in theme_options else 0
    selected_theme = st.selectbox("Theme", theme_options, index=current_idx, key="sidebar_theme", label_visibility="collapsed")
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        st.rerun()

# step nav — simple label
step = st.session_state.step
st.markdown(f"""
<div class="step-nav">
    <div>
        <span class="step-label">{STEP_EYEBROWS[step]}</span>
        <span class="step-desc">{STEP_DESCS[step]}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# IMPORTS FOR CACHED HELPERS
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def cached_parse(pdf_bytes, default_tech, _version=5):
    return extract_module_specs(pdf_bytes, default_tech)

@st.cache_data(show_spinner=False)
def cached_parse_wp(pdf_bytes, default_tech, selected_wp, _version=5):
    return extract_module_specs(pdf_bytes, default_tech, selected_wp=selected_wp)

@st.cache_data(show_spinner=False)
def cached_extract_text(pdf_bytes):
    text, method = extract_text_from_pdf(pdf_bytes)
    return text, method

@st.cache_data(show_spinner=False)
def cached_nasa(lat, lon):
    return fetch_nasa_power_monthly(lat, lon)

@st.cache_data(show_spinner=False)
def cached_pvgis(lat, lon):
    return fetch_pvgis_monthly(lat, lon)

DEFAULT_TECHS = ["Mono PERC", "N-TOPCon", "HJT", "Mono PERC", "Poly PERC"]


# ======================================================================
# STEP 0 — PROJECT
# ======================================================================
if step == 0:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-eyebrow">01 — PROJECT BRIEF</div><h2>Frame the solar asset.</h2><p>These inputs anchor energy-yield assumptions and scale commercial comparison.</p></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input("Customer / Organisation", "Raghavan", key="s_customer")
        project_name = st.text_input("Project name", "19.6 MW Solar Plant - Pudukottai", key="s_project")
        location = st.text_input("Site location", "Pudukottai, Tamilnadu, India", key="s_location")
        mounting_type = st.radio("Mounting structure", ["Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"], index=0, key="s_mounting")
    with col2:
        customer_company = st.text_input("Company", "Raghavan Group", key="s_company")
        plant_capacity = st.number_input("DC plant capacity (MWp)", 0.1, 500.0, 19.6, 0.1, key="s_cap")
        latitude = st.number_input("Latitude (°)", -90.0, 90.0, 10.38, 0.01, format="%.2f", key="s_lat")
        longitude = st.number_input("Longitude (°)", -180.0, 180.0, 78.82, 0.01, format="%.2f", key="s_lon")
        tilt_angle = None
        if mounting_type in ("Fixed Tilt", "Single Axis Tracker"):
            tilt_angle = st.number_input("Tilt angle (°)", 0, 60, 10, 1, key="s_tilt")

    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# STEP 1 — MODULES (side-by-side column layout)
# ======================================================================
elif step == 1:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-eyebrow">02 — CANDIDATE MODULES</div><h2>Bring the contenders.</h2><p>Upload PDF datasheets; specs are auto-extracted and editable below.</p></div>', unsafe_allow_html=True)

    # Restore n_modules from session state if available
    saved_n = st.session_state.get("module_specs_list", [])
    default_n = max(len(saved_n), 2) if saved_n else 2
    n_modules = st.number_input("Modules to compare", 2, 5, default_n, 1, key="n_mod")
    st.session_state["_n_mod"] = n_modules

    # Create side-by-side columns with 0.15 gap ratio for spacing between modules
    gap_ratio = 0.15
    col_ratios = [1.0] * n_modules
    gap_total = gap_ratio * (n_modules - 1)
    col_weight = (1.0 - gap_total) / n_modules
    spec_ratio = [col_weight] * n_modules
    cols = st.columns(spec_ratio, gap="small")

    # Restore previously stored data
    prev_specs = st.session_state.get("module_specs_list") or []
    prev_pdf_bytes = st.session_state.get("module_pdf_bytes") or {}
    prev_filenames = st.session_state.get("module_filenames") or {}

    module_specs_list = []
    for i in range(n_modules):
        label = f"Module {i+1}"
        default_tech = DEFAULT_TECHS[i] if i < len(DEFAULT_TECHS) else "Mono PERC"

        with cols[i]:
            st.markdown(f"""<div style="background:{t['card']};border:1px solid {t['border']};border-radius:10px;padding:0.8rem;margin-bottom:0.5rem">
                <div style="font-size:0.8rem;font-weight:600;color:{t['text']};margin-bottom:0.3rem">{label}</div>
            </div>""", unsafe_allow_html=True)

            uploaded = st.file_uploader(f"Datasheet (PDF)", type=["pdf"], key=f"upload_{i}", label_visibility="collapsed")

            # If new file uploaded, store bytes and filename
            if uploaded is not None:
                pdf_bytes = uploaded.read()
                prev_pdf_bytes[i] = pdf_bytes
                prev_filenames[i] = uploaded.name
                st.session_state.module_pdf_bytes = prev_pdf_bytes
                st.session_state.module_filenames = prev_filenames
            # Otherwise, restore from session state
            elif i in prev_pdf_bytes:
                pdf_bytes = prev_pdf_bytes[i]
                uploaded_name = prev_filenames.get(i, "")
            else:
                pdf_bytes = None

            existing = prev_specs[i] if i < len(prev_specs) else None

            if pdf_bytes is not None:
                if existing and existing.get("_filename") == prev_filenames.get(i, "") and not uploaded:
                    # Use existing specs (user edited them before)
                    specs = existing
                else:
                    # Parse fresh
                    try:
                        specs = cached_parse(pdf_bytes, default_tech)
                    except Exception as e:
                        st.error(f"Parse failed: {e}")
                        specs = None
                    if specs and specs.get("_error"):
                        st.warning(f"Partial: {specs['_error']}")

                    if specs and specs.get("power_options"):
                        opts = specs["power_options"]
                        mid_idx = len(opts) // 2
                        # Restore previously selected Wp if available
                        prev_wp = existing.get("power_wp") if existing else None
                        wp_index = opts.index(prev_wp) if prev_wp in opts else min(mid_idx+1, len(opts)-1)
                        selected_wp = st.selectbox("Wp", options=opts, index=wp_index, key=f"wp_{i}", label_visibility="collapsed")
                        specs = cached_parse_wp(pdf_bytes, default_tech, int(selected_wp))
                        specs["power_wp"] = int(selected_wp)
                    elif specs:
                        prev_wp_val = int(existing.get("power_wp", 600)) if existing else 600
                        selected_wp = st.number_input("Wp", 300, 800, prev_wp_val, 5, key=f"wp_m_{i}", label_visibility="collapsed")
                        specs["power_wp"] = int(selected_wp)
                        specs["power_options"] = [int(selected_wp)]

                if specs:
                    prev_price = float(existing.get("price_per_wp", 22)) if existing else 22.0
                    specs["price_per_wp"] = st.number_input(f"Price/Wp", 5.0, 50.0, float(prev_price), 0.5, key=f"price_{i}", label_visibility="collapsed")
                    specs["_filename"] = prev_filenames.get(i, "")

                    # Extracted specs toggle
                    with st.popover("Extracted specs", use_container_width=True):
                        st.text(format_specs_for_display(specs))

                    # Editable fields — restore from existing if available
                    vmp = st.number_input("Vmp (V)", 0.0, 100.0, float(existing.get("vmp", specs.get("vmp",0) or 0) if existing else specs.get("vmp",0) or 0), key=f"vmp_{i}")
                    imp = st.number_input("Imp (A)", 0.0, 30.0, float(existing.get("imp", specs.get("imp",0) or 0) if existing else specs.get("imp",0) or 0), key=f"imp_{i}")
                    voc = st.number_input("Voc (V)", 0.0, 100.0, float(existing.get("voc", specs.get("voc",0) or 0) if existing else specs.get("voc",0) or 0), key=f"voc_{i}")
                    eff = st.number_input("Efficiency (%)", 0.0, 30.0, float(existing.get("efficiency_pct", specs.get("efficiency_pct",0) or 0) if existing else specs.get("efficiency_pct",0) or 0), key=f"eff_{i}")
                    tc = st.number_input("TC Pmax (%/°C)", 0.0, 1.0, float(abs(existing.get("temp_coeff_pmax", specs.get("temp_coeff_pmax",0) or 0) if existing else specs.get("temp_coeff_pmax",0) or 0)), key=f"tc_{i}")
                    deg_y1 = st.number_input("Y1 Degr. (%)", 0.0, 5.0, float(existing.get("deg_y1_pct", specs.get("deg_y1_pct",0) or 0) if existing else specs.get("deg_y1_pct",0) or 0), key=f"deg_y1_{i}")
                    deg_ann = st.number_input("Ann. Degr. (%)", 0.0, 1.0, float(existing.get("deg_annual_pct", specs.get("deg_annual_pct",0) or 0) if existing else specs.get("deg_annual_pct",0) or 0), key=f"deg_ann_{i}")
                    noct = st.number_input("NOCT (°C)", 0, 60, int(existing.get("noct", specs.get("noct",0) or 0) if existing else specs.get("noct",0) or 0), key=f"noct_{i}")
                    pw = st.number_input("Warranty (yr)", 0, 40, int(existing.get("warranty_power", specs.get("warranty_power",0) or 0) if existing else specs.get("warranty_power",0) or 0), key=f"pw_{i}")

                    specs.update(vmp=vmp, imp=imp, voc=voc, efficiency_pct=eff, temp_coeff_pmax=-tc, deg_y1_pct=deg_y1, deg_annual_pct=deg_ann, noct=noct, warranty_power=pw)
                    st.caption(f"Extracted via {specs.get('_extraction_method','N/A')}")
            else:
                # Show previously uploaded module info if available
                if existing:
                    brand = existing.get("brand", existing.get("_filename", f"Module {i+1}"))
                    wp = existing.get("power_wp", "?")
                    st.markdown(f"""<div style="background:{t['card']};border:1px solid {t['accent']}40;border-radius:6px;padding:0.5rem 0.7rem;margin-top:0.3rem">
                        <span style="font-size:0.75rem;font-weight:600;color:{t['accent']}">{brand}</span>
                        <span style="font-size:0.7rem;color:{t['text']};margin-left:0.4rem">{wp} Wp</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info(f"Upload datasheet")
                specs = existing if existing else None
            module_specs_list.append(specs)

    st.session_state.module_specs_list = module_specs_list
    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# STEP 2 — PRIORITIES
# ======================================================================
elif step == 2:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-eyebrow">03 — DECISION PRIORITIES</div><h2>Weight what matters.</h2><p>Weights directly drive the composite ranking. They are normalised automatically.</p></div>', unsafe_allow_html=True)

    default_w = get_default_weights()
    c1, c2 = st.columns(2)
    with c1:
        w_lcoe = st.slider("LCOE Weight (%)", 0, 100, default_w["lcoe"], 5, key="w_lcoe")
        w_irr = st.slider("IRR Weight (%)", 0, 100, default_w["irr"], 5, key="w_irr")
        w_gen = st.slider("Generation Yield Weight (%)", 0, 100, default_w["generation_yield"], 5, key="w_gen")
        w_deg = st.slider("Degradation Weight (%)", 0, 100, default_w["degradation"], 5, key="w_deg")
    with c2:
        w_warr = st.slider("Warranty Weight (%)", 0, 100, default_w["warranty"], 5, key="w_warr")
        w_price = st.slider("Price Weight (%)", 0, 100, default_w["price"], 5, key="w_price")
        w_tc = st.slider("Temp Coeff Weight (%)", 0, 100, default_w["temp_coeff"], 5, key="w_tc")

    total_w = w_lcoe + w_irr + w_gen + w_deg + w_warr + w_price + w_tc
    st.caption(f"Total allocation: {total_w}% {'✅ Balanced' if total_w == 100 else '⚠️ Please adjust to sum to 100%'}")
    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# STEP 3 — FINANCE
# ======================================================================
elif step == 3:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-eyebrow">04 — ECONOMIC CASE</div><h2>Model the investment.</h2><p>Enter costs, tariff and financing terms.</p></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Weather & site**")
        weather_source = st.radio("Data source", ["NASA POWER API", "PVGIS TMY API", "Simplified Estimate"], index=0, key="s_ws")
        ground_albedo = st.number_input("Ground albedo", 0.0, 0.9, 0.20, 0.05, key="s_albedo")
        mounting_height_m = st.number_input("Mounting height (m)", 0.5, 3.0, 1.0, 0.1, key="s_height")
        st.markdown("**Currency**")
        currency_option = st.selectbox("Reporting currency", currency_options(), index=0, key="s_cur")
    with col2:
        st.markdown("**Revenue & financing**")
        ppa_tariff = st.number_input("PPA tariff (per kWh)", 1.0, 10.0, 4.50, 0.25, key="s_ppa")
        tariff_esc = st.number_input("PPA escalation (% p.a.)", 0.0, 5.0, 0.0, 0.1, key="s_esc") / 100
        debt_ratio = st.slider("Debt ratio", 0.5, 0.9, 0.70, 0.05, key="s_debt")
        interest_rate = st.number_input("Interest rate (% p.a.)", 5.0, 20.0, 9.0, 0.5, key="s_int") / 100
        loan_tenure = st.slider("Loan tenure (years)", 5, 20, 15, key="s_tenure")

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("**Cost assumptions**")
        bos_cost = st.number_input("BoS, EPC & Land (per Wp)", 5.0, 30.0, 12.0, 0.5, key="s_bos")
        discount_rate = st.number_input("Discount rate / WACC (%)", 5.0, 20.0, 10.0, 0.5, key="s_dr") / 100
    with col4:
        st.markdown("**Model defaults**")
        st.caption("25-year operating life · 0.55% annual degradation · 2.0% O&M of base cost")

    cur = get_currency(code_from_option(currency_option))
    F = make_formatter(cur)
    sym = F["symbol"]
    currency_code = code_from_option(currency_option)

    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# STEP 4 — COMPLIANCES (Statutory Approvals)
# ======================================================================
elif step == 4:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-eyebrow">05 — STATUTORY COMPLIANCES</div><h2>Track approvals.</h2><p>Capture status and timelines for all statutory clearances required for a ground-mount solar plant.</p></div>', unsafe_allow_html=True)

    STATUTORY_APPROVALS = [
        ("Environmental Clearance (EC)", "MoEFCC / SEIAA", 90),
        ("Grid Connectivity Approval", "STU / SLDC", 60),
        ("Land Conversion / Use Permission", "District Collector / Revenue Dept", 45),
        ("Forest Clearance (if applicable)", "MoEFCC / State Forest Dept", 120),
        ("Water Availability / NOC", "State Water Board / Irrigation Dept", 30),
        ("Fire Safety NOC", "State Fire Service", 21),
        ("Pollution Control Board Consent", "SPCB", 45),
        ("Labour License / Building Plan", "Local Authority / Labour Dept", 30),
        ("Aviation Clearance (if near airport)", "DGCA / AAI", 60),
        ("Heritage / Archaeological NOC", "ASI / State Archaeology", 45),
        ("Coastal Regulation Zone (CRZ) Clearance", "CRZ Authority / MoEFCC", 90),
        ("Transmission Line Crossing Clearance", "PTCL / STU", 45),
        ("Subscription Agreement (if open access)", "DISCOM / SLDC", 60),
        ("PPA Approval (if applicable)", "ERC / SLDC", 90),
        ("Investment Approval / DPR Sanction", "Sponsor / Lender", 45),
        ("Construction Permit", "Local Authority / PWD", 30),
        ("Electrical Inspector Approval", "Electrical Inspector", 21),
        ("Chief Inspector of Factories NOC", "Factory Inspector", 21),
    ]

    # Load saved compliances
    saved_compliances = st.session_state.get("compliances", {})

    comp_data = []
    for idx, (approval, authority, default_days) in enumerate(STATUTORY_APPROVALS):
        saved = saved_compliances.get(idx, {})
        comp_data.append({
            "approval": approval,
            "authority": authority,
            "default_days": default_days,
            "actual_days": saved.get("actual_days", default_days),
            "status": saved.get("status", "Not Started"),
        })

    # Display as editable table
    comp_headers = ["Statutory Approval", "Issuing Authority", "Approx. Days", "Expected Days", "Status"]
    col_widths = [3.0, 2.0, 1.0, 1.0, 1.2]

    # Use columns for header
    h1, h2, h3, h4, h5 = st.columns(col_widths)
    with h1: st.markdown(f"**{comp_headers[0]}**")
    with h2: st.markdown(f"**{comp_headers[1]}**")
    with h3: st.markdown(f"**{comp_headers[2]}**")
    with h4: st.markdown(f"**{comp_headers[3]}**")
    with h5: st.markdown(f"**{comp_headers[4]}**")

    st.markdown(f"<hr style='border:1px solid {t['border']};margin:0.3rem 0'>", unsafe_allow_html=True)

    new_compliances = {}
    for idx, item in enumerate(comp_data):
        c1, c2, c3, c4, c5 = st.columns(col_widths)
        with c1:
            st.markdown(f"<span style='font-size:0.75rem;color:{t['text']}'>{item['approval']}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<span style='font-size:0.7rem;color:{t['muted']}'>{item['authority']}</span>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<span style='font-size:0.75rem;color:{t['text']}'>{item['default_days']} days</span>", unsafe_allow_html=True)
        with c4:
            actual = st.number_input("Days", 0, 365, int(item['actual_days']), 5, key=f"comp_days_{idx}", label_visibility="collapsed")
        with c5:
            status = st.selectbox("Status", ["Not Started", "Under Progress", "Completed"],
                                  index=["Not Started", "Under Progress", "Completed"].index(item['status']),
                                  key=f"comp_status_{idx}", label_visibility="collapsed")
        new_compliances[idx] = {"actual_days": actual, "status": status}

    st.session_state.compliances = new_compliances

    # Summary
    total = len(comp_data)
    completed = sum(1 for v in new_compliances.values() if v["status"] == "Completed")
    in_progress = sum(1 for v in new_compliances.values() if v["status"] == "Under Progress")
    pending = total - completed - in_progress

    st.markdown(f"""<div style="display:flex;gap:1rem;padding:0.8rem 0;font-size:0.75rem">
        <span style="color:{t['success']}">&#9679; Completed: {completed}/{total}</span>
        <span style="color:{t['accent']}">&#9679; In Progress: {in_progress}/{total}</span>
        <span style="color:{t['dim']}">&#9679; Not Started: {pending}/{total}</span>
    </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# STEP 5 — REPORT (Run analysis & show results)
# ======================================================================
elif step == 5:
    st.markdown('<div class="step-panel">', unsafe_allow_html=True)

    # read all inputs from session state fallbacks
    customer_name = st.session_state.get("s_customer", "Raghavan")
    customer_company = st.session_state.get("s_company", "Raghavan Group")
    project_name = st.session_state.get("s_project", "19.6 MW Solar Plant - Pudukottai")
    location = st.session_state.get("s_location", "Pudukottai, Tamilnadu, India")
    mounting_type = st.session_state.get("s_mounting", "Fixed Tilt")
    plant_capacity = st.session_state.get("s_cap", 19.6)
    latitude = st.session_state.get("s_lat", 10.38)
    longitude = st.session_state.get("s_lon", 78.82)
    tilt_angle = st.session_state.get("s_tilt", 10)
    if mounting_type == "Dual Axis Tracker":
        tilt_angle = None
    n_modules = st.session_state.get("n_mod", 2)
    module_specs_list = st.session_state.get("module_specs_list", [])
    weather_source = st.session_state.get("s_ws", "NASA POWER API")
    ground_albedo = st.session_state.get("s_albedo", 0.20)
    mounting_height_m = st.session_state.get("s_height", 1.0)
    currency_option = st.session_state.get("s_cur", "INR - Indian Rupee (₹)")
    ppa_tariff = st.session_state.get("s_ppa", 4.50)
    tariff_esc = st.session_state.get("s_esc", 0.0) / 100
    debt_ratio = st.session_state.get("s_debt", 0.70)
    interest_rate = st.session_state.get("s_int", 9.0) / 100
    loan_tenure = st.session_state.get("s_tenure", 15)
    bos_cost = st.session_state.get("s_bos", 12.0)
    discount_rate = st.session_state.get("s_dr", 10.0) / 100
    w_lcoe = st.session_state.get("w_lcoe", 20)
    w_irr = st.session_state.get("w_irr", 20)
    w_gen = st.session_state.get("w_gen", 15)
    w_deg = st.session_state.get("w_deg", 10)
    w_warr = st.session_state.get("w_warr", 10)
    w_price = st.session_state.get("w_price", 15)
    w_tc = st.session_state.get("w_tc", 10)
    cur = get_currency(code_from_option(currency_option))
    F = make_formatter(cur)
    sym = F["symbol"]
    currency_code = code_from_option(currency_option)
    total_w = w_lcoe + w_irr + w_gen + w_deg + w_warr + w_price + w_tc

    # validate
    uploaded_all = all(s is not None for s in module_specs_list) and len(module_specs_list) >= 2
    if not uploaded_all:
        st.warning("Upload datasheets for all modules in Step 2 before generating the report.")
        st.button("← Back to Modules", on_click=lambda: setattr(st.session_state, "step", 1))
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if total_w != 100:
        st.warning(f"Scoring weights sum to {total_w}% (must be 100%). Please adjust in Step 3.")
        st.button("← Back to Priorities", on_click=lambda: setattr(st.session_state, "step", 2))
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # map weather source
    if weather_source == "NASA POWER API":
        ws = "api"
    elif weather_source == "PVGIS TMY API":
        ws = "pvgis"
    else:
        ws = "estimate"

    project_params = {
        "capacity_mw": plant_capacity, "latitude": latitude, "longitude": longitude,
        "ppa_tariff": ppa_tariff, "debt_ratio": debt_ratio, "interest_rate": interest_rate,
        "loan_tenure": loan_tenure, "tax_rate": 0.2517, "discount_rate": discount_rate,
        "om_per_mw": 180000, "om_esc": 0.03, "bos_per_w": bos_cost, "insurance_rate": 0.003,
        "mounting_type": mounting_type, "tilt_angle": tilt_angle, "tariff_esc": tariff_esc,
        "weather_source": ws, "ground_albedo": ground_albedo, "mounting_height_m": mounting_height_m,
        "currency": cur,
    }

    # build mod list
    def _get_mfr_name(specs, idx, fallback="Module"):
        if specs:
            mfr = specs.get("manufacturer", "")
            if mfr:
                return mfr.replace("_"," ").replace("-"," ").strip()[:22]
        fname = st.session_state.get(f"upload_{idx}")
        if fname and hasattr(fname, "name"):
            return os.path.splitext(fname.name)[0].replace("_"," ").strip()[:22]
        return fallback

    mod_list = []
    for i, specs in enumerate(module_specs_list):
        if specs is None:
            continue
        mfr = _get_mfr_name(specs, i)
        mod_list.append({
            "name": mfr, "short": mfr, "capacity_w": specs.get("power_wp") or 600,
            "efficiency_pct": specs.get("efficiency_pct") or 21.0,
            "temp_coeff_pmax": specs.get("temp_coeff_pmax") or -0.35,
            "deg_y1_pct": specs.get("deg_y1_pct") or 2.0,
            "deg_annual_pct": specs.get("deg_annual_pct") or 0.55,
            "price_per_wp": specs.get("price_per_wp") or 20.0,
            "warranty_yrs": specs.get("warranty_power") or 25,
            "technology": specs.get("technology", "Mono PERC"),
            "bifacial": specs.get("bifacial", False),
            "noct": specs.get("noct") or 43,
        })

    # Show Generate/Regenerate button if needed
    if not st.session_state.report_generated or st.session_state.inputs_dirty:
        status_msg = "Regenerate Report" if st.session_state.report_generated else "Ready to Generate Report"
        detail = "Inputs have been modified since last generation." if st.session_state.inputs_dirty else f"{len(mod_list)} modules configured | {plant_capacity} MW DC | {location}"
        st.markdown(f"""<div style="text-align:center;padding:2rem;background:{t['card']};border:1px solid {t['border']};border-radius:10px;margin:1rem 0">
            <div style="font-family:'Playfair Display',serif;font-size:1.2rem;color:{t['heading']};margin-bottom:0.5rem">{status_msg}</div>
            <p style="font-size:0.8rem;color:{t['muted']};margin:0">{detail}</p>
        </div>""", unsafe_allow_html=True)

        btn_label = "Regenerate Investor-Grade Report" if st.session_state.report_generated else "Generate Investor-Grade Report"
        if st.button(btn_label, key="gen_report_btn", type="primary", use_container_width=True):
            st.session_state.inputs_dirty = False
            st.session_state.report_generated = True
            st.rerun()

        # If we have old results, show them below the button
        if st.session_state.report_generated and st.session_state.results is not None:
            st.info("Showing previous results below. Click regenerate to update.")
            results = st.session_state.results
            chart_paths = st.session_state.chart_paths
            scored = (st.session_state.project_info or {}).get("scored", [])
            mod_names = list(results.keys())
            weather_data = st.session_state.get("weather_data")
        else:
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

    # ---- We have fresh or existing results to display ----
    _show_cached = False
    if st.session_state.report_generated and st.session_state.results is not None and not st.session_state.inputs_dirty:
        results = st.session_state.results
        chart_paths = st.session_state.chart_paths
        scored = (st.session_state.project_info or {}).get("scored", [])
        mod_names = list(results.keys())
        weather_data = st.session_state.get("weather_data")
        if st.button("← Back to Editing", key="back_edit_btn", type="secondary", on_click=_go_back, use_container_width=False):
            pass
        _show_cached = True
    elif st.session_state.inputs_dirty:
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if not _show_cached:
        # ---- RUN FRESH ANALYSIS ----
        # Check internet connectivity before weather API calls
        _offline_mode = False
        if ws in ("api", "pvgis") and not _check_internet():
            st.error("🔌 No Internet Connection")
            st.markdown("""
            **Unable to connect to weather data source.**
            
            The selected weather source (**NASA POWER API** or **PVGIS TMY API**) requires an active internet connection.
            
            **Please check:**
            - Your Wi-Fi or Ethernet connection is active
            - No firewall is blocking external API requests
            - The network has internet access
            
            ---
            *Click below to continue with estimated weather data based on your site's latitude.*
            """)
            if st.button("✅ Continue Without Internet", key="offline_btn", type="primary"):
                _offline_mode = True
            else:
                st.stop()
        
        with st.spinner("Running comprehensive analysis..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                if _offline_mode:
                    weather_data = None
                elif ws == "api":
                    weather_data = cached_nasa(latitude, longitude)
                elif ws == "pvgis":
                    weather_data = cached_pvgis(latitude, longitude)
                else:
                    weather_data = None
                results, chart_paths = run_analysis(mod_list, project_params, tmpdir, weather_data=weather_data)

                _raw_w = {"lcoe":w_lcoe, "irr":w_irr, "generation_yield":w_gen, "degradation":w_deg,
                          "warranty":w_warr, "price":w_price, "temp_coeff":w_tc}
                _wsum = sum(_raw_w.values()) or 1
                weights = {k: round(v/_wsum*100) for k,v in _raw_w.items()}
                scored = compute_scores(results, mod_list, weights)
                mod_names = [m["short"] for m in mod_list]

                # store in session
                st.session_state.results = results
                st.session_state.chart_paths = chart_paths
                st.session_state.project_info = {
                    "project_name": project_name, "customer_name": customer_name,
                    "customer_company": customer_company, "plant_capacity": f"{plant_capacity:.1f}",
                    "location": location, "latitude": str(latitude), "longitude": str(longitude),
                    "date": datetime.now().strftime("%B %Y"), "mounting_type": mounting_type,
                    "tilt_angle": tilt_angle, "scored": scored, "currency": cur,
                    "weather_summary": get_weather_summary(weather_data), "weather_source": weather_source,
                    "ground_albedo": ground_albedo, "mounting_height_m": mounting_height_m,
                    "bifacial_detected": any(s.get("bifacial",False) for s in module_specs_list if s),
                }
                st.session_state.mod_list = mod_list
                st.session_state.weather_data = weather_data
                st.session_state.project_params = project_params

                # Copy charts to persistent location before tmpdir closes
                _charts_dir = os.path.join(PROJECT_DIR, ".chart_cache")
                os.makedirs(_charts_dir, exist_ok=True)
                _persistent_paths = {}
                for cname, cpath in chart_paths.items():
                    if os.path.exists(cpath):
                        _dest = os.path.join(_charts_dir, cname)
                        import shutil; shutil.copy2(cpath, _dest)
                        _persistent_paths[cname] = _dest
                chart_paths = _persistent_paths
                st.session_state.chart_paths = chart_paths

    # ---- RESULTS DISPLAY ----
    st.success("Analysis complete")

    # metrics row
    metric_cols = st.columns(len(mod_names))
    for i, name in enumerate(mod_names):
        r = results[name]
        with metric_cols[i]:
            st.metric(f"{name} — IRR", f"{r['irr']*100:.2f}%")
            st.metric(f"{name} — Project Cost", F["money"](r["total_cost"]))
    best = scored[0]["short"] if scored else mod_names[0]
    st.markdown(f"<div style='text-align:center;padding:0.5rem 0;font-size:0.85rem;color:{t['accent']};font-weight:600'>&#10022; Recommended: {best} (Score: {scored[0]['weighted_total']:.1f}/100)</div>", unsafe_allow_html=True)

    # charts
    st.markdown("### Charts")
    ch_cols = st.columns(2)
    ch_names = list(chart_paths.keys())
    for i, cn in enumerate(ch_names):
        with ch_cols[i % 2]:
            if os.path.exists(chart_paths[cn]):
                st.image(chart_paths[cn], caption=cn.replace(".png","").replace("_"," ").title(), width="stretch")

    # scoring table
    st.markdown("### Multi-Criteria Scoring")
    score_headers, score_rows = format_scoring_table(scored)
    score_df = [dict(zip(score_headers, row)) for row in score_rows]
    st.table(score_df)

    # scenario
    with st.expander("Scenario & Sensitivity", expanded=False):
        sc_c1, sc_c2 = st.columns(2)
        with sc_c1:
            scenario_mounting = st.selectbox("Alternate mounting", ["None", "Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"], index=0, key="sc_mount")
        with sc_c2:
            force_bif = st.checkbox("Force bifacial for all modules", key="sc_bif")
        sens_range = st.slider("Sensitivity range (+/- %)", 5, 30, 10, 1, key="sc_range")

        if scenario_mounting != "None" or force_bif:
            sc_p = dict(project_params)
            if scenario_mounting != "None":
                sc_p["mounting_type"] = scenario_mounting
                if scenario_mounting != "Fixed Tilt":
                    sc_p["tilt_angle"] = None
            sc_ml = [dict(m, bifacial=True) for m in mod_list] if force_bif else mod_list
            with tempfile.TemporaryDirectory() as sc_d:
                sc_r, _ = run_analysis(sc_ml, sc_p, sc_d, weather_data=weather_data, skip_charts=True)
            scc = st.columns(len(mod_names))
            for i, name in enumerate(mod_names):
                base = results[name]
                sc = sc_r[name]
                with scc[i]:
                    st.metric(f"{name} IRR", f"{sc['irr']*100:.2f}%", f"{(sc['irr']-base['irr'])*100:+.2f}%")
                    st.metric(f"{name} NPV", F["money"](sc["npv"]), f"{F['money'](sc['npv']-base['npv'])}")
                    st.metric(f"{name} LCOE", f"{sc['lcoe']:.3f}", f"{sc['lcoe']-base['lcoe']:+.3f}")

        # tornado
        best_name = scored[0]["short"] if scored else mod_names[0]
        base_irr = results[best_name]["irr"]*100
        def _fn_tariff(p,m,s): p2=dict(p); p2["ppa_tariff"]=p["ppa_tariff"]*(1+s/100); return p2,m
        def _fn_price(p,m,s): m2=[dict(x,price_per_wp=x["price_per_wp"]*(1+s/100)) for x in m]; return p,m2
        def _fn_int(p,m,s): p2=dict(p); p2["interest_rate"]=p["interest_rate"]*(1+s/100); return p2,m
        def _fn_debt(p,m,s): p2=dict(p); p2["debt_ratio"]=min(.95,max(.4,p["debt_ratio"]*(1+s/100))); return p2,m
        def _fn_deg(p,m,s): m2=[dict(x,deg_annual_pct=min(2.0,x["deg_annual_pct"]*(1+s/100))) for x in m]; return p,m2
        def _fn_eff(p,m,s): m2=[dict(x,efficiency_pct=x["efficiency_pct"]*(1+s/100)) for x in m]; return p,m2
        def _fn_bos(p,m,s): p2=dict(p); p2["bos_per_w"]=p["bos_per_w"]*(1+s/100); return p2,m

        drivers = [("PPA Tariff",_fn_tariff),("Module Price",_fn_price),("Interest Rate",_fn_int),
                   ("Debt Ratio",_fn_debt),("Degradation",_fn_deg),("Efficiency",_fn_eff),("BoS Cost",_fn_bos)]
        lows, highs, labels = [], [], []
        for lab, fn in drivers:
            p_lo, m_lo = fn(project_params, mod_list, -sens_range)
            p_hi, m_hi = fn(project_params, mod_list, +sens_range)
            with tempfile.TemporaryDirectory() as d:
                r_lo, _ = run_analysis(m_lo, p_lo, d, weather_data=weather_data, skip_charts=True)
                r_hi, _ = run_analysis(m_hi, p_hi, d, weather_data=weather_data, skip_charts=True)
            lows.append(r_lo[best_name]["irr"]*100 - base_irr)
            highs.append(r_hi[best_name]["irr"]*100 - base_irr)
            labels.append(lab)

        import plotly.graph_objects as go
        fig = go.Figure()
        for i, lab in enumerate(labels):
            fig.add_trace(go.Scatter(x=[lows[i],highs[i]], y=[i,i], mode="lines+markers",
                line=dict(color="gray",width=1.5), marker=dict(size=8,color=["#e74c3c","#27ae60"]), showlegend=False))
        fig.add_vline(x=0, line=dict(color="white",width=1))
        fig.update_layout(
            title=f"IRR Sensitivity — {best_name}",
            xaxis=dict(title=f"IRR change vs base (%-pts) | base {base_irr:.1f}%", gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(tickmode="array", tickvals=list(range(len(labels))), ticktext=labels),
            template="none", height=350,
            paper_bgcolor=t['bg'], plot_bgcolor=t['bg'],
            font=dict(color=t['muted'], size=10),
            margin=dict(l=10,r=10,t=40,b=40),
        )
        st.plotly_chart(fig, width="stretch")

    # CSV export
    import csv as _csv
    _buf = io.StringIO()
    _cw = _csv.writer(_buf)
    _cw.writerow(["Module","IRR_%","NPV","Total_Cost","LCOE","Gen_Y1_kWh","CUF_%","Payback_yrs","Module_Count"])
    for n in mod_names:
        r = results[n]
        _cw.writerow([n, round(r["irr"]*100,2), round(r["npv"],2), round(r["total_cost"],2), round(r["lcoe"],4),
                      round(r["gen_y1_kwh"],0), round(r["cuf"]*100,2), r["payback"], r["module_count"]])
    st.download_button("Export CSV", data=_buf.getvalue(), file_name="comparison_results.csv", mime="text/csv")

    # PDF report
    spec_rows = []
    for i, specs in enumerate(module_specs_list):
        if specs is None: continue
        mfr = _get_mfr_name(specs, i)
        spec_rows.append([f"Module {i+1} Model", f"{specs.get('power_wp','')}Wp", ""])
        spec_rows.append([f"Module {i+1} Technology", specs.get("technology",""), ""])
        spec_rows.append([f"Module {i+1} Manufacturer", mfr, ""])
        r_mod = results.get(mfr,{})
        spec_rows.append([f"Module {i+1} Count", f'{r_mod.get("module_count",0):,}', "nos"])
    mod_info = [{"short":_get_mfr_name(module_specs_list[i], i),
                 "name":f"{_get_mfr_name(module_specs_list[i], i)} ({module_specs_list[i].get('power_wp','')}Wp)",
                 "brand":_get_mfr_name(module_specs_list[i], i), "wp":module_specs_list[i].get("power_wp",600)}
                for i in range(len(module_specs_list)) if module_specs_list[i]]

    plist = [f"Location: {location} ({latitude}, {longitude})",
             f"Plant Capacity: {plant_capacity:.1f} MW DC",
             f"Configuration: {mounting_type}{' (Tilt: '+str(tilt_angle)+'°)' if tilt_angle else ''}",
             f"PPA Tariff: {sym} {ppa_tariff:.2f}/kWh",
             f"Debt:Equity: {int(debt_ratio*100)}:{int((1-debt_ratio)*100)}",
             f"Interest: {interest_rate*100:.0f}% p.a., {loan_tenure}-yr",
             f"BoS & EPC: {sym} {bos_cost:.1f}/Wp",
             f"Weather: {get_weather_summary(weather_data)}"]

    p_info = dict(st.session_state.project_info)
    p_info.update(spec_rows=spec_rows, project_params=plist, mod_info=mod_info)
    p_info["score_headers"], p_info["score_rows"] = score_headers, score_rows
    p_info["compliances"] = st.session_state.get("compliances", {})

    with tempfile.TemporaryDirectory() as report_dir:
        # Copy charts into report_dir so report_generator can find them
        _charts_dir = os.path.join(PROJECT_DIR, ".chart_cache")
        if os.path.isdir(_charts_dir):
            import shutil
            for f in os.listdir(_charts_dir):
                if f.endswith(".png"):
                    shutil.copy2(os.path.join(_charts_dir, f), os.path.join(report_dir, f))

        report_path = os.path.join(report_dir, "investment_report.pdf")
        gen_report(results, p_info, report_dir, report_path)

        name_parts = []
        for i in range(len(module_specs_list)):
            mfr = _get_mfr_name(module_specs_list[i], i)
            name_parts.append(mfr.replace("/","_").replace("\\","_").split()[0])
        report_fn = f"SolarPro_Report_{'_vs_'.join(name_parts)}.pdf"

        with open(report_path, "rb") as f:
            st.download_button("Download Investment-Grade PDF Report", data=f.read(),
                               file_name=report_fn, mime="application/pdf", type="primary")

    st.markdown("</div>", unsafe_allow_html=True)

# ======================================================================
# WIZARD NAVIGATION — Previous | Next (runs after all step content)
# ======================================================================
nav_c1, nav_mid, nav_c2 = st.columns([1, 2, 1])
with nav_c1:
    if step > 0:
        st.button("← Previous", key="prev_btn", type="secondary", on_click=_go_back, use_container_width=True)
with nav_c2:
    if step < 5:
        st.button("Next →", key="next_btn", on_click=_go_forward, use_container_width=True)

# Footer with theme switcher
footer_html = f"""<div style="text-align:center;padding:1.2rem;font-size:0.6rem;color:{t['dim']};font-family:DM Mono,monospace;border-top:1px solid {t['border']}">
SOLAR<span style="color:{t['link']}">PRO</span> · PV Module Financial Intelligence
<br><a href="#" onclick="window.parent.document.querySelector('[data-testid=stSidebar]').click();return false;" style="color:{t['accent']};font-size:0.55rem;text-decoration:underline;cursor:pointer">Change Theme</a>
</div>"""
st.markdown(footer_html, unsafe_allow_html=True)
