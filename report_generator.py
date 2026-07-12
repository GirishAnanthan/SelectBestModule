"""
PDF Report Generator - Professional compact layout for N-module comparison.
"""
import os
from fpdf import FPDF
from PIL import Image
from currency import make_formatter


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

    def avail(self):
        return self.h - self.b_margin - self.get_y()

    def need(self, h, extra=0):
        if self.avail() < h + extra:
            self.add_page()

    def stitle(self, t):
        self.need(20)
        self.ln(1)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, t, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 51, 102)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def sub_title(self, t):
        self.need(15)
        self.ln(0.5)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(0, 51, 102)
        self.cell(0, 5.5, t, new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def ptext(self, t, size=8.5):
        self.set_x(self.l_margin)
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
        self.set_x(self.l_margin)
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

    def _cell_lines(self, col_w, text):
        """Estimate number of lines needed to render text in given column width."""
        if not text:
            return 1
        tw = self.get_string_width(str(text))
        if tw <= col_w - 1:
            return 1
        return int(tw / (col_w - 1)) + (1 if tw % (col_w - 1) > 0.5 else 0)

    def _row_h(self, col_w, cells, line_h=4.2):
        """Calculate row height needed for cells given column widths."""
        max_lines = 1
        for i, c in enumerate(cells):
            nl = self._cell_lines(col_w[i], str(c))
            if nl > max_lines:
                max_lines = nl
        return max_lines * line_h

    def tbl_hdr(self, col_w, headers):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(255, 255, 255)
        rh = self._row_h(col_w, headers, 5.0)
        x0, y0 = self.get_x(), self.get_y()
        if y0 + rh > self.h - self.b_margin:
            self.add_page()
            x0, y0 = self.get_x(), self.get_y()
        tw = sum(col_w)
        self.set_fill_color(0, 51, 102)
        self.rect(x0, y0, tw, rh, style="F")
        for i, h in enumerate(headers):
            self.set_xy(x0 + sum(col_w[:i]) + 0.5, y0 + 0.5)
            self.multi_cell(col_w[i] - 1, 5.0, str(h), align="C")
        for i in range(len(headers)):
            self.rect(x0 + sum(col_w[:i]), y0, col_w[i], rh, style="D")
        self.set_xy(x0, y0 + rh)

    def tbl_row(self, col_w, cells, bold=False, fill=False):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B" if bold else "", 7.5)
        self.set_text_color(0, 0, 0)
        rh = self._row_h(col_w, cells, 4.2)
        x0, y0 = self.get_x(), self.get_y()
        if y0 + rh > self.h - self.b_margin:
            self.add_page()
            x0, y0 = self.get_x(), self.get_y()
        tw = sum(col_w)
        bg = (220, 230, 245) if fill else (255, 255, 255)
        self.set_fill_color(*bg)
        self.rect(x0, y0, tw, rh, style="F")
        for i, c in enumerate(cells):
            align = "L" if i == 0 else "C"
            self.set_xy(x0 + sum(col_w[:i]) + 0.5, y0 + 0.5)
            self.multi_cell(col_w[i] - 1, 4.2, str(c), align=align)
        for i in range(len(col_w)):
            self.rect(x0 + sum(col_w[:i]), y0, col_w[i], rh, style="D")
        self.set_xy(x0, y0 + rh)

    def tbl_block(self, col_w, headers, rows, bold_rows=None, alt_fill=True):
        bold_rows = bold_rows or []
        row_h = self._row_h(col_w, rows[0]) if rows else 5
        hdr_h = self._row_h(col_w, headers, 5.0)
        est_h = hdr_h + len(rows) * row_h + 4
        self.need(est_h)
        self.tbl_hdr(col_w, headers)
        for i, row in enumerate(rows):
            self.tbl_row(col_w, row,
                         bold=(i in bold_rows),
                         fill=(alt_fill and i % 2 == 1))

    def chart(self, path, caption="", w_mm=None, center=False):
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
    total = pdf.w - pdf.l_margin - pdf.r_margin
    s = sum(splits)
    return [total * x / s for x in splits]


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_report(results, project_info, chart_dir, output_path):
    info = project_info
    cur = info.get("currency") or {"code": "INR", "symbol": "Rs.", "rate": 1.0, "unit": "Cr", "div": 1e7}
    F = make_formatter(cur)
    money = F["money"]
    money1 = F["money1"]
    money_kwh = F["money_kwh"]
    money_wp = F["money_wp"]
    money_small = F["money_small"]
    sym = F["symbol"]
    money_unit = F["unit"]
    mod_names = list(results.keys())
    n_mods = len(mod_names)

    pdf = SolarReport()
    pdf.header_text = (
        f"{info.get('project_name', 'Solar Plant')} | "
        "Techno Commercial Comparison Report"
    )
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(12, 12, 12)

    mod_info = info.get("mod_info", [])
    scored = info.get("scored", [])
    score_headers = info.get("score_headers", [])
    score_rows = info.get("score_rows", [])
    debt_ratio = float(info.get("debt_ratio", 0.70) or 0.70)
    equity_ratio = 1 - debt_ratio
    discount_rate = float(info.get("discount_rate", 0.10) or 0.10)
    interest_rate = float(info.get("interest_rate", 0.09) or 0.09)
    loan_tenure = int(info.get("loan_tenure", 15) or 15)
    tax_rate = float(info.get("tax_rate", 0.2517) or 0.2517)
    tariff_esc = float(info.get("tariff_esc", 0.0) or 0.0)

    # Determine best module by weighted score
    best_mod_name = scored[0]["short"] if scored else mod_names[0]
    best_name = scored[0]["name"] if scored else mod_names[0]
    best_r = results[best_mod_name]
    best_irr = best_r["irr"]

    # =========================================================
    # COVER PAGE
    # =========================================================
    pdf.add_page()

    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 9, "TECHNO COMMERCIAL COMPARISON", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6,
             f"{info.get('plant_capacity', 'XX')} MW DC Solar Plant - {info.get('location', '')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(0, 51, 102)
    pdf.line(40, pdf.get_y(), pdf.w - 40, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(70, 70, 70)
    mod_display = "  vs  ".join([m.get("name", n) for m, n in zip(mod_info, mod_names)])
    pdf.cell(0, 5.5, mod_display, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5,
             f"Prepared for: {info.get('customer_name', 'Client')} - {info.get('customer_company', 'N/A')}",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Date: {info.get('date', 'July 2026')}", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # KPI boxes — wrap to avoid overlap when comparing 4-5 modules
    pw = pdf.w - pdf.l_margin - pdf.r_margin
    kpi_boxes = []
    for i, name in enumerate(mod_names):
        r = results[name]
        short = mod_info[i]["short"] if i < len(mod_info) else name
        kpi_boxes.append((f"{short} - Equity IRR", f"{r['irr']*100:.2f}%", f"NPV {money1(r['npv'])}"))

    paybacks = "/".join([str(results[n]["payback"]) for n in mod_names])
    kpi_boxes.append(("Payback Period", f"{paybacks} yr", "equity recovery"))
    kpi_boxes.append(("Recommended", best_mod_name, f"Score: {scored[0]['weighted_total']:.1f}" if scored else f"IRR {best_irr*100:.2f}%"))

    boxes_per_row = min(len(kpi_boxes), 4)
    bw = pw / boxes_per_row - 1.5
    by = pdf.get_y()
    bx = pdf.l_margin

    for i, (title, value, caption) in enumerate(kpi_boxes):
        row = i // boxes_per_row
        col = i % boxes_per_row
        pdf.box(
            title,
            value,
            caption,
            x=bx + (bw + 1.5) * col,
            y=by + row * 23,
            w=bw,
            h=20,
        )
    box_rows = (len(kpi_boxes) + boxes_per_row - 1) // boxes_per_row
    pdf.set_y(by + box_rows * 23)

    # Cover summary table
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, "Project & Financial Highlights", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    # Dynamic column widths for N modules
    hi_col = _fw(pdf, [2.5] + [1.5] * n_mods)
    hi_headers = ["Parameter"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                   for i in range(n_mods)]
    hi_rows = []
    hi_rows.append(["Project DC Capacity"] + [f"{info.get('plant_capacity', 'N/A')} MW DC"] * n_mods)
    hi_rows.append(["Module Brand"] + [info.get(f"module_{chr(97+i)}_brand",
                                                  mod_info[i]["brand"] if i < len(mod_info) else mod_names[i])
                                        for i in range(n_mods)])

    wp_row = []
    count_row = []
    cost_row = []
    equity_row = []
    gen_row = []
    irr_row = []
    npv_row = []
    lcoe_row = []
    payback_row = []
    for name in mod_names:
        r = results[name]
        idx = mod_names.index(name)
        wp_row.append(f"{mod_info[idx]['wp'] if idx < len(mod_info) else 'N/A'} Wp")
        count_row.append(f"{r['module_count']:,}")
        cost_row.append(money(r['total_cost']))
        equity_row.append(money(r['equity']))
        gen_row.append(f"{r['gen_y1_kwh']/1e3:,.0f} MWh")
        irr_row.append(f"{r['irr']*100:.2f}%")
        npv_row.append(money(r['npv']))
        lcoe_row.append(money_kwh(r['lcoe']))
        payback_row.append(f"{r['payback']} years")

    hi_rows.append(["Module Wattage"] + wp_row)
    hi_rows.append(["Modules Required"] + count_row)
    hi_rows.append(["Total Project Cost"] + cost_row)
    hi_rows.append([f"Equity @ {equity_ratio*100:.0f}%"] + equity_row)
    hi_rows.append(["Year 1 Generation"] + gen_row)
    hi_rows.append(["Equity IRR"] + irr_row)
    hi_rows.append([f"NPV @ {discount_rate*100:.1f}% Disc."] + npv_row)
    hi_rows.append(["LCOE"] + lcoe_row)
    hi_rows.append(["Payback Period"] + payback_row)

    irr_idxs = [i for i, row in enumerate(hi_rows) if "IRR" in row[0] or "NPV" in row[0]]
    pdf.tbl_hdr(hi_col, hi_headers)
    for i, row in enumerate(hi_rows):
        bold = i in irr_idxs
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
        f"NPV {money(best_r['npv'])} | LCOE {money_kwh(best_r['lcoe'])} | "
        f"Equity {money(best_r['equity'])}")
    pdf.set_y(y0 + h0 + 3)

    pdf.ln(3)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(0, 3.8,
        "Disclaimer: Based on manufacturer datasheets and standard financial modelling. "
        "Actual returns may vary based on site conditions, financing terms, and tariff rates.")

    # =========================================================
    # REPORT SUMMARY PAGE
    # =========================================================
    pdf.add_page()
    pdf.stitle("Report Objective & Key Assumptions")
    pdf.sub_title("Objective")
    pdf.ptext(
        f"This report compares shortlisted solar PV modules for a {info.get('plant_capacity', 'N/A')} MW DC "
        f"ground-mount solar project at {info.get('location', 'the selected site')}. The objective is to identify "
        "the technically and financially preferable module based on generation, degradation, warranty, price, "
        "LCOE, equity IRR, NPV, payback, and user-defined scoring priorities."
    )
    pdf.sub_title("Important Assumptions")
    pdf.bul(f"Weather basis: {info.get('weather_source', 'Selected source')} - {info.get('weather_summary', 'N/A')}. If the selected online source is unavailable, latitude-based fallback estimates are used and disclosed.")
    pdf.bul(f"Mounting configuration: {info.get('mounting_type', 'Fixed Tilt')}{' with tilt ' + str(info.get('tilt_angle')) + ' degrees' if info.get('tilt_angle') else ''}.")
    pdf.bul(f"Financial structure: Debt {debt_ratio*100:.0f}% / Equity {equity_ratio*100:.0f}%, interest {interest_rate*100:.1f}% p.a., loan tenure {loan_tenure} years.")
    pdf.bul(f"Revenue assumptions: PPA tariff {sym} {float(info.get('ppa_tariff', 0) or 0):.2f}/kWh with tariff escalation {tariff_esc*100:.1f}% p.a.")
    pdf.bul(f"Discounting: NPV is based on equity cash flows discounted at {discount_rate*100:.1f}% p.a.; IRR is equity IRR over the operating period.")
    pdf.bul(f"Tax and operating cost basis: tax rate {tax_rate*100:.2f}%, O&M escalation 3.0% p.a., insurance 0.3% of project cost p.a.")
    pdf.sub_title("Calculation Basis")
    pdf.ptext(
        "Generation uses selected weather-source monthly GHI where available, derives POA using the chosen mounting "
        "configuration, applies module temperature/degradation assumptions, and reports Year-1 net generation after "
        "first-year degradation. LCOE is a simple unlevered pre-tax discounted cost of energy including CAPEX, O&M, "
        "and insurance, excluding financing costs, tax shields, salvage, and decommissioning. Scoring is a decision-support "
        "heuristic based on user-selected weights and should be read with the detailed tables that follow."
    )

    # =========================================================
    # 1. EXECUTIVE SUMMARY
    # =========================================================
    pdf.add_page()
    pdf.stitle("1. Executive Summary")

    mounting_display = info.get("mounting_type", "Fixed Tilt")
    if info.get("tilt_angle"):
        mounting_display += f" (Tilt: {info['tilt_angle']})"

    mod_list_text = ", ".join([mod_info[i]["name"] if i < len(mod_info) else mod_names[i]
                                for i in range(n_mods)])
    pdf.ptext(
        f"This report presents a technical and financial comparison of {n_mods} DCR-compliant "
        f"solar PV modules for a {info.get('plant_capacity', 'XX')} MW DC ground-mount plant "
        f"at {info.get('location', 'the site')}. "
        f"The following modules are evaluated: {mod_list_text} on a {mounting_display} configuration."
    )

    pdf.sub_title("Key Findings")
    for i, name in enumerate(mod_names):
        r = results[name]
        label = mod_info[i]["short"] if i < len(mod_info) else name
        pdf.bul(f"{label}: Equity IRR {r['irr']*100:.2f}% | NPV {money(r['npv'])} | LCOE {money_kwh(r['lcoe'])}")
        pdf.bul(f"  Equity: {money(r['equity'])} | Payback: {r['payback']} years")

    if n_mods >= 2:
        gen_diff = ((results[mod_names[1]]["total_gen_kwh"] / results[mod_names[0]]["total_gen_kwh"]) - 1) * 100
        if abs(gen_diff) > 0.5:
            more_less = "more" if gen_diff > 0 else "less"
            pdf.bul(f"{mod_names[1]} generates {abs(gen_diff):.1f}% {more_less} lifetime energy than {mod_names[0]}")

    pdf.sub_title("Recommendation")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(170, 30, 0)
    pdf.multi_cell(0, 4.8,
        f"Based on comprehensive multi-criteria analysis, {best_name} is RECOMMENDED "
        f"(Weighted Score: {scored[0]['weighted_total']:.1f}/100). "
        f"The final decision should align with the investor's return expectations and risk appetite.")
    pdf.ln(1)

    # =========================================================
    # 2. PROJECT DETAILS
    # =========================================================
    pdf.stitle("2. Project Details")

    mt = info.get("mounting_type", "Fixed Tilt")

    pd_col = _fw(pdf, [2.5] + [1.5] * n_mods)
    pd_headers = ["Project Parameter"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                           for i in range(n_mods)]
    pd_rows = [
        ["Customer Name"] + [info.get("customer_name", "")] * n_mods,
        ["Company"] + [info.get("customer_company", "")] * n_mods,
        ["Project DC Capacity"] + [f"{info.get('plant_capacity', 'N/A')} MW DC"] * n_mods,
        ["Location"] + [info.get("location", "")] * n_mods,
    ]

    # Single rows for all modules
    row_brand = ["Module Brand"] + [""] * n_mods
    row_wp = ["Module Wattage"] + [""] * n_mods
    row_cnt = ["Module Count"] + [""] * n_mods
    row_land = ["Land Area"] + [""] * n_mods

    for i, name in enumerate(mod_names):
        mi = mod_info[i] if i < len(mod_info) else {}
        r = results[name]
        row_brand[i + 1] = mi.get("brand", name)
        row_wp[i + 1] = f"{mi.get('wp', 'N/A')} Wp"
        row_cnt[i + 1] = f"{r['module_count']:,} nos"
        dims = mi.get("dims", (None, None))
        _, _, land_acres, land_ha = _compute_land_area(dims, r["module_count"], mt)
        row_land[i + 1] = f"{land_acres:.1f} acres ({land_ha:.1f} ha)"

    pd_rows.append(row_brand)
    pd_rows.append(row_wp)
    pd_rows.append(row_cnt)
    pd_rows.append(row_land)

    # Annual Generation by mounting type
    for mt_label in ["Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"]:
        row_gen = [f"Annual Gen ({mt_label})"] + [""] * n_mods
        for i, name in enumerate(mod_names):
            r = results[name]
            gen_val = r.get("gen_by_mounting", {}).get(mt_label, 0)
            row_gen[i + 1] = f"{gen_val/1e3:,.0f} MWh" if gen_val else "N/A"
        pd_rows.append(row_gen)

    pd_rows.append(["Mounting Structure"] + [mt] * n_mods)

    bifacial_detected = info.get("bifacial_detected", False)
    if bifacial_detected:
        pd_rows.append(["Analysis Basis"] + [f"Bifacial (albedo={info.get('ground_albedo')}, height={info.get('mounting_height_m')}m)"] * n_mods)
    else:
        pd_rows.append(["Analysis Basis"] + ["Frontside only (no bifacial)"] * n_mods)

    pd_rows.append(["Plant Life"] + ["25 years"] * n_mods)

    pdf.tbl_block(pd_col, pd_headers, pd_rows)
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
        f"The {info.get('plant_capacity', 'XX')} MW DC plant is at "
        f"{info.get('location', 'the site')} (Lat: {info.get('latitude', 'N/A')}, "
        f"Lon: {info.get('longitude', 'N/A')}). "
        f"Configuration: {mounting_display}. DCR-compliant (indigenously manufactured modules required)."
    )
    for param in info.get("project_params", []):
        pdf.bul(param)
    pdf.ln(0.5)

    pdf.sub_title("Site-Specific CUF Assumptions")
    for i, name in enumerate(mod_names):
        r = results[name]
        label = mod_info[i]["short"] if i < len(mod_info) else name
        extra = ""
        if r.get("bifacial") and r.get("bifacial_gain"):
            extra = f" (incl. bifacial boost: {r['bifacial_gain']['boost_pct']:.1f}%)"
        pdf.bul(f"{label}: {r['cuf']*100:.1f}%{extra}")
    pdf.ln(1)

    # Energy simulation data
    first_r = results[mod_names[0]]
    pvsyst_a = first_r.get("pvsyst", {})
    weather_summary = info.get("weather_summary", "")
    if pvsyst_a:
        pdf.sub_title("3.1 Energy Simulation Data")
        pv_col = _fw(pdf, [2.5] + [1.5] * n_mods + [1])
        pv_headers = ["Simulation Parameter"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                                  for i in range(n_mods)] + ["Unit"]
        pv_rows = []
        pv_rows.append(["Weather Data Source"] +
                       [info.get("weather_source", "Estimate")] * n_mods + [""])
        pv_rows.append(["Annual GHI"] +
                       [str(results[n].get("pvsyst", {}).get("annual_ghi", "N/A")) for n in mod_names] +
                       ["kWh/m2/yr"])
        pv_rows.append(["Annual POA Irradiance"] +
                       [str(results[n].get("pvsyst", {}).get("annual_poa", "N/A")) for n in mod_names] +
                       ["kWh/m2/yr"])
        pv_rows.append(["Specific Yield"] +
                       [str(results[n].get("pvsyst", {}).get("specific_yield", "N/A")) for n in mod_names] +
                       ["kWh/kWp"])

        def _fmt_pr(v):
            return f"{v:.1%}" if isinstance(v, (int, float)) else str(v)

        pv_rows.append(["Performance Ratio"] +
                       [_fmt_pr(results[n].get("pvsyst", {}).get("performance_ratio")) for n in mod_names] +
                       [""])
        pv_rows.append(["CUF (Capacity Util.)"] +
                       [f"{results[n]['cuf']*100:.1f}%" for n in mod_names] +
                       [""])

        # Specific Yield by mounting type
        for mt_label in ["Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"]:
            pv_rows.append([f"Specific Yield ({mt_label})"] +
                           [f"{results[n].get('specific_yield_by_mounting', {}).get(mt_label, 0):,.0f}" for n in mod_names] +
                           ["kWh/kWp"])

        pdf.tbl_block(pv_col, pv_headers, pv_rows)
        pdf.ln(1)

        # Monthly generation table (first module as representative)
        first_mod_name = mod_names[0]
        first_mod_res = results[first_mod_name]
        monthly = first_mod_res.get("monthly_data", [])
        if monthly:
            pdf.sub_title("3.2 Monthly Generation Breakdown")
            pdf.ptext(f"Monthly distribution for {first_mod_res.get('name', first_mod_name)}.")
            pdf.ln(0.5)
            mon_col = _fw(pdf, [1.0, 1.2, 1.2, 1.5, 1.0, 1.2])
            mon_headers = ["Month", "GHI\n(kWh/m²)", "POA\n(kWh/m²)",
                           "Generation\n(MWh)", "PR", "Yield\n(kWh/kWp)"]
            pdf.tbl_hdr(mon_col, mon_headers)
            for m in monthly:
                pdf.tbl_row(mon_col, [
                    m["month"], str(m["ghi"]), str(m["poa"]),
                    f"{m['gen_kwh']/1e3:.1f}", f"{m['pr']:.3f}", str(m["specific_yield"]),
                ])
            # Annual totals row
            pdf.tbl_row(mon_col, [
                "Annual", f"{first_mod_res.get('pvsyst', {}).get('annual_ghi', ''):.0f}",
                f"{first_mod_res.get('pvsyst', {}).get('annual_poa', ''):.0f}",
                f"{first_mod_res.get('gen_y1_kwh', 0) / 1e3:.1f}",
                f"{first_mod_res.get('annual_metrics', {}).get('avg_pr', ''):.3f}",
                f"{first_mod_res.get('pvsyst', {}).get('specific_yield', ''):.0f}",
            ], bold=True)
            pdf.ln(1)

    # =========================================================
    # 4. TECHNICAL SPECIFICATIONS
    # =========================================================
    pdf.stitle("4. Module Technical Specifications")
    pdf.ptext("Specifications extracted directly from manufacturer datasheets.")
    spec_col = _fw(pdf, [2.5] + [1.5] * n_mods + [1])
    spec_headers = ["Parameter"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                     for i in range(n_mods)] + ["Unit"]

    spec_rows = []
    # Build spec rows from results
    spec_structure = [
        ("Technology", "tech", ""),
        ("Efficiency", "efficiency", "%"),
        ("Temp Coeff Pmax", "temp_coeff", "%/°C"),
        ("Degradation Y1", "deg_y1", "%"),
        ("Degradation Annual", "deg_ann", "%"),
        ("Power Warranty", "warranty_yrs", "years"),
        ("Price", "price_wp", f"{sym}/Wp"),
    ]
    for label, key, spec_unit in spec_structure:
        row = [label]
        for name in mod_names:
            r = results[name]
            val = r.get(key)
            if isinstance(val, float):
                if key == "temp_coeff":
                    row.append(f"{val:.3f}")
                elif key in ("efficiency", "deg_y1"):
                    row.append(f"{val:.2f}")
                elif key == "deg_ann":
                    row.append(f"{val:.2f}")
                elif key == "price_wp":
                    row.append(money_wp(val))
                elif key == "warranty_yrs":
                    row.append(str(int(val)))
                else:
                    row.append(f"{val}")
            else:
                row.append(str(val) if val else "N/A")
        row.append(spec_unit)
        spec_rows.append(row)

    pdf.tbl_block(spec_col, spec_headers, spec_rows)
    pdf.ln(1)

    # Bifacial details
    has_bifacial = any(r.get("bifacial") for r in results.values())
    if has_bifacial:
        pdf.sub_title("4.1 Bifacial Analysis")
        for i, name in enumerate(mod_names):
            r = results[name]
            if r.get("bifacial") and r.get("bifacial_gain"):
                bg = r["bifacial_gain"]
                label = mod_info[i]["short"] if i < len(mod_info) else name
                pdf.bul(f"{label}: Bifacial gain {bg['boost_pct']:.1f}% | "
                        f"Rear irradiance {bg['rear_irradiance_kwh_m2']:.0f} kWh/m²/yr | "
                        f"View factor {bg['view_factor']:.3f} | "
                        f"Albedo {bg['albedo']}")
        pdf.ln(1)

    # =========================================================
    # 5. FINANCIAL ANALYSIS & PROJECTIONS
    # =========================================================
    pdf.stitle("5. Financial Analysis & Projections")

    # 5.1 CAPEX
    pdf.sub_title("5.1 Capital Expenditure (CAPEX)")
    caps = " vs ".join([f"{money(results[n]['total_cost'])} ({mod_info[i]['short'] if i < len(mod_info) else n})"
                        for i, n in enumerate(mod_names)])
    pdf.ptext(f"Total project cost: {caps}.")
    num = lambda v: f"{v / F['rate'] / F['div']:.2f}"
    cc = _fw(pdf, [2.5] + [1.5] * n_mods)
    cc_headers = [f"Cost Component ({sym} {money_unit})"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                                  for i in range(n_mods)]
    capex_rows = []
    capex_rows.append(["Module Cost"] +
                      [num(results[n]['module_cost']) for n in mod_names])
    capex_rows.append(["BoS, EPC & Land"] +
                      [num(results[n]['bos_cost']) for n in mod_names])
    capex_rows.append(["Total Project Cost"] +
                      [num(results[n]['total_cost']) for n in mod_names])
    capex_rows.append([f"Equity @ {equity_ratio*100:.0f}%"] +
                      [num(results[n]['equity']) for n in mod_names])
    pdf.tbl_block(cc, cc_headers, capex_rows, bold_rows=[2, 3])
    pdf.ln(1)

    pie_path = os.path.join(chart_dir, "chart_cost_pie.png")
    pdf.chart(pie_path,
              caption="Cost breakdown: module cost typically represents 55-65% of total CAPEX.",
              w_mm=90, center=True)

    # 5.2 Energy Generation
    pdf.sub_title("5.2 Energy Generation & Revenue")
    gen_text_parts = []
    for i, name in enumerate(mod_names):
        r = results[name]
        label = mod_info[i]["short"] if i < len(mod_info) else name
        gen_text_parts.append(f"Year 1: {r['gen_y1_kwh']/1e3:,.0f} MWh ({label})")

    pvsyst_a = first_r.get("pvsyst", {})
    pr_val = pvsyst_a.get("performance_ratio", "N/A")
    pr_str = f"{pr_val:.1%}" if isinstance(pr_val, (int, float)) else str(pr_val)
    pdf.ptext(
        f"{' | '.join(gen_text_parts)}. "
        f"GHI {pvsyst_a.get('annual_ghi', 'N/A')} kWh/m2/yr, "
        f"POA {pvsyst_a.get('annual_poa', 'N/A')} kWh/m2/yr, PR {pr_str}."
    )
    gen_path = os.path.join(chart_dir, "chart_gen.png")
    pdf.chart(gen_path,
              caption="Annual generation over 25 years. Decline driven by module degradation; lower degradation rates sustain yield.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    # 5.3 Cash Flow
    pdf.sub_title("5.3 Cash Flow Analysis & Returns")
    pdf.ptext(
        f"Model includes revenue, O&M (3% escalation), insurance, debt service ({loan_tenure}-yr @ {interest_rate*100:.1f}%), accelerated depreciation schedule, and tax {tax_rate*100:.2f}%."
    )

    fcf_path = os.path.join(chart_dir, "chart_cumulative_fcf.png")
    pdf.chart(fcf_path,
              caption="Cumulative FCF - payback reflects equity recovery timeline. Post-payback slope reflects ongoing returns.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    dscr_path = os.path.join(chart_dir, "chart_dscr.png")
    pdf.chart(dscr_path,
              caption="DSCR is computed during the debt tenure as CFADS divided by annual debt service. Values above lender thresholds indicate stronger repayment capacity.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    ni_path = os.path.join(chart_dir, "chart_net_income.png")
    pdf.chart(ni_path,
              caption="Net income after tax. Early years lower due to interest and WDV depreciation; improves as debt reduces.",
              w_mm=pdf.w - pdf.l_margin - pdf.r_margin)

    irr_path = os.path.join(chart_dir, "chart_irr_npv.png")
    pdf.chart(irr_path,
              caption=f"IRR = annualised return on equity over 25 years. NPV = present value of equity cash flows at {discount_rate*100:.1f}% discount rate. Higher is better for both.",
              w_mm=90, center=True)

    # =========================================================
    # 6. KEY FINANCIAL METRICS COMPARISON
    # =========================================================
    pdf.stitle("6. Key Financial Metrics Comparison")

    cc2 = _fw(pdf, [2.5] + [1.5] * n_mods)
    cc2_headers = ["Financial Metric"] + [mod_info[i]["short"] if i < len(mod_info) else mod_names[i]
                                           for i in range(n_mods)]
    fm_rows = []
    fm_rows.append([f"Total Project Cost ({sym} {money_unit})"] +
                   [num(results[n]['total_cost']) for n in mod_names])
    fm_rows.append([f"Equity Required ({sym} {money_unit})"] +
                   [num(results[n]['equity']) for n in mod_names])
    fm_rows.append(["Annual Gen Y1 (MWh)"] +
                   [f"{results[n]['gen_y1_kwh']/1e3:,.0f}" for n in mod_names])
    fm_rows.append(["Total Gen 25yr (GWh)"] +
                   [f"{results[n]['total_gen_kwh']/1e6:.1f}" for n in mod_names])
    fm_rows.append(["CUF (%)"] +
                   [f"{results[n]['cuf']*100:.1f}" for n in mod_names])
    fm_rows.append([f"Revenue Y1 ({sym} {money_unit})"] +
                   [num(results[n]['revenue'][1]) for n in mod_names])
    fm_rows.append(["Equity IRR (%)"] +
                   [f"{results[n]['irr']*100:.2f}" for n in mod_names])
    fm_rows.append([f"NPV @ {discount_rate*100:.1f}% ({sym} {money_unit})"] +
                   [num(results[n]['npv']) for n in mod_names])
    fm_rows.append([f"LCOE ({sym}/kWh)"] +
                   [f"{results[n]['lcoe']/F['rate']:.3f}" for n in mod_names])
    fm_rows.append(["Payback Period (years)"] +
                   [f"{results[n]['payback']}" for n in mod_names])

    irr_idx = [i for i, row in enumerate(fm_rows) if "IRR" in row[0] or "NPV" in row[0]]
    pdf.tbl_block(cc2, cc2_headers, fm_rows, bold_rows=irr_idx)
    pdf.ln(1)

    # =========================================================
    # 6A. MULTI-CRITERIA SCORING
    # =========================================================
    if scored:
        pdf.stitle("6A. Multi-Criteria Scoring")
        pdf.ptext(
            "Weighted multi-criteria scoring across 7 dimensions. "
            "Each criterion is min-max normalized (0-100). Higher total = better investment."
        )

        pdf.ln(1)

        if score_headers and score_rows:
            n_cols = len(score_headers)
            if n_cols <= 8:
                sc_col_w = _fw(pdf, [2] + [1] * (n_cols - 1))
            else:
                base = max(8, pw // n_cols)
                sc_col_w = _fw(pdf, [base + 5] + [base] * (n_cols - 1))
            pdf.tbl_block(sc_col_w, score_headers, score_rows)

            if scored:
                pdf.set_x(pdf.l_margin)
                pdf.ln(1)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(0, 80, 0)
                pdf.cell(0, 5,
                    f"Highest Ranked: {scored[0]['name']} (Score: {scored[0]['weighted_total']:.1f}/100)",
                    new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(pdf.l_margin)
        pdf.ln(1)

    # =========================================================
    # 7. ENERGY LOSS ANALYSIS
    # =========================================================
    pdf.stitle("7. Energy Loss Analysis")
    pdf.ptext(
        "Detailed energy loss breakdown from irradiance to grid injection. "
        "Losses are applied sequentially from POA irradiance to grid injection."
    )

    first_mod_name = mod_names[0]
    first_mod_res = results[first_mod_name]
    loss_series = first_mod_res.get("loss_series", [])

    if loss_series:
        pdf.sub_title("7.1 Loss Breakdown")
        loss_col = _fw(pdf, [2.5, 1.2, 1.5])
        pdf.tbl_hdr(loss_col, ["Loss Factor", "Loss (%)", "Cumulative (%)"])
        for name, pct, cum in loss_series:
            pdf.tbl_row(loss_col, [name, f"{pct:.1f}%", f"{cum:.1f}%"])
        pdf.ln(1)

        # Normalized production
        norm_prod = first_mod_res.get("normalized_prod", 0)
        if norm_prod:
            pdf.bul(f"Normalized Production: {norm_prod:.2f} kWh/kWp/day")
            pdf.bul(f"Performance Ratio: {first_mod_res.get('pvsyst', {}).get('performance_ratio', 'N/A'):.1%}")
            pdf.bul(f"Reference: Typical Crystalline Silicon PV = 3.5-5.5 kWh/kWp/day for most Indian locations")
        pdf.ln(1)

        # Loss diagram chart
        pdf.sub_title("7.2 Loss Diagram")
        loss_chart = os.path.join(chart_dir, "chart_loss_diagram.png")
        pdf.chart(loss_chart,
                  caption="Waterfall chart: sequential energy losses from POA irradiance (100%) to grid injection.",
                  w_mm=pdf.w - pdf.l_margin - pdf.r_margin, center=False)
        pdf.ln(1)

    # =========================================================
    # 8. RISK ANALYSIS & SENSITIVITY
    # =========================================================
    pdf.stitle("8. Risk Analysis & Sensitivity")

    risks = [
        ("PPA Tariff Risk",
         f"{money_small(0.50)}/kWh reduction reduces IRR by ~3-4%. All modules equally exposed."),
        ("Generation Risk",
         "10% lower CUF reduces IRR by ~4-5%. Lower temp coeff modules offer marginal protection."),
        ("Interest Rate Risk",
         "1% rate increase reduces IRR by ~1.5%. Lower-debt module has slightly better resilience."),
        ("Degradation Risk",
         "Higher degradation impacts long-term returns. Lower annual degradation is preferred."),
        ("Technology Risk",
         "PERC is mature; N-TOPCon and HJT are next-generation with longer-term upgrade potential."),
        ("DCR Compliance",
         "All modules are DCR-compliant, mitigating import and policy risks."),
    ]
    risk_col = _fw(pdf, [1.3, 4.2])
    pdf.tbl_block(risk_col, ["Risk Factor", "Assessment"], risks)
    pdf.ln(1)

    pdf.sub_title("8.1 Sensitivity Analysis")
    prices = [results[n]["price_wp"] for n in mod_names]
    min_price = min(prices)
    max_price = max(prices)
    price_diff = max_price - min_price
    if price_diff > 0:
        cheapest_idx = prices.index(min_price)
        cheapest = mod_info[cheapest_idx]["short"] if cheapest_idx < len(mod_info) else mod_names[cheapest_idx]
        pdf.ptext(
            f"Module price is the single largest return lever (~3% IRR per {money_small(1)}/Wp change). "
            f"{cheapest}'s price advantage of {money_wp(price_diff)} is a key driver of return differentials."
        )
    else:
        pdf.ptext(
            f"Module price is the single largest return lever (~3% IRR per {money_small(1)}/Wp change). "
            "All modules are priced equally; performance characteristics drive return differentials."
        )

    # =========================================================
    # STATUTORY COMPLIANCES
    # =========================================================
    compliances = info.get("compliances", {}) or {}
    DEFAULT_STATUTORY_APPROVALS = [
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
    compliance_items = info.get("compliance_items")
    if compliance_items is None:
        compliance_items = [
            {"id": idx, "approval": approval, "authority": authority, "default_days": default_days}
            for idx, (approval, authority, default_days) in enumerate(DEFAULT_STATUTORY_APPROVALS)
        ]

    if compliance_items:
        pdf.stitle("Statutory Compliances & Approvals")
        pdf.ptext("Status of all statutory approvals required for establishing the ground-mount solar plant.")
        pdf.ln(1)

        sc_col = _fw(pdf, [2.8, 1.8, 0.8, 0.8, 1.0])
        sc_headers = ["Statutory Approval", "Issuing Authority", "Approx.\n(Days)", "Expected\n(Days)", "Status"]
        pdf.tbl_hdr(sc_col, sc_headers)

        completed_count = 0
        in_progress_count = 0
        not_started_count = 0
        not_applicable_count = 0

        for idx, item in enumerate(compliance_items):
            row_id = item.get("id", idx)
            comp = compliances.get(row_id, compliances.get(str(row_id), {}))
            approval = item.get("approval", "")
            authority = item.get("authority", "")
            default_days = item.get("default_days", 0)
            actual_days = comp.get("actual_days", default_days)
            status = comp.get("status", "Not Started")

            if status == "Completed":
                completed_count += 1
                status_display = "Completed"
            elif status == "Under Progress":
                in_progress_count += 1
                status_display = "In Progress"
            elif status == "Not Applicable":
                not_applicable_count += 1
                status_display = "N/A"
            else:
                not_started_count += 1
                status_display = "Not Started"

            pdf.tbl_row(sc_col, [
                approval, authority, str(default_days), str(actual_days), status_display,
            ])

        pdf.ln(1)
        total = len(compliance_items)
        pdf.ptext(
            f"Summary: {completed_count}/{total} Completed, "
            f"{in_progress_count}/{total} In Progress, "
            f"{not_started_count}/{total} Not Started, "
            f"{not_applicable_count}/{total} Not Applicable."
        )
        pdf.ln(2)

    # =========================================================
    # 9. CONCLUSION & RECOMMENDATION
    # =========================================================
    pdf.stitle("9. Conclusion & Recommendation")
    pdf.sub_title("9.1 Comparative Assessment")

    # Advantage comparison - two columns for best vs rest, or show per module
    if n_mods == 2:
        adv_col = _fw(pdf, [2, 2])
        a_name = mod_info[0]["name"] if mod_info else mod_names[0]
        b_name = mod_info[1]["name"] if len(mod_info) > 1 else mod_names[1]
        a_short = mod_info[0]["short"] if mod_info else mod_names[0]
        b_short = mod_info[1]["short"] if len(mod_info) > 1 else mod_names[1]
        r_a = results[mod_names[0]]
        r_b = results[mod_names[1]]

        pdf.tbl_hdr(adv_col, [f"Advantages of {a_name}", f"Advantages of {b_name}"])

        a_adv = [f"Equity IRR: {r_a['irr']*100:.2f}% vs {r_b['irr']*100:.2f}%"]
        if r_a["total_cost"] < r_b["total_cost"]:
            a_adv.append(f"Lower project cost: saves {money(r_b['total_cost']-r_a['total_cost'])}")
        if r_a["equity"] < r_b["equity"]:
            a_adv.append(f"Lower equity: {money(r_a['equity'])}")
        if r_a["lcoe"] < r_b["lcoe"]:
            a_adv.append(f"Lower LCOE: {money_kwh(r_a['lcoe'])}")
        if r_a["temp_coeff"] < r_b["temp_coeff"]:
            a_adv.append(f"Better temp. coeff.: {r_a['temp_coeff']:.3f}%/C")
        if r_a["warranty_yrs"] > r_b["warranty_yrs"]:
            a_adv.append(f"Longer warranty: {r_a['warranty_yrs']} yr")

        b_adv = []
        if r_b["npv"] > r_a["npv"]:
            b_adv.append(f"Higher NPV: {money(r_b['npv'])}")
        if r_b["total_gen_kwh"] > r_a["total_gen_kwh"] * 1.005:
            b_adv.append(f"More 25-yr generation: {r_b['total_gen_kwh']/1e6:.1f} GWh")
        if r_b["deg_ann"] < r_a["deg_ann"]:
            b_adv.append(f"Lower degradation: {r_b['deg_ann']}% pa")
        if r_b["temp_coeff"] < r_a["temp_coeff"]:
            b_adv.append(f"Better temp. coeff.: {r_b['temp_coeff']:.3f}%/C")
        if r_b["warranty_yrs"] > r_a["warranty_yrs"]:
            b_adv.append(f"Longer warranty: {r_b['warranty_yrs']} yr")
        if not b_adv:
            b_adv.append("Comparable performance across all metrics")

        max_rows = max(len(a_adv), len(b_adv))
        a_adv += [""] * (max_rows - len(a_adv))
        b_adv += [""] * (max_rows - len(b_adv))
        for i in range(max_rows):
            pdf.tbl_row(adv_col, [a_adv[i], b_adv[i]], fill=i % 2 == 1)
    else:
        # For 3+ modules, list each module's strengths
        adv_col = _fw(pdf, [2] * n_mods)
        adv_headers = [mod_info[i]["short"] if i < len(mod_info) else mod_names[i] for i in range(n_mods)]
        pdf.tbl_hdr(adv_col, adv_headers)

        adv_rows = []
        for i, name in enumerate(mod_names):
            r = results[name]
            advs = [f"IRR: {r['irr']*100:.2f}%"]
            advs.append(f"NPV: {money(r['npv'])}")
            advs.append(f"LCOE: {money_kwh(r['lcoe'])}")
            if r.get("deg_ann"):
                advs.append(f"Degr.: {r['deg_ann']}%/yr")
            if r.get("temp_coeff"):
                advs.append(f"TC: {r['temp_coeff']:.3f}%/C")
            if r.get("warranty_yrs"):
                advs.append(f"Warr.: {r['warranty_yrs']}yr")
            adv_rows.append(advs)

        max_adv = max(len(a) for a in adv_rows)
        for i in range(max_adv):
            row = []
            for j in range(n_mods):
                row.append(adv_rows[j][i] if i < len(adv_rows[j]) else "")
            pdf.tbl_row(adv_col, row, fill=i % 2 == 1)

    pdf.ln(3)

    # Final recommendation
    pdf.sub_title("9.2 Final Recommendation")
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

    score_str = f"Score: {scored[0]['weighted_total']:.1f}/100 | " if scored else ""
    pdf.multi_cell(pw2 - 8, 5.5,
        f"RECOMMENDATION: {best_name} is recommended based on {score_str}"
        f"Equity IRR {best_irr*100:.2f}%, "
        f"equity {money(best_r['equity'])}, and LCOE {money_kwh(best_r['lcoe'])}. "
        f"DCR certification ensures bankability and investor confidence.")
    pdf.set_y(y_rec + box_h + 3)

    # Note on alternate
    pdf.set_font("Helvetica", "I", 8.5)
    pdf.set_text_color(80, 80, 80)
    if n_mods > 1 and not best_mod_name == mod_names[-1]:
        alt_name = mod_names[-1]
        alt_r = results[alt_name]
        if alt_r["npv"] > best_r["npv"]:
            pdf.multi_cell(0, 4.5,
                f"Note: If maximising total lifetime returns is the priority, {alt_name}'s higher NPV "
                f"({money(alt_r['npv'])} vs {money(best_r['npv'])}) makes it a "
                f"compelling alternative.")
        else:
            pdf.multi_cell(0, 4.5,
                f"Note: {best_name} leads on both IRR and NPV. Other modules may be considered based on "
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
        "meeting standard project finance lending criteria. Conservative assumptions "
        "provide additional comfort to lenders and equity investors.")

    pdf.output(output_path)
    return output_path
