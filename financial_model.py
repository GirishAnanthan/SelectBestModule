"""
19.6 MW DC Solar Plant - Financial Model & Investor Report
Location: Pudukottai, Tamilnadu, India
Comparison: Redren (Mono PERC, Rs.20/Wp) vs Waaree (N-TOPCon, Rs.22/Wp)
Frontside generation only - No bifacial gains considered
"""

import numpy as np
import numpy_financial as npf
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont
import os, json

# ====================================================================
# MODULE SPECIFICATIONS
# ====================================================================
modules = {
    "Redren": {
        "full_name": "Redren Steorra Mono PERC 600Wp (BIG DCR)",
        "short": "Redren",
        "technology": "Mono PERC (p-type)",
        "capacity_w": 600,
        "efficiency_pct": 21.30,
        "temp_coeff_pmax": -0.35,
        "noct": 43,
        "warranty_power_years": 27,
        "deg_y1_pct": 2.0,
        "deg_annual_pct": 0.55,
        "price_per_wp": 20,
    },
    "Waaree": {
        "full_name": "Waaree BiN-21-615 N-TOPCon 615Wp",
        "short": "Waaree",
        "technology": "N-type TOPCon",
        "capacity_w": 615,
        "efficiency_pct": 22.77,
        "temp_coeff_pmax": -0.30,
        "noct": 43,
        "warranty_power_years": 30,
        "deg_y1_pct": 1.0,
        "deg_annual_pct": 0.40,
        "price_per_wp": 22,
    }
}

# ====================================================================
# PROJECT PARAMETERS - Pudukottai, Tamilnadu
# ====================================================================
PROJECT_DC_MW = 19.6
PLANT_LIFE = 25
CUF_REDREN = 0.190    # 19.0% frontside - Mono PERC
CUF_WAAREE = 0.193    # 19.3% frontside - TOPCon (better low-light, lower temp coeff)

DEBT_RATIO = 0.70
EQUITY_RATIO = 0.30
INTEREST_RATE = 0.09
LOAN_TENURE = 15
TAX_RATE = 0.2517
DISCOUNT_RATE = 0.10  # WACC

PPA_TARIFF = 4.50      # Rs/kWh

OM_COST_PER_MW = 180000  # Rs/MW/yr
OM_ESC = 0.03
BOS_EPC_PER_W = 12.0    # Rs/Wp
INSURANCE_RATE = 0.003

# Depreciation WDV
DEP_SCHEDULE = [0.40, 0.20, 0.10] + [0.30 / 7]*7 + [0]*15  # 25 years

results = {}
HRS_PER_YR = 8760

for name, mod in modules.items():
    print(f"\n========== {mod['full_name']} ==========")

    cap_w = mod['capacity_w']
    n_modules = int(np.ceil(PROJECT_DC_MW * 1e6 / cap_w))
    actual_mw = n_modules * cap_w / 1e6
    actual_kw = actual_mw * 1000

    # Costs
    module_cost = mod['price_per_wp'] * n_modules * cap_w
    bos_cost = BOS_EPC_PER_W * n_modules * cap_w
    total_cost = module_cost + bos_cost
    debt = total_cost * DEBT_RATIO
    equity = total_cost * EQUITY_RATIO

    # Annual loan payment
    loan_pmt = -npf.pmt(INTEREST_RATE, LOAN_TENURE, debt)

    # Generation (kWh)
    cuf = CUF_REDREN if name == "Redren" else CUF_WAAREE
    gen_y1_kwh = actual_kw * HRS_PER_YR * cuf

    print(f"  Modules: {n_modules:,} x {cap_w}W = {actual_mw:.2f} MW")
    print(f"  Module Cost: Rs.{module_cost/1e7:.2f} Cr")
    print(f"  Total Cost:  Rs.{total_cost/1e7:.2f} Cr")
    print(f"  Equity:      Rs.{equity/1e7:.2f} Cr")
    print(f"  Gen Y1:      {gen_y1_kwh/1e3:,.0f} MWh  @ CUF {cuf*100:.1f}%")

    # Cash flow arrays (year 0..25)
    rev_arr = [0]
    om_arr = [0]
    ins_arr = [0]
    depr_arr = [0]
    int_arr = [0]
    prin_arr = [0]
    ni_arr = [0]
    fcf_arr = [-equity]  # year 0 equity outflow

    bal = debt
    for yr in range(1, PLANT_LIFE + 1):
        # Degradation
        dg = 1 - mod['deg_y1_pct']/100
        if yr > 1:
            dg *= (1 - mod['deg_annual_pct']/100) ** (yr - 1)

        gen_kwh = gen_y1_kwh * dg
        rev = gen_kwh * PPA_TARIFF

        om = OM_COST_PER_MW * actual_mw * (1 + OM_ESC)**(yr-1)
        ins = total_cost * INSURANCE_RATE

        # Loan
        if yr <= LOAN_TENURE:
            interest = bal * INTEREST_RATE
            principal = loan_pmt - interest
            bal -= principal
        else:
            interest = 0
            principal = 0

        depr = total_cost * DEP_SCHEDULE[yr-1]
        ebt = rev - om - ins - interest - depr
        tax = max(0, ebt * TAX_RATE)
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

    total_gen = sum([gen_y1_kwh * (1 - mod['deg_y1_pct']/100) *
                     ((1 - mod['deg_annual_pct']/100) ** max(0, yr-1))
                     for yr in range(1, PLANT_LIFE+1)])

    irr = npf.irr(fcf_arr)
    npv = npf.npv(DISCOUNT_RATE, fcf_arr)

    disc_rate = DISCOUNT_RATE
    discounted_cost = float(total_cost)
    discounted_energy = 0.0
    for yr in range(1, PLANT_LIFE + 1):
        dg_yr = (1 - mod['deg_y1_pct']/100) * ((1 - mod['deg_annual_pct']/100) ** max(0, yr-1))
        discounted_energy += gen_y1_kwh * dg_yr / (1 + disc_rate) ** yr
        discounted_cost += float(om_arr[yr] + ins_arr[yr]) / (1 + disc_rate) ** yr
    lcoe = discounted_cost / discounted_energy if discounted_energy > 0 else 0.0

    payout = None
    cum = 0
    for yr in range(1, PLANT_LIFE+1):
        cum += fcf_arr[yr]
        if cum >= equity and payout is None:
            payout = yr

    print(f"  Total Gen 25yr: {total_gen/1e6:.2f} GWh")
    print(f"  Revenue Y1:     Rs.{rev_arr[1]/1e7:.2f} Cr")
    print(f"  Equity IRR:     {irr*100:.2f}%")
    print(f"  NPV @10%:       Rs.{npv/1e7:.2f} Cr")
    print(f"  LCOE:           Rs.{lcoe:.2f}/kWh")
    print(f"  Payback:        ~{payout} yrs")

    results[name] = {
        "capacity_mw": actual_mw, "module_count": n_modules,
        "module_cost": module_cost, "bos_cost": bos_cost,
        "total_cost": total_cost, "debt": debt, "equity": equity,
        "loan_pmt": loan_pmt, "gen_y1_kwh": gen_y1_kwh,
        "total_gen_kwh": total_gen, "irr": irr, "npv": npv,
        "lcoe": lcoe,
        "payback": payout, "cuf": cuf,
        "revenue": rev_arr, "om": om_arr, "insurance": ins_arr,
        "depreciation": depr_arr, "interest": int_arr,
        "principal": prin_arr, "net_income": ni_arr,
        "fcf": fcf_arr,
        "tech": mod['technology'],
        "efficiency": mod['efficiency_pct'],
        "price_wp": mod['price_per_wp'],
        "deg_y1": mod['deg_y1_pct'],
        "deg_ann": mod['deg_annual_pct'],
        "temp_coeff": mod['temp_coeff_pmax'],
        "warranty_yrs": mod['warranty_power_years'],
    }

# ====================================================================
# PRINT COMPARISON TABLE
# ====================================================================
print("\n\n" + "=" * 65)
print("COMPARISON SUMMARY")
print("=" * 65)
h = f"{'Parameter':<35} {'Redren':<15} {'Waaree':<15}"
print(h)
print("-" * 65)
r = results["Redren"]; w = results["Waaree"]
rows = [
    ("Module Capacity (Wp)",        f"{600}",              f"{615}"),
    ("Price (Rs/Wp)",               f"{20}",               f"{22}"),
    ("Efficiency (%)",              f"{21.30}",            f"{22.77}"),
    ("Temp Coeff Pmax (%/C)",       f"{-0.35}",            f"{-0.30}"),
    ("Degradation Y1 (%)",          f"{2.0}",              f"{1.0}"),
    ("Annual Degradation (%)",      f"{0.55}",             f"{0.40}"),
    ("Power Warranty (yrs)",        f"{27}",               f"{30}"),
    ("", "", ""),
    ("Total Module Cost (Cr)",      f"{r['module_cost']/1e7:.2f}", f"{w['module_cost']/1e7:.2f}"),
    ("Total Project Cost (Cr)",     f"{r['total_cost']/1e7:.2f}",  f"{w['total_cost']/1e7:.2f}"),
    ("Equity Required (Cr)",        f"{r['equity']/1e7:.2f}",      f"{w['equity']/1e7:.2f}"),
    ("Annual Gen Y1 (MWh)",         f"{r['gen_y1_kwh']/1e3:,.0f}", f"{w['gen_y1_kwh']/1e3:,.0f}"),
    ("Total Gen 25yr (GWh)",        f"{r['total_gen_kwh']/1e6:.2f}",f"{w['total_gen_kwh']/1e6:.2f}"),
    ("CUF Frontside (%)",           f"{r['cuf']*100:.1f}",         f"{w['cuf']*100:.1f}"),
    ("Equity IRR (%)",              f"{r['irr']*100:.2f}",         f"{w['irr']*100:.2f}"),
    ("NPV @ 10% (Cr)",              f"{r['npv']/1e7:.2f}",         f"{w['npv']/1e7:.2f}"),
    ("LCOE (Rs/kWh)",               f"{r['lcoe']:.2f}",            f"{w['lcoe']:.2f}"),
    ("Payback Period (yrs)",        f"{r['payback']}",             f"{w['payback']}"),
]
for row in rows: print(f"{row[0]:<35} {row[1]:<15} {row[2]:<15}")

best = "Waaree" if w['irr'] > r['irr'] else "Redren"
print(f"\n\n>>> RECOMMENDATION: {best}")

# ====================================================================
# CHARTS
# ====================================================================
CHART_DIR = os.path.dirname(__file__) or '.'

def make_chart_ts(data_r, data_w, title, ylabel, fn,
                  c1=(41,128,185), c2=(231,76,60)):
    W,H = 1000, 600
    img = Image.new('RGB', (W,H), (255,255,255))
    d = ImageDraw.Draw(img)
    try:
        tf = ImageFont.truetype("arial.ttf", 22)
        lf = ImageFont.truetype("arial.ttf", 16)
        af = ImageFont.truetype("arial.ttf", 13)
    except:
        tf=lf=af=ImageFont.load_default()
    d.text((W//2-250,10), title, fill=(0,0,0), font=tf)
    ML,MR,MT,MB = 110, 60, 60, 80
    CW = W-ML-MR; CH_ = H-MT-MB
    all_v = data_r[1:] + data_w[1:]  # skip yr0
    ymin = min(all_v)*0.95 if min(all_v)>0 else 0
    ymax = max(all_v)*1.05
    yrng = ymax-ymin
    yrs = list(range(1, len(data_r)))
    # grid
    for i in range(5):
        vy = ymin + yrng*i/4
        py = H-MB - (vy-ymin)/yrng*CH_
        d.line([(ML,py),(W-MR,py)], fill=(220,220,220))
        d.text((3, py-8), f"{vy/1e7:.1f}", fill=(100,100,100), font=af)
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
    # legend
    d.rectangle([(W-370,10),(W-355,25)], fill=c1)
    d.text((W-345,10), "Redren (PERC)", fill=(0,0,0), font=lf)
    d.rectangle([(W-170,10),(W-155,25)], fill=c2)
    d.text((W-145,10), "Waaree (TOPCon)", fill=(0,0,0), font=lf)
    img.save(fn); print(f"  Saved {fn}")

def make_bar(data_r, data_w, labels, title, ylabel, fn):
    W,H = 800, 600
    img = Image.new('RGB', (W,H), (255,255,255))
    d = ImageDraw.Draw(img)
    try:
        tf=ImageFont.truetype("arial.ttf",20); lf=ImageFont.truetype("arial.ttf",14); af=ImageFont.truetype("arial.ttf",12)
    except: tf=lf=af=ImageFont.load_default()
    d.text((W//2-200,10), title, fill=(0,0,0), font=tf)
    ML,MR,MT,MB = 110, 50, 55, 100
    CW_=W-ML-MR; CH_=H-MT-MB
    mx = max(max(data_r), max(data_w))*1.2
    mn = 0
    n = len(data_r)
    bw = min(45, CW_//(n*3))
    gap = int(bw*0.3)
    gw = 2*bw+gap
    sx = ML + (CW_ - n*gw)/2
    for i in range(5):
        vy = mn+(mx-mn)*i/4
        py = H-MB - (vy-mn)/(mx-mn)*CH_
        d.line([(ML,py),(W-MR,py)], fill=(220,220,220))
        d.text((5,py-8), f"{vy:.1f}", fill=(100,100,100), font=af)
    for i in range(n):
        xc = sx + i*gw
        hr = (data_r[i]-mn)/(mx-mn)*CH_
        hw = (data_w[i]-mn)/(mx-mn)*CH_
        d.rectangle([(xc, H-MB-hr), (xc+bw, H-MB)], fill=(41,128,185))
        d.rectangle([(xc+bw+gap, H-MB-hw), (xc+2*bw+gap, H-MB)], fill=(231,76,60))
        d.text((xc-15, H-MB+8), labels[i], fill=(0,0,0), font=af)
    d.rectangle([(ML,10),(ML+14,25)], fill=(41,128,185))
    d.text((ML+20,10),"Redren (PERC)", fill=(0,0,0), font=lf)
    d.rectangle([(ML+160,10),(ML+174,25)], fill=(231,76,60))
    d.text((ML+180,10),"Waaree (TOPCon)", fill=(0,0,0), font=lf)
    img.save(fn); print(f"  Saved {fn}")

print("\nGenerating charts...")

# 1. Cumulative FCF
cum_r = [sum(results['Redren']['fcf'][:i+1]) for i in range(len(r['fcf']))]
cum_w = [sum(results['Waaree']['fcf'][:i+1]) for i in range(len(w['fcf']))]
make_chart_ts(cum_r, cum_w,
    "Cumulative Free Cash Flow to Equity (Rs. Crores)", "Cumulative FCF (Rs. Cr)",
    os.path.join(CHART_DIR,"chart_cumulative_fcf.png"))

# 2. Annual Generation
gen_r = [0] + [results['Redren']['gen_y1_kwh'] *
    ((1-r['deg_y1']/100)*((1-r['deg_ann']/100)**max(0,yr-1)))/1e3 for yr in range(1,26)]
gen_w = [0] + [results['Waaree']['gen_y1_kwh'] *
    ((1-w['deg_y1']/100)*((1-w['deg_ann']/100)**max(0,yr-1)))/1e3 for yr in range(1,26)]
make_chart_ts(gen_r, gen_w,
    "Annual Energy Generation (MWh) - 25 Year Horizon", "Generation (MWh/yr)",
    os.path.join(CHART_DIR,"chart_gen.png"))

# 3. Net Income
ni_r = [r['net_income'][i]/1e7 for i in range(len(r['net_income']))]
ni_w = [w['net_income'][i]/1e7 for i in range(len(w['net_income']))]
make_chart_ts(ni_r, ni_w,
    "Annual Net Income After Tax (Rs. Crores)", "Net Income (Rs. Cr)",
    os.path.join(CHART_DIR,"chart_net_income.png"))

# 4. DSCR
dscr_r = []
dscr_w = []
for i in range(1, 16):
    ds_r = (r['net_income'][i] + r['interest'][i] + r['depreciation'][i]) / (r['interest'][i] + r['principal'][i]) if (r['interest'][i]+r['principal'][i])>0 else 0
    ds_w = (w['net_income'][i] + w['interest'][i] + w['depreciation'][i]) / (w['interest'][i] + w['principal'][i]) if (w['interest'][i]+w['principal'][i])>0 else 0
    dscr_r.append(ds_r); dscr_w.append(ds_w)
# pad to 25
dscr_r = [0]+dscr_r+[0]*10
dscr_w = [0]+dscr_w+[0]*10
make_chart_ts(dscr_r, dscr_w,
    "Debt Service Coverage Ratio (Debt Tenure Period)", "DSCR (x)",
    os.path.join(CHART_DIR,"chart_dscr.png"))

# 5. Pie - cost breakdown (Waaree)
def pie(data, labels, colors, title, fn):
    W,H=800,650; img=Image.new('RGB',(W,H),(255,255,255)); d=ImageDraw.Draw(img)
    try: tf=ImageFont.truetype("arial.ttf",20); lf=ImageFont.truetype("arial.ttf",16)
    except: tf=lf=ImageFont.load_default()
    d.text((W//2-200,10), title, fill=(0,0,0), font=tf)
    total=sum(data); cx,cy,r=250,350,180
    sa=0
    for val,col in zip(data,colors):
        ang=360*val/total; ea=sa+ang
        d.pieslice([cx-r,cy-r,cx+r,cy+r], sa, ea, fill=col, outline=(255,255,255))
        sa=ea
    lx,ly=480,180
    for lab,col,val in zip(labels,colors,data):
        d.rectangle([(lx,ly),(lx+22,ly+22)], fill=col)
        d.text((lx+30,ly+2), f"{lab}: Rs.{val/1e7:.1f}Cr ({val/total*100:.1f}%)", fill=(0,0,0), font=lf)
        ly+=40
    img.save(fn); print(f"  Saved {fn}")
pie(
    [w['module_cost'], w['bos_cost']],
    ["Module Cost", "BoS, EPC & Land"],
    [(52,152,219),(46,204,113)],
    f"Project Cost Breakdown - Waaree (Total Rs.{w['total_cost']/1e7:.1f}Cr)",
    os.path.join(CHART_DIR,"chart_cost_pie.png")
)

# 6. IRR/NPV bar
make_bar(
    [r['irr']*100, r['npv']/1e7],
    [w['irr']*100, w['npv']/1e7],
    ["Equity IRR (%)", "NPV @ 10% (Rs.Cr)"],
    "Financial Metric Comparison - Redren vs Waaree", "",
    os.path.join(CHART_DIR,"chart_irr_npv.png")
)

print("All charts done.")

# Save results
with open(os.path.join(CHART_DIR,'fin_results.json'),'w') as f:
    class NpEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o,(np.integer,)): return int(o)
            if isinstance(o,(np.floating,)): return float(o)
            return super().default(o)
    json.dump(results, f, cls=NpEncoder)
print("Results saved.")
