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
    ppa_tariff = st.number_input("PPA Tariff (Rs./kWh)", 1.0, 10.0, 4.50, 0.25)
    debt_ratio = st.slider("Debt Ratio", 0.5, 0.9, 0.70, 0.05)
    interest_rate = st.number_input("Interest Rate (% p.a.)", 5.0, 20.0, 9.0, 0.5) / 100
    loan_tenure = st.slider("Loan Tenure (years)", 5, 20, 15)
    discount_rate = st.number_input("Discount Rate / WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
    bos_cost = st.number_input("BoS, EPC & Land (Rs./Wp)", 5.0, 30.0, 12.0, 0.5)

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
            f"{label} - Price (Rs./Wp)", 5.0, 50.0, float(default_price), 0.5,
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

# Render module UI for each module
module_specs_list = []
for i in range(n_modules):
    specs = render_module_ui(i)
    module_specs_list.append(specs)

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
    if st.button("⚙️ GENERATE TECHNO COMMERCIAL COMPARISON", type="primary", width="stretch"):
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
            "weather_source": ws,
            "ground_albedo": ground_albedo,
            "mounting_height_m": mounting_height_m,
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
                results, chart_paths = run_analysis(mod_list, project_params, tmpdir)

                # Build scoring
                weights = {
                    "lcoe": w_lcoe, "irr": w_irr,
                    "generation_yield": w_gen, "degradation": w_deg,
                    "warranty": w_warr, "price": w_price,
                    "temp_coeff": w_tc,
                }
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
                        st.metric(f"{name} - Project Cost", f"Rs.{r['total_cost']/1e7:.2f}Cr")
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
                        f'Rs.{specs["price_per_wp"]}/Wp',
                        "",
                    ])

                # Build project params list
                first_r = results[mod_names[0]]
                project_params_list = [
                    f"Location: {location} ({latitude}, {longitude})",
                    f"Plant Capacity: {plant_capacity:.1f} MW DC",
                    f"Configuration: {mounting_type}{' (Tilt: '+str(tilt_angle)+'°)' if tilt_angle else ''} ground mount",
                    f"PPA Tariff: Rs. {ppa_tariff:.2f}/kWh",
                    "Plant Life: 25 years",
                    f"Debt:Equity: {int(debt_ratio*100)}:{int((1-debt_ratio)*100)}",
                    f"Interest Rate: {interest_rate*100:.0f}% p.a., {loan_tenure}-year tenure",
                    f"BoS & EPC: Rs. {bos_cost:.1f}/Wp (adjusted for module count)",
                    f"Weather: {get_weather_summary(fetch_nasa_power_monthly(latitude, longitude) if ws == 'api' else None)}",
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
                }

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
else:
    st.info("Upload datasheets for all modules in the expanders above to proceed.")
