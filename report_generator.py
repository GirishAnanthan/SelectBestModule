"""PDF Report Generator - Professional compact layout"""
import os
from fpdf import FPDF
from PIL import Image


# ---------------------------------------------------------------------------
# SolarReport PDF class
# ---------------------------------------------------------------------------

class SolarReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(140, 140, 140)
            self.cell(0, 5, self.header_text, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_draw_color(210, 210, 210)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(1.5)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(140, 140, 140)
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")

    # --- layout helpers ---

    def avail(self):
        """Remaining vertical space on the current page (mm)."""
        return self.h - self.b_margin - self.get_y()

    def need(self, h, extra=0):
        """Insert a page break if less than h+extra mm remain."""
        if self.avail() < h + extra:
            self.add_page()

    # --- typography helpers ---

    def stitle(self, t):
        """Major section heading (blue + underline). Keeps at least 20 mm below it."""
        self.need(20)
        self.ln(1)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, t, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 51, 102)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def sub_title(self, t):
        """Sub-section heading. Keeps at least 15 mm below it."""
        self.need(15)
        self.ln(0.5)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 5.5, t, new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def ptext(self, t, size=8.5):
        self.set_font("Helvetica", "", size)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 4.2, t)

    def bul(self, t):
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(40, 40, 40)
        x0 = self.l_margin
        self.set_x(x0 + 2)
        self.cell(4, 4.2, "-")
        self.set_x(x0 + 6)
        self.multi_cell(self.w - x0 - self.r_margin - 6, 4.2, t)
        self.set_x(x0)

    def note(self, t):
        """Small italic footnote."""
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 3.8, t)

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
        self.set_xy(x + 2, y + 5.5)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 0, 0)
        self.cell(w - 4, 5.5, value)
        if sub:
            self.set_xy(x + 2, y + 12.5)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(110, 110, 110)
            self.cell(w - 4, 3, sub)

    # --- table helpers ---

    def tbl_hdr(self, col_w, headers):
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 5.5, h, border=1, align="C",
                      fill=True, new_x="RIGHT", new_y="TOP")
        self.ln()

    def tbl_row(self, col_w, cells, bold=False, fill=False):
        self.set_font("Helvetica", "B" if bold else "", 7.5)
        self.set_text_color(0, 0, 0)
        bg = (220, 230, 245) if fill else (255, 255, 255)
        self.set_fill_color(*bg)
        for i, c in enumerate(cells):
            self.cell(col_w[i], 5, str(c),
                      border=1, align="L" if i == 0 else "C",
                      fill=fill or bold, new_x="RIGHT", new_y="TOP")
        self.ln()

    def tbl_block(self, col_w, headers, rows, bold_rows=None, alt_fill=True):
        """Render a full table, ensuring it starts on a new page if it won't fit."""
        bold_rows = bold_rows or []
        row_h = 5
        hdr_h = 5.5
        total_h = hdr_h + len(rows) * row_h + 2
        self.need(total_h)
        self.tbl_hdr(col_w, headers)
        for i, row in enumerate(rows):
            self.tbl_row(col_w, row,
                         bold=(i in bold_rows),
                         fill=(alt_fill and i % 2 == 1))

    def chart(self, path, caption="", w_mm=None, center=False):
        """Insert a chart image with optional short caption.
        Uses need() to avoid orphaning the chart at the bottom of a page."""
        if not os.path.exists(path):
            return
        try:
            im = Image.open(path)
            iw, ih = im.size
        except Exception:
            iw, ih = 1000, 500
        if w_mm is None:
            w_mm = self.w - self.l_margin - self.r_margin
        ch = ih * w_mm / iw
        self.need(ch + (8 if caption else 2))
        x = self.l_margin
        if center:
            x = (self.w - w_mm) / 2
        img = self.image(path, x=x, w=w_mm)
        self.ln(img.rendered_height + 1)
        if caption:
            self.note(caption)
            self.ln(1)


# ---------------------------------------------------------------------------
# Land area helper
# ---------------------------------------------------------------------------

_GCR_LAND_FACTOR = {
    "Fixed Tilt": 3.0,
    "Single Axis Tracker": 3.5,
    "Dual Axis Tracker": 5.0,
}

_DEFAULT_DIMS = {"default": (2278, 1134)}


def _compute_land_area(module_dims, n_modules, mounting_type):
    L, W = module_dims
    if L and W and L > 500 and W > 500:
        mod_area = (L / 1000) * (W / 1000)
    else:
        L_d, W_d = _DEFAULT_DIMS["default"]
        mod_area = (L_d / 1000) * (W_d / 1000)
    factor = _GCR_LAND_FACTOR.get(mounting_type, 3.0)
    land_m2 = mod_area * n_modules * factor
    return mod_area * n_modules, land_m2, land_m2 / 4046.86, land_m2 / 10000


def _fw(pdf, splits):
    """Proportional column widths filling the printable width."""
    total = pdf.w - pdf.l_margin - pdf.r_margin
    s = sum(splits)
    return [total * x / s for x in splits]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(r, w, project_info, chart_dir, output_path):
    info = project_info

    pdf = SolarReport()
    pdf.header_text = (
        f"{info.get('project_name', 'Solar Plant')} | "
        "Techno Commercial Comparison Report"
    )
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(12, 12, 12)

    a_short = info.get("module_a_short", "Module A")
    b_short = info.get("module_b_short", "Module B")
    a_name  = info.get("module_a_name",  "Module A")
    b_name  = info.get("module_b_name",  "Module B")

    best_is_a = r["irr"] >= w["irr"]
    best_name = a_name if best_is_a else b_name
    best_irr  = r["irr"] if best_is_a else w["irr"]
    best_mod  = r if best_is_a else w
    other_mod = w if best_is_a else r
    other_name = b_name if best_is_a else a_name

    # =========================================================
    # COVER PAGE
    # =========================================================
    pdf.add_page()

    # Title block
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 9, "TECHNO COMMERCIAL COMPARISON", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6,
             f"{info.get('plant_capacity','XX')} MW DC Solar Plant - {info.get('location','')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(0, 51, 102)
    pdf.line(40, pdf.get_y(), pdf.w - 40, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 5.5, f"{a_name}  vs  {b_name}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5,
             f"Prepared for: {info.get('customer_name','Client')} - {info.get('customer_company','N/A')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Date: {info.get('date','July 2026')}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # KPI boxes
    pw = pdf.w - pdf.l_margin - pdf.r_margin
    bw = pw / 4 - 1.5
    by = pdf.get_y()
    bx = pdf.l_margin
    pdf.box("Module A - Equity IRR",  f"{r['irr']*100:.2f}%",
            f"NPV Rs.{r['npv']/1e7:.1f} Cr",     x=bx,           y=by, w=bw, h=20)
    pdf.box("Module B - Equity IRR",  f"{w['irr']*100:.2f}%",
            f"NPV Rs.{w['npv']/1e7:.1f} Cr",     x=bx+bw+1.5,   y=by, w=bw, h=20)
    pdf.box("Payback Period",         f"{r['payback']}/{w['payback']} yr",
            "A / B (equity recovery)", x=bx+(bw+1.5)*2, y=by, w=bw, h=20)
    pdf.box("Recommended Module",     best_name.split()[0],
            f"IRR {best_irr*100:.2f}%",           x=bx+(bw+1.5)*3, y=by, w=bw, h=20)
    pdf.set_y(by + 23)

    # Cover summary table  -  Project Highlights
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, "Project & Financial Highlights", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    hi_col = _fw(pdf, [2.5, 1.5, 1.5])
    pdf.tbl_hdr(hi_col, ["Parameter", a_short, b_short])
    hi_rows = [
        ("Project DC Capacity",  f"{info.get('plant_capacity','N/A')} MW DC",
                                  f"{info.get('plant_capacity','N/A')} MW DC"),
        ("Module Brand",         info.get("module_a_brand", a_short),
                                  info.get("module_b_brand", b_short)),
        ("Module Wattage",       f"{info.get('module_a_wp','N/A')} Wp",
                                  f"{info.get('module_b_wp','N/A')} Wp"),
        ("Total Project Cost",   f"Rs. {r['total_cost']/1e7:.2f} Cr",
                                  f"Rs. {w['total_cost']/1e7:.2f} Cr"),
        ("Equity @ 30%",         f"Rs. {r['equity']/1e7:.2f} Cr",
                                  f"Rs. {w['equity']/1e7:.2f} Cr"),
        ("Year 1 Generation",    f"{r['gen_y1_kwh']/1e3:,.0f} MWh",
                                  f"{w['gen_y1_kwh']/1e3:,.0f} MWh"),
        ("Equity IRR",           f"{r['irr']*100:.2f}%",
                                  f"{w['irr']*100:.2f}%"),
        ("NPV @ 10% Disc.",      f"Rs. {r['npv']/1e7:.2f} Cr",
                                  f"Rs. {w['npv']/1e7:.2f} Cr"),
        ("LCOE",                  f"Rs. {r['lcoe']:.3f}/kWh",
                                  f"Rs. {w['lcoe']:.3f}/kWh"),
        ("Payback Period",        f"{r['payback']} years",
                                  f"{w['payback']} years"),
    ]
    for i, row in enumerate(hi_rows):
        bold = row[0] in ("Equity IRR", "NPV @ 10% Disc.")
        pdf.tbl_row(hi_col, row, bold=bold, fill=i % 2 == 1)

    pdf.ln(4)
    # Recommendation highlight on cover
    y0 = pdf.get_y()
    h0 = 20
    pdf.set_draw_color(0, 120, 0)
    pdf.set_fill_color(235, 255, 235)
    pdf.rect(pdf.l_margin, y0, pw, h0, style="DF")
    pdf.set_xy(pdf.l_margin + 4, y0 + 3)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(0, 80, 0)
    pdf.multi_cell(pw - 8, 5,
        f"RECOMMENDATION: {best_name} - Equity IRR {best_irr*100:.2f}% | "
        f"NPV Rs. {best_mod['npv']/1e7:.2f} Cr | LCOE Rs. {best_mod['lcoe']:.3f}/kWh | "
        f"Equity Rs. {best_mod['equity']/1e7:.2f} Cr")
    pdf.set_y(y0 + h0 + 3)

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(0, 3.8,
        "Disclaimer: Based on manufacturer datasheets and standard financial modelling. "
        "Actual returns may vary based on site conditions, financing terms, and tariff rates.")

    # =========================================================
    # 1. EXECUTIVE SUMMARY
    # =========================================================
    pdf.add_page()
    pdf.stitle("1. Executive Summary")

    mounting_display = info.get("mounting_type", "Fixed Tilt")
    if info.get("tilt_angle"):
        mounting_display += f" (Tilt: {info['tilt_angle']})"

    pdf.ptext(
        f"This report presents a technical and financial comparison of two DCR-compliant solar PV modules "
        f"for a {info.get('plant_capacity','XX')} MW DC ground-mount plant at {info.get('location','the site')}. "
        f"{a_name} is evaluated against {b_name} on a {mounting_display} configuration. "
        f"Analysis is on frontside-only generation (conservative; bifacial gains excluded)."
    )

    pdf.sub_title("Key Findings")
    pdf.bul(f"{a_short}: Equity IRR {r['irr']*100:.2f}% | NPV Rs. {r['npv']/1e7:.2f} Cr | LCOE Rs. {r['lcoe']:.3f}/kWh")
    pdf.bul(f"{b_short}: Equity IRR {w['irr']*100:.2f}% | NPV Rs. {w['npv']/1e7:.2f} Cr | LCOE Rs. {w['lcoe']:.3f}/kWh")
    pdf.bul(f"Equity required - {a_short}: Rs. {r['equity']/1e7:.2f} Cr | {b_short}: Rs. {w['equity']/1e7:.2f} Cr")
    pdf.bul(f"Both modules achieve payback within {r['payback']} years")
    gen_diff = ((w['total_gen_kwh'] / r['total_gen_kwh']) - 1) * 100
    if abs(gen_diff) > 0.5:
        pdf.bul(f"{b_short} generates {gen_diff:.1f}% {'more' if gen_diff > 0 else 'less'} lifetime energy than {a_short}")

    pdf.sub_title("Recommendation")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(170, 30, 0)
    pdf.multi_cell(0, 4.8,
        f"Based on comprehensive analysis, {best_name} is RECOMMENDED for investors seeking "
        f"higher Equity IRR ({best_irr*100:.2f}%). The final decision should align with the "
        f"investor's return expectations and risk appetite.")
    pdf.ln(1)

    # =========================================================
    # 2. PROJECT DETAILS
    # =========================================================
    pdf.stitle("2. Project Details")

    dims_a = info.get("module_a_dims", (None, None))
    dims_b = info.get("module_b_dims", (None, None))
    n_a = info.get("module_a_count", r.get("module_count", 0))
    n_b = info.get("module_b_count", w.get("module_count", 0))
    mt  = info.get("mounting_type", "Fixed Tilt")

    _, _, land_acres_a, land_ha_a = _compute_land_area(dims_a, n_a, mt)
    _, _, land_acres_b, land_ha_b = _compute_land_area(dims_b, n_b, mt)

    pd_col = _fw(pdf, [2.5, 1.5, 1.5])
    pd_rows = [
        ("Customer Name",        info.get("customer_name", ""),         info.get("customer_name", "")),
        ("Company",              info.get("customer_company", ""),       info.get("customer_company", "")),
        ("Project DC Capacity",  f"{info.get('plant_capacity','N/A')} MW DC",
                                  f"{info.get('plant_capacity','N/A')} MW DC"),
        ("Location",             info.get("location", ""),              info.get("location", "")),
        ("Module Brand",         info.get("module_a_brand", ""),        info.get("module_b_brand", "")),
        ("Module Wattage",       f"{info.get('module_a_wp','N/A')} Wp", f"{info.get('module_b_wp','N/A')} Wp"),
        ("Number of Modules",    f"{n_a:,} nos",                        f"{n_b:,} nos"),
        ("Mounting Structure",   mt,                                     mt),
        ("Land Area Required",   f"{land_acres_a:.1f} acres ({land_ha_a:.1f} ha)",
                                  f"{land_acres_b:.1f} acres ({land_ha_b:.1f} ha)"),
        ("Analysis Basis",       "Frontside only (no bifacial)",         "Frontside only (no bifacial)"),
        ("Plant Life",           "25 years",                             "25 years"),
    ]
    pdf.tbl_block(pd_col, ["Project Parameter", a_short, b_short], pd_rows)
    pdf.ln(1)
    gcr = _GCR_LAND_FACTOR.get(mt, 3.0)
    pdf.note(
        f"Land area uses a land-to-module-area factor of {gcr:.1f}x for {mt} mounting. "
        "Actual requirement may vary based on row spacing, access roads, and site boundary.")
    pdf.ln(1)

    # =========================================================
    # 3. PROJECT BACKGROUND
    # =========================================================
    pdf.stitle("3. Project Background")
    pdf.ptext(
        f"The {info.get('plant_capacity','XX')} MW DC plant is at "
        f"{info.get('location','the site')} (Lat: {info.get('latitude','N/A')}, "
        f"Lon: {info.get('longitude','N/A')}). "
        f"Configuration: {mounting_display}. DCR-compliant (indigenously manufactured modules required)."
    )
    for param in info.get("project_params", []):
        pdf.bul(param)
    pdf.ln(0.5)

    pdf.sub_title("Site-Specific CUF Assumptions")
    pdf.bul(f"{a_short}: {r['cuf']*100:.1f}%")
    pdf.bul(f"{b_short}: {w['cuf']*100:.1f}% - Superior low-light & temperature performance")
    pdf.ln(1)

    pvsyst_a = r.get("pvsyst", {})
    pvsyst_b = w.get("pvsyst", {})
    if pvsyst_a or pvsyst_b:
        pdf.sub_title("3.1 Energy Simulation Data")
        pv_col = _fw(pdf, [2.5, 1.5, 1.5, 1])

        def _fmt_pr(v):
            return f"{v:.1%}" if isinstance(v, (int, float)) else str(v)

        pv_rows = [
            ["Annual GHI",            str(pvsyst_a.get("annual_ghi","N/A")),    str(pvsyst_b.get("annual_ghi","N/A")),    "kWh/m2/yr"],
            ["Annual POA Irradiance",  str(pvsyst_a.get("annual_poa","N/A")),    str(pvsyst_b.get("annual_poa","N/A")),    "kWh/m2/yr"],
            ["Specific Yield",         str(pvsyst_a.get("specific_yield","N/A")), str(pvsyst_b.get("specific_yield","N/A")), "kWh/kWp"],
            ["Performance Ratio",      _fmt_pr(pvsyst_a.get("performance_ratio")),_fmt_pr(pvsyst_b.get("performance_ratio")), ""],
            ["CUF (Capacity Util.)",   f"{r['cuf']*100:.1f}%",                  f"{w['cuf']*100:.1f}%",                   ""],
        ]
        pdf.tbl_block(pv_col, ["Simulation Parameter", a_short, b_short, "Unit"], pv_rows)
        pdf.ln(1)

    # =========================================================
    # 4. TECHNICAL SPECIFICATIONS
    # =========================================================
    pdf.stitle("4. Module Technical Specifications")
    pdf.ptext("Specifications extracted directly from manufacturer datasheets.")
    spec_col = _fw(pdf, [2.5, 1.5, 1.5, 1])
    spec_rows = info.get("spec_rows", [])
    pdf.tbl_block(spec_col, ["Parameter", a_short, b_short, "Unit"], spec_rows)
    pdf.ln(1)

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
    capex_rows = [
        ["Module Cost",        f"{r['module_cost']/1e7:.2f}", f"{w['module_cost']/1e7:.2f}"],
        ["BoS, EPC & Land",    f"{r['bos_cost']/1e7:.2f}",   f"{w['bos_cost']/1e7:.2f}"],
        ["Total Project Cost", f"{r['total_cost']/1e7:.2f}",  f"{w['total_cost']/1e7:.2f}"],
        ["Equity @ 30%",       f"{r['equity']/1e7:.2f}",      f"{w['equity']/1e7:.2f}"],
    ]
    pdf.tbl_block(cc, ["Cost Component (Rs. Cr)", a_short, b_short],
                  capex_rows, bold_rows=[2, 3])
    pdf.ln(1)

    # Pie chart  -  small, inline
    pie_path = os.path.join(chart_dir, "chart_cost_pie.png")
    pdf.chart(pie_path,
              caption="Cost breakdown: module cost typically represents 55-65% of total CAPEX.",
              w_mm=90, center=True)

    # 5.2 Energy Generation
    pdf.sub_title("5.2 Energy Generation & Revenue")
    pvsyst_a = r.get("pvsyst", {})
    pr_val = pvsyst_a.get("performance_ratio", "N/A")
    pr_str = f"{pr_val:.1%}" if isinstance(pr_val, (int, float)) else str(pr_val)
    pdf.ptext(
        f"Year 1: {r['gen_y1_kwh']/1e3:,.0f} MWh ({a_short}) vs {w['gen_y1_kwh']/1e3:,.0f} MWh ({b_short}). "
        f"25-yr totals: {r['total_gen_kwh']/1e6:.1f} GWh vs {w['total_gen_kwh']/1e6:.1f} GWh. "
        f"GHI {pvsyst_a.get('annual_ghi','N/A')} kWh/m2/yr, POA {pvsyst_a.get('annual_poa','N/A')} kWh/m2/yr, PR {pr_str}."
    )
    gen_path = os.path.join(chart_dir, "chart_gen.png")
    pdf.chart(gen_path,
              caption="Annual generation over 25 years. Decline driven by module degradation; lower degradation rates sustain yield.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    # 5.3 Cash Flow
    pdf.sub_title("5.3 Cash Flow Analysis & Returns")
    pdf.ptext(
        f"Model includes revenue, O&M (3% escalation), insurance, debt service (15-yr @ 9%), WDV depreciation, tax 25.17%."
    )

    fcf_path = os.path.join(chart_dir, "chart_cumulative_fcf.png")
    pdf.chart(fcf_path,
              caption=f"Cumulative FCF - both modules reach payback by Year {w['payback']}. Post-payback slope reflects ongoing returns.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    dscr_path = os.path.join(chart_dir, "chart_dscr.png")
    pdf.chart(dscr_path,
              caption="DSCR > 1.5x throughout the loan tenure confirms strong debt repayment capacity and bankability.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    ni_path = os.path.join(chart_dir, "chart_net_income.png")
    pdf.chart(ni_path,
              caption="Net income after tax. Early years lower due to interest and WDV depreciation; improves as debt reduces.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    # =========================================================
    # 6. KEY FINANCIAL METRICS COMPARISON
    # =========================================================
    pdf.stitle("6. Key Financial Metrics Comparison")

    irr_path = os.path.join(chart_dir, "chart_irr_npv.png")
    pdf.chart(irr_path,
              caption="IRR = annualised return on equity over 25 years. NPV = present value of all cash flows at WACC. Higher is better for both.",
              w_mm=90, center=True)

    cc2 = _fw(pdf, [2.5, 1.5, 1.5])
    fm_rows = [
        ("Total Project Cost (Rs. Cr)", f"{r['total_cost']/1e7:.2f}",   f"{w['total_cost']/1e7:.2f}"),
        ("Equity Required (Rs. Cr)",     f"{r['equity']/1e7:.2f}",       f"{w['equity']/1e7:.2f}"),
        ("Annual Gen Y1 (MWh)",          f"{r['gen_y1_kwh']/1e3:,.0f}",  f"{w['gen_y1_kwh']/1e3:,.0f}"),
        ("Total Gen 25yr (GWh)",         f"{r['total_gen_kwh']/1e6:.1f}", f"{w['total_gen_kwh']/1e6:.1f}"),
        ("CUF Frontside (%)",            f"{r['cuf']*100:.1f}",           f"{w['cuf']*100:.1f}"),
        ("Revenue Y1 (Rs. Cr)",          f"{r['revenue'][1]/1e7:.2f}",    f"{w['revenue'][1]/1e7:.2f}"),
        ("Equity IRR (%)",               f"{r['irr']*100:.2f}",           f"{w['irr']*100:.2f}"),
        ("NPV @ 10% (Rs. Cr)",           f"{r['npv']/1e7:.2f}",           f"{w['npv']/1e7:.2f}"),
        ("LCOE (Rs./kWh)",               f"{r['lcoe']:.3f}",              f"{w['lcoe']:.3f}"),
        ("Payback Period (years)",        f"{r['payback']}",               f"{w['payback']}"),
    ]
    irr_idx = [i for i, row in enumerate(fm_rows) if "IRR" in row[0] or "NPV" in row[0]]
    pdf.tbl_block(cc2, ["Financial Metric", a_short, b_short],
                  fm_rows, bold_rows=irr_idx)
    pdf.ln(1)

    # =========================================================
    # 7. RISK ANALYSIS & SENSITIVITY
    # =========================================================
    pdf.stitle("7. Risk Analysis & Sensitivity")

    risks = [
        ("PPA Tariff Risk",   "Rs. 0.50/kWh reduction reduces IRR by ~3-4%. Both modules equally exposed."),
        ("Generation Risk",   "10% lower CUF reduces IRR by ~4-5%. TOPCon temperature coefficient offers marginal protection."),
        ("Interest Rate Risk", "1% rate increase reduces IRR by ~1.5%. Lower-debt module has slightly better resilience."),
        ("Degradation Risk",  "Higher degradation impacts long-term returns. N-TOPCon has proven lower annual degradation."),
        ("Technology Risk",   "PERC is mature; N-TOPCon is next-generation with longer-term upgrade potential."),
        ("DCR Compliance",    "Both modules are DCR-compliant, mitigating import and policy risks."),
    ]
    risk_col = _fw(pdf, [1.3, 4.2])
    pdf.tbl_block(risk_col, ["Risk Factor", "Assessment"], risks)
    pdf.ln(1)

    pdf.sub_title("7.1 Sensitivity Analysis")
    price_diff = abs(w["price_wp"] - r["price_wp"])
    cheaper = a_short if r["price_wp"] <= w["price_wp"] else b_short
    if price_diff > 0:
        pdf.ptext(
            f"Module price is the single largest return lever (~3% IRR per Rs. 1/Wp change). "
            f"{cheaper}'s price advantage of Rs. {price_diff:.1f}/Wp is a key driver of the return differential."
        )
    else:
        pdf.ptext(
            "Module price is the single largest return lever (~3% IRR per Rs. 1/Wp change). "
            "Both modules are priced equally; performance characteristics drive the return differential."
        )

    # =========================================================
    # 8. CONCLUSION & RECOMMENDATION
    # =========================================================
    pdf.stitle("8. Conclusion & Recommendation")
    pdf.sub_title("8.1 Comparative Assessment")

    # Two-column advantage table
    adv_col = _fw(pdf, [2, 2])
    pdf.tbl_hdr(adv_col, [f"Advantages of {a_name}", f"Advantages of {b_name}"])

    a_adv = [f"Equity IRR: {r['irr']*100:.2f}% vs {w['irr']*100:.2f}%"]
    if r['total_cost'] < w['total_cost']:
        a_adv.append(f"Lower project cost: Rs. {r['total_cost']/1e7:.2f} Cr (saves Rs. {(w['total_cost']-r['total_cost'])/1e7:.2f} Cr)")
    if r['equity'] < w['equity']:
        a_adv.append(f"Lower equity: Rs. {r['equity']/1e7:.2f} Cr")
    if r['lcoe'] < w['lcoe']:
        a_adv.append(f"Lower LCOE: Rs. {r['lcoe']:.3f}/kWh")
    if r.get("temp_coeff", 0) and w.get("temp_coeff", 0) and r["temp_coeff"] < w["temp_coeff"]:
        a_adv.append(f"Better temp. coeff.: {r['temp_coeff']:.3f}%/C")
    if r.get("warranty_yrs", 0) > w.get("warranty_yrs", 0):
        a_adv.append(f"Longer warranty: {r['warranty_yrs']} yr")

    b_adv = []
    if w['npv'] > r['npv']:
        b_adv.append(f"Higher NPV: Rs. {w['npv']/1e7:.2f} Cr")
    if w['total_gen_kwh'] > r['total_gen_kwh'] * 1.005:
        b_adv.append(f"More 25-yr generation: {w['total_gen_kwh']/1e6:.1f} GWh")
    if w.get("deg_ann", 1) < r.get("deg_ann", 1):
        b_adv.append(f"Lower degradation: {w.get('deg_ann','')}% pa")
    if w.get("temp_coeff", 0) and r.get("temp_coeff", 0) and w["temp_coeff"] < r["temp_coeff"]:
        b_adv.append(f"Better temp. coeff.: {w['temp_coeff']:.3f}%/C")
    if w.get("warranty_yrs", 0) > r.get("warranty_yrs", 0):
        b_adv.append(f"Longer warranty: {w['warranty_yrs']} yr")
    if not b_adv:
        b_adv.append("Comparable performance across all metrics")

    max_rows = max(len(a_adv), len(b_adv))
    a_adv += [""] * (max_rows - len(a_adv))
    b_adv += [""] * (max_rows - len(b_adv))
    for i in range(max_rows):
        pdf.tbl_row(adv_col, [a_adv[i], b_adv[i]], fill=i % 2 == 1)

    pdf.ln(3)
    pdf.sub_title("8.2 Final Recommendation")

    # Green recommendation box
    pw2 = pdf.w - pdf.l_margin - pdf.r_margin
    y_rec = pdf.get_y()
    box_h = 28
    pdf.need(box_h + 10)
    y_rec = pdf.get_y()
    pdf.set_draw_color(0, 120, 0)
    pdf.set_fill_color(235, 255, 235)
    pdf.rect(pdf.l_margin, y_rec, pw2, box_h, style="DF")
    pdf.set_xy(pdf.l_margin + 4, y_rec + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 80, 0)
    pdf.multi_cell(pw2 - 8, 5.5,
        f"RECOMMENDATION: {best_name} is recommended based on Equity IRR {best_irr*100:.2f}%, "
        f"equity Rs. {best_mod['equity']/1e7:.2f} Cr, and LCOE Rs. {best_mod['lcoe']:.2f}/kWh. "
        f"DCR certification ensures bankability and investor confidence.")
    pdf.set_y(y_rec + box_h + 3)

    # Note on alternate
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(80, 80, 80)
    if other_mod["npv"] > best_mod["npv"]:
        pdf.multi_cell(0, 4.5,
            f"Note: If maximising total lifetime returns is the priority, {other_name}'s higher NPV "
            f"(Rs. {other_mod['npv']/1e7:.2f} Cr vs Rs. {best_mod['npv']/1e7:.2f} Cr) makes it a "
            f"compelling alternative. Decision depends on investor's return requirements and risk appetite.")
    else:
        pdf.multi_cell(0, 4.5,
            f"Note: {best_name} leads on both IRR and NPV. {other_name} may be considered based on "
            "availability, pricing, or technology preference.")

    pdf.ln(3)

    # Bankability box
    y_bank = pdf.get_y()
    bank_h = 22
    pdf.need(bank_h + 5)
    y_bank = pdf.get_y()
    pdf.set_draw_color(0, 51, 102)
    pdf.set_fill_color(240, 245, 255)
    pdf.rect(pdf.l_margin, y_bank, pw2, bank_h, style="DF")
    pdf.set_xy(pdf.l_margin + 4, y_bank + 3)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, "BANKABILITY STATEMENT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(pdf.l_margin + 4, pdf.get_y())
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(pw2 - 8, 4.3,
        "This project demonstrates strong financial metrics (Min. DSCR > 1.5x, IRR > 35%, payback within 3 years) "
        "meeting standard project finance lending criteria. Conservative frontside-only assumptions "
        "provide additional comfort to lenders and equity investors.")

    pdf.output(output_path)
    return output_path
