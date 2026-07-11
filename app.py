"""
Streamlit App - N-Module Solar PV Comparison & Investment Report Generator
Upload 2-5 datasheets, enter financials, generate comparison PDF report.
"""
import streamlit as st
import os, io, json, tempfile, sys, re, hashlib
from datetime import datetime
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from pdf_parser import extract_module_specs, format_specs_for_display, extract_text_from_pdf, parse_specs
from financial_engine import run_analysis
from report_generator import generate_report as gen_report
from scoring import compute_scores, get_default_weights, format_scoring_table
from weather_data import fetch_nasa_power_monthly, compute_annual_solar_metrics, get_weather_summary
from currency import currency_options, code_from_option, get_currency, make_formatter

st.set_page_config(page_title="Solar Module Comparison", page_icon="☀️", layout="wide")
st.title("☀️ Solar Module Investment Comparison Engine")
st.markdown("Upload datasheets for 2-5 solar modules. The system automatically extracts specifications.")

# ----- CACHED HELPERS -----
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

# ===== SIDEBAR =====
with st.sidebar:
    st.header("🏢 Customer & Project")
    customer_name = st.text_input("Customer Name", "Raghavan")
    customer_company = st.text_input("Company", "Raghavan Group")
    project_name = st.text_input("Project Name", "19.6 MW Solar Plant - Pudukottai")
    plant_capacity = st.number_input("Plant Capacity (MW DC)", 0.1, 500.0, 19.6, 0.1)
    location = st.text_input("Location", "Pudukottai, Tamilnadu, India")
    col_lat, col_lon = st.columns(2)
    with col_lat:
        latitude = st.number_input("Latitude", -90.0, 90.0, 10.38, 0.01, format="%.2f")
    with col_lon:
        longitude = st.number_input("Longitude", -180.0, 180.0, 78.82, 0.01, format="%.2f")

    st.markdown("---")
    st.header("💱 Reporting Currency")
    currency_option = st.selectbox(
        "Select Currency", currency_options(), index=0,
        help="All monetary values in the app and PDF report are converted to this currency.",
    )
    cur = get_currency(code_from_option(currency_option))
    F = make_formatter(cur)
    sym = F["symbol"]
    currency_code = code_from_option(currency_option)

    st.markdown("---")
    st.header("🌤️ Weather Data")
    weather_source = st.radio(
        "Data Source",
        ["NASA POWER API (Recommended)", "Simplified Estimate"],
        index=0,
        help="NASA POWER provides real satellite-derived solar & weather data",
    )
    ground_albedo = st.number_input(
        "Ground Albedo", 0.0, 0.9, 0.20, 0.05,
        help="Surface reflectivity (0.2 = grass, 0.6 = sand, 0.8 = snow). Used for bifacial gain.",
    )
    mounting_height_m = st.number_input(
        "Mounting Height (m)", 0.5, 3.0, 1.0, 0.1,
        help="Height of modules above ground. Affects bifacial rear irradiance view factor.",
    )

    st.markdown("---")
    st.header("💰 Financial Parameters")
    ppa_tariff = st.number_input(f"PPA Tariff ({sym}/kWh)", 1.0, 10.0, 4.50, 0.25)
    tariff_esc = st.number_input(
        "PPA Tariff Escalation (% p.a.)", 0.0, 5.0, 0.0, 0.1,
        help="Annual escalation applied to the PPA tariff over the plant life.",
    ) / 100
    debt_ratio = st.slider("Debt Ratio", 0.5, 0.9, 0.70, 0.05)
    interest_rate = st.number_input("Interest Rate (% p.a.)", 5.0, 20.0, 9.0, 0.5) / 100
    loan_tenure = st.slider("Loan Tenure (years)", 5, 20, 15)
    discount_rate = st.number_input("Discount Rate / WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
    bos_cost = st.number_input(f"BoS, EPC & Land ({sym}/Wp)", 5.0, 30.0, 12.0, 0.5)

    st.markdown("---")
    st.header("🏗️ Mounting Structure")
    mounting_type = st.radio(
        "Select Mounting Type",
        ["Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"],
        index=0,
    )
    tilt_angle = None
    if mounting_type == "Fixed Tilt":
        tilt_angle = st.number_input("Tilt Angle (degrees)", 0, 60, 10, 1)

    st.markdown("---")
    st.header("⚖️ Scoring Weights")
    with st.expander("Adjust Scoring Weights", expanded=False):
        default_w = get_default_weights()
        w_lcoe = st.slider("LCOE Weight (%)", 0, 100, default_w["lcoe"], 5)
        w_irr = st.slider("IRR Weight (%)", 0, 100, default_w["irr"], 5)
        w_gen = st.slider("Generation Yield Weight (%)", 0, 100, default_w["generation_yield"], 5)
        w_deg = st.slider("Degradation Weight (%)", 0, 100, default_w["degradation"], 5)
        w_warr = st.slider("Warranty Weight (%)", 0, 100, default_w["warranty"], 5)
        w_price = st.slider("Price Weight (%)", 0, 100, default_w["price"], 5)
        w_tc = st.slider("Temp Coeff Weight (%)", 0, 100, default_w["temp_coeff"], 5)
        total_w = w_lcoe + w_irr + w_gen + w_deg + w_warr + w_price + w_tc
        st.caption(f"Total: {total_w}% {'✅' if total_w == 100 else '⚠️ Must sum to 100%'}")
        weights_valid = (total_w == 100)
        if not weights_valid:
            st.warning("Weights must sum to exactly 100%")

    st.markdown("---")
    st.header("💾 Load Configuration")
    _cfg_file = st.file_uploader("Load saved config (JSON)", type=["json"], key="cfg_upload")
    if _cfg_file is not None:
        try:
            st.session_state["cfg"] = json.loads(_cfg_file.read())
            st.success("Config loaded — applied to the analysis below.")
        except Exception as e:
            st.error(f"Invalid config: {e}")
    if st.session_state.get("cfg") and st.button("Clear loaded config"):
        st.session_state.pop("cfg", None)
        st.rerun()

    st.markdown("---")
    n_modules = st.number_input("Modules to Compare", 2, 5, 2, 1,
                                 help="Number of modules to compare (2-5)")

# ===== MAIN: Module Upload & Parse =====
DEFAULT_TECHS = ["Mono PERC", "N-TOPCon", "HJT", "Mono PERC", "Poly PERC"]

def render_module_ui(idx):
    """Render file uploader and spec editor for one module. Returns specs dict or None."""
    label = f"Module {idx + 1}"
    default_tech = DEFAULT_TECHS[idx] if idx < len(DEFAULT_TECHS) else "Mono PERC"

    with st.expander(f"📄 {label}", expanded=True):
        uploaded = st.file_uploader(
            f"Upload {label} Datasheet (PDF)", type=["pdf"],
            key=f"upload_{idx}",
        )
        if uploaded is None:
            st.info(f"Upload {label} datasheet PDF to begin")
            return None

        pdf_bytes = uploaded.read()

        specs = cached_parse(pdf_bytes, default_tech)
        st.success(f"Extracted via {specs.get('_extraction_method', 'N/A')}")

        if specs.get("power_options"):
            opts = specs["power_options"]
            mid_idx = len(opts) // 2
            default_idx = min(mid_idx + 1, len(opts) - 1)
            selected_wp = st.selectbox(
                f"{label} - Select Module Wattage (Wp)",
                options=opts, index=default_idx,
                key=f"wp_{idx}",
            )
            specs = cached_parse_wp(pdf_bytes, default_tech, int(selected_wp))
            specs["power_wp"] = int(selected_wp)
        else:
            st.warning("Could not detect power ratings. Enter manually below.")
            selected_wp = st.number_input(f"{label} - Module Power (Wp)", 300, 800, 600, 5, key=f"wp_manual_{idx}")
            specs["power_wp"] = int(selected_wp)
            specs["power_options"] = [int(selected_wp)]

        default_price = 20 if "redren" in (uploaded.name or "").lower() else 22
        price = st.number_input(
            f"{label} - Price ({sym}/Wp)", 5.0, 50.0, float(default_price), 0.5,
            key=f"price_{idx}",
        )
        specs["price_per_wp"] = price
        specs["_filename"] = uploaded.name

        with st.expander(f"🔍 {label} - Extracted Specifications", expanded=False):
            st.text(format_specs_for_display(specs))

        st.caption("Edit any incorrectly extracted values below:")
        col_a, col_b = st.columns(2)
        with col_a:
            vmp = st.number_input("Vmp (V)", 0.0, 100.0, float(specs.get("vmp", 0) or 0), key=f"vmp_{idx}")
            imp = st.number_input("Imp (A)", 0.0, 30.0, float(specs.get("imp", 0) or 0), key=f"imp_{idx}")
            voc = st.number_input("Voc (V)", 0.0, 100.0, float(specs.get("voc", 0) or 0), key=f"voc_{idx}")
            isc = st.number_input("Isc (A)", 0.0, 30.0, float(specs.get("isc", 0) or 0), key=f"isc_{idx}")
            eff = st.number_input("Efficiency (%)", 0.0, 30.0, float(specs.get("efficiency_pct", 0) or 0), key=f"eff_{idx}")
        with col_b:
            tc = st.number_input("Temp Coeff Pmax (%/°C)", 0.0, 1.0, float(abs(specs.get("temp_coeff_pmax", 0) or 0)), key=f"tc_{idx}")
            deg_y1 = st.number_input("Y1 Degradation (%)", 0.0, 5.0, float(specs.get("deg_y1_pct", 0) or 0), key=f"deg_y1_{idx}")
            deg_ann = st.number_input("Annual Degradation (%)", 0.0, 1.0, float(specs.get("deg_annual_pct", 0) or 0), key=f"deg_ann_{idx}")
            pw = st.number_input("Power Warranty (years)", 0, 40, int(specs.get("warranty_power", 0) or 0), key=f"pw_{idx}")
            noct = st.number_input("NOCT (°C)", 0, 60, int(specs.get("noct", 0) or 0), key=f"noct_{idx}")

        specs.update(
            vmp=vmp,
            imp=imp,
            voc=voc,
            isc=isc,
            efficiency_pct=eff,
            temp_coeff_pmax=-tc,
            deg_y1_pct=deg_y1,
            deg_annual_pct=deg_ann,
            warranty_power=pw,
            noct=noct,
        )

        return specs

# Render module UI for each module (supports batch + manual entry)
st.markdown("---")
st.header("📄 Module Datasheets")
batch_files = st.file_uploader(
    "📥 Batch upload multiple datasheets (optional)",
    type=["pdf"], accept_multiple_files=True, key="batch_upload",
    help="Upload several PDFs at once to auto-compare them. Overrides the manual section below.",
)

if batch_files:
    module_specs_list = []
    for bi, bf in enumerate(batch_files):
        pdf_bytes = bf.read()
        default_tech = DEFAULT_TECHS[bi] if bi < len(DEFAULT_TECHS) else "Mono PERC"
        specs = cached_parse(pdf_bytes, default_tech)
        if specs.get("power_options"):
            selected_wp = max(specs["power_options"])
        else:
            selected_wp = specs.get("power_wp") or 600
        specs = cached_parse_wp(pdf_bytes, default_tech, int(selected_wp))
        specs["power_wp"] = int(selected_wp)
        default_price = 20 if "redren" in (bf.name or "").lower() else 22
        specs["price_per_wp"] = default_price
        specs["_filename"] = bf.name
        st.success(f"Module {bi + 1} ({bf.name}): extracted via {specs.get('_extraction_method', 'N/A')} "
                   f"@ {specs['power_wp']}Wp, {specs.get('technology', 'N/A')}")
        module_specs_list.append(specs)
    st.info("Batch mode active. Use the manual section below for single-module fine-tuning "
            "or clear the batch uploader to switch back.")
else:
    module_specs_list = []
    for i in range(n_modules):
        specs = render_module_ui(i)
        module_specs_list.append(specs)

# ----- Apply loaded configuration overrides -----
_cfg = st.session_state.get("cfg")
if _cfg:
    plant_capacity = _cfg.get("plant_capacity", plant_capacity)
    latitude = _cfg.get("latitude", latitude)
    longitude = _cfg.get("longitude", longitude)
    ppa_tariff = _cfg.get("ppa_tariff", ppa_tariff)
    tariff_esc = _cfg.get("tariff_esc", tariff_esc)
    debt_ratio = _cfg.get("debt_ratio", debt_ratio)
    interest_rate = _cfg.get("interest_rate", interest_rate)
    loan_tenure = _cfg.get("loan_tenure", loan_tenure)
    discount_rate = _cfg.get("discount_rate", discount_rate)
    bos_cost = _cfg.get("bos_cost", bos_cost)
    ground_albedo = _cfg.get("ground_albedo", ground_albedo)
    mounting_height_m = _cfg.get("mounting_height_m", mounting_height_m)
    mounting_type = _cfg.get("mounting_type", mounting_type)
    tilt_angle = _cfg.get("tilt_angle", tilt_angle)
    w_lcoe = _cfg.get("w_lcoe", w_lcoe)
    w_irr = _cfg.get("w_irr", w_irr)
    w_gen = _cfg.get("w_gen", w_gen)
    w_deg = _cfg.get("w_deg", w_deg)
    w_warr = _cfg.get("w_warr", w_warr)
    w_price = _cfg.get("w_price", w_price)
    w_tc = _cfg.get("w_tc", w_tc)
    _cfg_cur = get_currency(_cfg.get("currency_code", currency_code))
    # Keep original cur (with "code" key); just update formatter and code
    F = make_formatter(_cfg_cur)
    sym = F["symbol"]
    currency_code = _cfg.get("currency_code", currency_code)
    for _i, _cm in enumerate(_cfg.get("modules", [])):
        if _i < len(module_specs_list) and module_specs_list[_i] is not None:
            module_specs_list[_i]["price_per_wp"] = _cm.get(
                "price_per_wp", module_specs_list[_i].get("price_per_wp"))
            module_specs_list[_i]["bifacial"] = _cm.get(
                "bifacial", module_specs_list[_i].get("bifacial", False))

def _get_mfr_name(specs, idx, fallback="Module"):
    if specs:
        mfr = specs.get("manufacturer", "")
        if mfr:
            return _clean_name(mfr)
    uploaded_widget = st.session_state.get(f"upload_{idx}")
    if uploaded_widget and hasattr(uploaded_widget, "name"):
        mfr = os.path.splitext(uploaded_widget.name)[0]
        if mfr:
            return _clean_name(mfr)
    return fallback

def _clean_name(name, max_len=22):
    """Clean module name for display: replace separators, truncate."""
    name = name.replace("_", " ").replace("-", " ").replace("  ", " ")
    if len(name) > max_len:
        name = name[:max_len].rsplit(" ", 1)[0] if " " in name[:max_len] else name[:max_len]
    return name.strip()

# ===== GENERATE REPORT =====
st.markdown("---")
uploaded_all = all(s is not None for s in module_specs_list)

if uploaded_all:
    if weather_source == "NASA POWER API (Recommended)":
        ws = "api"
    else:
        ws = "estimate"

    project_params = {
        "capacity_mw": plant_capacity,
        "latitude": latitude,
        "longitude": longitude,
        "ppa_tariff": ppa_tariff,
        "debt_ratio": debt_ratio,
        "interest_rate": interest_rate,
        "loan_tenure": loan_tenure,
        "tax_rate": 0.2517,
        "discount_rate": discount_rate,
        "om_per_mw": 180000,
        "om_esc": 0.03,
        "bos_per_w": bos_cost,
        "insurance_rate": 0.003,
        "mounting_type": mounting_type,
        "tilt_angle": tilt_angle,
        "tariff_esc": tariff_esc,
        "weather_source": ws,
        "ground_albedo": ground_albedo,
        "mounting_height_m": mounting_height_m,
        "currency": cur,
    }

    # Build module list for financial engine
    mod_list = []
    for i, specs in enumerate(module_specs_list):
        if specs is None:
            continue
        mfr = _get_mfr_name(specs, i)
        mod_list.append({
            "name": mfr,
            "short": mfr,
            "capacity_w": specs["power_wp"],
            "efficiency_pct": specs.get("efficiency_pct", 21.0),
            "temp_coeff_pmax": specs.get("temp_coeff_pmax", -0.35),
            "deg_y1_pct": specs.get("deg_y1_pct", 2.0),
            "deg_annual_pct": specs.get("deg_annual_pct", 0.55),
            "price_per_wp": specs["price_per_wp"],
            "warranty_yrs": specs.get("warranty_power", 25),
            "technology": specs.get("technology", "Mono PERC"),
            "bifacial": specs.get("bifacial", False),
            "noct": specs.get("noct", 43),
        })

    with st.spinner("Running comprehensive analysis..."):
        with tempfile.TemporaryDirectory() as tmpdir:
            weather_data = cached_nasa(latitude, longitude) if ws == "api" else None
            results, chart_paths = run_analysis(
                mod_list, project_params, tmpdir, weather_data=weather_data
            )

            # Build scoring (normalise weights so they always sum to 100)
            _raw_weights = {
                "lcoe": w_lcoe, "irr": w_irr,
                "generation_yield": w_gen, "degradation": w_deg,
                "warranty": w_warr, "price": w_price,
                "temp_coeff": w_tc,
            }
            _wsum = sum(_raw_weights.values()) or 1
            weights = {k: round(v / _wsum * 100) for k, v in _raw_weights.items()}
            scored = compute_scores(results, mod_list, weights)

            mod_names = [m["short"] for m in mod_list]

            # Show results
            st.success("✅ Analysis complete!")

            # Metrics row
            metric_cols = st.columns(len(mod_names) + 1)
            for i, name in enumerate(mod_names):
                r = results[name]
                with metric_cols[i]:
                    st.metric(f"{name} - IRR", f"{r['irr']*100:.2f}%")
                    st.metric(f"{name} - Project Cost", F["money"](r['total_cost']))
            with metric_cols[-1]:
                best = scored[0]["short"] if scored else mod_names[0]
                best_irr = results[best]["irr"] * 100
                st.metric("🥇 Recommended", best)
                st.metric("Score", f'{scored[0]["weighted_total"]:.1f}' if scored else "N/A")

            # Scoring table
            st.subheader("🏆 Multi-Criteria Scoring")
            score_headers, score_rows = format_scoring_table(scored)
            score_df_data = [dict(zip(score_headers, row)) for row in score_rows]
            st.table(score_df_data)

            # Chart previews
            st.subheader("Chart Preview")
            ch_cols = st.columns(2)
            ch_names = list(chart_paths.keys())
            for i, cn in enumerate(ch_names):
                with ch_cols[i % 2]:
                    if os.path.exists(chart_paths[cn]):
                        st.image(chart_paths[cn],
                                 caption=cn.replace(".png", "").replace("_", " ").title(),
                                 width="stretch")

            # Build spec_rows for report
            def safe_val(specs, key, default="N/A"):
                v = specs.get(key, default)
                return str(v) if v is not None else str(default)

            spec_rows = []
            for i, specs in enumerate(module_specs_list):
                if specs is None:
                    continue
                mfr = mod_names[i]
                spec_rows.append([
                    f"Module {i+1} Model",
                    safe_val(specs, "power_wp") + "Wp",
                    "",
                ])
                spec_rows.append([
                    f"Module {i+1} Technology",
                    safe_val(specs, "technology"),
                    "",
                ])
                spec_rows.append([
                    f"Module {i+1} Manufacturer",
                    mfr,
                    "",
                ])
                r = results[mfr]
                spec_rows.append([
                    f"Module {i+1} Count",
                    f'{r["module_count"]:,}',
                    "nos",
                ])
                spec_rows.append([
                    f"Module {i+1} Efficiency",
                    f'{specs.get("efficiency_pct", 0):.2f}%',
                    "",
                ])
                spec_rows.append([
                    f"Module {i+1} Vmp",
                    f'{specs.get("vmp", 0):.2f}V',
                    "V",
                ])
                spec_rows.append([
                    f"Module {i+1} Imp",
                    f'{specs.get("imp", 0):.2f}A',
                    "A",
                ])
                spec_rows.append([
                    f"Module {i+1} Voc",
                    f'{specs.get("voc", 0):.2f}V',
                    "V",
                ])
                spec_rows.append([
                    f"Module {i+1} Isc",
                    f'{specs.get("isc", 0):.2f}A',
                    "A",
                ])
                spec_rows.append([
                    f"Module {i+1} Temp Coeff",
                    f'{specs.get("temp_coeff_pmax", 0):.3f}%/C',
                    "%/°C",
                ])
                spec_rows.append([
                    f"Module {i+1} Deg Y1",
                    f'{specs.get("deg_y1_pct", 0):.1f}%',
                    "%",
                ])
                spec_rows.append([
                    f"Module {i+1} Deg Annual",
                    f'{specs.get("deg_annual_pct", 0):.2f}%',
                    "%",
                ])
                spec_rows.append([
                    f"Module {i+1} Warranty",
                    f'{specs.get("warranty_power", 0)}yr',
                    "years",
                ])
                spec_rows.append([
                    f"Module {i+1} Price",
                    f'{sym}{specs["price_per_wp"]:.1f}/Wp',
                    "",
                ])

            # Build project params list
            first_r = results[mod_names[0]]
            project_params_list = [
                f"Location: {location} ({latitude}, {longitude})",
                f"Plant Capacity: {plant_capacity:.1f} MW DC",
                f"Configuration: {mounting_type}{' (Tilt: '+str(tilt_angle)+'°)' if tilt_angle else ''} ground mount",
                f"PPA Tariff: {sym} {ppa_tariff:.2f}/kWh",
                "Plant Life: 25 years",
                f"Debt:Equity: {int(debt_ratio*100)}:{int((1-debt_ratio)*100)}",
                f"Interest Rate: {interest_rate*100:.0f}% p.a., {loan_tenure}-year tenure",
                f"BoS & EPC: {sym} {bos_cost:.1f}/Wp (adjusted for module count)",
                f"Weather: {get_weather_summary(cached_nasa(latitude, longitude) if ws == 'api' else None)}",
            ]
            for i, (m, specs) in enumerate(zip(mod_names, module_specs_list)):
                r_mod = results[m]
                project_params_list.append(
                    f"{m}: {r_mod['module_count']:,} units @ {specs['power_wp']}Wp"
                )

            bifacial_detected = any(s.get("bifacial", False) for s in module_specs_list if s)
            if bifacial_detected:
                project_params_list.append(
                    f"Analysis includes bifacial gains (albedo={ground_albedo}, height={mounting_height_m}m)"
                )
            else:
                project_params_list.append(
                    "Analysis: Frontside-only generation (no bifacial gains detected)"
                )

            # Module info for report
            mod_info = []
            for i, (m, specs) in enumerate(zip(mod_names, module_specs_list)):
                if specs is None:
                    continue
                r_mod = results[m]
                mod_info.append({
                    "short": m,
                    "name": f"{_get_mfr_name(specs, i)} ({safe_val(specs, 'power_wp')}Wp)",
                    "brand": _get_mfr_name(specs, i),
                    "wp": specs["power_wp"],
                    "count": r_mod["module_count"],
                    "dims": (
                        specs.get("length_mm") or specs.get("length"),
                        specs.get("width_mm") or specs.get("width"),
                    ),
                })

            module_a_name = mod_info[0]["name"] if len(mod_info) > 0 else "Module 1"
            module_b_name = mod_info[1]["name"] if len(mod_info) > 1 else "Module 2"
            module_a_short = mod_info[0]["short"] if len(mod_info) > 0 else "Module 1"
            module_b_short = mod_info[1]["short"] if len(mod_info) > 1 else "Module 2"

            project_info = {
                "project_name": project_name,
                "customer_name": customer_name,
                "customer_company": customer_company,
                "plant_capacity": f"{plant_capacity:.1f}",
                "location": location,
                "latitude": str(latitude),
                "longitude": str(longitude),
                "date": datetime.now().strftime("%B %Y"),
                "mounting_type": mounting_type,
                "tilt_angle": tilt_angle,
                "module_a_name": module_a_name,
                "module_b_name": module_b_name,
                "module_a_short": module_a_short,
                "module_b_short": module_b_short,
                "spec_rows": spec_rows,
                "project_params": project_params_list,
                "mod_info": mod_info,
                "scored": scored,
                "score_headers": score_headers,
                "score_rows": score_rows,
                "weather_summary": project_params_list[8],
                "weather_source": weather_source,
                "ground_albedo": ground_albedo,
                "mounting_height_m": mounting_height_m,
                "bifacial_detected": bifacial_detected,
                "currency": cur,
            }

            # ===================== SCENARIO & SENSITIVITY =====================
            with st.expander("🔁 Scenario & Sensitivity Analysis", expanded=False):
                st.markdown("Explore alternate assumptions — changes re-run the model instantly.")
                sc_col1, sc_col2 = st.columns(2)
                with sc_col1:
                    scenario_mounting = st.selectbox(
                        "Alternate mounting type",
                        ["None", "Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"],
                        index=0,
                    )
                with sc_col2:
                    force_bif = st.checkbox("Force bifacial gain for all modules")

                sens_range = st.slider("Sensitivity range (+/- %)", 5, 30, 10, 1)

                if scenario_mounting != "None" or force_bif:
                    sc_params = dict(project_params)
                    if scenario_mounting != "None":
                        sc_params["mounting_type"] = scenario_mounting
                        if scenario_mounting != "Fixed Tilt":
                            sc_params["tilt_angle"] = None
                    sc_mod_list = [dict(m, bifacial=True) for m in mod_list] if force_bif else mod_list
                    with tempfile.TemporaryDirectory() as sc_dir:
                        sc_results, _ = run_analysis(
                            sc_mod_list, sc_params, sc_dir,
                            weather_data=weather_data, skip_charts=True,
                        )
                    st.markdown(f"**Scenario vs Base** — "
                                f"{scenario_mounting if scenario_mounting != 'None' else 'frontside'}"
                                f"{' + bifacial' if force_bif else ''}")
                    sc_cols = st.columns(len(mod_names))
                    for i, name in enumerate(mod_names):
                        base = results[name]
                        sc = sc_results[name]
                        with sc_cols[i]:
                            st.metric(f"{name} IRR", f"{sc['irr']*100:.2f}%",
                                      f"{(sc['irr']-base['irr'])*100:+.2f}%")
                            st.metric(f"{name} NPV", F["money"](sc['npv']),
                                      f"{F['money'](sc['npv']-base['npv'])}")
                            st.metric(f"{name} LCOE", f"{sc['lcoe']:.3f}",
                                      f"{sc['lcoe']-base['lcoe']:+.3f}")

                # Tornado chart for the recommended module
                best_name = scored[0]["short"] if scored else mod_names[0]
                base_irr = results[best_name]["irr"] * 100

                def _apply_tariff(p, m, s):
                    p2 = dict(p); p2["ppa_tariff"] = p["ppa_tariff"] * (1 + s / 100); return p2, m
                def _apply_price(p, m, s):
                    m2 = [dict(x, price_per_wp=x["price_per_wp"] * (1 + s / 100)) for x in m]; return p, m2
                def _apply_interest(p, m, s):
                    p2 = dict(p); p2["interest_rate"] = p["interest_rate"] * (1 + s / 100); return p2, m
                def _apply_debt(p, m, s):
                    p2 = dict(p); p2["debt_ratio"] = min(0.95, max(0.4, p["debt_ratio"] * (1 + s / 100))); return p2, m
                def _apply_deg(p, m, s):
                    m2 = [dict(x, deg_annual_pct=min(2.0, x["deg_annual_pct"] * (1 + s / 100))) for x in m]; return p, m2
                def _apply_eff(p, m, s):
                    m2 = [dict(x, efficiency_pct=x["efficiency_pct"] * (1 + s / 100)) for x in m]; return p, m2
                def _apply_bos(p, m, s):
                    p2 = dict(p); p2["bos_per_w"] = p["bos_per_w"] * (1 + s / 100); return p2, m

                _drivers = [
                    ("PPA Tariff", _apply_tariff),
                    ("Module Price", _apply_price),
                    ("Interest Rate", _apply_interest),
                    ("Debt Ratio", _apply_debt),
                    ("Degradation", _apply_deg),
                    ("Efficiency", _apply_eff),
                    ("BoS Cost", _apply_bos),
                ]
                _lows, _highs, _labels = [], [], []
                for _lab, _fn in _drivers:
                    _p_lo, _m_lo = _fn(project_params, mod_list, -sens_range)
                    _p_hi, _m_hi = _fn(project_params, mod_list, +sens_range)
                    with tempfile.TemporaryDirectory() as _d:
                        _r_lo, _ = run_analysis(_m_lo, _p_lo, _d, weather_data=weather_data, skip_charts=True)
                        _r_hi, _ = run_analysis(_m_hi, _p_hi, _d, weather_data=weather_data, skip_charts=True)
                    _lows.append(_r_lo[best_name]["irr"] * 100 - base_irr)
                    _highs.append(_r_hi[best_name]["irr"] * 100 - base_irr)
                    _labels.append(_lab)

                import plotly.graph_objects as _go
                _fig = _go.Figure()
                for i, _lab in enumerate(_labels):
                    _fig.add_trace(_go.Scatter(
                        x=[_lows[i], _highs[i]], y=[i, i],
                        mode="lines+markers",
                        line=dict(color="gray", width=1.5),
                        marker=dict(size=8, color=["#e74c3c", "#27ae60"]),
                        showlegend=False,
                    ))
                _fig.add_vline(x=0, line=dict(color="black", width=1))
                _fig.update_layout(
                    title=f"Tornado - IRR sensitivity ({best_name})",
                    xaxis=dict(title=f"IRR change vs base (%-pts)  |  base IRR {base_irr:.1f}%",
                               gridcolor="#eee"),
                    yaxis=dict(tickmode="array", tickvals=list(range(len(_labels))),
                               ticktext=_labels),
                    template="none",
                    height=400,
                    margin=dict(l=20, r=20, t=40, b=60),
                )
                st.plotly_chart(_fig, use_container_width=True)

            # ===================== CSV EXPORT =====================
            import csv as _csv
            import io as _io
            _buf = _io.StringIO()
            _cw = _csv.writer(_buf)
            _cw.writerow(["Module", "IRR_%", "NPV", "Total_Cost", "LCOE",
                          "Gen_Y1_kWh", "CUF_%", "Payback_yrs", "Module_Count"])
            for _n in mod_names:
                _r = results[_n]
                _cw.writerow([_n, round(_r["irr"] * 100, 2), round(_r["npv"], 2),
                              round(_r["total_cost"], 2), round(_r["lcoe"], 4),
                              round(_r["gen_y1_kwh"], 0), round(_r["cuf"] * 100, 2),
                              _r["payback"], _r["module_count"]])
            st.download_button(
                "📊 Export Results (CSV)",
                data=_buf.getvalue(),
                file_name="comparison_results.csv",
                mime="text/csv",
            )

            # ===================== SAVE CONFIG =====================
            _cfg_out = {
                "plant_capacity": plant_capacity, "latitude": latitude, "longitude": longitude,
                "ppa_tariff": ppa_tariff, "tariff_esc": tariff_esc, "debt_ratio": debt_ratio,
                "interest_rate": interest_rate, "loan_tenure": loan_tenure, "discount_rate": discount_rate,
                "bos_cost": bos_cost, "ground_albedo": ground_albedo, "mounting_height_m": mounting_height_m,
                "mounting_type": mounting_type, "tilt_angle": tilt_angle,
                "currency_code": currency_code,
                "w_lcoe": w_lcoe, "w_irr": w_irr, "w_gen": w_gen, "w_deg": w_deg,
                "w_warr": w_warr, "w_price": w_price, "w_tc": w_tc,
                "modules": [
                    {"price_per_wp": s.get("price_per_wp"), "bifacial": s.get("bifacial", False),
                     "power_wp": s.get("power_wp"), "technology": s.get("technology")}
                    for s in module_specs_list if s
                ],
            }
            st.download_button(
                "💾 Save Configuration",
                data=json.dumps(_cfg_out, indent=2),
                file_name="solar_config.json",
                mime="application/json",
            )

            report_path = os.path.join(tmpdir, "investment_report.pdf")
            gen_report(results, project_info, tmpdir, report_path)

            # Build dynamic filename
            def get_mfr_name_for_file(specs, i):
                mfr = _get_mfr_name(specs, i)
                return mfr.replace("/", "_").replace("\\", "_").split()[0]

            name_parts = [get_mfr_name_for_file(module_specs_list[i], i)
                          for i in range(len(module_specs_list))]
            report_filename = f"Comparison_Report_{'_vs_'.join(name_parts)}.pdf"

            with open(report_path, "rb") as f:
                report_data = f.read()
            st.download_button(
                "📥 PRINT / SAVE INVESTMENT GRADE PDF REPORT",
                data=report_data,
                file_name=report_filename,
                mime="application/pdf",
                width="stretch",
                type="primary",
            )
            st.info("The report includes: Executive Summary, Project Details, "
                    "Module Specifications, CAPEX, Energy Projections, Cash Flow, "
                    "Financial Metrics (IRR/NPV/LCOE), Multi-Criteria Scoring, "
                    "Risk Analysis, and Recommendation.")
if not uploaded_all:
    st.info("Upload datasheets for all modules in the expanders above to proceed.")
