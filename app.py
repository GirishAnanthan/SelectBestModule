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

st.set_page_config(page_title="Solar Module Comparison", page_icon="\u2600\ufe0f", layout="wide")
st.title("\u2600\ufe0f Solar Module Investment Comparison Engine")
st.markdown("Upload datasheets for two solar modules. The system automatically extracts specifications.")

# ----- CACHED HELPERS -----
@st.cache_data(show_spinner=False)
def cached_parse(pdf_bytes, default_tech):
    return extract_module_specs(pdf_bytes, default_tech)

@st.cache_data(show_spinner=False)
def cached_extract_text(pdf_bytes):
    text, method = extract_text_from_pdf(pdf_bytes)
    return text, method

def extract_wp_data(text, selected_wp, default_tech):
    """Extract electrical data for a specific Wp from raw PDF text."""
    specs = {}
    power_str = str(selected_wp)
    lines = text.split('\n')
    for line in lines:
        if power_str not in line:
            continue
        clean = re.sub(r'[A-Za-z]+[-\d]*\s', '', line)
        nums = [float(n) for n in re.findall(r'(\d+\.?\d*)', clean)]
        if len(nums) >= 11:
            for i in range(len(nums) - 10):
                chunk = nums[i:i+11]
                pw1, pw2 = chunk[0], chunk[1]
                v_s, v_n = chunk[2], chunk[3]
                i_s, i_n = chunk[4], chunk[5]
                isc_s, isc_n = chunk[6], chunk[7]
                voc_s, voc_n = chunk[8], chunk[9]
                eff = chunk[10]
                if (300 <= pw1 <= 800 and 300 <= pw2 <= 800 and
                    25 <= v_s <= 55 and v_n < v_s and
                    8 <= i_s <= 20 and i_n < i_s and
                    8 <= isc_s <= 22 and isc_n < isc_s and
                    35 <= voc_s <= 60 and voc_n < voc_s and
                    18 <= eff <= 26):
                    specs.update(vmp=v_s, imp=i_s, isc=isc_s, voc=voc_s, efficiency_pct=eff)
                    return specs
        feasible = [n for n in nums if 8 <= n <= 60]
        for idx in range(len(feasible) - 4):
            v, imp_, isc_, voc = feasible[idx:idx+4]
            if 25 <= v <= 55 and 8 <= imp_ <= 20 and 8 <= isc_ <= 22 and 35 <= voc <= 60:
                specs.update(vmp=v, imp=imp_, isc=isc_, voc=voc)
                if idx+4 < len(feasible) and 18 <= feasible[idx+4] <= 26:
                    specs["efficiency_pct"] = feasible[idx+4]
                return specs
    return specs

# ===== SIDEBAR: Customer & Financial =====
with st.sidebar:
    st.header("\U0001f3e2 Customer & Project")
    customer_name = st.text_input("Customer Name", "Raghavan")
    customer_company = st.text_input("Company", "Raghavan Group")
    project_name = st.text_input("Project Name", "19.6 MW Solar Plant - Pudukottai")
    plant_capacity = st.number_input("Plant Capacity (MW DC)", 0.1, 500.0, 19.6, 0.1)
    location = st.text_input("Location", "Pudukottai, Tamilnadu, India")
    col_lat, col_lon = st.columns(2)
    with col_lat: latitude = st.number_input("Latitude", -90.0, 90.0, 10.38, 0.01, format="%.2f")
    with col_lon: longitude = st.number_input("Longitude", -180.0, 180.0, 78.82, 0.01, format="%.2f")
    st.markdown("---")
    st.header("\U0001f4b0 Financial Parameters")
    ppa_tariff = st.number_input("PPA Tariff (Rs./kWh)", 1.0, 10.0, 4.50, 0.25)
    debt_ratio = st.slider("Debt Ratio", 0.5, 0.9, 0.70, 0.05)
    interest_rate = st.number_input("Interest Rate (% p.a.)", 5.0, 20.0, 9.0, 0.5) / 100
    loan_tenure = st.slider("Loan Tenure (years)", 5, 20, 15)
    discount_rate = st.number_input("Discount Rate / WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
    bos_cost = st.number_input("BoS, EPC & Land (Rs./Wp)", 5.0, 30.0, 12.0, 0.5)
    st.markdown("---")
    st.header("\U0001f3d7\ufe0f Mounting Structure")
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
            help="Optimal tilt for this latitude is approximately 9\u00b0"
        )
    st.info("Module prices are entered below per-module after datasheet upload.")

# ===== MAIN: Module Upload & Parse =====
col1, col2 = st.columns(2)

def handle_module(col, label, default_tech):
    with col:
        st.subheader(f"\U0001f4c4 {label}")
        uploaded = st.file_uploader(f"Upload {label} Datasheet (PDF)", type=["pdf"],
                                     key=f"upload_{label}")
        if uploaded is None:
            st.info(f"Upload {label} datasheet PDF to begin")
            return None

        pdf_bytes = uploaded.read()
        key = hashlib.md5(pdf_bytes).hexdigest()

        # Parse PDF (cached - only runs when file changes)
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
            specs["power_wp"] = selected_wp

            # Extract Wp-specific electrical data (cached by pdf hash + wp)
            text_key = f"text_{key}"
            if text_key not in st.session_state:
                st.session_state[text_key], _ = cached_extract_text(pdf_bytes)
            text = st.session_state[text_key]
            wp_data = extract_wp_data(text, selected_wp, default_tech)
            specs.update(wp_data)
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

        with st.expander(f"\U0001f50d {label} - Extracted Specifications", expanded=False):
            st.text(format_specs_for_display(specs))

        display = {k: v for k, v in specs.items()
                   if not k.startswith('_') and v is not None and v != []}
        st.json(display)
        return specs
    return None

specs_a = handle_module(col1, "Module 1", "Mono PERC")
specs_b = handle_module(col2, "Module 2", "N-TOPCon")

# Store uploaded filenames for report naming
uploaded_a = st.session_state.get("upload_Module 1")
uploaded_b = st.session_state.get("upload_Module 2")

# ===== GENERATE REPORT =====
st.markdown("---")
if specs_a and specs_b:
    if st.button("\u2699\ufe0f GENERATE INVESTMENT GRADE REPORT", type="primary", width='stretch'):
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

                spec_rows = [
                    ["Model", safe_val(specs_a, "power_wp") + "Wp", safe_val(specs_b, "power_wp") + "Wp", ""],
                    ["Technology", safe_val(specs_a, "technology"), safe_val(specs_b, "technology"), ""],
                    ["Efficiency", f'{specs_a.get("efficiency_pct", 0):.2f}%', f'{specs_b.get("efficiency_pct", 0):.2f}%', ""],
                    ["Vmp", f'{specs_a.get("vmp", 0):.2f}V', f'{specs_b.get("vmp", 0):.2f}V', ""],
                    ["Imp", f'{specs_a.get("imp", 0):.2f}A', f'{specs_b.get("imp", 0):.2f}A', ""],
                    ["Voc", f'{specs_a.get("voc", 0):.2f}V', f'{specs_b.get("voc", 0):.2f}V', ""],
                    ["Isc", f'{specs_a.get("isc", 0):.2f}A', f'{specs_b.get("isc", 0):.2f}A', ""],
                    ["Temp Coeff Pmax", f'{specs_a.get("temp_coeff_pmax", 0):.2f}/C', f'{specs_b.get("temp_coeff_pmax", 0):.2f}/C', ""],
                    ["Degradation Y1", f'{specs_a.get("deg_y1_pct", 0):.1f}%', f'{specs_b.get("deg_y1_pct", 0):.1f}%', ""],
                    ["Degradation Annual", f'{specs_a.get("deg_annual_pct", 0):.2f}%', f'{specs_b.get("deg_annual_pct", 0):.2f}%', ""],
                    ["Power Warranty", f'{specs_a.get("warranty_power", 0)}yr', f'{specs_b.get("warranty_power", 0)}yr', ""],
                    ["Price", f'Rs.{specs_a["price_per_wp"]}/Wp', f'Rs.{specs_b["price_per_wp"]}/Wp', ""],
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
                    "project_params": [
                        f"Location: {location} ({latitude}, {longitude})",
                        f"Plant Capacity: {plant_capacity:.1f} MW DC",
                        f"Configuration: {mounting_type}{' (Tilt: '+str(tilt_angle)+')' if tilt_angle else ''} ground mount",
                        f"PPA Tariff: Rs. {ppa_tariff:.2f}/kWh",
                        "Plant Life: 25 years",
                        f"Debt:Equity: {int(debt_ratio*100)}:{int((1-debt_ratio)*100)}",
                        f"Interest Rate: {interest_rate*100:.0f}% p.a., {loan_tenure}-year tenure",
                        f"BoS & EPC: Rs. {bos_cost:.1f}/Wp",
                        "Analysis: Frontside-only generation (no bifacial gains)",
                    ],
                }

                report_path = os.path.join(tmpdir, "investment_report.pdf")
                generate_report(r, w, project_info, tmpdir, report_path)

                # Show results
                st.success("\u2705 Analysis complete!")
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
                    "\U0001f4e5 PRINT / SAVE INVESTMENT GRADE PDF REPORT",
                    data=report_data,
                    file_name=report_filename,
                    mime="application/pdf",
                    width='stretch',
                    type="primary",
                )
                st.info("The report includes: Executive Summary, Project Background, "
                        "Module Specifications, CAPEX, Energy Projections, Cash Flow, "
                        "Financial Metrics (IRR/NPV/LCOE), Risk Analysis, and Bankability Statement.")
else:
    st.info("Upload datasheets for both modules in the columns above to proceed.")
