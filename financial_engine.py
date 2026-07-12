"""
Financial Model Engine - N-Module Solar PV Comparison
Computes IRR, NPV, LCOE, CUF, generation, and generates charts for N modules.
Integrates with weather_data.py for NASA POWER API and scoring.py for rankings.
"""
import numpy as np
import numpy_financial as npf
import json, os, logging

from weather_data import (
    fetch_nasa_power_monthly, fetch_pvgis_monthly,
    compute_annual_solar_metrics,
    adjust_cuf_for_module, compute_bifacial_gain, get_weather_summary,
    compute_monthly_breakdown, compute_energy_losses,
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


def run_analysis(module_list, project_params, chart_dir, weather_data=None, skip_charts=False):
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
        weather_data: optional pre-fetched NASA POWER data (avoids re-fetch)

    Returns:
        (results dict keyed by module short name, chart paths dict)
    """
    n_mods = len(module_list)
    DEP_SCHEDULE = [0.40, 0.20, 0.10] + [0.30 / 7] * 7 + [0] * 15

    # Fetch weather data once for the site
    lat = project_params["latitude"]
    lon = project_params["longitude"]
    weather_source = project_params.get("weather_source", "api")
    solar_metrics = None

    if weather_source == "api" and weather_data is None:
        weather_data = fetch_nasa_power_monthly(lat, lon)
    elif weather_source == "pvgis" and weather_data is None:
        weather_data = fetch_pvgis_monthly(lat, lon)
    if weather_data is not None:
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
    standard_irradiance = 800  # W/m2, standard operating irradiance for NOCT-based temperature adjustment

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
            irradiance_w_m2=standard_irradiance,
        )

        # Bifacial boost
        bifacial_gain = None
        if mod.get("bifacial", False):
            bifacial_gain = compute_bifacial_gain(
                ground_albedo, mounting_height_m, tilt_angle, annual_ghi,
                bifaciality_factor=0.7,
            )
            cuf = round(cuf * (1 + bifacial_gain["boost_pct"] / 100), 4)

        gross_y1_kwh = actual_kw * HRS_PER_YR * cuf
        net_y1_kwh = gross_y1_kwh * (1 - mod["deg_y1_pct"] / 100)
        net_y1_cuf = net_y1_kwh / (actual_kw * HRS_PER_YR) if actual_kw > 0 else 0

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
        tariff_esc = project_params.get("tariff_esc", 0.0)
        for yr in range(1, 26):
            dg = 1 - mod["deg_y1_pct"] / 100
            if yr > 1:
                dg *= (1 - mod["deg_annual_pct"] / 100) ** (yr - 1)

            gen_kwh = gross_y1_kwh * dg
            rev = gen_kwh * project_params["ppa_tariff"] * (1 + tariff_esc) ** (yr - 1)

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
            gross_y1_kwh * (1 - mod["deg_y1_pct"] / 100) * ((1 - mod["deg_annual_pct"] / 100) ** max(0, yr - 1))
            for yr in range(1, 26)
        ])

        irr = npf.irr(fcf_arr)
        if irr is None or (isinstance(irr, float) and np.isnan(irr)):
            irr = 0.0
        npv = npf.npv(project_params["discount_rate"], fcf_arr)
        if npv is None or (isinstance(npv, float) and np.isnan(npv)):
            npv = 0.0

        disc_rate = project_params["discount_rate"]
        discounted_cost = float(total_cost)
        discounted_energy = 0.0
        for yr in range(1, 26):
            dg = 1 - mod["deg_y1_pct"] / 100
            if yr > 1:
                dg *= (1 - mod["deg_annual_pct"] / 100) ** (yr - 1)
            gen_kwh = gross_y1_kwh * dg
            discounted_energy += gen_kwh / (1 + disc_rate) ** yr
            discounted_cost += float(om_arr[yr] + ins_arr[yr]) / (1 + disc_rate) ** yr
        lcoe = discounted_cost / discounted_energy if discounted_energy > 0 else 0.0

        cum = 0
        payback = None
        for yr in range(1, 26):
            cum += fcf_arr[yr]
            if cum >= equity and payback is None:
                payback = yr
                break

        module_specific_yield = net_y1_kwh / actual_kw if actual_kw > 0 else 0
        module_pr = module_specific_yield / solar_metrics["annual_poa"] if solar_metrics["annual_poa"] > 0 else 0

        # Solar simulation metrics
        pvsyst = {
            "annual_ghi": solar_metrics["annual_ghi"],
            "annual_poa": solar_metrics["annual_poa"],
            "specific_yield": round(module_specific_yield, 0),
            "performance_ratio": round(module_pr, 3),
            "optimal_tilt": solar_metrics.get("optimal_tilt"),
        }

        # Monthly generation breakdown
        module_capacity_kw = actual_kw
        monthly_data, annual_metrics = compute_monthly_breakdown(
            weather_data, solar_metrics["annual_ghi"], solar_metrics["annual_poa"],
            {}, net_y1_kwh, net_y1_cuf, module_capacity_kw, latitude=project_params.get("latitude"),
        )

        # Loss breakdown
        loss_series, loss_factors = compute_energy_losses(
            mod.get("temp_coeff_pmax", -0.35),
            mod.get("noct", 43),
            avg_temp, cuf,
            albedo=ground_albedo,
            mounting_type=mounting_type,
            irradiance_w_m2=standard_irradiance,
        )

        # Normalized production (kWh/kWp/day)
        normalized_prod = net_y1_kwh / actual_kw / 365 if actual_kw > 0 else 0

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
            "gen_y1_kwh": float(net_y1_kwh),
            "gross_y1_kwh": float(gross_y1_kwh),
            "total_gen_kwh": float(total_gen),
            "irr": float(irr),
            "npv": float(npv),
            "lcoe": float(lcoe),
            "payback": payback,
            "cuf": round(net_y1_cuf, 4),
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
            "monthly_data": monthly_data,
            "annual_metrics": annual_metrics,
            "loss_series": loss_series,
            "loss_factors": loss_factors,
            "normalized_prod": round(normalized_prod, 2),
        }

    # Generate charts for N modules
    chart_paths = {}
    if not skip_charts:
        currency = project_params.get("currency")
        chart_paths = generate_charts(results, module_list, project_params, chart_dir, currency=currency)

    # Calculate generation for all three mounting types for comparison
    lat = project_params.get("latitude", 10.38)
    lon = project_params.get("longitude", 78.82)
    tilt_angle = project_params.get("tilt_angle")
    for short_name, r in results.items():
        gen_by_mount = {}
        sy_by_mount = {}
        for mt in ["Fixed Tilt", "Single Axis Tracker", "Dual Axis Tracker"]:
            sm = compute_annual_solar_metrics(lat, lon, weather_data, mounting_type=mt, tilt_angle=tilt_angle)
            # Calculate generation using the same module specs but different POA
            actual_kw = r["capacity_mw"] * 1000
            cuf_mt = sm["cuf"]
            gen_mt = actual_kw * HRS_PER_YR * cuf_mt
            sy_mt = sm["specific_yield"]
            gen_by_mount[mt] = float(gen_mt)
            sy_by_mount[mt] = float(sy_mt)
        r["gen_by_mounting"] = gen_by_mount
        r["specific_yield_by_mounting"] = sy_by_mount

    return results, chart_paths


# ---------------------------------------------------------------------------
# Chart generation
# ---------------------------------------------------------------------------

def _hex(color_tuple):
    return "#%02x%02x%02x" % color_tuple


def generate_charts(results, module_list, project_params, chart_dir, currency=None):
    """Generate comparison charts for N modules. Returns dict of chart paths."""
    mod_names = [m["short"] for m in module_list]
    colors = [_hex(c) for c in CHART_COLORS[:len(mod_names)]]
    cur = currency or {"symbol": "Rs.", "rate": 1.0, "unit": "Cr", "div": 1e7}
    sym, rate, unit, div = cur["symbol"], cur["rate"], cur["unit"], cur["div"]
    loan_tenure = int(project_params.get("loan_tenure", 15) or 15)

    series = []
    for name in mod_names:
        r = results[name]
        cum = [sum(r["fcf"][:i + 1]) for i in range(len(r["fcf"]))]
        gen = [0] + [
            r["gen_y1_kwh"] * ((1 - r["deg_ann"] / 100) ** max(0, yr - 1)) / 1e3
            for yr in range(1, 26)
        ]
        ni = [r["net_income"][i] / rate / div for i in range(len(r["net_income"]))]
        dscr = [0] + [
            (r["net_income"][i] + r["interest"][i] + r["depreciation"][i]) / (r["interest"][i] + r["principal"][i])
            if i <= loan_tenure and (r["interest"][i] + r["principal"][i]) > 0 else 0
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
        "Cumulative Free Cash Flow to Equity",
        f"Cumulative FCF ({sym} {unit})",
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

    charts["chart_net_income.png"] = _make_ts_chart(
        [s["ni"] for s in series],
        [s["name"] for s in series],
        [s["color"] for s in series],
        "Annual Net Income After Tax",
        f"Net Income ({sym} {unit})",
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
        f"Project Cost Breakdown (Total {sym} {first['total_cost'] / rate / div:.1f}{unit})",
        os.path.join(chart_dir, "chart_cost_pie.png"),
        sym, rate, div, cur["unit"],
    )

    irr_vals = [results[n]["irr"] * 100 for n in mod_names]
    npv_vals = [results[n]["npv"] / rate / div for n in mod_names]
    charts["chart_irr_npv.png"] = _make_grouped_bar_chart(
        irr_vals, npv_vals,
        mod_names, [s["color"] for s in series],
        [f"Equity IRR (%)", f"NPV ({sym} {unit})"],
        "Financial Metric Comparison",
        os.path.join(chart_dir, "chart_irr_npv.png"),
    )

    # Loss diagram waterfall for each module (first kept for backwards-compat path)
    for name in mod_names:
        mod_res = results[name]
        if mod_res.get("loss_series"):
            charts[f"chart_loss_diagram_{name}.png"] = _make_loss_diagram(
                mod_res["loss_series"],
                mod_res["name"],
                os.path.join(chart_dir, f"chart_loss_diagram_{name}.png"),
            )
    if results[mod_names[0]].get("loss_series"):
        charts["chart_loss_diagram.png"] = charts[f"chart_loss_diagram_{mod_names[0]}.png"]

    return charts


def _make_ts_chart(data_list, names, colors, title, ylabel, fn):
    """Time series line chart for N data series (plotly)."""
    import plotly.graph_objects as go
    import plotly.io as pio
    n_pts = len(data_list[0]) - 1
    years = list(range(1, n_pts + 1))
    fig = go.Figure()
    for idx, data in enumerate(data_list):
        fig.add_trace(go.Scatter(
            x=years, y=data[1:],
            mode="lines+markers",
            name=names[idx],
            line=dict(color=colors[idx], width=2),
            marker=dict(size=4),
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#003366")),
        xaxis=dict(title="Year", gridcolor="#eee", showline=False),
        yaxis=dict(title=ylabel, gridcolor="#eee"),
        template="none",
        width=1000, height=300,
        margin=dict(l=50, r=20, t=45, b=45),
        legend=dict(font=dict(size=10)),
    )
    pio.write_image(fig, fn, format="png")
    return fn


def _make_grouped_bar_chart(group1_vals, group2_vals, names, colors, labels, title, fn):
    """Grouped bar chart with two metric groups (e.g. IRR and NPV) - plotly."""
    import plotly.graph_objects as go
    import plotly.io as pio
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=group1_vals,
        name=labels[0],
        marker=dict(color=colors),
        text=[f"{v:.1f}" for v in group1_vals],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=names, y=group2_vals,
        name=labels[1],
        marker=dict(color="#e67e22"),
        text=[f"{v:.1f}" for v in group2_vals],
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#003366")),
        barmode="group",
        template="none",
        width=800, height=430,
        margin=dict(l=50, r=20, t=45, b=45),
        legend=dict(font=dict(size=10)),
        yaxis=dict(gridcolor="#eee"),
    )
    pio.write_image(fig, fn, format="png")
    return fn


def _make_pie_chart(data, labels, title, fn, sym, rate, div, unit="Cr"):
    """Pie chart of cost breakdown for the first module - plotly."""
    import plotly.graph_objects as go
    import plotly.io as pio
    total = sum(data)
    full_labels = [
        f"{lab}: {sym} {v / rate / div:.1f}{unit} ({v / total * 100:.1f}%)"
        for lab, v in zip(labels, data)
    ]
    fig = go.Figure(go.Pie(
        values=data,
        labels=full_labels,
        textinfo="label+percent",
        marker=dict(colors=["#3498db", "#2ecc71"]),
        textposition="outside",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#003366")),
        template="none",
        width=800, height=430,
        margin=dict(l=45, r=45, t=45, b=45),
        showlegend=False,
    )
    pio.write_image(fig, fn, format="png")
    return fn


def _make_loss_diagram(loss_series, module_name, fn):
    """Waterfall loss diagram from irradiance to grid (plotly)."""
    import plotly.graph_objects as go
    import plotly.io as pio
    labels = ["POA Irradiance"]
    values = [100.0]
    texts = ["100.0%"]
    for name, pct, cumulative in loss_series:
        labels.append(name.replace("\n", " "))
        values.append(-abs(pct))
        texts.append(f"-{abs(pct):.1f}%")
    labels.append("Grid Injection")
    final_val = loss_series[-1][2] if loss_series else 100.0
    values.append(0)
    texts.append(f"{final_val:.1f}%")

    measure = ["absolute"] + ["relative"] * (len(values) - 2) + ["total"]

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=measure,
        x=labels,
        y=values,
        text=texts,
        textposition="outside",
        connector=dict(line=dict(color="gray", width=1, dash="dot")),
        increasing=dict(marker=dict(color="#2ecc71")),
        decreasing=dict(marker=dict(color="#e74c3c")),
        totals=dict(marker=dict(color="#2ecc71")),
    ))
    fig.update_layout(
        title=dict(text=f"Energy Loss Diagram — {module_name}",
                   font=dict(size=12, color="#003366")),
        yaxis=dict(title="Energy (% of POA)", range=[0, 108], gridcolor="#eee"),
        template="none",
        width=1000, height=340,
        margin=dict(l=50, r=20, t=40, b=90),
        showlegend=False,
    )
    pio.write_image(fig, fn, format="png")
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
