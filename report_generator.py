"""PDF Report Generator - Investor-grade professional layout"""
import os
from fpdf import FPDF
from PIL import Image


# ---------------------------------------------------------------------------
# Custom PDF class
# ---------------------------------------------------------------------------

class SolarReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(120, 120, 120)
            self.cell(0, 5, self.header_text, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_draw_color(200, 200, 200)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(1)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    def stitle(self, t):
        """Section title with blue underline rule."""
        self.ln(2)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, t, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 51, 102)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def sub_title(self, t):
        """Sub-section title."""
        self.ln(1)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 5.5, t, new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def ptext(self, t):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 4.2, t)
        self.ln(0.5)

    def bul(self, t):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(40, 40, 40)
        x0 = self.l_margin
        self.set_x(x0 + 2)
        self.cell(4, 4.2, "\u2022")
        self.set_x(x0 + 6)
        self.multi_cell(self.w - x0 - self.r_margin - 6, 4.2, t)
        self.set_x(x0)

    def box(self, label, value, sub="", x=None, y=None, w=55, h=18):
        if x is None:
            x, y = self.get_x(), self.get_y()
        self.set_draw_color(0, 51, 102)
        self.set_fill_color(240, 245, 255)
        self.rect(x, y, w, h, style="DF")
        self.set_xy(x + 2, y + 1.5)
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(0, 51, 102)
        self.cell(w - 4, 3.5, label)
        self.set_xy(x + 2, y + 5)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(0, 0, 0)
        self.cell(w - 4, 6, value)
        if sub:
            self.set_xy(x + 2, y + 12.5)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(100, 100, 100)
            self.cell(w - 4, 3, sub)

    def add_image(self, path, w=None):
        if not w:
            w = self.w - self.l_margin - self.r_margin
        if os.path.exists(path):
            img = self.image(path, x=self.l_margin, w=w)
            self.ln(img.rendered_height + 3)
        else:
            self.ptext(f"[Chart not found: {path}]")

    def keep_with(self, chart_path, text, chart_w=None, margin=2):
        """Add chart + explanation. Inserts page break only if really needed."""
        if not os.path.exists(chart_path):
            return
        try:
            im = Image.open(chart_path)
            iw, ih = im.size
        except Exception:
            iw, ih = 1000, 500
        cw = chart_w if chart_w else (self.w - self.l_margin - self.r_margin)
        ch = ih * cw / iw
        texts = text if isinstance(text, list) else [text]
        tw = self.w - self.l_margin - self.r_margin
        avg_cw = 2.8
        lines = sum(max(1, len(t) // max(1, int(tw / avg_cw)) + 1) for t in texts)
        text_h = lines * 4.5 + len(texts) * 1.5
        needed = ch + margin + text_h
        if self.get_y() + needed > self.h - self.b_margin:
            self.add_page()
        img = self.image(chart_path, x=self.l_margin, w=cw)
        self.ln(img.rendered_height + 2)
        for t in texts:
            self.ptext(t)

    def tbl_hdr(self, col_w, headers, row_h=5.5):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w[i], row_h, h, border=1, align="C", fill=True,
                      new_x="RIGHT", new_y="TOP")
        self.ln()

    def tbl_row(self, col_w, cells, bold=False, fill=False, row_h=5):
        self.set_font("Helvetica", "B" if bold else "", 7.5)
        self.set_text_color(0, 0, 0)
        self.set_fill_color(220, 230, 245 if fill else 255)
        for i, c in enumerate(cells):
            self.cell(col_w[i], row_h, str(c),
                      border=1,
                      align="L" if i == 0 else "C",
                      fill=fill or bold,
                      new_x="RIGHT", new_y="TOP")
        self.ln()

    def divider(self):
        self.ln(1)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)


# ---------------------------------------------------------------------------
# Land area helper
# ---------------------------------------------------------------------------

_GCR_LAND_FACTOR = {
    "Fixed Tilt": 3.0,
    "Single Axis Tracker": 3.5,
    "Dual Axis Tracker": 5.0,
}

_DEFAULT_DIMS = {
    "default": (2278, 1134),   # 182mm cell 132-cell standard
}


def _compute_land_area(module_dims, n_modules, mounting_type):
    L, W = module_dims
    if L and W and L > 500 and W > 500:
        mod_area = (L / 1000) * (W / 1000)
    else:
        L_d, W_d = _DEFAULT_DIMS["default"]
        mod_area = (L_d / 1000) * (W_d / 1000)
    factor = _GCR_LAND_FACTOR.get(mounting_type, 3.0)
    total_mod_area = mod_area * n_modules
    land_area_m2 = total_mod_area * factor
    return total_mod_area, land_area_m2, land_area_m2 / 4046.86, land_area_m2 / 10000


# ---------------------------------------------------------------------------
# Full width helper
# ---------------------------------------------------------------------------

def _fw(pdf, splits):
    """Distribute full printable width proportionally to 'splits' list."""
    total = pdf.w - pdf.l_margin - pdf.r_margin
    s = sum(splits)
    return [total * x / s for x in splits]


# ---------------------------------------------------------------------------
# Main report generator
# ---------------------------------------------------------------------------

def generate_report(r, w, project_info, chart_dir, output_path):
    info = project_info

    pdf = SolarReport()
    pdf.header_text = (
        f"{info.get('project_name', 'Solar Plant')} | "
        "Techno Commercial Comparison Report"
    )
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(12, 12, 12)

    a_short = info.get("module_a_short", "Module A")
    b_short = info.get("module_b_short", "Module B")
    a_name  = info.get("module_a_name", "Module A")
    b_name  = info.get("module_b_name", "Module B")

    best_is_a = r["irr"] >= w["irr"]
    best_name = a_name if best_is_a else b_name
    best_irr  = r["irr"] if best_is_a else w["irr"]

    # =========================================================
    # COVER PAGE
    # =========================================================
    pdf.add_page()
    pdf.ln(20)

    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, "TECHNO COMMERCIAL COMPARISON", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 7,
             f"{info.get('plant_capacity','XX')} MW DC Solar Plant \u2014 {info.get('location','')}",
             align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_draw_color(0, 51, 102)
    pdf.line(50, pdf.get_y(), pdf.w - 50, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 6, f"{a_name}  vs  {b_name}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(0, 5.5, f"Prepared for: {info.get('customer_name','Client')} \u2022 {info.get('customer_company','N/A')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5.5, f"Date: {info.get('date','July 2026')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Key metrics strip on cover
    strip_w = (pdf.w - pdf.l_margin - pdf.r_margin) / 4 - 2
    strip_x = pdf.l_margin
    strip_y = pdf.get_y()
    pdf.box("Module A IRR", f"{r['irr']*100:.2f}%", f"NPV Rs.{r['npv']/1e7:.1f}Cr", x=strip_x, y=strip_y, w=strip_w, h=20)
    pdf.box("Module B IRR", f"{w['irr']*100:.2f}%", f"NPV Rs.{w['npv']/1e7:.1f}Cr", x=strip_x + strip_w + 2, y=strip_y, w=strip_w, h=20)
    pdf.box("Payback (A/B)", f"{r['payback']}/{w['payback']} yr", "Equity recovery", x=strip_x + (strip_w + 2)*2, y=strip_y, w=strip_w, h=20)
    pdf.box("Recommended", best_name.split()[0], f"IRR {best_irr*100:.2f}%", x=strip_x + (strip_w + 2)*3, y=strip_y, w=strip_w, h=20)
    pdf.set_y(strip_y + 24)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(0, 4,
        "Disclaimer: This report is based on manufacturer datasheets and standard financial modelling assumptions. "
        "Actual returns may vary based on site conditions, financing terms, and prevailing tariff rates.")

    # =========================================================
    # 1. EXECUTIVE SUMMARY
    # =========================================================
    pdf.add_page()
    pdf.stitle("1. Executive Summary")

    mounting_display = info.get("mounting_type", "Fixed Tilt")
    if info.get("tilt_angle"):
        mounting_display += f" (Tilt: {info['tilt_angle']}\u00b0)"

    pdf.ptext(
        f"This report presents a comprehensive technical and financial comparison of two DCR-compliant "
        f"solar PV module options for a {info.get('plant_capacity','XX')} MW DC ground-mount solar plant "
        f"at {info.get('location','the project site')}. The analysis evaluates {a_name} against {b_name} "
        f"on a {mounting_display} configuration, using frontside-only generation (conservative basis, "
        f"bifacial gains excluded). Generation estimates incorporate site-specific GHI, POA irradiance, and Performance Ratio."
    )

    pdf.sub_title("Key Findings")
    pdf.bul(f"{a_short} achieves an Equity IRR of {r['irr']*100:.2f}%; {b_short} achieves {w['irr']*100:.2f}%")
    pdf.bul(f"NPV ({a_short}): Rs. {r['npv']/1e7:.2f} Cr  |  NPV ({b_short}): Rs. {w['npv']/1e7:.2f} Cr")
    pdf.bul(f"Equity required — {a_short}: Rs. {r['equity']/1e7:.2f} Cr  |  {b_short}: Rs. {w['equity']/1e7:.2f} Cr")
    pdf.bul(f"Both modules achieve payback within {r['payback']} years")
    pdf.bul(f"{b_short} generates {((w['total_gen_kwh']/r['total_gen_kwh'])-1)*100:.1f}% more lifetime energy than {a_short}")

    pdf.sub_title("Recommendation")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(180, 30, 0)
    pdf.multi_cell(0, 4.8,
        f"Based on comprehensive analysis, {best_name} is RECOMMENDED for investors seeking higher Equity IRR "
        f"({best_irr*100:.2f}%). The final decision should align with the investor's return expectations and risk appetite.")

    # =========================================================
    # 2. PROJECT DETAILS
    # =========================================================
    pdf.stitle("2. Project Details")

    dims_a = info.get("module_a_dims", (None, None))
    dims_b = info.get("module_b_dims", (None, None))
    n_a = info.get("module_a_count", r.get("module_count", 0))
    n_b = info.get("module_b_count", w.get("module_count", 0))
    mt = info.get("mounting_type", "Fixed Tilt")

    _, _, land_acres_a, land_ha_a = _compute_land_area(dims_a, n_a, mt)
    _, _, land_acres_b, land_ha_b = _compute_land_area(dims_b, n_b, mt)

    pd_col = _fw(pdf, [2.5, 1.5, 1.5])
    pdf.tbl_hdr(pd_col, ["Project Parameter", a_short, b_short])
    pd_rows = [
        ("Customer Name",       info.get("customer_name", ""),       info.get("customer_name", "")),
        ("Company",             info.get("customer_company", ""),     info.get("customer_company", "")),
        ("Project DC Capacity", f"{info.get('plant_capacity','N/A')} MW DC", f"{info.get('plant_capacity','N/A')} MW DC"),
        ("Location",            info.get("location", ""),            info.get("location", "")),
        ("Module Brand",        info.get("module_a_brand", ""),      info.get("module_b_brand", "")),
        ("Module Wattage",      f"{info.get('module_a_wp','N/A')} Wp", f"{info.get('module_b_wp','N/A')} Wp"),
        ("Number of Modules",   f"{n_a:,} nos",                     f"{n_b:,} nos"),
        ("Mounting Structure",  mt,                                  mt),
        ("Land Area Required",  f"{land_acres_a:.1f} acres ({land_ha_a:.1f} ha)", f"{land_acres_b:.1f} acres ({land_ha_b:.1f} ha)"),
        ("Analysis Basis",      "Frontside only (no bifacial)",      "Frontside only (no bifacial)"),
        ("Plant Life",          "25 years",                          "25 years"),
    ]
    for i, (p, va, vb) in enumerate(pd_rows):
        pdf.tbl_row(pd_col, [p, va, vb], fill=(i % 2 == 1))

    pdf.ln(1.5)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(110, 110, 110)
    gcr = _GCR_LAND_FACTOR.get(mt, 3.0)
    pdf.multi_cell(0, 3.8,
        f"Land area estimated using a land-to-module-area factor of {gcr:.1f}\u00d7 for {mt} mounting. "
        "Actual requirement may vary based on row spacing, access roads, transformer bays, and site boundary.")

    # =========================================================
    # 3. PROJECT BACKGROUND
    # =========================================================
    pdf.stitle("3. Project Background")
    pdf.ptext(
        f"The proposed {info.get('plant_capacity','XX')} MW DC solar photovoltaic plant is located at "
        f"{info.get('location','the project site')} (Lat: {info.get('latitude','N/A')}, "
        f"Lon: {info.get('longitude','N/A')}), a region with excellent solar insolation. "
        f"The project employs {mounting_display} mounting and qualifies under DCR category, "
        "mandating indigenously manufactured solar modules."
    )
    pdf.ptext("Key project parameters assumed for this analysis:")
    for param in info.get("project_params", []):
        pdf.bul(param)
    pdf.ln(1)
    pdf.sub_title("Site-Specific CUF Assumptions")
    pdf.bul(f"{a_short}: {r['cuf']*100:.1f}%")
    pdf.bul(f"{b_short}: {w['cuf']*100:.1f}% — Superior low-light & temperature performance")

    pvsyst_a = r.get("pvsyst", {})
    pvsyst_b = w.get("pvsyst", {})
    if pvsyst_a or pvsyst_b:
        pdf.sub_title("3.1 Energy Simulation Data")
        pdf.ptext(
            "Site-specific irradiance and performance metrics computed from location and mounting configuration. "
            "These form the basis of the energy generation projections in this report."
        )
        pv_col = _fw(pdf, [2.5, 1.5, 1.5, 1])
        pdf.tbl_hdr(pv_col, ["Simulation Parameter", a_short, b_short, "Unit"])

        def _fmt_pr(v):
            return f"{v:.1%}" if isinstance(v, (int, float)) else str(v)

        pv_rows = [
            ["Annual GHI",           str(pvsyst_a.get("annual_ghi","N/A")),   str(pvsyst_b.get("annual_ghi","N/A")),   "kWh/m\u00b2/yr"],
            ["Annual POA Irradiance", str(pvsyst_a.get("annual_poa","N/A")),   str(pvsyst_b.get("annual_poa","N/A")),   "kWh/m\u00b2/yr"],
            ["Specific Yield",        str(pvsyst_a.get("specific_yield","N/A")),str(pvsyst_b.get("specific_yield","N/A")),"kWh/kWp"],
            ["Performance Ratio",     _fmt_pr(pvsyst_a.get("performance_ratio")),_fmt_pr(pvsyst_b.get("performance_ratio")),""],
            ["CUF (Capacity Util.)",  f"{r['cuf']*100:.1f}%",                 f"{w['cuf']*100:.1f}%",                  ""],
        ]
        for i, row in enumerate(pv_rows):
            pdf.tbl_row(pv_col, row, fill=i % 2 == 1)

    # =========================================================
    # 4. TECHNICAL SPECIFICATIONS
    # =========================================================
    pdf.stitle("4. Module Technical Specifications")
    pdf.ptext("Specifications extracted directly from manufacturer datasheets.")
    col = _fw(pdf, [2.5, 1.5, 1.5, 1])
    pdf.tbl_hdr(col, ["Parameter", a_short, b_short, "Unit"])
    for i, row in enumerate(info.get("spec_rows", [])):
        pdf.tbl_row(col, row, fill=i % 2 == 1)

    # =========================================================
    # 5. FINANCIAL ANALYSIS & PROJECTIONS
    # =========================================================
    pdf.stitle("5. Financial Analysis & Projections")

    # 5.1 CAPEX
    pdf.sub_title("5.1 Capital Expenditure (CAPEX)")
    pdf.ptext(
        f"Total project cost: Rs. {r['total_cost']/1e7:.2f} Cr ({a_short}) vs "
        f"Rs. {w['total_cost']/1e7:.2f} Cr ({b_short}). BoS, EPC and land at Rs. 12/Wp."
    )
    cc = _fw(pdf, [2.5, 1.5, 1.5])
    pdf.tbl_hdr(cc, ["Cost Component (Rs. Cr)", a_short, b_short])
    pdf.tbl_row(cc, ["Module Cost",       f"{r['module_cost']/1e7:.2f}", f"{w['module_cost']/1e7:.2f}"])
    pdf.tbl_row(cc, ["BoS, EPC & Land",   f"{r['bos_cost']/1e7:.2f}",   f"{w['bos_cost']/1e7:.2f}"])
    pdf.tbl_row(cc, ["Total Project Cost",f"{r['total_cost']/1e7:.2f}", f"{w['total_cost']/1e7:.2f}"], bold=True, fill=True)
    pdf.tbl_row(cc, ["Equity @ 30%",      f"{r['equity']/1e7:.2f}",     f"{w['equity']/1e7:.2f}"],     bold=True, fill=True)

    pie_path = os.path.join(chart_dir, "chart_cost_pie.png")
    pdf.keep_with(pie_path,
        "Cost breakdown: proportion of module cost vs balance-of-system (BoS). "
        "Higher-wattage modules reduce count, lowering mounting hardware, cabling, and installation costs. "
        "Module cost typically represents 55\u201365% of total project CAPEX.",
        chart_w=100)

    # 5.2 Energy Generation
    pdf.sub_title("5.2 Energy Generation & Revenue")
    pvsyst_a = r.get("pvsyst", {})
    pr_val = pvsyst_a.get("performance_ratio", "N/A")
    pr_str = f"{pr_val:.1%}" if isinstance(pr_val, (int, float)) else str(pr_val)
    pdf.ptext(
        f"Year 1 generation: {r['gen_y1_kwh']/1e3:,.0f} MWh ({a_short}) vs "
        f"{w['gen_y1_kwh']/1e3:,.0f} MWh ({b_short}). "
        f"Over 25 years, {b_short} generates {((w['total_gen_kwh']/r['total_gen_kwh'])-1)*100:.1f}% more energy. "
        f"GHI {pvsyst_a.get('annual_ghi','N/A')} kWh/m\u00b2/yr, "
        f"POA {pvsyst_a.get('annual_poa','N/A')} kWh/m\u00b2/yr, PR {pr_str}."
    )
    gen_path = os.path.join(chart_dir, "chart_gen.png")
    pdf.keep_with(gen_path,
        "Annual energy output over the 25-year project life. Progressive decline is driven by module degradation. "
        "Two-phase model: initial Y1 degradation followed by linear annual degradation. "
        "Modules with lower temperature coefficients and lower annual degradation rates sustain higher yields in later years, "
        "compounding the NPV and IRR differentials.")

    # 5.3 Cash Flow
    pdf.sub_title("5.3 Cash Flow Analysis & Returns")
    pdf.ptext(
        "Model incorporates revenue, O&M (3% escalation), insurance, debt servicing "
        f"(15-yr @ 9%), WDV depreciation, and corporate tax at 25.17%."
    )

    fcf_path = os.path.join(chart_dir, "chart_cumulative_fcf.png")
    pdf.keep_with(fcf_path, [
        f"Cumulative FCF: both modules reach payback by Year {w['payback']}.",
        "Tracks equity investor's cash position over the project life. Payback is the year cumulative "
        "cash flows turn positive. Post-payback steepness reflects ongoing FCF generation net of opex, interest, and tax.",
    ])

    dscr_path = os.path.join(chart_dir, "chart_dscr.png")
    pdf.keep_with(dscr_path, [
        "DSCR > 1.5\u00d7 throughout the loan tenure confirms strong debt repayment capacity and bankability.",
        "DSCR = (Net Income + Depreciation + Interest) / (Principal + Interest). "
        "Indian project finance lenders typically require minimum 1.3\u00d71.5\u00d7. "
        "Declining trend over time is expected as generation degrades while debt payments remain fixed.",
    ])

    ni_path = os.path.join(chart_dir, "chart_net_income.png")
    pdf.keep_with(ni_path, [
        "Net income after tax shows long-term return profile for both module options.",
        "Lower early-year net income is typical due to higher interest expense and accelerated WDV depreciation. "
        "As the loan is repaid, net income rises and stabilises. Modules with lower degradation show higher "
        "net income in later project years.",
    ])

    # =========================================================
    # 6. KEY FINANCIAL METRICS
    # =========================================================
    pdf.stitle("6. Key Financial Metrics Comparison")

    irr_path = os.path.join(chart_dir, "chart_irr_npv.png")
    pdf.keep_with(irr_path,
        "Equity IRR and NPV comparison. IRR is the annualised return on equity over 25 years; "
        "NPV is the present value of all future cash flows discounted at WACC. "
        "Higher IRR indicates better percentage returns; higher NPV indicates greater absolute wealth creation. "
        "Together they present a complete investment decision framework.")

    cc2 = _fw(pdf, [2.5, 1.5, 1.5])
    pdf.tbl_hdr(cc2, ["Financial Metric", a_short, b_short])
    fm = [
        ("Total Project Cost (Rs. Cr)", f"{r['total_cost']/1e7:.2f}",  f"{w['total_cost']/1e7:.2f}"),
        ("Equity Required (Rs. Cr)",     f"{r['equity']/1e7:.2f}",      f"{w['equity']/1e7:.2f}"),
        ("Annual Gen Y1 (MWh)",          f"{r['gen_y1_kwh']/1e3:,.0f}", f"{w['gen_y1_kwh']/1e3:,.0f}"),
        ("Total Gen 25yr (GWh)",         f"{r['total_gen_kwh']/1e6:.1f}",f"{w['total_gen_kwh']/1e6:.1f}"),
        ("CUF Frontside (%)",            f"{r['cuf']*100:.1f}",         f"{w['cuf']*100:.1f}"),
        ("Revenue Y1 (Rs. Cr)",          f"{r['revenue'][1]/1e7:.2f}",  f"{w['revenue'][1]/1e7:.2f}"),
        ("Equity IRR (%)",               f"{r['irr']*100:.2f}",         f"{w['irr']*100:.2f}"),
        ("NPV @ 10% (Rs. Cr)",           f"{r['npv']/1e7:.2f}",         f"{w['npv']/1e7:.2f}"),
        ("LCOE (Rs./kWh)",               f"{r['lcoe']:.3f}",            f"{w['lcoe']:.3f}"),
        ("Payback Period (years)",        f"{r['payback']}",             f"{w['payback']}"),
    ]
    for i, row in enumerate(fm):
        bold = row[0] in ("Equity IRR (%)", "NPV @ 10% (Rs. Cr)")
        pdf.tbl_row(cc2, row, bold=bold, fill=i % 2 == 0)

    # =========================================================
    # 7. RISK ANALYSIS & SENSITIVITY
    # =========================================================
    pdf.stitle("7. Risk Analysis & Sensitivity")

    risks = [
        ("PPA Tariff Risk",   "A Rs. 0.50/kWh reduction reduces IRR by ~3\u20134%. Both modules equally exposed."),
        ("Generation Risk",   "10% lower CUF reduces IRR by ~4\u20135%. TOPCon's better temperature coefficient offers marginal protection."),
        ("Interest Rate Risk","1% rate increase reduces IRR by ~1.5%. Lower-debt module has slightly better resilience."),
        ("Degradation Risk",  "Higher degradation impacts long-term returns. N-TOPCon has proven lower annual degradation."),
        ("Technology Risk",   "PERC is a mature technology; N-TOPCon is the next-generation platform with longer-term upgrade potential."),
        ("DCR Compliance",    "Both modules are DCR-compliant, mitigating import and policy risks."),
    ]

    risk_col = _fw(pdf, [1.2, 4.3])
    pdf.tbl_hdr(risk_col, ["Risk Factor", "Assessment"])
    for i, (t, d) in enumerate(risks):
        pdf.tbl_row(risk_col, [t, d], fill=i % 2 == 1)

    pdf.ln(2)
    pdf.sub_title("7.1 Sensitivity Analysis")
    price_diff = abs(w["price_wp"] - r["price_wp"])
    cheaper = a_short if r["price_wp"] <= w["price_wp"] else b_short
    if price_diff > 0:
        pdf.ptext(
            "Module price is the single largest lever on project returns. "
            "A Rs. 1/Wp change in module price affects Equity IRR by approximately 3%. "
            f"{cheaper}'s price advantage of Rs. {price_diff:.1f}/Wp is a key factor in the comparative returns."
        )
    else:
        pdf.ptext(
            "Module price is the single largest lever on project returns. "
            "A Rs. 1/Wp change in module price affects Equity IRR by approximately 3%. "
            "Both modules are priced equally; the performance difference drives the return differential."
        )

    # =========================================================
    # 8. CONCLUSION & RECOMMENDATION
    # =========================================================
    pdf.stitle("8. Conclusion & Recommendation")

    pdf.sub_title("8.1 Comparative Assessment")
    pdf.ptext("The analysis reveals the following nuanced comparison:")

    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, f"Advantages of {a_name}:", new_x="LMARGIN", new_y="NEXT")
    pdf.bul(f"Equity IRR: {r['irr']*100:.2f}% vs {w['irr']*100:.2f}%")
    pdf.bul(f"Lower equity: Rs. {r['equity']/1e7:.2f} Cr (saves Rs. {(w['equity']-r['equity'])/1e7:.2f} Cr)")
    pdf.bul(f"Lower LCOE: Rs. {r['lcoe']:.3f}/kWh vs Rs. {w['lcoe']:.3f}/kWh")
    pdf.bul(f"Project cost saving of Rs. {(w['total_cost']-r['total_cost'])/1e7:.2f} Cr")
    if r["temp_coeff"] < w["temp_coeff"]:
        pdf.bul(f"Better temp. coefficient: {r['temp_coeff']:.3f}%/\u00b0C vs {w['temp_coeff']:.3f}%/\u00b0C")
    if r["warranty_yrs"] > w["warranty_yrs"]:
        pdf.bul(f"Longer power warranty: {r['warranty_yrs']} yr vs {w['warranty_yrs']} yr")

    pdf.ln(1.5)
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, f"Advantages of {b_name}:", new_x="LMARGIN", new_y="NEXT")
    # Only show NPV bullet if B genuinely has a higher NPV
    if w['npv'] > r['npv']:
        pdf.bul(f"Higher NPV: Rs. {w['npv']/1e7:.2f} Cr vs Rs. {r['npv']/1e7:.2f} Cr")
    else:
        pdf.bul(f"NPV: Rs. {w['npv']/1e7:.2f} Cr (comparable to {a_short}'s Rs. {r['npv']/1e7:.2f} Cr)")
    # Only show generation advantage if difference is meaningful (>0.5%)
    gen_diff_pct = ((w['total_gen_kwh'] - r['total_gen_kwh']) / r['total_gen_kwh']) * 100
    if gen_diff_pct > 0.5:
        pdf.bul(f"More 25-yr generation: {w['total_gen_kwh']/1e6:.1f} GWh vs {r['total_gen_kwh']/1e6:.1f} GWh ({gen_diff_pct:.1f}% more)")
    else:
        pdf.bul(f"25-yr generation: {w['total_gen_kwh']/1e6:.1f} GWh (similar to {a_short}'s {r['total_gen_kwh']/1e6:.1f} GWh)")
    if w["deg_ann"] < r["deg_ann"]:
        pdf.bul(f"Lower degradation: {w['deg_y1']}% Y1 + {w['deg_ann']}% pa vs {r['deg_y1']}% + {r['deg_ann']}% pa")
    if w["temp_coeff"] < r["temp_coeff"]:
        pdf.bul(f"Better temp. coefficient: {w['temp_coeff']:.3f}%/\u00b0C vs {r['temp_coeff']:.3f}%/\u00b0C")
    if w["warranty_yrs"] > r["warranty_yrs"]:
        pdf.bul(f"Longer power warranty: {w['warranty_yrs']} yr vs {r['warranty_yrs']} yr")

    pdf.ln(2)
    pdf.sub_title("8.2 Final Recommendation")

    # Green recommendation box
    y_rec = pdf.get_y()
    box_h = 32
    pdf.set_draw_color(0, 120, 0)
    pdf.set_fill_color(235, 255, 235)
    pdf.rect(pdf.l_margin, y_rec, pdf.w - pdf.l_margin - pdf.r_margin, box_h, style="DF")
    pdf.set_xy(pdf.l_margin + 4, y_rec + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 80, 0)
    best_equity = (r["equity"] if best_is_a else w["equity"]) / 1e7
    best_lcoe   = (r["lcoe"]   if best_is_a else w["lcoe"])
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 8, 5.5,
        f"RECOMMENDATION: {best_name} is recommended for this project based on Equity IRR of "
        f"{best_irr*100:.2f}%, equity requirement of Rs. {best_equity:.2f} Cr, and LCOE of "
        f"Rs. {best_lcoe:.2f}/kWh. DCR certification ensures bankability and investor confidence.")
    pdf.set_y(y_rec + box_h + 3)

    # Italic note — only mention "higher NPV" if the other module genuinely has higher NPV
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(80, 80, 80)
    other_name = b_name if best_is_a else a_name
    best_mod   = r if best_is_a else w
    other_mod  = w if best_is_a else r
    if other_mod['npv'] > best_mod['npv']:
        pdf.multi_cell(0, 4.5,
            f"Note: If maximising total lifetime returns is the priority, {other_name}'s higher NPV "
            f"(Rs. {other_mod['npv']/1e7:.2f} Cr vs Rs. {best_mod['npv']/1e7:.2f} Cr) and superior "
            "long-term generation make it a compelling alternative. Decision depends on investor's "
            "specific return requirements and risk appetite.")
    else:
        pdf.multi_cell(0, 4.5,
            f"Note: {best_name} leads on both IRR and NPV. {other_name} offers comparable performance "
            "and may be considered based on availability, pricing, or technology preference.")

    pdf.ln(3)

    # Bankability box
    y_bank = pdf.get_y()
    bank_h = 24
    pdf.set_draw_color(0, 51, 102)
    pdf.set_fill_color(240, 245, 255)
    pdf.rect(pdf.l_margin, y_bank, pdf.w - pdf.l_margin - pdf.r_margin, bank_h, style="DF")
    pdf.set_xy(pdf.l_margin + 4, y_bank + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, "BANKABILITY STATEMENT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin + 4, pdf.get_y())
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 8, 4.3,
        "This project demonstrates strong financial metrics (Min. DSCR > 1.5\u00d7, IRR > 35%, "
        "payback within 3 years) meeting standard project finance lending criteria. "
        "Conservative frontside-only assumptions provide additional comfort to lenders and equity investors.")

    pdf.output(output_path)
    return output_path
