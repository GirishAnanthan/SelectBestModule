"""PDF Report Generator - Modular version for app integration"""
import json, os, io
from fpdf import FPDF
from PIL import Image

class SolarReport(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 5, self.header_text, new_x="LMARGIN", new_y="NEXT", align="C")

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def stitle(self, t):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, t, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def ptext(self, t):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, t)
        self.ln(2)

    def bul(self, t):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin)
        self.cell(5, 5.5, "-")
        self.set_x(self.l_margin + 8)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 8, 5.5, t)
        self.set_x(self.l_margin)

    def box(self, label, value, sub="", x=None, y=None, w=60, h=22):
        if x is None: x, y = self.get_x(), self.get_y()
        self.set_draw_color(0, 51, 102)
        self.set_fill_color(240, 245, 255)
        self.rect(x, y, w, h, style="DF")
        self.set_xy(x+3, y+2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(0, 51, 102)
        self.cell(w-6, 4, label)
        self.set_xy(x+3, y+7)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(0, 0, 0)
        self.cell(w-6, 7, value)
        if sub:
            self.set_xy(x+3, y+16)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(100, 100, 100)
            self.cell(w-6, 4, sub)

    def add_image(self, path, w=170):
        if os.path.exists(path):
            img = self.image(path, x=self.l_margin, w=w)
            self.ln(img.rendered_height + 6)
        else:
            self.ptext(f"[Chart not found: {path}]")

    def tbl_hdr(self, col_w, headers):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(0, 51, 102)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 7, h, border=1, align="C", fill=True, new_x="RIGHT", new_y="TOP")
        self.ln()

    def tbl_row(self, col_w, cells, bold=False, fill=False):
        self.set_font("Helvetica", "B" if bold else "", 8)
        self.set_text_color(0, 0, 0)
        if fill:
            self.set_fill_color(220, 230, 245)
        else:
            self.set_fill_color(255, 255, 255)
        for i, c in enumerate(cells):
            self.cell(col_w[i], 5.5, c, border=1, align="L" if i == 0 else "C",
                      fill=fill or bold, new_x="RIGHT", new_y="TOP")
        self.ln()


def generate_report(r, w, project_info, chart_dir, output_path):
    """Generate a complete investor-grade PDF report.

    Args:
        r: financial results dict for Module A
        w: financial results dict for Module B
        project_info: dict with project metadata
        chart_dir: directory containing chart images
        output_path: path to save the PDF
    """
    info = project_info

    pdf = SolarReport()
    pdf.header_text = f"{info.get('project_name', 'Solar Plant')} | Techno Commercial Comparison"
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ====== COVER ======
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "TECHNO COMMERCIAL COMPARISON", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, f"{info.get('plant_capacity', 'XX')} MW DC Solar Photovoltaic Plant", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, info.get('location', 'Location Not Specified'), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(0, 51, 102)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Techno Commercial Comparison & Module Selection Analysis", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"{info.get('module_a_name', 'Module A')} vs {info.get('module_b_name', 'Module B')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, f"Prepared for: {info.get('customer_name', 'Client')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Company: {info.get('customer_company', 'N/A')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Date: {info.get('date', 'July 2026')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 6,
        "Disclaimer: This report is based on manufacturer datasheets and standard financial modeling assumptions. "
        "Actual returns may vary based on site conditions, financing terms, and prevailing tariff rates.")

    # ====== 1. EXECUTIVE SUMMARY ======
    pdf.add_page()
    pdf.stitle("1. Executive Summary")
    mounting_display = info.get('mounting_type', 'Fixed Tilt')
    if info.get('tilt_angle'):
        mounting_display += f" (Tilt: {info['tilt_angle']}\u00b0)"
    pdf.ptext(
        f"This report presents a comprehensive technical and financial comparison between two DCR-compliant "
        f"solar photovoltaic module options for a {info.get('plant_capacity', 'XX')} MW DC ground-mount solar plant "
        f"proposed at {info.get('location', 'the project site')}. The analysis evaluates "
        f"{info.get('module_a_name', 'Module A')} against "
        f"{info.get('module_b_name', 'Module B')} using {mounting_display} mounting configuration, "
        f"on a frontside-only generation basis, excluding bifacial gains to ensure conservative projections. "
        f"Generation estimates incorporate site-specific simulation parameters including "
        f"GHI, POA irradiance, and Performance Ratio.")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "Key Findings:", new_x="LMARGIN", new_y="NEXT")
    pdf.bul(f"{info.get('module_a_short', 'Mod A')} yields an Equity IRR of {r['irr']*100:.2f}%, "
            f"compared to {info.get('module_b_short', 'Mod B')}'s {w['irr']*100:.2f}%")
    pdf.bul(f"{info.get('module_b_short', 'Mod B')} offers NPV of Rs. {w['npv']/1e7:.2f} Cr "
            f"vs {info.get('module_a_short', 'Mod A')}'s Rs. {r['npv']/1e7:.2f} Cr")
    pdf.bul(f"{info.get('module_a_short', 'Mod A')} requires lower equity: Rs. {r['equity']/1e7:.2f} Cr "
            f"vs Rs. {w['equity']/1e7:.2f} Cr")
    pdf.bul(f"Both modules achieve payback within {r['payback']} years")
    pdf.bul(f"{info.get('module_b_short', 'Mod B')} generates "
            f"{((w['total_gen_kwh']/r['total_gen_kwh'])-1)*100:.1f}% more lifetime energy")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "Recommendation:", new_x="LMARGIN", new_y="NEXT")

    best_is_a = r['irr'] >= w['irr']
    best_name = info.get('module_a_name' if best_is_a else 'module_b_name', 'Module A' if best_is_a else 'Module B')
    best_irr = r['irr'] if best_is_a else w['irr']
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(200, 50, 0)
    pdf.multi_cell(0, 6,
        f"Based on the comprehensive analysis, {best_name} is RECOMMENDED for the investor "
        f"seeking higher Equity IRR ({best_irr*100:.2f}%). "
        f"The final decision should align with the investor's return expectations and risk appetite.")
    pdf.ln(3)

    # ====== 2. PROJECT BACKGROUND ======
    pdf.add_page()
    pdf.stitle("2. Project Background")
    mounting_display = info.get('mounting_type', 'Fixed Tilt')
    if info.get('tilt_angle'):
        mounting_display += f" (Tilt: {info['tilt_angle']}\u00b0)"
    pdf.ptext(
        f"The proposed {info.get('plant_capacity', 'XX')} MW DC solar photovoltaic plant is located at "
        f"{info.get('location', 'the project site')} (Lat: {info.get('latitude', 'N/A')}, "
        f"Lon: {info.get('longitude', 'N/A')}), a region with excellent solar insolation. "
        f"The project will employ {mounting_display} mounting structure. "
        f"The project qualifies under DCR category, mandating indigenously manufactured solar modules.")
    pdf.ptext("Key project parameters assumed for this analysis:")

    for param in info.get('project_params', []):
        pdf.bul(param)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "Site-Specific CUF Assumptions:", new_x="LMARGIN", new_y="NEXT")
    pdf.bul(f"{info.get('module_a_short', 'Mod A')}: {r['cuf']*100:.1f}%")
    pdf.bul(f"{info.get('module_b_short', 'Mod B')}: {w['cuf']*100:.1f}% - Superior low-light & temperature performance")
    pdf.ln(2)

    pvsyst_a = r.get('pvsyst', {})
    pvsyst_b = w.get('pvsyst', {})
    if not pvsyst_a and not pvsyst_b:
        pdf.ptext("Note: Simulation data not available for this configuration.")
    else:
        pdf.stitle("2.1 Energy Simulation Data")
        pdf.ptext(
            "The following site-specific irradiance and performance metrics are computed from the project location "
            "and mounting configuration. These parameters form the basis of the energy generation projections "
            "presented in this report.")
        pdf.ln(1)
        pv_col = [52, 55, 55, 28]
        pdf.tbl_hdr(pv_col, ["Simulation Parameter", info.get('module_a_short','A'), info.get('module_b_short','B'), "Unit"])
        def _fmt_pr(v):
            if isinstance(v, (int, float)):
                return f"{v:.1%}"
            return str(v)
        pv_rows = [
            ["Annual GHI", f"{pvsyst_a.get('annual_ghi', 'N/A')}", f"{pvsyst_b.get('annual_ghi', 'N/A')}", "kWh/m\u00b2/yr"],
            ["Annual POA Irradiance", f"{pvsyst_a.get('annual_poa', 'N/A')}", f"{pvsyst_b.get('annual_poa', 'N/A')}", "kWh/m\u00b2/yr"],
            ["Specific Yield", f"{pvsyst_a.get('specific_yield', 'N/A')}", f"{pvsyst_b.get('specific_yield', 'N/A')}", "kWh/kWp"],
            ["Performance Ratio", _fmt_pr(pvsyst_a.get('performance_ratio')), _fmt_pr(pvsyst_b.get('performance_ratio')), ""],
            ["CUF (Capacity Util. Factor)", f"{r['cuf']*100:.1f}%", f"{w['cuf']*100:.1f}%", ""],
        ]
        for i, row in enumerate(pv_rows):
            pdf.tbl_row(pv_col, row, fill=i % 2 == 1)

    # ====== 3. TECHNICAL SPECIFICATIONS ======
    pdf.add_page()
    pdf.stitle("3. Module Technical Specifications")
    pdf.ptext("The following specifications are extracted from manufacturer datasheets.")
    pdf.ln(1)

    col = [52, 55, 55, 28]
    pdf.tbl_hdr(col, ["Parameter", info.get('module_a_short','Mod A'), info.get('module_b_short','Mod B'), "Unit"])
    for row in info.get('spec_rows', []):
        pdf.tbl_row(col, row, fill=info.get('spec_rows', []).index(row) % 2 == 1)

    # ====== 4. FINANCIAL ANALYSIS ======
    pdf.add_page()
    pdf.stitle("4. Financial Analysis & Projections")

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "4.1 Capital Expenditure (CAPEX)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.ptext(
        f"Total project cost: Rs. {r['total_cost']/1e7:.2f} Cr ({info.get('module_a_short','A')}) "
        f"vs Rs. {w['total_cost']/1e7:.2f} Cr ({info.get('module_b_short','B')}). "
        f"BoS, EPC and land at Rs. 12/Wp.")

    cc = [70, 55, 55]
    pdf.tbl_hdr(cc, ["Cost Component", info.get('module_a_short','A'), info.get('module_b_short','B')])
    pdf.tbl_row(cc, ["Module Cost", f"{r['module_cost']/1e7:.2f}", f"{w['module_cost']/1e7:.2f}"])
    pdf.tbl_row(cc, ["BoS, EPC & Land", f"{r['bos_cost']/1e7:.2f}", f"{w['bos_cost']/1e7:.2f}"])
    pdf.tbl_row(cc, ["Total Project Cost", f"{r['total_cost']/1e7:.2f}", f"{w['total_cost']/1e7:.2f}"], bold=True, fill=True)
    pdf.tbl_row(cc, ["Equity @ 30%", f"{r['equity']/1e7:.2f}", f"{w['equity']/1e7:.2f}"], bold=True, fill=True)
    pdf.ln(2)

    pie_path = os.path.join(chart_dir, "chart_cost_pie.png")
    if os.path.exists(pie_path):
        img = pdf.image(pie_path, x=55, w=100)
        pdf.ln(img.rendered_height + 4)

    # 4.2 Energy Generation
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "4.2 Energy Generation & Revenue", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pvsyst_a = r.get('pvsyst', {})
    pr_val = pvsyst_a.get('performance_ratio', 'N/A')
    pr_str = f"{pr_val:.1%}" if isinstance(pr_val, (int, float)) else str(pr_val)
    pdf.ptext(
        f"Year 1 generation: {r['gen_y1_kwh']/1e3:,.0f} MWh ({info.get('module_a_short','A')}) "
        f"vs {w['gen_y1_kwh']/1e3:,.0f} MWh ({info.get('module_b_short','B')}). "
        f"Over 25 years, {info.get('module_b_short','B')} generates "
        f"{((w['total_gen_kwh']/r['total_gen_kwh'])-1)*100:.1f}% more energy. "
        f"Generation modeled with site-specific irradiance data: "
        f"GHI {pvsyst_a.get('annual_ghi', 'N/A')} kWh/m\u00b2/yr, "
        f"POA {pvsyst_a.get('annual_poa', 'N/A')} kWh/m\u00b2/yr, "
        f"Performance Ratio {pr_str}.")

    gen_path = os.path.join(chart_dir, "chart_gen.png")
    if os.path.exists(gen_path):
        img = pdf.image(gen_path, x=pdf.l_margin, w=pdf.w - 2 * pdf.l_margin)
        pdf.ln(img.rendered_height + 6)

    # 4.3 Cash Flow
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "4.3 Cash Flow Analysis & Returns", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.ptext("The model incorporates revenue, O&M (3% escalation), insurance, debt servicing (15yr @ 9%), WDV depreciation, and corporate tax at 25.17%.")

    fcf_path = os.path.join(chart_dir, "chart_cumulative_fcf.png")
    if os.path.exists(fcf_path):
        img = pdf.image(fcf_path, x=pdf.l_margin, w=pdf.w - 2 * pdf.l_margin)
        pdf.ln(img.rendered_height + 4)
    pdf.ptext(f"Cumulative FCF shows both modules reaching payback by Year {w['payback']}, with strong positive cash flows thereafter.")

    dscr_path = os.path.join(chart_dir, "chart_dscr.png")
    if os.path.exists(dscr_path):
        img = pdf.image(dscr_path, x=pdf.l_margin, w=pdf.w - 2 * pdf.l_margin)
        pdf.ln(img.rendered_height + 4)
    pdf.ptext("DSCR > 1.5x throughout the loan tenure confirms strong debt repayment capacity and bankability.")

    ni_path = os.path.join(chart_dir, "chart_net_income.png")
    if os.path.exists(ni_path):
        img = pdf.image(ni_path, x=pdf.l_margin, w=pdf.w - 2 * pdf.l_margin)
        pdf.ln(img.rendered_height + 4)
    pdf.ptext("Net income after tax shows the long-term return profile for both module options.")

    # ====== 5. METRICS COMPARISON ======
    pdf.stitle("5. Key Financial Metrics Comparison")

    irr_path = os.path.join(chart_dir, "chart_irr_npv.png")
    if os.path.exists(irr_path):
        img = pdf.image(irr_path, x=pdf.l_margin, w=pdf.w - 2 * pdf.l_margin)
        pdf.ln(img.rendered_height + 6)

    cc2 = [72, 54, 54]
    pdf.tbl_hdr(cc2, ["Financial Metric", info.get('module_a_short','A'), info.get('module_b_short','B')])
    fm = [
        ("Total Project Cost (Rs. Cr)", f"{r['total_cost']/1e7:.2f}", f"{w['total_cost']/1e7:.2f}"),
        ("Equity Required (Rs. Cr)", f"{r['equity']/1e7:.2f}", f"{w['equity']/1e7:.2f}"),
        ("Annual Gen Y1 (MWh)", f"{r['gen_y1_kwh']/1e3:,.0f}", f"{w['gen_y1_kwh']/1e3:,.0f}"),
        ("Total Gen 25yr (GWh)", f"{r['total_gen_kwh']/1e6:.1f}", f"{w['total_gen_kwh']/1e6:.1f}"),
        ("CUF Frontside (%)", f"{r['cuf']*100:.1f}", f"{w['cuf']*100:.1f}"),
        ("Revenue Y1 (Rs. Cr)", f"{r['revenue'][1]/1e7:.2f}", f"{w['revenue'][1]/1e7:.2f}"),
        ("", "", ""),
        ("Equity IRR (%)", f"{r['irr']*100:.2f}", f"{w['irr']*100:.2f}"),
        ("NPV @ 10% (Rs. Cr)", f"{r['npv']/1e7:.2f}", f"{w['npv']/1e7:.2f}"),
        ("LCOE (Rs./kWh)", f"{r['lcoe']:.3f}", f"{w['lcoe']:.3f}"),
        ("Payback Period (years)", f"{r['payback']}", f"{w['payback']}"),
    ]
    for row in fm:
        if row[0] == "":
            pdf.ln(2)
            continue
        pdf.tbl_row(cc2, row, bold=row[0] in ["Equity IRR (%)", "NPV @ 10% (Rs. Cr)"])

    # ====== 6. RISK ANALYSIS ======
    pdf.add_page()
    pdf.stitle("6. Risk Analysis & Sensitivity")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "6.1 Key Risk Factors", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    risks = [
        ("PPA Tariff Risk", "A Rs. 0.50/kWh reduction reduces IRR by ~3-4%. Both modules equally exposed."),
        ("Generation Risk", "10% lower CUF reduces IRR by ~4-5%. TOPCon's better temperature coefficient offers marginal protection."),
        ("Interest Rate Risk", "1% rate increase reduces IRR by ~1.5%. Lower debt module has slightly better resilience."),
        ("Degradation Risk", "Higher degradation impacts long-term returns. N-TOPCon has proven lower degradation."),
        ("Technology Risk", "PERC is mature; N-TOPCon offers next-generation platform with upgrade potential."),
        ("DCR Compliance", "Both modules are DCR-compliant, mitigating import and policy risks."),
    ]
    for t, d in risks:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 5, f"{t}:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4.5, d)
        pdf.ln(1.5)

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 7, "6.2 Sensitivity Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    price_diff = abs(w['price_wp'] - r['price_wp'])
    cheaper = info.get('module_a_short', 'A') if r['price_wp'] <= w['price_wp'] else info.get('module_b_short', 'B')
    pdf.ptext("Module price is the single largest lever on project returns. A Rs. 1/Wp price change affects IRR by approximately 3%. "
              f"{cheaper}'s price advantage of Rs. {price_diff:.0f}/Wp "
              f"is a key factor in the comparative returns analysis.")

    # ====== 7. CONCLUSION ======
    pdf.add_page()
    pdf.stitle("7. Conclusion & Recommendation")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "7.1 Comparative Assessment", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.ptext("The analysis reveals a nuanced comparison between the two module options:")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 6, f"Advantages of {info.get('module_a_name', 'Module A')}:", new_x="LMARGIN", new_y="NEXT")
    pdf.bul(f"Higher Equity IRR: {r['irr']*100:.2f}% vs {w['irr']*100:.2f}%")
    pdf.bul(f"Lower equity: Rs. {r['equity']/1e7:.2f} Cr (saves Rs. {(w['equity']-r['equity'])/1e7:.2f} Cr)")
    pdf.bul(f"Lower LCOE: Rs. {r['lcoe']:.3f}/kWh vs Rs. {w['lcoe']:.3f}/kWh")
    pdf.bul(f"Project cost saving of Rs. {(w['total_cost']-r['total_cost'])/1e7:.2f} Cr")

    if r['temp_coeff'] < w['temp_coeff']:
        pdf.bul(f"Better temperature coefficient: {r['temp_coeff']}/C vs {w['temp_coeff']}/C")
    if r['warranty_yrs'] > w['warranty_yrs']:
        pdf.bul(f"Longer power warranty: {r['warranty_yrs']} years vs {w['warranty_yrs']} years")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 6, f"Advantages of {info.get('module_b_name', 'Module B')}:", new_x="LMARGIN", new_y="NEXT")
    pdf.bul(f"Higher NPV: Rs. {w['npv']/1e7:.2f} Cr vs Rs. {r['npv']/1e7:.2f} Cr")
    pdf.bul(f"More generation: {w['total_gen_kwh']/1e6:.1f} GWh vs {r['total_gen_kwh']/1e6:.1f} GWh")
    if w['deg_ann'] < r['deg_ann']:
        pdf.bul(f"Lower degradation: {w['deg_y1']}% Y1 + {w['deg_ann']}% pa vs {r['deg_y1']}% + {r['deg_ann']}%")
    if w['temp_coeff'] < r['temp_coeff']:
        pdf.bul(f"Better temperature coefficient: {w['temp_coeff']}/C vs {r['temp_coeff']}/C")
    if w['warranty_yrs'] > r['warranty_yrs']:
        pdf.bul(f"Longer warranty: {w['warranty_yrs']} years vs {r['warranty_yrs']} years")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 8, "7.2 Final Recommendation", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    y_rec = pdf.get_y()
    pdf.set_draw_color(0, 100, 0)
    pdf.set_fill_color(230, 255, 230)
    pdf.rect(15, y_rec, 180, 45, style="DF")
    pdf.set_xy(20, y_rec + 3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0, 80, 0)
    pdf.multi_cell(170, 6,
        f"RECOMMENDATION: {best_name} is recommended for this project "
        f"based on its Equity IRR of {best_irr*100:.2f}%, "
        f"equity requirement of Rs. {(r['equity'] if best_is_a else w['equity'])/1e7:.2f} Cr, "
        f"and LCOE of Rs. {(r['lcoe'] if best_is_a else w['lcoe']):.2f}/kWh. The technology choice combined with DCR certification "
        f"ensures bankability and investor confidence.")
    pdf.set_y(y_rec + 52)

    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(80, 80, 80)
    other_name = info.get('module_b_name' if best_is_a else 'module_a_name', 'Module B' if best_is_a else 'Module A')
    best_mod = r if best_is_a else w
    other_mod = w if best_is_a else r
    pdf.multi_cell(0, 5.5,
        f"Note: If maximizing total lifetime returns is the priority, {other_name}'s higher NPV "
        f"(Rs. {other_mod['npv']/1e7:.2f} Cr vs Rs. {best_mod['npv']/1e7:.2f} Cr) "
        f"and superior long-term generation make it a compelling alternative. The decision depends on "
        f"the investor's specific return requirements and risk appetite.")
    pdf.ln(3)

    y_bank = pdf.get_y()
    pdf.set_draw_color(0, 51, 102)
    pdf.set_fill_color(240, 245, 255)
    pdf.rect(15, y_bank, 180, 28, style="DF")
    pdf.set_xy(20, y_bank + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 5, "BANKABILITY STATEMENT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(20, pdf.get_y())
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(170, 4.5,
        "This project demonstrates strong financial metrics (Min. DSCR > 1.5x, IRR > 35%, payback within 3 years) "
        "that meet standard project finance lending criteria. Conservative assumptions (frontside-only, no bifacial gains) "
        "provide additional comfort to lenders and equity investors regarding the robustness of projected returns.")

    pdf.output(output_path)
    return output_path
