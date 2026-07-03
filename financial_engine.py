"""
Financial Model Engine - 19.6 MW DC Solar Plant
Computes IRR, NPV, LCOE, and generates chart data given module specs and location
"""
import numpy as np
import numpy_financial as npf
import json, os

HRS_PER_YR = 8760

def get_optimal_tilt(latitude):
    """Return the optimal fixed tilt angle for grid-tied systems."""
    return round(0.87 * abs(float(latitude)), 1)


def get_cuf_from_location(latitude, longitude, tech_type="PERC",
                          mounting_type="Fixed Tilt", tilt_angle=None):
    """Estimate CUF based on location, mounting structure and tilt angle.
    Uses a simplified insolation model adjusted for mounting configuration.
    For production, this should use NASA POWER or PVGIS API with TMY data.
    """
    lat = float(latitude)
    cuf_base = 0.19  # base CUF for central India (~20N) fixed tilt

    lat_factor = 1.0 - 0.002 * abs(lat - 20)
    cuf = cuf_base * lat_factor

    if mounting_type == "Fixed Tilt":
        opt_tilt = get_optimal_tilt(lat)
        if tilt_angle is not None:
            tilt = float(tilt_angle)
            penalty = 0.002 * abs(tilt - opt_tilt)
            cuf *= (1 - penalty)
    elif mounting_type == "Single Axis Tracker":
        gain = 0.15 + 0.003 * abs(lat - 10)
        cuf *= (1 + gain)
    elif mounting_type == "Dual Axis Tracker":
        gain = 0.25 + 0.004 * abs(lat - 10)
        cuf *= (1 + gain)

    if tech_type.lower() in ["topcon", "n-type", "n-topcon"]:
        cuf += 0.003
    return round(cuf, 4)


def get_pvsyst_metrics(latitude, longitude, cuf, mounting_type="Fixed Tilt"):
    """Compute PVSyst-style generation metrics for report credibility.
    Returns dict with Annual GHI, POA, Specific Yield, Performance Ratio.
    POA is estimated using latitude-adjusted factors; PR naturally falls
    in the 0.75-0.83 range for well-designed utility-scale plants.
    """
    lat = float(latitude)
    ghi = 2100 - 5 * abs(lat - 10)

    if mounting_type == "Fixed Tilt":
        opt_tilt = get_optimal_tilt(lat)
        poa = ghi * (1.0 + 0.003 * opt_tilt)
    elif mounting_type == "Single Axis Tracker":
        poa = ghi * (1.10 + 0.004 * abs(lat))
    else:
        poa = ghi * (1.15 + 0.005 * abs(lat))

    specific_yield = cuf * 8760
    performance_ratio = cuf * 8760 / poa if poa > 0 else 0

    return {
        "annual_ghi": round(ghi, 0),
        "annual_poa": round(poa, 0),
        "specific_yield": round(specific_yield, 0),
        "performance_ratio": round(performance_ratio, 3),
        "optimal_tilt": round(get_optimal_tilt(lat), 1) if mounting_type == "Fixed Tilt" else None,
    }


def run_analysis(module_a_specs, module_b_specs, project_params, chart_dir):
    """Run complete financial analysis for two module types.

    Args:
        module_a_specs: dict with keys - name, short, capacity_w, efficiency_pct,
                        temp_coeff_pmax, deg_y1_pct, deg_annual_pct, price_per_wp,
                        warranty_yrs, technology
        module_b_specs: same structure
        project_params: dict with - capacity_mw, latitude, longitude, ppa_tariff,
                        debt_ratio, interest_rate, loan_tenure, tax_rate, discount_rate,
                        om_per_mw, om_esc, bos_per_w, insurance_rate
        chart_dir: directory to save charts

    Returns:
        results dict, chart paths
    """
    # Combine modules
    mod_specs = {
        "A": module_a_specs,
        "B": module_b_specs,
    }

    results = {}
    DEP_SCHEDULE = [0.40, 0.20, 0.10] + [0.04375]*7 + [0]*15

    for key, mod in mod_specs.items():
        cap_w = mod['capacity_w']
        project_mw = project_params['capacity_mw']
        n_modules = int(np.ceil(project_mw * 1e6 / cap_w))
        actual_mw = n_modules * cap_w / 1e6
        actual_kw = actual_mw * 1000

        module_cost = mod['price_per_wp'] * n_modules * cap_w
        bos_cost = project_params['bos_per_w'] * n_modules * cap_w
        total_cost = module_cost + bos_cost
        debt = total_cost * project_params['debt_ratio']
        equity = total_cost * (1 - project_params['debt_ratio'])

        loan_pmt = -npf.pmt(project_params['interest_rate'], project_params['loan_tenure'], debt)

        mounting_type = project_params.get('mounting_type', 'Fixed Tilt')
        tilt_angle = project_params.get('tilt_angle', None)
        cuf = get_cuf_from_location(
            project_params['latitude'], project_params['longitude'],
            mod['technology'], mounting_type, tilt_angle
        )
        pvsyst = get_pvsyst_metrics(
            project_params['latitude'], project_params['longitude'],
            cuf, mounting_type
        )
        gen_y1_kwh = actual_kw * HRS_PER_YR * cuf

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
            dg = 1 - mod['deg_y1_pct']/100
            if yr > 1:
                dg *= (1 - mod['deg_annual_pct']/100) ** (yr - 1)

            gen_kwh = gen_y1_kwh * dg
            rev = gen_kwh * project_params['ppa_tariff']

            om = project_params['om_per_mw'] * actual_mw * (1 + project_params['om_esc'])**(yr-1)
            ins = total_cost * project_params['insurance_rate']

            if yr <= project_params['loan_tenure']:
                interest = bal * project_params['interest_rate']
                principal = loan_pmt - interest
                bal -= principal
            else:
                interest = 0
                principal = 0

            depr = total_cost * DEP_SCHEDULE[yr-1]
            ebt = rev - om - ins - interest - depr
            tax = max(0, ebt * project_params['tax_rate'])
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
            gen_y1_kwh * (1 - mod['deg_y1_pct']/100) * ((1 - mod['deg_annual_pct']/100) ** max(0, yr-1))
            for yr in range(1, 26)
        ])

        irr = npf.irr(fcf_arr)
        npv = npf.npv(project_params['discount_rate'], fcf_arr)
        lcoe = total_cost / total_gen

        cum = 0
        payback = None
        for yr in range(1, 26):
            cum += fcf_arr[yr]
            if cum >= equity and payback is None:
                payback = yr
                break

        results[key] = {
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
            # Module specs
            "tech": mod['technology'],
            "efficiency": mod['efficiency_pct'],
            "price_wp": mod['price_per_wp'],
            "deg_y1": mod['deg_y1_pct'],
            "deg_ann": mod['deg_annual_pct'],
            "temp_coeff": mod['temp_coeff_pmax'],
            "warranty_yrs": mod['warranty_yrs'],
            "pvsyst": pvsyst,
            "mounting_type": mounting_type,
        }

    # Generate charts
    chart_paths = generate_charts(results, project_params, chart_dir)

    # Map A->module short name, B->module short name for generic output
    mod_a_name = module_a_specs.get('short', 'Module A')
    mod_b_name = module_b_specs.get('short', 'Module B')
    results["A"]['name'] = mod_a_name
    results["B"]['name'] = mod_b_name
    mapped = {mod_a_name: results["A"], mod_b_name: results["B"]}
    return mapped, chart_paths


def generate_charts(results, project_params, chart_dir):
    """Generate comparison charts. Returns dict of chart paths."""
    r, w = results["A"], results["B"]

    # Compute data series
    cum_r = [sum(r['fcf'][:i+1]) for i in range(len(r['fcf']))]
    cum_w = [sum(w['fcf'][:i+1]) for i in range(len(w['fcf']))]

    gen_r = [0] + [r['gen_y1_kwh'] * ((1-r['deg_y1']/100)*((1-r['deg_ann']/100)**max(0, yr-1)))/1e3 for yr in range(1, 26)]
    gen_w = [0] + [w['gen_y1_kwh'] * ((1-w['deg_y1']/100)*((1-w['deg_ann']/100)**max(0, yr-1)))/1e3 for yr in range(1, 26)]

    ni_r = [r['net_income'][i]/1e7 for i in range(len(r['net_income']))]
    ni_w = [w['net_income'][i]/1e7 for i in range(len(w['net_income']))]

    dscr_r = [0] + [(r['net_income'][i]+r['depreciation'][i])/(r['interest'][i]+r['principal'][i])
                    if i < 16 and (r['interest'][i]+r['principal'][i]) > 0 else 0 for i in range(1,26)]
    dscr_w = [0] + [(w['net_income'][i]+w['depreciation'][i])/(w['interest'][i]+w['principal'][i])
                    if i < 16 and (w['interest'][i]+w['principal'][i]) > 0 else 0 for i in range(1,26)]

    charts = {}

    # 1. Cumulative FCF
    charts['chart_cumulative_fcf.png'] = _make_ts_chart(
        cum_r, cum_w, "Cumulative Free Cash Flow to Equity (Rs. Crores)",
        "Cumulative FCF (Rs. Cr)", os.path.join(chart_dir, "chart_cumulative_fcf.png"))

    # 2. Generation
    charts['chart_gen.png'] = _make_ts_chart(
        gen_r, gen_w, "Annual Energy Generation (MWh) - 25 Year Horizon",
        "Generation (MWh/yr)", os.path.join(chart_dir, "chart_gen.png"))

    # 3. Net Income (bar chart)
    charts['chart_net_income.png'] = _make_ts_bar_chart(
        ni_r[1:], ni_w[1:], "Annual Net Income After Tax (Rs. Crores)",
        "Net Income (Rs. Cr)", os.path.join(chart_dir, "chart_net_income.png"))

    # 4. DSCR
    charts['chart_dscr.png'] = _make_ts_chart(
        dscr_r, dscr_w, "Debt Service Coverage Ratio (Debt Tenure Period)",
        "DSCR (x)", os.path.join(chart_dir, "chart_dscr.png"))

    # 5. Cost pie (Module A as representative)
    charts['chart_cost_pie.png'] = _make_pie_chart(
        [r['module_cost'], r['bos_cost']],
        ["Module Cost", "BoS, EPC & Land"],
        f"Project Cost Breakdown (Total Rs. {r['total_cost']/1e7:.1f}Cr)",
        os.path.join(chart_dir, "chart_cost_pie.png"))

    # 6. IRR/NPV bar
    charts['chart_irr_npv.png'] = _make_bar_chart(
        [r['irr']*100, r['npv']/1e7],
        [w['irr']*100, w['npv']/1e7],
        ["Equity IRR (%)", "NPV @ 10% (Rs.Cr)"],
        "Financial Metric Comparison", os.path.join(chart_dir, "chart_irr_npv.png"))

    return charts


def _make_ts_chart(data_r, data_w, title, ylabel, fn,
                   c1=(41,128,185), c2=(231,76,60)):
    """Generate a time series comparison chart."""
    from PIL import Image, ImageDraw, ImageFont
    W,H = 1000, 600
    img = Image.new('RGB', (W,H), (255,255,255))
    d = ImageDraw.Draw(img)
    try: tf=ImageFont.truetype("arial.ttf", 22); lf=ImageFont.truetype("arial.ttf", 16); af=ImageFont.truetype("arial.ttf", 13)
    except: tf=lf=af=ImageFont.load_default()

    d.text((W//2-250,10), title, fill=(0,0,0), font=tf)
    ML,MR,MT,MB = 110, 60, 60, 80
    CW = W-ML-MR; CH_ = H-MT-MB

    all_v = data_r[1:] + data_w[1:]
    ymin = min(all_v)*0.95 if min(all_v)>0 else 0
    ymax = max(all_v)*1.05
    yrng = max(ymax-ymin, 0.001)
    yrs = list(range(1, len(data_r)))

    for i in range(5):
        vy = ymin + yrng*i/4
        py = H-MB - (vy-ymin)/yrng*CH_
        d.line([(ML,py),(W-MR,py)], fill=(220,220,220))
        d.text((3, py-8), f"{vy/1e7:.1f}" if ylabel != "DSCR (x)" else f"{vy:.2f}", fill=(100,100,100), font=af)

    step = max(1, len(yrs)//10)
    for yr in yrs:
        if yr%step==0 or yr==1 or yr==yrs[-1]:
            px = ML + (yr-1)/(len(yrs)-1)*CW
            d.line([(px,H-MB),(px,H-MB+5)], fill=(100,100,100))
            d.text((px-8,H-MB+8), str(yr), fill=(100,100,100), font=af)

    d.text((ML+CW//2-30, H-30), "Year", fill=(0,0,0), font=lf)
    d.text((5, MT+CH_//2-40), ylabel, fill=(0,0,0), font=lf)

    for data,c in [(data_r,c1),(data_w,c2)]:
        pts = []
        for i,val in enumerate(data):
            if i==0: continue
            x = ML + (i-1)/(len(data)-2)*CW
            y = H-MB - (val-ymin)/yrng*CH_
            pts.append((x,y))
        for i in range(len(pts)-1):
            d.line([pts[i],pts[i+1]], fill=c, width=3)
        for pt in pts:
            d.ellipse([pt[0]-4,pt[1]-4,pt[0]+4,pt[1]+4], fill=c)

    d.rectangle([(ML, H-30),(ML+14, H-15)], fill=c1)
    d.text((ML+20, H-33), "Module A", fill=(0,0,0), font=lf)
    d.rectangle([(ML+120, H-30),(ML+134, H-15)], fill=c2)
    d.text((ML+140, H-33), "Module B", fill=(0,0,0), font=lf)
    img.save(fn); return fn


def _make_ts_bar_chart(data_r, data_w, title, ylabel, fn,
                       c1=(41,128,185), c2=(231,76,60)):
    """Grouped bar chart for two time series (e.g. net income)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1000, 600
    img = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 22)
        lf = ImageFont.truetype("arial.ttf", 16)
        af = ImageFont.truetype("arial.ttf", 13)
    except:
        tf = lf = af = ImageFont.load_default()

    d.text((W//2 - 250, 10), title, fill=(0, 0, 0), font=tf)
    ML, MR, MT, MB = 110, 60, 60, 80
    PW = W - ML - MR
    PH = H - MT - MB

    all_v = data_r + data_w
    ymin = min(0, min(all_v)) * 1.1
    ymax = max(all_v) * 1.15 if max(all_v) > 0 else 1
    yrng = max(ymax - ymin, 0.001)
    n = len(data_r)

    for i in range(5):
        vy = ymin + yrng * i / 4
        py = H - MB - (vy - ymin) / yrng * PH
        d.line([(ML, py), (W - MR, py)], fill=(220, 220, 220))
        d.text((3, py - 8), f"{vy:.1f}", fill=(100, 100, 100), font=af)

    zero_y = H - MB - (0 - ymin) / yrng * PH
    d.line([(ML, zero_y), (W - MR, zero_y)], fill=(80, 80, 80), width=2)

    bw = max(4, min(12, PW // (n * 4)))
    gap = max(1, bw // 3)
    gw = 2 * bw + gap
    total_w = n * gw
    sx = ML + (PW - total_w) / 2

    step = max(1, n // 12)
    for i in range(n):
        xc = sx + i * gw
        yr_label = i + 1
        if yr_label % step == 0 or yr_label == 1 or yr_label == n:
            cx = xc + bw
            d.line([(cx, H - MB), (cx, H - MB + 5)], fill=(100, 100, 100))
            d.text((cx - 8, H - MB + 8), str(yr_label), fill=(100, 100, 100), font=af)

        for data, color, offset in [(data_r, c1, 0), (data_w, c2, bw + gap)]:
            val = data[i]
            val_y = H - MB - (val - ymin) / yrng * PH
            if val >= 0:
                d.rectangle([(xc + offset, val_y), (xc + offset + bw, zero_y)], fill=color)
            else:
                d.rectangle([(xc + offset, zero_y), (xc + offset + bw, val_y)], fill=color)

    d.text((ML + PW // 2 - 30, H - 30), "Year", fill=(0, 0, 0), font=lf)
    d.text((5, MT + PH // 2 - 40), ylabel, fill=(0, 0, 0), font=lf)

    d.rectangle([(ML, H - 30), (ML + 14, H - 15)], fill=c1)
    d.text((ML + 20, H - 33), "Module A", fill=(0, 0, 0), font=lf)
    d.rectangle([(ML + 120, H - 30), (ML + 134, H - 15)], fill=c2)
    d.text((ML + 140, H - 33), "Module B", fill=(0, 0, 0), font=lf)
    img.save(fn)
    return fn


def _make_bar_chart(data_r, data_w, labels, title, fn):
    from PIL import Image, ImageDraw, ImageFont
    W,H = 800, 600
    img = Image.new('RGB', (W,H), (255,255,255))
    d = ImageDraw.Draw(img)
    try: tf=ImageFont.truetype("arial.ttf",20); lf=ImageFont.truetype("arial.ttf",14); af=ImageFont.truetype("arial.ttf",12)
    except: tf=lf=af=ImageFont.load_default()
    d.text((W//2-200,10), title, fill=(0,0,0), font=tf)
    ML,MR,MT,MB = 110, 50, 55, 100
    CW_=W-ML-MR; CH_=H-MT-MB
    mx = max(max(data_r), max(data_w))*1.2; mn=0
    n=len(data_r); bw=min(45, CW_//(n*3)); gap=int(bw*0.3); gw=2*bw+gap
    sx=ML+(CW_-n*gw)/2
    for i in range(5):
        vy=mn+(mx-mn)*i/4; py=H-MB-(vy-mn)/(mx-mn)*CH_
        d.line([(ML,py),(W-MR,py)], fill=(220,220,220))
        d.text((5,py-8), f"{vy:.1f}", fill=(100,100,100), font=af)
    for i in range(n):
        xc=sx+i*gw
        hr=(data_r[i]-mn)/(mx-mn)*CH_; hw=(data_w[i]-mn)/(mx-mn)*CH_
        d.rectangle([(xc,H-MB-hr),(xc+bw,H-MB)], fill=(41,128,185))
        d.rectangle([(xc+bw+gap,H-MB-hw),(xc+2*bw+gap,H-MB)], fill=(231,76,60))
        d.text((xc-15,H-MB+8), labels[i], fill=(0,0,0), font=af)
    d.rectangle([(ML, H-30),(ML+14, H-15)], fill=(41,128,185))
    d.text((ML+20, H-33),"Module A", fill=(0,0,0), font=lf)
    d.rectangle([(ML+120, H-30),(ML+134, H-15)], fill=(231,76,60))
    d.text((ML+140, H-33),"Module B", fill=(0,0,0), font=lf)
    img.save(fn); return fn


def _make_pie_chart(data, labels, title, fn):
    from PIL import Image, ImageDraw, ImageFont
    W,H=800,650; img=Image.new('RGB',(W,H),(255,255,255)); d=ImageDraw.Draw(img)
    try: tf=ImageFont.truetype("arial.ttf",20); lf=ImageFont.truetype("arial.ttf",16)
    except: tf=lf=ImageFont.load_default()
    d.text((W//2-200,10), title, fill=(0,0,0), font=tf)
    total=sum(data); cx,cy,r=250,350,180; sa=0
    colors=[(52,152,219),(46,204,113)]
    for val,col in zip(data,colors):
        ang=360*val/total; ea=sa+ang
        d.pieslice([cx-r,cy-r,cx+r,cy+r], sa, ea, fill=col, outline=(255,255,255))
        sa=ea
    lx,ly=480,180
    for lab,col,val in zip(labels,colors,data):
        d.rectangle([(lx,ly),(lx+22,ly+22)], fill=col)
        d.text((lx+30,ly+2), f"{lab}: Rs.{val/1e7:.1f}Cr ({val/total*100:.1f}%)", fill=(0,0,0), font=lf)
        ly+=40
    img.save(fn); return fn


if __name__ == "__main__":
    # Test with current project data
    mod_a = {
        "name": "Redren Steorra Mono PERC", "short": "Redren",
        "capacity_w": 600, "efficiency_pct": 21.30,
        "temp_coeff_pmax": -0.35, "deg_y1_pct": 2.0, "deg_annual_pct": 0.55,
        "price_per_wp": 20, "warranty_yrs": 27, "technology": "PERC"
    }
    mod_b = {
        "name": "Waaree BiN-21 N-TOPCon", "short": "Waaree",
        "capacity_w": 615, "efficiency_pct": 22.77,
        "temp_coeff_pmax": -0.30, "deg_y1_pct": 1.0, "deg_annual_pct": 0.40,
        "price_per_wp": 22, "warranty_yrs": 30, "technology": "N-TOPCon"
    }
    proj = {
        "capacity_mw": 19.6, "latitude": 10.38, "longitude": 78.82,
        "ppa_tariff": 4.50, "debt_ratio": 0.70, "interest_rate": 0.09,
        "loan_tenure": 15, "tax_rate": 0.2517, "discount_rate": 0.10,
        "om_per_mw": 180000, "om_esc": 0.03, "bos_per_w": 12.0,
        "insurance_rate": 0.003
    }
    d = os.path.dirname(__file__) or '.'
    res, ch = run_analysis(mod_a, mod_b, proj, d)
    for k in ["Redren", "Waaree"]:
        v = res[k]
        print(f"{k}: IRR={v['irr']*100:.2f}%, NPV={v['npv']/1e7:.2f}Cr, LCOE={v['lcoe']:.2f}")
    print(f"Charts: {list(ch.keys())}")
    print("Test OK")
