"""
Weather Data Module - NASA POWER & PVGIS TMY API Integration
Fetches real meteorological data (GHI, DNI, temperature, wind) for solar analysis.
Falls back to heuristic estimates if API is unavailable.
"""
import logging
import math

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests not installed; weather APIs unavailable")

_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _days_in_month(year, month):
    if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        return 29
    return _DAYS_IN_MONTH[month - 1]


def _nasa_monthly_average(raw_dict, as_monthly_total=True):
    """Average NASA POWER monthly values across years by calendar month.

    NASA POWER monthly solar parameters are daily-average irradiation values
    keyed as YYYYMM. For GHI/DNI/DIF we convert each month to monthly total
    kWh/m2/month, then average Jan..Dec across all available years. For
    temperature/wind we average the monthly values directly.
    """
    buckets = {f"{m:02d}": [] for m in range(1, 13)}
    for key, val in raw_dict.items():
        if val is None or len(str(key)) < 6:
            continue
        year = int(str(key)[:4])
        month = int(str(key)[4:6])
        value = val * _days_in_month(year, month) if as_monthly_total else val
        buckets[f"{month:02d}"].append(value)
    return {
        month: round(sum(values) / len(values), 1)
        for month, values in buckets.items()
        if values
    }


# ---------------------------------------------------------------------------
# NASA POWER
# ---------------------------------------------------------------------------

def fetch_nasa_power_monthly(lat, lon, start_year=2020, end_year=2024):
    """Fetch monthly solar meteorology from NASA POWER REST API.
    Returns dict of monthly arrays or None on failure.
    Values are converted to monthly totals (kWh/m²/month) for GHI/DNI and
    monthly average temperature (°C).
    """
    if not HAS_REQUESTS:
        logger.warning("Cannot fetch NASA POWER data: requests library not installed")
        return None

    params = [
        "ALLSKY_SFC_SW_GHI",
        "ALLSKY_SFC_SW_DNI",
        "ALLSKY_SFC_SW_DIF",
        "T2M",
        "WS2M",
    ]
    param_str = ",".join(params)
    url = (
        f"https://power.larc.nasa.gov/api/temporal/monthly/point"
        f"?parameters={param_str}"
        f"&community=RE"
        f"&latitude={lat}&longitude={lon}"
        f"&start={start_year}&end={end_year}"
        f"&format=json"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        properties = data.get("properties", {}).get("parameter", {})
        if not properties:
            return None

        monthly = {}
        for param in params:
            raw = properties.get(param, {})
            if param == "T2M" or param == "WS2M":
                monthly[param] = _nasa_monthly_average(raw, as_monthly_total=False)
            else:
                monthly[param] = _nasa_monthly_average(raw, as_monthly_total=True)
        return monthly
    except Exception as e:
        logger.warning(f"NASA POWER API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# PVGIS (Typical Meteorological Year)
# ---------------------------------------------------------------------------

def fetch_pvgis_monthly(lat, lon):
    """Fetch typical meteorological year data from PVGIS API v5.2.
    Aggregates hourly TMY data to monthly totals.
    Returns dict with keys:
        PVGIS_GHI:  {'01': val, ...}  kWh/m²/month
        PVGIS_DNI:  {'01': val, ...}  kWh/m²/month
        PVGIS_TEMP: {'01': val, ...}  °C
        PVGIS_WS:   {'01': val, ...}  m/s
    or None on failure.
    """
    if not HAS_REQUESTS:
        logger.warning("Cannot fetch PVGIS data: requests library not installed")
        return None

    url = (
        f"https://re.jrc.ec.europa.eu/api/v5_2/tmy"
        f"?lat={lat}&lon={lon}&outputformat=json"
    )
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        hourly = data.get("outputs", {}).get("tmy_hourly", [])
        if not hourly:
            return None

        acc = {m: {"ghi": 0.0, "dni": 0.0, "temp": 0.0, "ws": 0.0, "n": 0}
               for m in range(1, 13)}
        for h in hourly:
            ts = h.get("time(UTC)", "")
            if len(ts) < 6:
                continue
            month = int(ts[4:6])
            acc[month]["ghi"] += h.get("G(h)", 0)
            acc[month]["dni"] += h.get("Gb(n)", 0)
            acc[month]["temp"] += h.get("T2m", 25)
            acc[month]["ws"] += h.get("WS10m", 0)
            acc[month]["n"] += 1

        result = {}
        ghi_m = {}
        dni_m = {}
        temp_m = {}
        ws_m = {}
        for m in range(1, 13):
            d = acc[m]
            ghi_m[f"{m:02d}"] = round(d["ghi"] / 1000, 1)
            dni_m[f"{m:02d}"] = round(d["dni"] / 1000, 1)
            temp_m[f"{m:02d}"] = round(d["temp"] / d["n"], 1) if d["n"] > 0 else 25.0
            ws_m[f"{m:02d}"] = round(d["ws"] / d["n"], 1) if d["n"] > 0 else 0.0
        result["PVGIS_GHI"] = ghi_m
        result["PVGIS_DNI"] = dni_m
        result["PVGIS_TEMP"] = temp_m
        result["PVGIS_WS"] = ws_m
        return result
    except Exception as e:
        logger.warning(f"PVGIS API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Data aggregation helpers
# ---------------------------------------------------------------------------

def _extract_monthly_data(weather_data):
    """Extract GHI, DNI, and temperature monthly dicts from any supported format.
    Returns (ghi_monthly, dni_monthly, temp_monthly, source_name) where each
    is a dict with '01'..'12' keys. GHI/DNI in kWh/m²/month, temp in °C.
    """
    if not weather_data:
        return None, None, None, None

    if "ALLSKY_SFC_SW_GHI" in weather_data:
        ghi = weather_data["ALLSKY_SFC_SW_GHI"]
        dni = weather_data.get("ALLSKY_SFC_SW_DNI", {})
        temp = weather_data.get("T2M", {})
        source = "NASA POWER"
    elif "PVGIS_GHI" in weather_data:
        ghi = weather_data["PVGIS_GHI"]
        dni = weather_data.get("PVGIS_DNI", {})
        temp = weather_data.get("PVGIS_TEMP", {})
        source = "PVGIS"
    else:
        return None, None, None, None

    return ghi, dni, temp, source


def compute_annual_solar_metrics(lat, lon, weather_data, mounting_type="Fixed Tilt", tilt_angle=None):
    """Compute annual solar metrics from NASA POWER / PVGIS data or heuristic fallback.
    Returns dict with annual_ghi, annual_poa, specific_yield, performance_ratio, cuf, avg_temp.
    """
    ghi_monthly, dni_monthly, temp_monthly, _ = _extract_monthly_data(weather_data)

    if ghi_monthly:
        ghi_values = [v for v in ghi_monthly.values() if v is not None]
        temp_values = [v for v in temp_monthly.values() if v is not None] if temp_monthly else []
        if ghi_values:
            annual_ghi = sum(ghi_values)
            avg_temp = sum(temp_values) / len(temp_values) if temp_values else 25.0
        else:
            return _heuristic_metrics(lat, mounting_type, tilt_angle)
    else:
        return _heuristic_metrics(lat, mounting_type, tilt_angle)

    if dni_monthly:
        dni_values = [v for v in dni_monthly.values() if v is not None]
        annual_dni = sum(dni_values) if dni_values else annual_ghi * 0.55
    else:
        annual_dni = annual_ghi * 0.55

    if mounting_type == "Fixed Tilt":
        opt_tilt = _get_optimal_tilt(lat)
        tilt = tilt_angle if tilt_angle is not None else opt_tilt
        poa_factor = 1.0 + 0.003 * tilt
    elif mounting_type == "Single Axis Tracker":
        poa_factor = 1.10 + 0.004 * abs(lat)
    else:
        poa_factor = 1.15 + 0.005 * abs(lat)

    annual_poa = annual_ghi * poa_factor

    cuf = annual_poa / 8760 * 0.78
    cuf = round(cuf, 4)

    specific_yield = cuf * 8760
    performance_ratio = cuf * 8760 / annual_poa if annual_poa > 0 else 0

    return {
        "annual_ghi": round(annual_ghi, 0),
        "annual_poa": round(annual_poa, 0),
        "annual_dni": round(annual_dni, 0),
        "specific_yield": round(specific_yield, 0),
        "performance_ratio": round(performance_ratio, 3),
        "cuf": cuf,
        "avg_ambient_temp": round(avg_temp, 1),
        "optimal_tilt": round(_get_optimal_tilt(lat), 1) if mounting_type == "Fixed Tilt" else None,
    }


def _get_optimal_tilt(latitude):
    return round(0.87 * abs(float(latitude)), 1)


def _heuristic_metrics(lat, mounting_type="Fixed Tilt", tilt_angle=None):
    """Fallback heuristic when API data is unavailable."""
    lat = float(lat)
    ghi = 2100 - 5 * abs(lat - 10)

    if mounting_type == "Fixed Tilt":
        opt_tilt = _get_optimal_tilt(lat)
        tilt = tilt_angle if tilt_angle is not None else opt_tilt
        poa = ghi * (1.0 + 0.003 * tilt)
    elif mounting_type == "Single Axis Tracker":
        poa = ghi * (1.10 + 0.004 * abs(lat))
    else:
        poa = ghi * (1.15 + 0.005 * abs(lat))

    cuf_base = 0.19
    lat_factor = 1.0 - 0.002 * abs(lat - 20)
    cuf = cuf_base * lat_factor

    if mounting_type == "Fixed Tilt":
        if tilt_angle is not None:
            tilt = float(tilt_angle)
            penalty = 0.002 * abs(tilt - _get_optimal_tilt(lat))
            cuf *= (1 - penalty)
    elif mounting_type == "Single Axis Tracker":
        gain = 0.15 + 0.003 * abs(lat - 10)
        cuf *= (1 + gain)
    elif mounting_type == "Dual Axis Tracker":
        gain = 0.25 + 0.004 * abs(lat - 10)
        cuf *= (1 + gain)

    cuf = round(cuf, 4)
    specific_yield = cuf * 8760
    performance_ratio = cuf * 8760 / poa if poa > 0 else 0

    return {
        "annual_ghi": round(ghi, 0),
        "annual_poa": round(poa, 0),
        "annual_dni": round(ghi * 0.55, 0),
        "specific_yield": round(specific_yield, 0),
        "performance_ratio": round(performance_ratio, 3),
        "cuf": cuf,
        "avg_ambient_temp": 25.0,
        "optimal_tilt": round(_get_optimal_tilt(lat), 1) if mounting_type == "Fixed Tilt" else None,
    }


def adjust_cuf_for_module(cuf, module_efficiency, reference_efficiency=21.0, temp_coeff=-0.35, noct=43, avg_temp=25.0, irradiance_w_m2=800):
    """Adjust CUF for module-specific characteristics (efficiency, temperature, NOCT).
    Returns adjusted CUF.
    """
    cell_temp = avg_temp + (noct - 20) / 800 * irradiance_w_m2
    temp_factor = 1 + (temp_coeff / 100) * (cell_temp - 25)
    temp_factor = max(0.70, min(1.05, temp_factor))

    # For fixed-DC MW comparisons, module efficiency mainly affects module count,
    # land, and BOS, not kWh/kWp. Temperature coefficient and NOCT affect yield.
    cuf_adj = cuf * temp_factor
    return round(cuf_adj, 4)


def compute_bifacial_gain(albedo, mounting_height_m, tilt_angle, ghi_annual, bifaciality_factor=0.7):
    """Compute bifacial generation boost.
    Returns dict with view_factor, rear_irradiance, boost_pct.
    """
    if tilt_angle is None:
        tilt_angle = 10
    tilt_rad = math.radians(tilt_angle)
    view_factor = (1 + math.cos(tilt_rad)) / 2
    height_factor = min(1.0, 1 + 0.1 * math.log(max(mounting_height_m, 0.1) / 0.5))

    rear_irradiance = ghi_annual * albedo * view_factor * height_factor
    front_irradiance = ghi_annual
    boost_pct = (rear_irradiance / front_irradiance) * bifaciality_factor * 100

    return {
        "view_factor": round(view_factor, 3),
        "rear_irradiance_kwh_m2": round(rear_irradiance, 0),
        "boost_pct": round(boost_pct, 2),
        "albedo": albedo,
        "mounting_height_m": mounting_height_m,
    }


def compute_monthly_breakdown(weather_data, annual_ghi, annual_poa, loss_factors,
                               gen_y1_kwh, cuf, module_capacity_kw, latitude=None):
    """Compute monthly generation, PR, and yield from weather data.
    Returns list of 12 dicts, one per month.
    """
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    ghi_monthly, _, temp_monthly, _ = _extract_monthly_data(weather_data)

    # Build latitude-based seasonal temps if no real data
    _lat = latitude if latitude is not None else 20.0
    _mean_temp = max(5.0, min(35.0, 30.0 - 0.5 * abs(_lat)))
    _est_temps = {}
    for m_idx in range(12):
        _est_temps[f"{m_idx+1:02d}"] = round(_mean_temp + 10.0 * math.sin(2 * math.pi * (m_idx - 3) / 12), 1)

    if not ghi_monthly:
        # Seasonal fallback: not bankable meteo data, but avoids impossible flat monthly values.
        # Northern hemisphere peaks around June; southern hemisphere shifted by 6 months.
        amp = min(0.35, 0.12 + 0.003 * abs(float(_lat)))
        phase_shift = 0 if float(_lat) >= 0 else 6
        raw_weights = []
        for m_idx in range(12):
            raw_weights.append(max(0.55, 1 + amp * math.sin(2 * math.pi * (m_idx - 2 - phase_shift) / 12)))
        weight_sum = sum(raw_weights) or 12
        ghi_monthly = {
            f"{m_idx+1:02d}": annual_ghi * raw_weights[m_idx] / weight_sum
            for m_idx in range(12)
        }
        temp_monthly = {}

    ghi_values = [v for v in ghi_monthly.values() if v is not None]
    total_ghi = sum(ghi_values) if ghi_values else annual_ghi

    monthly_inputs = []
    for m_idx in range(12):
        m_key = f"{m_idx+1:02d}"
        m_ghi = ghi_monthly.get(m_key, annual_ghi / 12) if ghi_monthly else annual_ghi / 12
        m_temp = temp_monthly.get(m_key) if temp_monthly else None
        if m_temp is None:
            m_temp = _est_temps[m_key]
        if m_ghi is None:
            m_ghi = annual_ghi / 12
        # Generic temperature effect for monthly shape only; annual generation remains the calibrated value.
        temp_factor = max(0.85, min(1.05, 1 - 0.004 * (m_temp - 25)))
        monthly_inputs.append((m_idx, m_key, m_ghi, m_temp, temp_factor))

    total_gen_basis = sum(m_ghi * temp_factor for _, _, m_ghi, _, temp_factor in monthly_inputs)
    if total_gen_basis <= 0:
        total_gen_basis = total_ghi or 1

    monthly_data = []
    for m_idx, m_key, m_ghi, m_temp, temp_factor in monthly_inputs:
        ghi_frac = m_ghi / total_ghi if total_ghi > 0 else 1 / 12
        gen_frac = (m_ghi * temp_factor) / total_gen_basis if total_gen_basis > 0 else 1 / 12
        m_gen = gen_y1_kwh * gen_frac
        m_poa = annual_poa * ghi_frac
        m_pr = (m_gen / (m_poa * module_capacity_kw)) if (m_poa > 0 and module_capacity_kw > 0) else 0
        m_sy = m_gen / module_capacity_kw if module_capacity_kw > 0 else 0

        monthly_data.append({
            "month": months[m_idx],
            "ghi": round(m_ghi, 1),
            "poa": round(m_poa, 1),
            "temp": round(m_temp, 1),
            "gen_kwh": round(m_gen, 0),
            "pr": round(m_pr, 3),
            "specific_yield": round(m_sy, 0),
        })

    # Annual totals
    total_poa = sum(d["poa"] for d in monthly_data)
    total_gen = sum(d["gen_kwh"] for d in monthly_data)
    annual_metrics = {
        "total_gen": round(total_gen, 0),
        "avg_pr": round(total_gen / (total_poa * module_capacity_kw), 3) if total_poa > 0 and module_capacity_kw > 0 else 0,
        "avg_temp": round(sum(d["temp"] for d in monthly_data) / 12, 1),
        "total_ghi": round(sum(d["ghi"] for d in monthly_data), 0),
        "total_poa": round(total_poa, 0),
    }

    return monthly_data, annual_metrics


def compute_energy_losses(temp_coeff_pmax, noct, avg_temp, cuf, albedo=0.20,
                           mounting_type="Fixed Tilt", irradiance_w_m2=800):
    """Compute energy loss breakdown.
    Returns list of (loss_name, loss_pct, cumulative_pct) tuples for waterfall chart,
    and a dict of individual loss factors.
    """
    # Starting from POA irradiance (100%), each loss reduces the energy
    losses = {}

    # 1. IAM loss (Incidence Angle Modifier) - typical 3% for fixed tilt, 5% for trackers
    if "Tracker" in mounting_type:
        losses["IAM"] = 5.0
    else:
        losses["IAM"] = 3.0

    # 2. Soiling loss - typical 2% for Indian sites
    losses["Soiling"] = 2.0

    # 3. Shading / horizon loss - typical 1.5%
    losses["Shading"] = 1.5

    # 4. Module quality / LID - typical 1.5%
    losses["Module Quality / LID"] = 1.5

    # 5. Temperature loss - computed from NOCT, ambient temp and irradiance
    cell_temp = avg_temp + (noct - 20) / 800 * irradiance_w_m2
    temp_loss = abs(temp_coeff_pmax) * max(0, cell_temp - 25)
    losses["Temperature"] = round(max(0, temp_loss), 1)

    # 6. Low irradiance loss - typical 2%
    losses["Low Irradiance"] = 2.0

    # 7. Mismatch loss - typical 1%
    losses["Mismatch"] = 1.0

    # 8. Ohmic wiring loss - typical 1.5%
    losses["Ohmic Wiring"] = 1.5

    # 9. Inverter loss - typical 2.5%
    losses["Inverter"] = 2.5

    # 10. Transformer / grid connection - typical 1%
    losses["Transformer & Grid"] = 1.0

    # 11. Availability - typical 1.5%
    losses["Availability"] = 1.5

    # Build cumulative series for waterfall
    cumulative = 100.0
    loss_series = []
    for name, pct in losses.items():
        cumulative -= pct
        loss_series.append((name, pct, round(cumulative, 1)))

    return loss_series, losses


def get_weather_summary(weather_data):
    """Format weather data summary for report display."""
    if not weather_data:
        return "Weather data: Heuristic estimate"
    ghi_monthly, _, _, source = _extract_monthly_data(weather_data)
    if not ghi_monthly:
        return "Weather data: Heuristic estimate"
    vals = [v for v in ghi_monthly.values() if v is not None]
    if not vals:
        return "Weather data: Heuristic estimate"
    annual = sum(vals)
    monthly_avg = annual / 12
    return f"{source}: GHI {annual:.0f} kWh/m²/yr ({monthly_avg:.1f} kWh/m²/month avg)"
