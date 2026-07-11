"""
Weather Data Module - NASA POWER API Integration
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
    logger.warning("requests not installed; NASA POWER API unavailable")


def fetch_nasa_power_monthly(lat, lon, start_year=2020, end_year=2024):
    """Fetch monthly solar meteorology from NASA POWER REST API.
    Returns dict of monthly arrays or None on failure.
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
        f"&community=re"
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
            values = properties.get(param, {})
            monthly[param] = values
        return monthly
    except Exception as e:
        logger.warning(f"NASA POWER API call failed: {e}")
        return None


def compute_annual_solar_metrics(lat, lon, weather_data, mounting_type="Fixed Tilt", tilt_angle=None):
    """Compute annual solar metrics from NASA POWER data or heuristic fallback.
    Returns dict with annual_ghi, annual_poa, specific_yield, performance_ratio, cuf, avg_temp.
    """
    if weather_data and "ALLSKY_SFC_SW_GHI" in weather_data:
        ghi_values = [v for v in weather_data["ALLSKY_SFC_SW_GHI"].values() if v is not None]
        t2m_values = [v for v in weather_data.get("T2M", {}).values() if v is not None]
        if ghi_values:
            annual_ghi = sum(ghi_values)
            avg_temp = sum(t2m_values) / len(t2m_values) if t2m_values else 25.0
        else:
            return _heuristic_metrics(lat, mounting_type, tilt_angle)
    else:
        return _heuristic_metrics(lat, mounting_type, tilt_angle)

    dni_values = [v for v in weather_data.get("ALLSKY_SFC_SW_DNI", {}).values() if v is not None]
    annual_dni = sum(dni_values) if dni_values else annual_ghi * 0.55

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
    """Fallback heuristic when NASA POWER is unavailable."""
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


def adjust_cuf_for_module(cuf, module_efficiency, reference_efficiency=21.0, temp_coeff=-0.35, noct=43, avg_temp=25.0, ghi_avg=5.5):
    """Adjust CUF for module-specific characteristics (efficiency, temperature, NOCT).
    Returns adjusted CUF.
    """
    eff_factor = module_efficiency / reference_efficiency

    cell_temp = avg_temp + (noct - 20) / 800 * (ghi_avg * 1000)
    temp_loss = abs(temp_coeff) * (cell_temp - 25)
    temp_factor = 1 - temp_loss / 100

    cuf_adj = cuf * eff_factor * temp_factor
    return round(cuf_adj, 4)


def compute_bifacial_gain(albedo, mounting_height_m, tilt_angle, ghi_annual, bifaciality_factor=0.7):
    """Compute bifacial generation boost.
    Returns dict with view_factor, rear_irradiance, boost_pct.
    """
    if tilt_angle is None:
        tilt_angle = 10
    tilt_rad = math.radians(tilt_angle)
    view_factor = (1 - math.cos(math.radians(90 - tilt_angle))) / 2
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
                               gen_y1_kwh, cuf, module_capacity_kw):
    """Compute monthly generation, PR, and yield from NASA POWER monthly data.
    Returns list of 12 dicts, one per month.
    """
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    ghi_monthly = weather_data.get("ALLSKY_SFC_SW_GHI", {}) if weather_data else {}
    t2m_monthly = weather_data.get("T2M", {}) if weather_data else {}

    ghi_values = [v for v in ghi_monthly.values() if v is not None]
    total_ghi = sum(ghi_values) if ghi_values else annual_ghi

    monthly_data = []
    for m_idx in range(12):
        m_key = list(ghi_monthly.keys())[m_idx] if ghi_monthly and len(ghi_monthly) > m_idx else f"{m_idx+1:02d}"
        m_ghi = ghi_monthly.get(m_key, annual_ghi / 12) if ghi_monthly else annual_ghi / 12
        m_temp = t2m_monthly.get(m_key, 25.0) if t2m_monthly else 25.0
        if m_ghi is None:
            m_ghi = annual_ghi / 12
        if m_temp is None:
            m_temp = 25.0

        ghi_frac = m_ghi / total_ghi if total_ghi > 0 else 1 / 12
        m_gen = gen_y1_kwh * ghi_frac
        m_poa = annual_poa * ghi_frac
        m_pr = (m_gen / (m_poa * module_capacity_kw * 1000)) if (m_poa > 0 and module_capacity_kw > 0) else 0
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
    annual_metrics = {
        "total_gen": round(sum(d["gen_kwh"] for d in monthly_data), 0),
        "avg_pr": round(sum(d["pr"] for d in monthly_data) / 12, 3),
        "avg_temp": round(sum(d["temp"] for d in monthly_data) / 12, 1),
        "total_ghi": round(sum(d["ghi"] for d in monthly_data), 0),
        "total_poa": round(sum(d["poa"] for d in monthly_data), 0),
    }

    return monthly_data, annual_metrics


def compute_pvsyst_losses(temp_coeff_pmax, noct, avg_temp, cuf, albedo=0.20,
                           mounting_type="Fixed Tilt", ghi_avg=5.5):
    """Compute PVSyst-style energy loss breakdown.
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
    cell_temp = avg_temp + (noct - 20) / 800 * (ghi_avg * 1000)
    temp_loss = abs(temp_coeff_pmax) * (cell_temp - 25)
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
        return "Weather data: Heuristic estimate (NASA POWER unavailable)"
    ghi = weather_data.get("ALLSKY_SFC_SW_GHI", {})
    if not ghi:
        return "Weather data: Heuristic estimate"
    vals = [v for v in ghi.values() if v is not None]
    if not vals:
        return "Weather data: Heuristic estimate"
    annual = sum(vals)
    monthly_avg = annual / 12
    return f"NASA POWER: GHI {annual:.0f} kWh/m²/yr ({monthly_avg:.1f} kWh/m²/month avg)"
