"""
Weighted Multi-Criteria Scoring Module
Ranks modules across 7 criteria using min-max normalization and user-defined weights.
"""
import numpy as np


def get_default_weights():
    """Return default weights for all 7 criteria (sum = 100)."""
    return {
        "lcoe": 20,
        "irr": 20,
        "generation_yield": 15,
        "degradation": 10,
        "warranty": 10,
        "price": 15,
        "temp_coeff": 10,
    }


def _normalize(values, higher_is_better=True):
    """Min-max normalize a list of values to 0-100 scale."""
    arr = np.array(values, dtype=float)
    mn, mx = np.min(arr), np.max(arr)
    if mx == mn:
        return [50.0] * len(arr)
    if higher_is_better:
        return ((arr - mn) / (mx - mn) * 100).tolist()
    else:
        return ((mx - arr) / (mx - mn) * 100).tolist()


def compute_scores(results_dict, module_specs_list, weights=None):
    """Compute weighted multi-criteria scores for all modules.

    Args:
        results_dict: dict of {module_short_name: result_dict} from financial_engine
        module_specs_list: list of module spec dicts (parallel to results_dict values)
        weights: dict of {criterion_name: weight} or None for defaults

    Returns:
        list of dicts: [{short, name, scores: {criterion: val}, weighted_total, rank}, ...]
    """
    if weights is None:
        weights = get_default_weights()

    modules = list(results_dict.keys())
    if not modules:
        return []

    # Extract raw values for each criterion
    raw = {m: results_dict[m] for m in modules}

    lcoe_vals = [raw[m]["lcoe"] for m in modules]
    irr_vals = [raw[m]["irr"] * 100 for m in modules]
    gen_yield_vals = [raw[m]["gen_y1_kwh"] / raw[m]["capacity_mw"] / 1000 for m in modules]
    deg_vals = [raw[m].get("deg_ann", 0.55) for m in modules]
    warranty_vals = [raw[m].get("warranty_yrs", 25) for m in modules]
    price_vals = [raw[m].get("price_wp", 20) for m in modules]
    tc_vals = [abs(raw[m].get("temp_coeff", -0.35)) for m in modules]

    # Normalize: LCOE lower is better, degradation lower is better,
    # price lower is better, temp coeff (abs) lower is better.
    # IRR higher is better, generation yield higher is better,
    # warranty higher is better.
    norm = {
        "lcoe": _normalize(lcoe_vals, higher_is_better=False),
        "irr": _normalize(irr_vals, higher_is_better=True),
        "generation_yield": _normalize(gen_yield_vals, higher_is_better=True),
        "degradation": _normalize(deg_vals, higher_is_better=False),
        "warranty": _normalize(warranty_vals, higher_is_better=True),
        "price": _normalize(price_vals, higher_is_better=False),
        "temp_coeff": _normalize(tc_vals, higher_is_better=False),
    }

    scored = []
    for i, m in enumerate(modules):
        total = 0
        scores = {}
        for criterion, w in weights.items():
            val = norm[criterion][i] * (w / 100)
            scores[criterion] = round(norm[criterion][i], 1)
            total += val
        scored.append({
            "short": m,
            "name": module_specs_list[i].get("name", m),
            "scores": scores,
            "weighted_total": round(total, 1),
        })

    # Rank by weighted_total descending
    scored.sort(key=lambda x: x["weighted_total"], reverse=True)
    for rank, entry in enumerate(scored, 1):
        entry["rank"] = rank

    return scored


def format_scoring_table(scored_list):
    """Format scoring results as a list of tuples for PDF table rendering."""
    headers = ["Module", "LCOE", "IRR", "Yield", "Degr.", "Warr.", "Price", "TC", "Total", "Rank"]
    rows = []
    for entry in scored_list:
        s = entry["scores"]
        rows.append([
            entry["name"],
            f'{s.get("lcoe", 0):.0f}',
            f'{s.get("irr", 0):.0f}',
            f'{s.get("generation_yield", 0):.0f}',
            f'{s.get("degradation", 0):.0f}',
            f'{s.get("warranty", 0):.0f}',
            f'{s.get("price", 0):.0f}',
            f'{s.get("temp_coeff", 0):.0f}',
            f'{entry["weighted_total"]:.1f}',
            f'#{entry["rank"]}',
        ])
    return headers, rows
