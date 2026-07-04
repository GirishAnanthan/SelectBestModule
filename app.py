"""
Streamlit App - Solar Module Comparison & Investment Report Generator
User uploads 2 datasheets, selects Wp, enters price + financials, gets report
"""
import streamlit as st
import os, io, json, tempfile, sys, re, hashlib
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from pdf_parser import extract_module_specs, format_specs_for_display, extract_text_from_pdf, parse_specs
from financial_engine import run_analysis
from report_generator import generate_report

st.set_page_config(page_title="Solar Module Comparison", page_icon="☀️", layout="wide")
st.title("☀️ Solar Module Investment Comparison Engine")
st.markdown("Upload datasheets for two solar modules. The system automatically extracts specifications.")

# ----- CACHED HELPERS -----
@st.cache_data(show_spinner=False)
def cached_parse(pdf_bytes, default_tech, _version=5):
    """Initial parse — detect power options and basic specs (no selected_wp yet)."""
    return extract_module_specs(pdf_bytes, default_tech)

@st.cache_data(show_spinner=False)
def cached_parse_wp(pdf_bytes, default_tech, selected_wp, _version=5):
    """Re-parse with a specific selected_wp for focused electrical extraction."""
    return extract_module_specs(pdf_bytes, default_tech, selected_wp=selected_wp)

@st.cache_data(show_spinner=False)
def cached_extract_text(pdf_bytes):
    text, method = extract_text_from_pdf(pdf_bytes)
    return text, method

# ===== SIDEBAR: Customer & Financial =====
with st.sidebar:
    st.header("🏢 Customer & Project")
    customer_name = st.text_input("Customer Name", "Raghavan")
    customer_company = st.text_input("Company", "Raghavan Group")
    project_name = st.text_input("Project Name", "19.6 MW Solar Plant - Pudukottai")
    plant_capacity = st.number_input("Plant Capacity (MW DC)", 0.1, 500.0, 19.6, 0.1)
    location = st.text_input("Location", "Pudukottai, Tamilnadu, India")
    col_lat, col_lon = st.columns(2)
    with col_lat: latitude = st.number_input("Latitude", -90.0, 90.0, 10.38, 0.01, format="%.2f")
    with col_lon: longitude = st.number_input("Longitude", -180.0, 180.0, 78.82, 0.01, format="%.2f")
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
        help="Fixed Tilt: modules at a fixed angle; Single Axis: tracks sun East-West; Dual Axis: full two-axis tracking"
    )
    tilt_angle = None
    if mounting_type == "Fixed Tilt":
        tilt_angle = st.number_input(
            "Tilt Angle (degrees from horizontal)",
            0, 60, 10, 1,
            help="Optimal tilt for this latitude is approximately 9°"
        )
    st.info("Module prices are entered below per-module after datasheet upload.")

# ===== MAIN: Module Upload & Parse =====
col1, col2 = st.columns(2)

def handle_module(col, label, default_tech):
    with col:
        st.subheader(f"📄 {label}")
        uploaded = st.file_uploader(f"Upload {label} Datasheet (PDF)", type=["pdf"],
                                     key=f"upload_{label}")
        if uploaded is None:
            st.info(f"Upload {label} datasheet PDF to begin")
            return None

        pdf_bytes = uploaded.read()

        # Initial parse: detect power options and coarse specs
        specs = cached_parse(pdf_bytes, default_tech)
        st.success(f"Extracted via {specs.get('_extraction_method', 'N/A')}")

        if specs.get("power_options"):
            opts = specs["power_options"]
            mid_idx = len(opts) // 2
            default_idx = min(mid_idx + 1, len(opts) - 1)

            selected_wp = st.selectbox(
                f"{label} - Select Module Wattage (Wp)",
                options=opts, index=default_idx,
                key=f"wp_{label}",
                help="Choose the Wp rating you plan to deploy"
            )

            # Re-parse focused on the selected wattage for accurate electrical params
            specs = cached_parse_wp(pdf_bytes, default_tech, int(selected_wp))
            specs["power_wp"] = int(selected_wp)
        else:
            st.warning("Could not detect power ratings. Enter manually below.")
            selected_wp = st.number_input(
                f"{label} - Module Power (Wp)", 300, 800, 600, 5,
                key=f"wp_manual_{label}")
            specs["power_wp"] = int(selected_wp)
            specs["power_options"] = [int(selected_wp)]

        default_price = 20 if "redren" in (uploaded.name or "").lower() else 22
        price = st.number_input(
            f"{label} - Price (Rs./Wp)", 5.0, 50.0, float(default_price), 0.5,
            key=f"price_{label}",
            help="Enter the price at which this module is available")
        specs["price_per_wp"] = price
        specs["_filename"] = uploaded.name

        with st.expander(f"🔍 {label} - Extracted Specifications", expanded=False):
            st.text(format_specs_for_display(specs))

        st.caption("Edit any incorrectly extracted values below:")
        vmp = st.number_input("Vmp (V)", 0.0, 100.0, float(specs.get("vmp", 0) or 0), key=f"vmp_{label}")
        imp = st.number_input("Imp (A)", 0.0, 30.0, float(specs.get("imp", 0) or 0), key=f"imp_{label}")
        voc = st.number_input("Voc (V)", 0.0, 100.0, float(specs.get("voc", 0) or 0), key=f"voc_{label}")
        isc = st.number_input("Isc (A)", 0.0, 30.0, float(specs.get("isc", 0) or 0), key=f"isc_{label}")
        eff = st.number_input("Efficiency (%)", 0.0, 30.0, float(specs.get("efficiency_pct", 0) or 0), key=f"eff_{label}")
        tc  = st.number_input("Temp Coeff Pmax (%/°C)", 0.0, 1.0, float(abs(specs.get("temp_coeff_pmax", 0) or 0)), key=f"tc_{label}")
        deg_y1  = st.number_input("Y1 Degradation (%)", 0.0, 5.0, float(specs.get("deg_y1_pct", 0) or 0), key=f"deg_y1_{label}")
        deg_ann = st.number_input("Annual Degradation (%)", 0.0, 1.0, float(specs.get("deg_annual_pct", 0) or 0), key=f"deg_ann_{label}")
        pw   = st.number_input("Power Warranty (years)", 0, 40, int(specs.get("warranty_power", 0) or 0), key=f"pw_{label}")
        noct = st.number_input("NOCT (°C)", 0, 60, int(specs.get("noct", 0) or 0), key=f"noct_{label}")
        specs.update(
            vmp=vmp if vmp else specs.get("vmp"),
            imp=imp if imp else specs.get("imp"),
            voc=voc if voc else specs.get("voc"),
            isc=isc if isc else specs.get("isc"),
            efficiency_pct=eff if eff else specs.get("efficiency_pct"),
            temp_coeff_pmax=-tc if tc else specs.get("temp_coeff_pmax"),
            deg_y1_pct=deg_y1 if deg_y1 else specs.get("deg_y1_pct"),
            deg_annual_pct=deg_ann if deg_ann else specs.get("deg_annual_pct"),
            warranty_power=pw if pw else specs.get("warranty_power"),
            noct=noct if noct else specs.get("noct"),
        )

        return specs
    return None

specs_a = handle_module(col1, "Module 1", "Mono PERC")
specs_b = handle_module(col2, "Module 2", "N-TOPCon")

# Store uploaded filenames for report naming
uploaded_a = st.session_state.get("upload_Module 1")
uploaded_b = st.session_state.get("upload_Module 2")

def _get_mfr_name(specs, uploaded_widget, fallback="Module"):
    """Extract manufacturer display name from specs or filename."""
    if specs:
        mfr = specs.get("manufacturer", "")
        if mfr:
            return mfr
    if uploaded_widget and hasattr(uploaded_widget, 'name'):
        mfr = os.path.splitext(uploaded_widget.name)[0]
        if mfr:
            return mfr
    return fallback

# ===== GENERATE REPORT =====
st.markdown("---")
if specs_a and specs_b:
    if st.button("⚙️ GENERATE TECHNO COMMERCIAL COMPARISON", type="primary", width='stretch'):
        with st.spinner("Running comprehensive analysis..."):
            project_params = {
                "capacity_mw": plant_capacity, "latitude": latitude,
                "longitude": longitude, "ppa_tariff": ppa_tariff,
                "debt_ratio": debt_ratio, "interest_rate": interest_rate,
                "loan_tenure": loan_tenure, "tax_rate": 0.2517,
                "discount_rate": discount_rate, "om_per_mw": 180000,
                "om_esc": 0.03, "bos_per_w": bos_cost, "insurance_rate": 0.003,
                "mounting_type": mounting_type, "tilt_angle": tilt_angle,
            }

            # Build module specs for financial engine
            mod_a_specs = {
                "name": specs_a.get("_filename", specs_a.get("power_wp", "Module 1")),
                "short": "Module A",
                "capacity_w": specs_a["power_wp"],
                "efficiency_pct": specs_a.get("efficiency_pct", 21.0),
                "temp_coeff_pmax": specs_a.get("temp_coeff_pmax", -0.35),
                "deg_y1_pct": specs_a.get("deg_y1_pct", 2.0),
                "deg_annual_pct": specs_a.get("deg_annual_pct", 0.55),
                "price_per_wp": specs_a["price_per_wp"],
                "warranty_yrs": specs_a.get("warranty_power", 27),
                "technology": specs_a.get("technology", "Mono PERC"),
            }
            mod_b_specs = {
                "name": specs_b.get("_filename", specs_b.get("power_wp", "Module 2")),
                "short": "Module B",
                "capacity_w": specs_b["power_wp"],
                "efficiency_pct": specs_b.get("efficiency_pct", 22.77),
                "temp_coeff_pmax": specs_b.get("temp_coeff_pmax", -0.30),
                "deg_y1_pct": specs_b.get("deg_y1_pct", 1.0),
                "deg_annual_pct": specs_b.get("deg_annual_pct", 0.40),
                "price_per_wp": specs_b["price_per_wp"],
                "warranty_yrs": specs_b.get("warranty_power", 30),
                "technology": specs_b.get("technology", "N-TOPCon"),
            }

            with tempfile.TemporaryDirectory() as tmpdir:
                results, chart_paths = run_analysis(mod_a_specs, mod_b_specs, project_params, tmpdir)
                r = results[mod_a_specs['short']]
                w = results[mod_b_specs['short']]

                # Build project info for report
                def safe_val(specs, key, default="N/A"):
                    v = specs.get(key, default)
                    return str(v) if v is not None else str(default)

                mfr_a = specs_a.get("manufacturer") or _get_mfr_name(specs_a, uploaded_a, "Module 1")
                mfr_b = specs_b.get("manufacturer") or _get_mfr_name(specs_b, uploaded_b, "Module 2")

                spec_rows = [
                    ["Model",              safe_val(specs_a, "power_wp") + "Wp",    safe_val(specs_b, "power_wp") + "Wp",    ""],
                    ["Technology",         safe_val(specs_a, "technology"),          safe_val(specs_b, "technology"),          ""],
                    ["Manufacturer",       mfr_a,                                    mfr_b,                                    ""],
                    ["Modules Required",   f'{r["module_count"]:,}',                 f'{w["module_count"]:,}',                 "nos"],
                    ["Efficiency",         f'{specs_a.get("efficiency_pct", 0):.2f}%',f'{specs_b.get("efficiency_pct", 0):.2f}%',""],
                    ["Vmp",               f'{specs_a.get("vmp", 0):.2f}V',          f'{specs_b.get("vmp", 0):.2f}V',          "V"],
                    ["Imp",               f'{specs_a.get("imp", 0):.2f}A',          f'{specs_b.get("imp", 0):.2f}A',          "A"],
                    ["Voc",               f'{specs_a.get("voc", 0):.2f}V',          f'{specs_b.get("voc", 0):.2f}V',          "V"],
                    ["Isc",               f'{specs_a.get("isc", 0):.2f}A',          f'{specs_b.get("isc", 0):.2f}A',          "A"],
                    ["Temp Coeff Pmax",   f'{specs_a.get("temp_coeff_pmax", 0):.3f}%/C', f'{specs_b.get("temp_coeff_pmax", 0):.3f}%/C', "%/°C"],
                    ["Degradation Y1",    f'{specs_a.get("deg_y1_pct", 0):.1f}%',   f'{specs_b.get("deg_y1_pct", 0):.1f}%',   "%"],
                    ["Degradation Annual",f'{specs_a.get("deg_annual_pct", 0):.2f}%',f'{specs_b.get("deg_annual_pct", 0):.2f}%',"%"],
                    ["Power Warranty",    f'{specs_a.get("warranty_power", 0)}yr',   f'{specs_b.get("warranty_power", 0)}yr',   "years"],
                    ["Price",             f'Rs.{specs_a["price_per_wp"]}/Wp',        f'Rs.{specs_b["price_per_wp"]}/Wp',        ""],
                ]

                project_info = {
                    "project_name": project_name, "customer_name": customer_name,
                    "customer_company": customer_company,
                    "plant_capacity": f"{plant_capacity:.1f}",
                    "location": location, "latitude": str(latitude),
                    "longitude": str(longitude), "date": datetime.now().strftime("%B %Y"),
                    "mounting_type": mounting_type, "tilt_angle": tilt_angle,
                    "module_a_name": f"Module 1 ({safe_val(specs_a, 'power_wp')}Wp)",
                    "module_b_name": f"Module 2 ({safe_val(specs_b, 'power_wp')}Wp)",
                    "module_a_short": "Module A", "module_b_short": "Module B",
                    "spec_rows": spec_rows,
                    # Extended fields for Project Details section
                    "module_a_brand": mfr_a,
                    "module_b_brand": mfr_b,
                    "module_a_wp": specs_a["power_wp"],
                    "module_b_wp": specs_b["power_wp"],
                    "module_a_count": r["module_count"],
                    "module_b_count": w["module_count"],
                    "module_a_dims": (
                        specs_a.get("length_mm") or specs_a.get("length"),
                        specs_a.get("width_mm") or specs_a.get("width"),
                    ),
                    "module_b_dims": (
                        specs_b.get("length_mm") or specs_b.get("length"),
                        specs_b.get("width_mm") or specs_b.get("width"),
                    ),
                    "project_params": [
                        f"Location: {location} ({latitude}, {longitude})",
                        f"Plant Capacity: {plant_capacity:.1f} MW DC",
                        f"Configuration: {mounting_type}{' (Tilt: '+str(tilt_angle)+'°)' if tilt_angle else ''} ground mount",
                        f"PPA Tariff: Rs. {ppa_tariff:.2f}/kWh",
                        "Plant Life: 25 years",
                        f"Debt:Equity: {int(debt_ratio*100)}:{int((1-debt_ratio)*100)}",
                        f"Interest Rate: {interest_rate*100:.0f}% p.a., {loan_tenure}-year tenure",
                        f"BoS & EPC: Rs. {bos_cost:.1f}/Wp (adjusted for module count)",
                        f"Module A: {r['module_count']:,} units @ {specs_a['power_wp']}Wp",
                        f"Module B: {w['module_count']:,} units @ {specs_b['power_wp']}Wp",
                        "Analysis: Frontside-only generation (no bifacial gains)",
                    ],
                }

                report_path = os.path.join(tmpdir, "investment_report.pdf")
                generate_report(r, w, project_info, tmpdir, report_path)

                # Show results
                st.success("✅ Analysis complete!")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Module A - IRR", f"{r['irr']*100:.2f}%",
                              f"Cost: Rs.{r['total_cost']/1e7:.1f}Cr")
                    st.metric("Module A - Project Cost", f"Rs.{r['total_cost']/1e7:.2f}Cr",
                              f"CUF: {r['cuf']*100:.1f}%")
                with c2:
                    st.metric("Module B - IRR", f"{w['irr']*100:.2f}%",
                              f"Cost: Rs.{w['total_cost']/1e7:.1f}Cr")
                    st.metric("Module B - Project Cost", f"Rs.{w['total_cost']/1e7:.2f}Cr",
                              f"CUF: {w['cuf']*100:.1f}%")
                with c3:
                    best = "Module A" if r['irr'] >= w['irr'] else "Module B"
                    st.metric("Recommended", best,
                              f"IRR diff: {abs(r['irr']-w['irr'])*100:.2f}%")
                    st.metric("Gen Diff", f"{abs(w['total_gen_kwh']-r['total_gen_kwh'])/1e6:.1f}GWh",
                              f"favoring {'B' if w['total_gen_kwh']>r['total_gen_kwh'] else 'A'}")

                # Chart previews
                st.subheader("Chart Preview")
                ch_cols = st.columns(2)
                ch_names = list(chart_paths.keys())
                for i, cn in enumerate(ch_names[:6]):
                    with ch_cols[i%2]:
                        if os.path.exists(chart_paths[cn]):
                            st.image(chart_paths[cn],
                                     caption=cn.replace('.png','').replace('_',' ').title(),
                                     width='stretch')

                # Build dynamic report filename from manufacturer names
                def get_mfr_name(specs, uploaded_widget):
                    mfr = specs.get("manufacturer", "")
                    if not mfr and uploaded_widget:
                        mfr = os.path.splitext(uploaded_widget.name)[0] if hasattr(uploaded_widget, 'name') else ""
                    if not mfr:
                        mfr = "Module"
                    return mfr.replace('/', '_').replace('\\', '_').split()[0]
                mfr_a_clean = get_mfr_name(specs_a, uploaded_a)
                mfr_b_clean = get_mfr_name(specs_b, uploaded_b)
                report_filename = f"Comparison_Report_{mfr_a_clean}_vs_{mfr_b_clean}.pdf"

                # Download
                with open(report_path, "rb") as f:
                    report_data = f.read()
                st.download_button(
                    "📥 PRINT / SAVE INVESTMENT GRADE PDF REPORT",
                    data=report_data,
                    file_name=report_filename,
                    mime="application/pdf",
                    width='stretch',
                    type="primary",
                )
                st.info("The report includes: Executive Summary, Project Details, Project Background, "
                        "Module Specifications, CAPEX, Energy Projections, Cash Flow, "
                        "Financial Metrics (IRR/NPV/LCOE), PVSyst Simulation Data, Risk Analysis, and Recommendation.")
else:
    st.info("Upload datasheets for both modules in the columns above to proceed.")
