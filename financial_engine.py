"""
Financial Model Engine - N-Module Solar PV Comparison
Computes IRR, NPV, LCOE, CUF, generation, and generates charts for N modules.
Integrates with weather_data.py for NASA POWER API and scoring.py for rankings.
"""
import numpy as np
import numpy_financial as npf
import json, os, logging

from weather_data import (
    fetch_nasa_power_monthly, compute_annual_solar_metrics,
    adjust_cuf_for_module, compute_bifacial_gain, get_weather_summary,
)

logger = logging.getLogger(__name__)

HRS_PER_YR = 8760
CHART_COLORS = [
    (41, 128, 185),
    (231, 76, 60),
    (46, 204, 113),
    (243, 156, 18),
    (142, 68, 173),
]


def run_analysis(module_list, project_params, chart_dir):
    """Run complete financial analysis for N module types.

    Args:
        module_list: list of dicts, each with keys:
            name, short, capacity_w, efficiency_pct, temp_coeff_pmax,
            deg_y1_pct, deg_annual_pct, price_per_wp, warranty_yrs,
            technology, [bifacial], [noct], [albedo]
        project_params: dict with keys:
            capacity_mw, latitude, longitude, ppa_tariff, debt_ratio,
            interest_rate, loan_tenure, tax_rate, discount_rate,
            om_per_mw, om_esc, bos_per_w, insurance_rate,
            mounting_type, tilt_angle,
            [weather_source], [ground_albedo], [mounting_height_m]
        chart_dir: directory to save charts

    Returns:
        (results dict keyed by module short name, chart paths dict)
    """
    n_mods = len(module_list)
    DEP_SCHEDULE = [0.40, 0.20, 0.10] + [0.04375] * 7 + [0] * 15

    # Fetch weather data once for the site
    lat = project_params["latitude"]
    lon = project_params["longitude"]
    weather_source = project_params.get("weather_source", "api")
    weather_data = None
    solar_metrics = None

    if weather_source == "api":
        weather_data = fetch_nasa_power_monthly(lat, lon)
        solar_metrics = compute_annual_solar_metrics(
            lat, lon, weather_data,
            project_params.get("mounting_type", "Fixed Tilt"),
            project_params.get("tilt_angle"),
        )
    else:
        solar_metrics = compute_annual_solar_metrics(
            lat, lon, None,
            project_params.get("mounting_type", "Fixed Tilt"),
            project_params.get("tilt_angle"),
        )

    base_cuf = solar_metrics["cuf"]
    annual_ghi = solar_metrics["annual_ghi"]
    avg_temp = solar_metrics["avg_ambient_temp"]
    ghi_avg = annual_ghi / 365 / 1000 if annual_ghi else 5.5

    # Bifacial settings
    ground_albedo = project_params.get("ground_albedo", 0.20)
    mounting_height_m = project_params.get("mounting_height_m", 1.0)
    tilt_angle = project_params.get("tilt_angle", 10)
    mounting_type = project_params.get("mounting_type", "Fixed Tilt")

    results = {}

    for mod in module_list:
        cap_w = mod["capacity_w"]
        project_mw = project_params["capacity_mw"]
        n_modules = int(np.ceil(project_mw * 1e6 / cap_w))
        actual_mw = n_modules * cap_w / 1e6
        actual_kw = actual_mw * 1000

        module_cost = mod["price_per_wp"] * n_modules * cap_w

        ref_modules = int(np.ceil(project_mw * 1e6 / 600))
        fixed_bos_frac = 0.50
        var_bos_frac = 0.50
        bos_adj = fixed_bos_frac + var_bos_frac * (n_modules / ref_modules)
        bos_cost = project_params["bos_per_w"] * n_modules * cap_w * bos_adj
        total_cost = module_cost + bos_cost
        debt = total_cost * project_params["debt_ratio"]
        equity = total_cost * (1 - project_params["debt_ratio"])

        loan_pmt = -npf.pmt(project_params["interest_rate"], project_params["loan_tenure"], debt)

        # Module-specific CUF with temperature adjustment
        cuf = adjust_cuf_for_module(
            base_cuf,
            mod.get("efficiency_pct", 21.0),
            reference_efficiency=21.0,
            temp_coeff=mod.get("temp_coeff_pmax", -0.35),
            noct=mod.get("noct", 43),
            avg_temp=avg_temp,
            ghi_avg=ghi_avg,
        )

        # Bifacial boost
        bifacial_gain = None
        if mod.get("bifacial", False):
            bifacial_gain = compute_bifacial_gain(
                ground_albedo, mounting_height_m, tilt_angle, annual_ghi,
                bifaciality_factor=0.7,
            )
            cuf = round(cuf * (1 + bifacial_gain["boost_pct"] / 100), 4)

        gen_y1_kwh = actual_kw * HRS_PER_YR * cuf

        # 25-year cash flow
        rev_arr = [0]
        om_arr = [0]
        ins_arr = [0]
        depr_arr = [0]
        int_arr = [0]
        prin_arr = [0]
        ni_arr = [0]
        fcf_arr = [-equity]

        bal = debt
        for yr in range(1, 26):
            dg = 1 - mod["deg_y1_pct"] / 100
            if yr > 1:
                dg *= (1 - mod["deg_annual_pct"] / 100) ** (yr - 1)

            gen_kwh = gen_y1_kwh * dg
            rev = gen_kwh * project_params["ppa_tariff"]

            om = project_params["om_per_mw"] * actual_mw * (1 + project_params["om_esc"]) ** (yr - 1)
            ins = total_cost * project_params["insurance_rate"]

            if yr <= project_params["loan_tenure"]:
                interest = bal * project_params["interest_rate"]
                principal = loan_pmt - interest
                bal -= principal
            else:
                interest = 0
                principal = 0

            depr = total_cost * DEP_SCHEDULE[yr - 1]
            ebt = rev - om - ins - interest - depr
            tax = max(0, ebt * project_params["tax_rate"])
            ni = ebt - tax
            fcf = ni + depr - principal

            rev_arr.append(rev)
            om_arr.append(om)
            ins_arr.append(ins)
            depr_arr.append(depr)
            int_arr.append(interest)
            prin_arr.append(principal)
            ni_arr.append(ni)
            fcf_arr.append(fcf)

        total_gen = sum([
            gen_y1_kwh * (1 - mod["deg_y1_pct"] / 100) * ((1 - mod["deg_annual_pct"] / 100) ** max(0, yr - 1))
            for yr in range(1, 26)
        ])

        irr = npf.irr(fcf_arr)
        npv = npf.npv(project_params["discount_rate"], fcf_arr)
        lcoe = total_cost / total_gen

        cum = 0
        payback = None
        for yr in range(1, 26):
            cum += fcf_arr[yr]
            if cum >= equity and payback is None:
                payback = yr
                break

        # PVSyst-style metrics
        pvsyst = {
            "annual_ghi": solar_metrics["annual_ghi"],
            "annual_poa": solar_metrics["annual_poa"],
            "specific_yield": solar_metrics["specific_yield"],
            "performance_ratio": solar_metrics["performance_ratio"],
            "optimal_tilt": solar_metrics.get("optimal_tilt"),
        }

        short_name = mod["short"]
        results[short_name] = {
            "capacity_mw": actual_mw,
            "module_count": n_modules,
            "module_cost": module_cost,
            "bos_cost": bos_cost,
            "total_cost": total_cost,
            "debt": debt,
            "equity": equity,
            "loan_pmt": float(loan_pmt),
            "gen_y1_kwh": float(gen_y1_kwh),
            "total_gen_kwh": float(total_gen),
            "irr": float(irr),
            "npv": float(npv),
            "lcoe": float(lcoe),
            "payback": payback,
            "cuf": cuf,
            "revenue": [float(x) for x in rev_arr],
            "net_income": [float(x) for x in ni_arr],
            "fcf": [float(x) for x in fcf_arr],
            "depreciation": [float(x) for x in depr_arr],
            "interest": [float(x) for x in int_arr],
            "principal": [float(x) for x in prin_arr],
            "om": [float(x) for x in om_arr],
            "insurance": [float(x) for x in ins_arr],
            "tech": mod["technology"],
            "efficiency": mod["efficiency_pct"],
            "price_wp": mod["price_per_wp"],
            "deg_y1": mod["deg_y1_pct"],
            "deg_ann": mod["deg_annual_pct"],
            "temp_coeff": mod["temp_coeff_pmax"],
            "warranty_yrs": mod["warranty_yrs"],
            "pvsyst": pvsyst,
            "mounting_type": mounting_type,
            "bifacial": mod.get("bifacial", False),
            "bifacial_gain": bifacial_gain,
            "name": mod["name"],
            "weather_summary": get_weather_summary(weather_data),
        }

    # Generate charts for N modules
    chart_paths = generate_charts(results, module_list, project_params, chart_dir)

    return results, chart_paths


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def generate_charts(results, module_list, project_params, chart_dir):
    """Generate comparison charts for N modules. Returns dict of chart paths."""
    mod_names = [m["short"] for m in module_list]
    colors = CHART_COLORS[:len(mod_names)]

    series = []
    for name in mod_names:
        r = results[name]
        cum = [sum(r["fcf"][:i + 1]) for i in range(len(r["fcf"]))]
        gen = [0] + [
            r["gen_y1_kwh"] * ((1 - r["deg_y1"] / 100) * ((1 - r["deg_ann"] / 100) ** max(0, yr - 1))) / 1e3
            for yr in range(1, 26)
        ]
        ni = [r["net_income"][i] / 1e7 for i in range(len(r["net_income"]))]
        dscr = [0] + [
            (r["net_income"][i] + r["depreciation"][i]) / (r["interest"][i] + r["principal"][i])
            if i < 16 and (r["interest"][i] + r["principal"][i]) > 0 else 0
            for i in range(1, 26)
        ]
        series.append({
            "name": name,
            "cum_fcf": cum,
            "gen": gen,
            "ni": ni,
            "dscr": dscr,
            "color": colors[len(series)],
        })

    charts = {}

    charts["chart_cumulative_fcf.png"] = _make_ts_chart(
        [s["cum_fcf"] for s in series],
        [s["name"] for s in series],
        [s["color"] for s in series],
        "Cumulative Free Cash Flow to Equity (Rs. Crores)",
        "Cumulative FCF (Rs. Cr)",
        os.path.join(chart_dir, "chart_cumulative_fcf.png"),
    )

    charts["chart_gen.png"] = _make_ts_chart(
        [s["gen"] for s in series],
        [s["name"] for s in series],
        [s["color"] for s in series],
        "Annual Energy Generation (MWh) - 25 Year Horizon",
        "Generation (MWh/yr)",
        os.path.join(chart_dir, "chart_gen.png"),
    )

    charts["chart_net_income.png"] = _make_ts_bar_chart(
        [s["ni"][1:] for s in series],
        [s["name"] for s in series],
        [s["color"] for s in series],
        "Annual Net Income After Tax (Rs. Crores)",
        "Net Income (Rs. Cr)",
        os.path.join(chart_dir, "chart_net_income.png"),
    )

    charts["chart_dscr.png"] = _make_ts_chart(
        [s["dscr"] for s in series],
        [s["name"] for s in series],
        [s["color"] for s in series],
        "Debt Service Coverage Ratio (Debt Tenure Period)",
        "DSCR (x)",
        os.path.join(chart_dir, "chart_dscr.png"),
    )

    first = results[mod_names[0]]
    charts["chart_cost_pie.png"] = _make_pie_chart(
        [first["module_cost"], first["bos_cost"]],
        ["Module Cost", "BoS, EPC & Land"],
        f"Project Cost Breakdown (Total Rs. {first['total_cost'] / 1e7:.1f}Cr)",
        os.path.join(chart_dir, "chart_cost_pie.png"),
    )

    irr_vals = [results[n]["irr"] * 100 for n in mod_names]
    npv_vals = [results[n]["npv"] / 1e7 for n in mod_names]
    charts["chart_irr_npv.png"] = _make_grouped_bar_chart(
        irr_vals, npv_vals,
        mod_names, [s["color"] for s in series],
        ["Equity IRR (%)", "NPV @ 10% (Rs.Cr)"],
        "Financial Metric Comparison",
        os.path.join(chart_dir, "chart_irr_npv.png"),
    )

    return charts


def _make_ts_chart(data_list, names, colors, title, ylabel, fn):
    """Time series line chart for N data series."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1000, 350
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 22)
        lf = ImageFont.truetype("arial.ttf", 16)
        af = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        tf = lf = af = ImageFont.load_default()

    d.text((W // 2 - 250, 10), title, fill=(0, 0, 0), font=tf)
    ML, MR, MT, MB = 110, 60, 60, 80
    CW = W - ML - MR
    CH_ = H - MT - MB

    all_v = []
    for data in data_list:
        all_v.extend(data[1:])
    ymin = min(all_v) * 0.95 if min(all_v) > 0 else 0
    ymax = max(all_v) * 1.05
    yrng = max(ymax - ymin, 0.001)
    n_pts = len(data_list[0]) - 1

    for i in range(5):
        vy = ymin + yrng * i / 4
        py = H - MB - (vy - ymin) / yrng * CH_
        d.line([(ML, py), (W - MR, py)], fill=(220, 220, 220))
        label = f"{vy / 1e7:.1f}" if ylabel != "DSCR (x)" else f"{vy:.2f}"
        d.text((3, py - 8), label, fill=(100, 100, 100), font=af)

    step = max(1, n_pts // 10)
    for yr in range(1, n_pts + 1):
        if yr % step == 0 or yr == 1 or yr == n_pts:
            px = ML + (yr - 1) / (n_pts - 1) * CW
            d.line([(px, H - MB), (px, H - MB + 5)], fill=(100, 100, 100))
            d.text((px - 8, H - MB + 8), str(yr), fill=(100, 100, 100), font=af)

    d.text((ML + CW // 2 - 30, H - 30), "Year", fill=(0, 0, 0), font=lf)
    d.text((5, MT + CH_ // 2 - 40), ylabel, fill=(0, 0, 0), font=lf)

    for idx, data in enumerate(data_list):
        c = colors[idx]
        pts = []
        for i, val in enumerate(data):
            if i == 0:
                continue
            x = ML + (i - 1) / (n_pts - 1) * CW
            y = H - MB - (val - ymin) / yrng * CH_
            pts.append((x, y))
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=c, width=3)
        for pt in pts:
            d.ellipse([pt[0] - 4, pt[1] - 4, pt[0] + 4, pt[1] + 4], fill=c)

    x_leg = ML
    for idx, name in enumerate(names):
        c = colors[idx]
        d.rectangle([(x_leg, H - 30), (x_leg + 14, H - 15)], fill=c)
        d.text((x_leg + 20, H - 33), name, fill=(0, 0, 0), font=lf)
        x_leg += 120

    img.save(fn)
    return fn


def _make_ts_bar_chart(data_list, names, colors, title, ylabel, fn):
    """Grouped bar chart for N time series (e.g. net income)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1000, 350
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 22)
        lf = ImageFont.truetype("arial.ttf", 16)
        af = ImageFont.truetype("arial.ttf", 13)
    except Exception:
        tf = lf = af = ImageFont.load_default()

    d.text((W // 2 - 250, 10), title, fill=(0, 0, 0), font=tf)
    ML, MR, MT, MB = 110, 60, 60, 80
    PW = W - ML - MR
    PH = H - MT - MB

    all_v = []
    for data in data_list:
        all_v.extend(data)
    ymin = min(0, min(all_v)) * 1.1
    ymax = max(all_v) * 1.15 if max(all_v) > 0 else 1
    yrng = max(ymax - ymin, 0.001)
    n = len(data_list[0])
    n_mods = len(data_list)

    for i in range(5):
        vy = ymin + yrng * i / 4
        py = H - MB - (vy - ymin) / yrng * PH
        d.line([(ML, py), (W - MR, py)], fill=(220, 220, 220))
        d.text((3, py - 8), f"{vy:.1f}", fill=(100, 100, 100), font=af)

    zero_y = H - MB - (0 - ymin) / yrng * PH
    d.line([(ML, zero_y), (W - MR, zero_y)], fill=(80, 80, 80), width=2)

    bw = max(4, min(12, PW // (n * (n_mods + 1))))
    gap = max(1, bw // 3)
    gw = n_mods * bw + gap
    total_w = n * gw
    sx = ML + (PW - total_w) / 2

    step = max(1, n // 12)
    for i in range(n):
        xc = sx + i * gw
        yr_label = i + 1
        if yr_label % step == 0 or yr_label == 1 or yr_label == n:
            cx = xc + n_mods * bw / 2
            d.line([(cx, H - MB), (cx, H - MB + 5)], fill=(100, 100, 100))
            d.text((cx - 8, H - MB + 8), str(yr_label), fill=(100, 100, 100), font=af)

        for mod_idx in range(n_mods):
            val = data_list[mod_idx][i]
            offset = mod_idx * (bw + gap // max(1, n_mods - 1))
            val_y = H - MB - (val - ymin) / yrng * PH
            if val >= 0:
                d.rectangle([(xc + offset, val_y), (xc + offset + bw, zero_y)], fill=colors[mod_idx])
            else:
                d.rectangle([(xc + offset, zero_y), (xc + offset + bw, val_y)], fill=colors[mod_idx])

    d.text((ML + PW // 2 - 30, H - 30), "Year", fill=(0, 0, 0), font=lf)
    d.text((5, MT + PH // 2 - 40), ylabel, fill=(0, 0, 0), font=lf)

    x_leg = ML
    for idx, name in enumerate(names):
        d.rectangle([(x_leg, H - 30), (x_leg + 14, H - 15)], fill=colors[idx])
        d.text((x_leg + 20, H - 33), name, fill=(0, 0, 0), font=lf)
        x_leg += 120

    img.save(fn)
    return fn


def _make_grouped_bar_chart(group1_vals, group2_vals, names, colors, labels, title, fn):
    """Grouped bar chart with two metric groups (e.g. IRR and NPV)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 800, 600
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 20)
        lf = ImageFont.truetype("arial.ttf", 14)
        af = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        tf = lf = af = ImageFont.load_default()

    d.text((W // 2 - 200, 10), title, fill=(0, 0, 0), font=tf)
    ML, MR, MT, MB = 110, 50, 55, 100
    CW_ = W - ML - MR
    CH_ = H - MT - MB
    n_mods = len(names)

    all_v = group1_vals + group2_vals
    mx = max(all_v) * 1.2 if max(all_v) > 0 else 1
    mn = min(0, min(all_v))

    n_groups = 2
    bw = min(35, CW_ // (n_groups * (n_mods + 1)))
    gap = max(2, bw // 2)
    gw = n_mods * bw + gap
    total_w = n_groups * gw
    sx = ML + (CW_ - total_w) / 2

    for i in range(5):
        vy = mn + (mx - mn) * i / 4
        py = H - MB - (vy - mn) / (mx - mn) * CH_
        d.line([(ML, py), (W - MR, py)], fill=(220, 220, 220))
        d.text((5, py - 8), f"{vy:.1f}", fill=(100, 100, 100), font=af)

    for g_idx, vals in enumerate([group1_vals, group2_vals]):
        xc = sx + g_idx * gw
        for m_idx in range(n_mods):
            offset = m_idx * (bw + gap // max(1, n_mods - 1))
            h_bar = (vals[m_idx] - mn) / (mx - mn) * CH_
            d.rectangle(
                [(xc + offset, H - MB - h_bar), (xc + offset + bw, H - MB)],
                fill=colors[m_idx],
            )
        d.text((xc - 15 + n_mods * bw / 2, H - MB + 8), labels[g_idx], fill=(0, 0, 0), font=af)

    x_leg = ML
    for idx, name in enumerate(names):
        d.rectangle([(x_leg, H - 30), (x_leg + 14, H - 15)], fill=colors[idx])
        d.text((x_leg + 20, H - 33), name, fill=(0, 0, 0), font=lf)
        x_leg += 120

    img.save(fn)
    return fn


def _make_pie_chart(data, labels, title, fn):
    """Pie chart (unchanged, shows first module cost breakdown)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 800, 650
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 20)
        lf = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        tf = lf = ImageFont.load_default()

    d.text((W // 2 - 200, 10), title, fill=(0, 0, 0), font=tf)
    total = sum(data)
    cx, cy, r = 250, 350, 180
    sa = 0
    palette = [(52, 152, 219), (46, 204, 113)]
    for val, col in zip(data, palette):
        ang = 360 * val / total
        ea = sa + ang
        d.pieslice([cx - r, cy - r, cx + r, cy + r], sa, ea, fill=col, outline=(255, 255, 255))
        sa = ea
    lx, ly = 480, 180
    for lab, col, val in zip(labels, palette, data):
        d.rectangle([(lx, ly), (lx + 22, ly + 22)], fill=col)
        d.text((lx + 30, ly + 2), f"{lab}: Rs.{val / 1e7:.1f}Cr ({val / total * 100:.1f}%)", fill=(0, 0, 0), font=lf)
        ly += 40
    img.save(fn)
    return fn


if __name__ == "__main__":
    mods = [
        {
            "name": "Redren Steorra Mono PERC", "short": "Redren",
            "capacity_w": 600, "efficiency_pct": 21.30,
            "temp_coeff_pmax": -0.35, "deg_y1_pct": 2.0, "deg_annual_pct": 0.55,
            "price_per_wp": 20, "warranty_yrs": 27, "technology": "PERC",
            "bifacial": True, "noct": 43,
        },
        {
            "name": "Waaree BiN-21 N-TOPCon", "short": "Waaree",
            "capacity_w": 615, "efficiency_pct": 22.77,
            "temp_coeff_pmax": -0.30, "deg_y1_pct": 1.0, "deg_annual_pct": 0.40,
            "price_per_wp": 22, "warranty_yrs": 30, "technology": "N-TOPCon",
            "bifacial": False, "noct": 43,
        },
    ]
    proj = {
        "capacity_mw": 19.6, "latitude": 10.38, "longitude": 78.82,
        "ppa_tariff": 4.50, "debt_ratio": 0.70, "interest_rate": 0.09,
        "loan_tenure": 15, "tax_rate": 0.2517, "discount_rate": 0.10,
        "om_per_mw": 180000, "om_esc": 0.03, "bos_per_w": 12.0,
        "insurance_rate": 0.003, "mounting_type": "Fixed Tilt", "tilt_angle": 10,
        "weather_source": "estimate",
    }
    d = os.path.dirname(__file__) or "."
    res, ch = run_analysis(mods, proj, d)
    for k in ["Redren", "Waaree"]:
        v = res[k]
        print(f"{k}: IRR={v['irr']*100:.2f}%, NPV={v['npv']/1e7:.2f}Cr, LCOE={v['lcoe']:.2f}")
    print(f"Charts: {list(ch.keys())}")
    print("Test OK")
