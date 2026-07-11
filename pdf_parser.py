"""
Solar Module Datasheet Parser
Automatically extracts specifications from manufacturer PDF datasheets.
Supports text-based PDFs and image-based PDFs (via OCR).

Multi-Strategy Extraction Pipeline:
  Strategy A: Labelled-row scan  (Vmp / Imp / Isc / Voc rows, Wp as column header)
  Strategy B: Header-data scan   (Pmax Vmp Imp Isc Voc header row, then data rows)
  Strategy C: Interleaved pairs  (Redren-style STC+NOCT interleaved in one row)
  Strategy D: Heuristic scan     (any line containing the target Wp, pattern-match floats)

After extraction, cross-validation enforces:
  |Vmp * Imp - Pmax| < 15W  |  Isc > Imp  |  Voc > Vmp
"""
import re
import os
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF bytes. Returns (text, method_used)."""

    # Try pypdf first (fastest, best for native-text PDFs)
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        if len(text.strip()) > 100:
            return text, "pypdf"
    except Exception:
        pass

    # Try pdfminer (better layout reconstruction)
    try:
        from pdfminer.high_level import extract_text as pm_extract
        text = pm_extract(io.BytesIO(pdf_bytes))
        if len(text.strip()) > 100:
            return text, "pdfminer"
    except Exception:
        pass

    # Fallback: OCR via PyMuPDF + tesseract
    try:
        import fitz
        import pytesseract
        if os.name == "nt":
            pytesseract.pytesseract.tesseract_cmd = (
                r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            )
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            mat = fitz.Matrix(3, 3)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            t = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
            text += t + "\n"
        if len(text.strip()) > 100:
            return text, "ocr"
    except Exception:
        pass

    return "", "none"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text):
    """Normalise whitespace: collapse multiple spaces/tabs to single space."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n", "\n", text)
    return text


def _to_floats(line):
    """Extract all numeric tokens (int or float) from a line as float list.
    Skips tokens that look like model-code fragments (e.g. 21 inside BiN-21).
    Strategy: tokenise on whitespace, keep tokens that are *purely* numeric
    (possibly with one decimal point), ignore anything that also contains letters
    or hyphens that are adjacent to digits (model codes).
    """
    # Remove known model-code-like patterns first: letters-digits-digits
    cleaned = re.sub(r"[A-Za-z][A-Za-z0-9]*[-][0-9]+", "", line)
    # Also strip leading alphabetic model names at start of line
    cleaned = re.sub(r"^[A-Za-z][A-Za-z0-9\-_]+\s+", "", cleaned)
    nums = re.findall(r"\b(\d+\.?\d*)\b", cleaned)
    return [float(n) for n in nums]


def _pick_power_cluster(powers):
    """Gap-based (>50 W) clustering: keep the upper cluster (STC powers).
    Returns sorted list.
    """
    if not powers:
        return []
    sp = sorted(powers)
    if len(sp) <= 1:
        return sp
    max_gap, max_idx = 0, 0
    for i in range(len(sp) - 1):
        gap = sp[i + 1] - sp[i]
        if gap > max_gap:
            max_gap = gap
            max_idx = i
    if max_gap > 50:
        return sp[max_idx + 1 :]
    return sp


def _is_valid_elec(vmp, imp, isc, voc, pmax=None):
    """Return True if the 4-tuple looks like plausible STC electrical params."""
    ok = (
        25.0 <= vmp <= 65.0
        and 8.0 <= imp <= 22.0
        and 8.0 <= isc <= 24.0
        and 30.0 <= voc <= 75.0
        and isc > imp
        and voc > vmp
    )
    if ok and pmax is not None:
        ok = abs(vmp * imp - pmax) <= 20
    return ok


def _cross_validate(specs, selected_wp):
    """Remove electrical values that fail cross-validation."""
    vmp = specs.get("vmp")
    imp = specs.get("imp")
    isc = specs.get("isc")
    voc = specs.get("voc")
    if None in (vmp, imp, isc, voc):
        return
    if not _is_valid_elec(vmp, imp, isc, voc, pmax=selected_wp):
        for k in ("vmp", "imp", "isc", "voc"):
            specs.pop(k, None)


# ---------------------------------------------------------------------------
# Power-option detection
# ---------------------------------------------------------------------------

def _detect_power_options(text, lines):
    """Return sorted list of likely STC Wp values found in datasheet."""
    all_powers = set()
    model_powers = set()

    # --- Strategy 1: model-code patterns (most reliable) ---
    # Pass 1: simple codes — letter prefix directly followed by dash then -NNN
    # e.g. G12R-600, Steorra-600, WSM-615
    for m in re.finditer(
        r"[A-Za-z][A-Za-z0-9]{2,}[-](\d{3})(?:[Ww](?:p)?)?(?:\s|,|$|\)|\n)",
        text,
    ):
        val = int(m.group(1))
        if 300 <= val <= 750:
            model_powers.add(val)

    # Pass 2: compound codes like BiN-21-615 (letter, internal dash+digits, -NNN)
    # Only use if pass 1 found nothing (avoids OCR artifacts matching this broad pattern)
    if not model_powers:
        for m in re.finditer(
            r"[A-Za-z][A-Za-z0-9\-]{2,}[-](\d{3})(?:[Ww](?:p)?)?(?:\s|,|$|\)|\n)",
            text,
        ):
            val = int(m.group(1))
            if 300 <= val <= 750:
                model_powers.add(val)

    # Pass 3: Redren/OCR style — long model code followed by its Pmax on the same line
    # e.g. "RSMIOMP-I5GHCBF610 610 45.70 13.35 ..."
    # Validate: the 3-digit standalone value must match the last 3 digits of the code.
    # This avoids the Bifacial Gain table rows (HCBF600 followed by 630.00).
    if not model_powers:
        for line in lines:
            # \S{8,}: any non-whitespace sequence of 8+ chars (model code may have dashes)
            lm = re.match(r"(\S{8,})\s+(\d{3})\s+\d+\.\d+", line)
            if lm:
                code_suffix = lm.group(1)[-3:]  # last 3 chars of model code
                pmax_str = lm.group(2)
                if code_suffix == pmax_str:  # must match (e.g. BF610 ends in 610)
                    val = int(pmax_str)
                    if 300 <= val <= 750:
                        model_powers.add(val)




    # --- Strategy 2: explicit Pmax / Power keyword ---
    for pat in [
        r"(?:Pmax|Max\.?\s*Power|Maximum\s*Power)\s*(?:\(W[pP]?\)|\(Pmax\))?[:\s]*(\d+)\s*W",
        r"(\d{3})\s*W[pP]?\s*(?:\(STC\)|@\s*STC|STC)",
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
            val = int(m.group(1))
            if 300 <= val <= 750:
                all_powers.add(val)

    # --- Strategy 3: table rows — lines that have >=3 decimal groups
    #     AND at least one int in the 300-750 range ---
    # (Inox-style columnar headers list wattages in one row)
    for line in lines:
        ints_in_range = [
            int(n) for n in re.findall(r"\b(\d{3})\b", line)
            if 300 <= int(n) <= 750
        ]
        if len(ints_in_range) >= 3:
            for v in ints_in_range:
                all_powers.add(v)

    # --- Strategy 4: Wp suffix anywhere ---
    for m in re.finditer(r"(\d{3})\s*Wp\b", text, re.IGNORECASE):
        val = int(m.group(1))
        if 300 <= val <= 750:
            all_powers.add(val)

    # --- Strategy 5: wattage range from product title/cover ---
    # Matches: "580 To 610W", "580-610W", "580 to 610 Wp", "580W ~ 610W"
    range_powers = set()
    range_m = re.search(
        r"(\d{3})\s*(?:To|to|~|-)\s*(\d{3})\s*W[pP]?",
        text
    )
    if range_m:
        lo_r, hi_r = int(range_m.group(1)), int(range_m.group(2))
        if 300 <= lo_r <= 750 and 300 <= hi_r <= 750 and hi_r > lo_r:
            # Generate 5W steps within the range
            for v in range(lo_r, hi_r + 5, 5):
                if v <= hi_r:
                    range_powers.add(v)

    # If a clean range was found, use it as authoritative (overrides OCR noise)
    if range_powers:
        return sorted(range_powers)

    # Prefer model-code results as primary source
    primary = model_powers if model_powers else all_powers

    # Exclude NOCT/low values by gap clustering
    clustered = _pick_power_cluster(primary)

    # Merge nearby all_powers values into the clustered set, BUT only if
    # we don't already have model_powers (those are authoritative).
    if not model_powers and clustered and all_powers:
        lo, hi = min(clustered) - 20, max(clustered) + 20
        for v in all_powers:
            if lo <= v <= hi:
                clustered.append(v)
        clustered = sorted(set(clustered))

        # For non-model-code PDFs (often OCR), filter to values that fit a
        # consistent step pattern (5W or 10W increments, real product ranges).
        # This removes OCR artifacts like 609, 614, 619 that don't fit a 5W grid.
        def _filter_to_5w_grid(vals):
            """Keep only values that land on a 5W grid (mod 5 == 0)."""
            on_grid = [v for v in vals if v % 5 == 0]
            if len(on_grid) >= 2:
                return on_grid
            return vals  # fallback: return all if insufficient on-grid values
        clustered = _filter_to_5w_grid(clustered)

    # Secondary cleanup: cap at model_powers max + 10W
    # This removes low-irradiance STC equivalents (e.g. Waaree 660-750W rows)
    if model_powers and clustered:
        anchor_max = max(model_powers)
        clustered = [v for v in clustered if v <= anchor_max + 10]

    return clustered


# ---------------------------------------------------------------------------
# Electrical parameter extraction — multi-strategy cascade
# ---------------------------------------------------------------------------

def _extract_electrical(lines, text, selected_wp):
    """
    Try 4 strategies in order to extract Vmp, Imp, Isc, Voc, Eff for selected_wp.
    Returns dict with found keys (may be partial / empty).
    """
    pw_str = str(int(selected_wp))

    # ---- Strategy A: Labelled-row scan (Inox / columnar style) ----
    result = _strategy_A_labelled_rows(lines, selected_wp)
    if result and _is_valid_elec(
        result.get("vmp", 0), result.get("imp", 0),
        result.get("isc", 0), result.get("voc", 0), selected_wp
    ):
        return result

    # ---- Strategy B: Header→data scan (Waaree / standard table) ----
    result = _strategy_B_header_data(lines, selected_wp)
    if result and _is_valid_elec(
        result.get("vmp", 0), result.get("imp", 0),
        result.get("isc", 0), result.get("voc", 0), selected_wp
    ):
        return result

    # ---- Strategy C: Interleaved STC/NOCT pairs (Redren style) ----
    result = _strategy_C_interleaved(lines, selected_wp)
    if result and _is_valid_elec(
        result.get("vmp", 0), result.get("imp", 0),
        result.get("isc", 0), result.get("voc", 0), selected_wp
    ):
        return result

    # ---- Strategy D: Heuristic scan (last resort) ----
    result = _strategy_D_heuristic(lines, selected_wp)
    if result and _is_valid_elec(
        result.get("vmp", 0), result.get("imp", 0),
        result.get("isc", 0), result.get("voc", 0), selected_wp
    ):
        return result

    return {}


def _strategy_A_labelled_rows(lines, selected_wp):
    """
    Columnar format: parameters are row labels, wattages are column headers.
    Two sub-variants handled:
      (a) Numeric header row:  | 600 | 605 | 610 | 615 | 620 | 625 |
      (b) Model-name header:   | ISL NG12R 600 | ISL NG12R 605 | ...

    For interleaved STC/NOCT data rows (Inox), the Wp column index
    in the header maps to data-column index = col_idx*2 (STC value)
    because each Wp has one STC and one NOCT value.
    """
    col_idx = None
    power_row_line_idx = None
    is_interleaved = False

    for i, line in enumerate(lines):
        # Variant (a): pure numeric header row with 3+ values in 300-750 range
        nums = [int(n) for n in re.findall(r"\b(\d{3})\b", line)
                if 300 <= int(n) <= 750]
        if len(nums) >= 3 and int(selected_wp) in nums:
            col_idx = nums.index(int(selected_wp))
            power_row_line_idx = i
            # Check if table has interleaved STC/NOCT — look for "NOCT" in header
            # or look for a "STC NOCT STC NOCT" pattern nearby
            for check_line in lines[max(0, i-2):i+4]:
                if re.search(r'NOCT', check_line, re.IGNORECASE):
                    is_interleaved = True
                    break
            break

        # Variant (b): model-name header containing the Wp embedded in names
        # e.g. 'ISL NG12R 600  ISL NG12R 605  ISL NG12R 610'
        # Count how many 3-digit numbers appear in 300-750 range
        embedded_powers = [int(n) for n in re.findall(r"\b(\d{3})\b", line)
                           if 300 <= int(n) <= 750]
        if len(embedded_powers) >= 3 and int(selected_wp) in embedded_powers:
            col_idx = embedded_powers.index(int(selected_wp))
            power_row_line_idx = i
            # These model-name headers always precede interleaved STC/NOCT tables
            # Check for STC/NOCT header nearby
            for check_line in lines[max(0, i-2):i+4]:
                if re.search(r'NOCT', check_line, re.IGNORECASE):
                    is_interleaved = True
                    break
            break

    if col_idx is None:
        return {}

    specs = {}
    param_patterns = {
        "vmp": r"\bVmp\b|Maximum Power Voltage|Voltage.*(?:Pmax|MPP)|MPP.*Voltage",
        "imp": r"\bImp\b|Maximum Power Current|Current.*(?:Pmax|MPP)|MPP.*Current",
        "isc": r"\bIsc\b|Short[\s\-]*Circuit.*Current|Current.*Short[\s\-]*Circuit",
        "voc": r"\bVoc\b|Open[\s\-]*Circuit.*Voltage|Voltage.*Open[\s\-]*Circuit",
        "efficiency_pct": r"\bEff(?:iciency)?\b|\bη\b|Module Eff",
    }
    # Search a window of ±50 lines around the power row
    lo = max(0, power_row_line_idx - 5)
    hi = min(len(lines), power_row_line_idx + 55)

    for key, pat in param_patterns.items():
        for line in lines[lo:hi]:
            if re.search(pat, line, re.IGNORECASE):
                floats = _to_floats(line)
                if key == "efficiency_pct":
                    eff_vals = [f for f in floats if 15 <= f <= 30]
                    # Efficiency is STC-only (no NOCT), col_idx direct
                    if col_idx < len(eff_vals):
                        specs[key] = eff_vals[col_idx]
                    elif eff_vals:
                        specs[key] = eff_vals[0]
                else:
                    # For voltage/current: filter to plausible ranges
                    if key in ("vmp", "voc"):
                        cands = [f for f in floats if 20 <= f <= 80]
                    else:
                        cands = [f for f in floats if 5 <= f <= 30]

                    if is_interleaved:
                        # interleaved: STC value at position col_idx*2
                        stc_idx = col_idx * 2
                        if stc_idx < len(cands):
                            specs[key] = cands[stc_idx]
                    else:
                        if col_idx < len(cands):
                            specs[key] = cands[col_idx]
                        elif cands:
                            specs[key] = cands[0]
                break  # found a matching row for this param

    return specs


def _strategy_B_header_data(lines, selected_wp):
    """
    Standard table: one header row with Pmax Vmp Imp Isc Voc,
    then data rows where the first column is the Pmax value.
    Handles both STC-only and STC+NOCT column pairs.
    """
    pw_str = str(int(selected_wp))

    for i, line in enumerate(lines):
        # Look for a header row containing Pmax and at least two of Vmp/Imp/Isc/Voc
        if not re.search(r"Pmax|Pmpp", line, re.IGNORECASE):
            continue
        elec_kws = sum(1 for kw in ("Vmp", "Imp", "Isc", "Voc")
                       if re.search(kw, line, re.IGNORECASE))
        if elec_kws < 2:
            continue

        # Determine column order from header
        header_order = []
        for kw, key in [("Pmax", "pmax"), ("Vmp", "vmp"), ("Imp", "imp"),
                         ("Isc", "isc"), ("Voc", "voc"), ("Eff", "efficiency_pct")]:
            if re.search(kw, line, re.IGNORECASE):
                header_order.append(key)

        # Scan next 20 lines for data rows containing selected_wp
        for j in range(i + 1, min(i + 25, len(lines))):
            dline = lines[j]
            if pw_str not in dline:
                continue
            floats = _to_floats(dline)
            # Find all positions of selected_wp value in floats
            pmax_idxs = [k for k, f in enumerate(floats)
                         if abs(f - selected_wp) <= 2]
            if not pmax_idxs:
                continue

            for pmax_idx in pmax_idxs:
                # Try to map float positions to header columns
                data_floats = floats[pmax_idx:]
                if len(data_floats) < 4:
                    continue

                specs = {}
                # Check if STC/NOCT interleaved (every other value)
                # STC columns at positions 0,2,4,6,8; NOCT at 1,3,5,7,9
                # Both STC Vmp range 25-65, NOCT Vmp range 22-60 (slightly lower)
                if (len(data_floats) >= 9 and
                        25 <= data_floats[2] <= 65 and
                        20 <= data_floats[3] <= 60 and
                        data_floats[3] < data_floats[2]):
                    # Interleaved: take even-indexed (STC)
                    specs = {
                        "vmp": data_floats[2],
                        "imp": data_floats[4],
                        "isc": data_floats[6],
                        "voc": data_floats[8],
                    }
                    if len(data_floats) > 10 and 15 <= data_floats[10] <= 30:
                        specs["efficiency_pct"] = data_floats[10]
                elif len(data_floats) >= 5:
                    # Straight columns: skip pmax at index 0
                    cands = data_floats[1:]
                    # Find Vmp (25-65), Imp (8-22), Isc (8-24), Voc (30-75)
                    stc = _pick_stc_from_sequence(cands, selected_wp)
                    if stc:
                        specs = stc

                if specs and _is_valid_elec(
                    specs.get("vmp", 0), specs.get("imp", 0),
                    specs.get("isc", 0), specs.get("voc", 0), selected_wp
                ):
                    return specs

    return {}


def _pick_stc_from_sequence(floats, pmax):
    """
    Given a list of floats that follow a Pmax value,
    try to identify Vmp, Imp, Isc, Voc in order.
    Handles straight STC-only and STC/NOCT interleaved sequences.
    """
    # Check interleaved (pairs: STC, NOCT for each param)
    if len(floats) >= 8:
        v_s, v_n = floats[0], floats[1]
        i_s, i_n = floats[2], floats[3]
        isc_s, isc_n = floats[4], floats[5]
        voc_s, voc_n = floats[6], floats[7]
        if (25 <= v_s <= 65 and 20 <= v_n <= 60 and v_n < v_s and
                8 <= i_s <= 22 and 6 <= i_n <= 20 and i_n < i_s and
                8 <= isc_s <= 24 and 6 <= isc_n <= 22 and isc_n < isc_s and
                30 <= voc_s <= 75 and 25 <= voc_n <= 70 and voc_n < voc_s):
            result = {"vmp": v_s, "imp": i_s, "isc": isc_s, "voc": voc_s}
            if len(floats) > 8 and 15 <= floats[8] <= 30:
                result["efficiency_pct"] = floats[8]
            return result

    # Straight sequence: Vmp Imp Isc Voc [Eff]
    if len(floats) >= 4:
        v, imp_, isc_, voc_ = floats[0], floats[1], floats[2], floats[3]
        if (25 <= v <= 65 and 8 <= imp_ <= 22 and
                8 <= isc_ <= 24 and 30 <= voc_ <= 75 and
                isc_ > imp_ and voc_ > v):
            result = {"vmp": v, "imp": imp_, "isc": isc_, "voc": voc_}
            if len(floats) > 4 and 15 <= floats[4] <= 30:
                result["efficiency_pct"] = floats[4]
            return result

    # Try sliding window
    for i in range(len(floats) - 3):
        v, imp_, isc_, voc_ = floats[i], floats[i+1], floats[i+2], floats[i+3]
        if (25 <= v <= 65 and 8 <= imp_ <= 22 and
                8 <= isc_ <= 24 and 30 <= voc_ <= 75 and
                isc_ > imp_ and voc_ > v):
            result = {"vmp": v, "imp": imp_, "isc": isc_, "voc": voc_}
            if i + 4 < len(floats) and 15 <= floats[i+4] <= 30:
                result["efficiency_pct"] = floats[i+4]
            return result

    return {}


def _strategy_C_interleaved(lines, selected_wp):
    """
    Redren-style: a single data row contains:
    Pmax_STC Pmax_NOCT Vmp_STC Vmp_NOCT Imp_STC Imp_NOCT Isc_STC Isc_NOCT Voc_STC Voc_NOCT Eff
    Find rows containing the selected_wp int and try interleaved extraction.
    """
    pw_str = str(int(selected_wp))

    for line in lines:
        if pw_str not in line:
            continue
        floats = _to_floats(line)
        if len(floats) < 9:
            continue

        # Find position of selected_wp in float list
        pmax_positions = [i for i, f in enumerate(floats)
                          if abs(f - selected_wp) <= 2]
        for pos in pmax_positions:
            chunk = floats[pos:]
            # Try 11-value interleaved pattern
            if len(chunk) >= 11:
                pw1, pw2 = chunk[0], chunk[1]
                v_s, v_n = chunk[2], chunk[3]
                i_s, i_n = chunk[4], chunk[5]
                isc_s, isc_n = chunk[6], chunk[7]
                voc_s, voc_n = chunk[8], chunk[9]
                eff = chunk[10]

                if (300 <= pw1 <= 750 and 250 <= pw2 <= 750 and pw2 < pw1 and
                        25 <= v_s <= 65 and 20 <= v_n <= 60 and v_n < v_s and
                        8 <= i_s <= 22 and 6 <= i_n <= 20 and
                        8 <= isc_s <= 24 and 6 <= isc_n <= 22 and
                        30 <= voc_s <= 75 and 25 <= voc_n <= 70 and
                        15 <= eff <= 30):
                    return {
                        "vmp": v_s, "imp": i_s, "isc": isc_s,
                        "voc": voc_s, "efficiency_pct": eff,
                    }

            # Try 9-value interleaved without efficiency
            if len(chunk) >= 9:
                v_s, v_n = chunk[1], chunk[2]
                i_s, i_n = chunk[3], chunk[4]
                isc_s, isc_n = chunk[5], chunk[6]
                voc_s, voc_n = chunk[7], chunk[8]
                if (25 <= v_s <= 65 and 20 <= v_n <= 60 and v_n < v_s and
                        8 <= i_s <= 22 and 6 <= i_n <= 20 and
                        8 <= isc_s <= 24 and 6 <= isc_n <= 22 and
                        30 <= voc_s <= 75 and 25 <= voc_n <= 70):
                    return {
                        "vmp": v_s, "imp": i_s, "isc": isc_s, "voc": voc_s,
                    }

    return {}


def _strategy_D_heuristic(lines, selected_wp):
    """
    Last-resort: on any line containing selected_wp,
    extract all floats and try every sliding window of 4+ values.
    """
    pw_str = str(int(selected_wp))

    for line in lines:
        if pw_str not in line:
            continue
        floats = _to_floats(line)
        result = _pick_stc_from_sequence(floats, selected_wp)
        if result:
            return result

        # Also try after removing values in the power range
        filtered = [f for f in floats if not (250 <= f <= 800)]
        result = _pick_stc_from_sequence(filtered, selected_wp)
        if result:
            return result

    return {}


# ---------------------------------------------------------------------------
# Main spec parser
# ---------------------------------------------------------------------------

def parse_specs(text, technology_hint=None, selected_wp=None):
    """
    Parse extracted PDF text and return dict of module specifications.

    Args:
        text: raw text extracted from the PDF
        technology_hint: e.g. "Mono PERC", "N-TOPCon"
        selected_wp: if provided, extract electrical params for this wattage

    Returns:
        dict with specification keys
    """
    specs = {}
    text = _normalise(text)
    lines = text.split("\n")

    # ----- Power options -----
    power_opts = _detect_power_options(text, lines)
    specs["power_options"] = power_opts
    if power_opts:
        specs["power_wp"] = max(power_opts)  # default to highest Wp
    else:
        specs["power_wp"] = None

    # ----- Electrical parameters for selected_wp -----
    wp_to_use = selected_wp if selected_wp is not None else specs.get("power_wp")
    if wp_to_use is not None:
        elec = _extract_electrical(lines, text, wp_to_use)
        specs.update(elec)
        # Cross-validate: clear inconsistent values
        _cross_validate(specs, wp_to_use)

    # ----- Efficiency (standalone, if not already found) -----
    if "efficiency_pct" not in specs or not specs["efficiency_pct"]:
        for pat in [
            r"(?:Module\s*)?Eff(?:iciency)?\.?\s*(?:\(%\)|\(STC\)|:)?\s*(\d+\.?\d*)\s*%",
            r"(\d+\.\d+)\s*%\s*(?:Module\s*Eff)",
            r"Eff(?:iciency)?\s*[:\s]+(\d{2}\.\d+)",
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 15 <= val <= 30:
                    specs["efficiency_pct"] = val
                    break

    if "efficiency_pct" not in specs:
        for v in re.findall(r"(\d+\.\d+)\s*%", text):
            val = float(v)
            if 15 <= val <= 30:
                specs["efficiency_pct"] = val
                break

    # ----- Cell Technology -----
    tech_patterns = [
        (r"Mono\s*PERC|p-PERC|p\s*type\s*PERC", "Mono PERC"),
        (r"N[-\s]?Type\s*TOPCon|N-TOPCon|n\s*type\s*TOPCon|TOPCon", "N-TOPCon"),
        (r"HJT|HIT|Heterojunction", "HJT"),
        (r"Poly\s*PERC|Multi\s*PERC", "Poly PERC"),
    ]
    for pat, tech in tech_patterns:
        if re.search(pat, text, re.IGNORECASE):
            specs["technology"] = tech
            break
    if "technology" not in specs:
        specs["technology"] = technology_hint or "Mono PERC"

    # ----- Temperature Coefficients -----
    # Pmax
    tc_patterns = [
        r"Temperature\s*Co[-\s]*efficient\s*(?:of\s*)?P(?:max|mpp?)\s*(?:\(γ|\(Pmax|\(P\).*?)?[:\s]*[-\u2212]?(\d+\.?\d*)",
        r"Pmax\s*Temperature\s*Co[-\s]*efficient[:\s]*[-\u2212]?(\d+\.?\d*)",
        r"γ.*?[-\u2212](\d+\.?\d*)",
        r"Power\s*Temp(?:erature)?\s*Coeff?\.?\s*[:\s]*[-\u2212](\d+\.?\d*)",
        r"Coefficient\s*of\s*Pmax\s*[:\s]*[-\u2212](\d+\.?\d*)",
    ]
    for pat in tc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0.1 <= val <= 0.6:
                specs["temp_coeff_pmax"] = -val
                break

    if "temp_coeff_pmax" not in specs:
        m = re.search(r"[-\u2212](\d+\.\d+)\s*%/°?C", text)
        if m:
            val = float(m.group(1))
            if 0.2 <= val <= 0.6:
                specs["temp_coeff_pmax"] = -val

    # Voc temp coefficient
    voc_tc = re.search(
        r"(?:Temp.*Voc|Voc.*Temp|Temperature.*Voc).*?[-\u2212](\d+\.\d+)",
        text, re.IGNORECASE
    )
    if voc_tc:
        specs["temp_coeff_voc"] = -float(voc_tc.group(1))

    # Isc temp coefficient
    isc_tc = re.search(
        r"(?:Temp.*Isc|Isc.*Temp|Temperature.*Isc).*?[+\-](\d+\.?\d*)",
        text, re.IGNORECASE
    )
    if isc_tc:
        specs["temp_coeff_isc"] = float(isc_tc.group(1))

    # ----- NOCT -----
    noct_m = re.search(r"NOCT\s*[:\(]?\s*(\d{2})\s*[°±℃]", text, re.IGNORECASE)
    if noct_m:
        specs["noct"] = int(noct_m.group(1))

    # ----- Warranty -----
    prod_w = re.search(
        r"(\d+)\s*Years?\s*Product\s*(?:Warranty|Guarantee)",
        text, re.IGNORECASE
    )
    if prod_w:
        specs["warranty_product"] = int(prod_w.group(1))

    perf_w = re.search(
        r"(\d+)\s*Years?\s*(?:Linear\s*)?Power\s*(?:Output\s*)?(?:Warranty|Guarantee|Performance)",
        text, re.IGNORECASE
    )
    if perf_w:
        specs["warranty_power"] = int(perf_w.group(1))

    # ----- Degradation -----
    deg_y1 = re.search(
        r"(?:Year\s*[1I]|First\s*Year).*?(\d+\.?\d*)\s*%",
        text, re.IGNORECASE
    )
    if deg_y1:
        v = float(deg_y1.group(1))
        if 0.5 <= v <= 5:
            specs["deg_y1_pct"] = v

    deg_ann = re.search(
        r"(?:Annual|Subsequent|Linear).*?(\d+\.?\d*)\s*%\s*(?:per\s*year|annual|p\.a\.|/year)",
        text, re.IGNORECASE
    )
    if deg_ann:
        v = float(deg_ann.group(1))
        if 0.1 <= v <= 1.0:
            specs["deg_annual_pct"] = v

    if "deg_annual_pct" not in specs:
        deg_lin = re.search(
            r"(\d+\.?\d*)\s*%\s*(?:per\s*year|annual|p\.?a\.?)\s*(?:after|then|thereafter)",
            text, re.IGNORECASE
        )
        if deg_lin:
            v = float(deg_lin.group(1))
            if 0.1 <= v <= 1.0:
                specs["deg_annual_pct"] = v

    # ----- Dimensions -----
    # Try standard mm × mm × mm pattern (4-digit × 4-digit × 2-3-digit)
    dim_m = re.search(r"(\d{4})\s*[xX×*]\s*(\d{3,4})\s*[xX×*]\s*(\d{2,3})", text)
    if dim_m:
        specs["dimensions"] = f"{dim_m.group(1)}x{dim_m.group(2)}x{dim_m.group(3)}"
        specs["length_mm"] = int(dim_m.group(1))
        specs["width_mm"] = int(dim_m.group(2))
        specs["thickness_mm"] = int(dim_m.group(3))
        # Keep legacy keys for backwards compatibility
        specs["length"] = specs["length_mm"]
        specs["width"] = specs["width_mm"]
        specs["thickness"] = specs["thickness_mm"]

    # ----- Weight -----
    wt_m = re.search(r"(\d+\.?\d*)\s*(?:kgs?|kg|Kg|KG)\b", text)
    if wt_m:
        v = float(wt_m.group(1))
        if 15 <= v <= 60:
            specs["weight_kg"] = v

    # ----- Manufacturer -----
    mfr = ""
    # 1. Domain name
    dm = re.search(r"(?:www\.)?([A-Za-z]+)\.(?:com|co\.in|in)\b", text)
    if dm:
        candidate = dm.group(1)
        if len(candidate) >= 4:
            mfr = candidate[0].upper() + candidate[1:]
    # 2. Company suffix
    if not mfr:
        em = re.search(
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+"
            r"(?:Energy|Energies|Technologies|Pvt\.?\s*Ltd|Industries|Power|Solar)",
            text,
        )
        if em:
            mfr = em.group(1).strip()
    # 3. First capitalised multi-word on early lines
    if not mfr:
        skip = (r"Watt|Volt|Amp|Cell|Module|Panel|Model|Temp|Graph|I-V|"
                r"Current|Voltage|Power|Warranty|Dimension|Weight|Operating|"
                r"Mechanical|Electrical|Specifications|Data|Sheet|Product")
        for line in lines[:25]:
            line = line.strip()
            if not line or len(line) < 4 or re.match(r"^\d", line):
                continue
            if re.search(skip, line, re.IGNORECASE):
                continue
            m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", line)
            if m:
                candidate = m.group(1).strip()
                if 4 <= len(candidate) < 30:
                    mfr = candidate
                    break
    if mfr:
        specs["manufacturer"] = mfr

    # ----- Cell count -----
    cell_m = re.search(r"(\d+)\s*(?:Cells?|cells?)\s*[,/]", text)
    if cell_m:
        specs["cell_count"] = int(cell_m.group(1))
    else:
        cell_m2 = re.search(r"(\d+)\s*(?:HC|BB|half.?cut|Half.?Cut)", text, re.IGNORECASE)
        if cell_m2:
            c = int(cell_m2.group(1))
            if 60 <= c <= 200:
                specs["cell_count"] = c

    # ----- Bifacial -----
    specs["bifacial"] = bool(re.search(r"Bi[-\s]*facial|Bifacial", text, re.IGNORECASE))

    # ----- Technology-specific defaults for missing values -----
    tech = specs.get("technology", "Mono PERC")
    if "temp_coeff_pmax" not in specs:
        specs["temp_coeff_pmax"] = -0.30 if "TOPCon" in tech else -0.35
    if "temp_coeff_voc" not in specs:
        specs["temp_coeff_voc"] = -0.26 if "TOPCon" in tech else -0.27
    if "temp_coeff_isc" not in specs:
        specs["temp_coeff_isc"] = 0.046 if "TOPCon" in tech else 0.050
    if "noct" not in specs:
        specs["noct"] = 43
    if "deg_y1_pct" not in specs:
        specs["deg_y1_pct"] = 1.0 if "TOPCon" in tech else 2.0
    if "deg_annual_pct" not in specs:
        specs["deg_annual_pct"] = 0.40 if "TOPCon" in tech else 0.55
    if "warranty_product" not in specs:
        specs["warranty_product"] = 12
    if "warranty_power" not in specs:
        specs["warranty_power"] = 30 if "TOPCon" in tech else 27

    return specs


# ---------------------------------------------------------------------------
# High-level entry points
# ---------------------------------------------------------------------------

def extract_module_specs(pdf_bytes, technology_hint=None, selected_wp=None):
    """Extract text from PDF, parse specs, return structured data dict."""
    try:
        text, method = extract_text_from_pdf(pdf_bytes)
        specs = parse_specs(text, technology_hint, selected_wp=selected_wp)
        specs["_extraction_method"] = method
        specs["_raw_text_length"] = len(text)
    except Exception as e:
        logger.warning("PDF parsing failed: %s", e)
        specs = {
            "power_options": [],
            "power_wp": None,
            "efficiency_pct": 21.0,
            "technology": technology_hint or "Mono PERC",
            "temp_coeff_pmax": -0.35,
            "deg_y1_pct": 2.0,
            "deg_annual_pct": 0.55,
            "warranty_power": 25,
            "warranty_product": 12,
            "noct": 43,
            "bifacial": False,
            "_extraction_method": "error",
            "_error": str(e),
        }
    return specs


def format_specs_for_display(specs):
    """Format specs dict for human-readable display."""
    lines = []
    if specs.get("manufacturer"):
        lines.append(f"Manufacturer    : {specs['manufacturer']}")
    if specs.get("power_options"):
        lines.append(f"Power Options   : {specs['power_options']} Wp")
    if specs.get("power_wp"):
        lines.append(f"Selected Power  : {specs['power_wp']} Wp")
    if specs.get("efficiency_pct"):
        lines.append(f"Efficiency      : {specs['efficiency_pct']:.2f}%")
    if specs.get("technology"):
        lines.append(f"Technology      : {specs['technology']}")
    if specs.get("vmp"):
        lines.append(f"Vmp (STC)       : {specs['vmp']:.2f} V")
    if specs.get("imp"):
        lines.append(f"Imp (STC)       : {specs['imp']:.2f} A")
    if specs.get("voc"):
        lines.append(f"Voc (STC)       : {specs['voc']:.2f} V")
    if specs.get("isc"):
        lines.append(f"Isc (STC)       : {specs['isc']:.2f} A")

    # Cross-validation result
    vmp, imp, isc, voc, pw = (specs.get(k) for k in ("vmp","imp","isc","voc","power_wp"))
    if vmp and imp and pw:
        calc_pmax = vmp * imp
        lines.append(f"  [Vmp×Imp={calc_pmax:.1f}W vs Pmax={pw}W "
                     f"| Δ={abs(calc_pmax-pw):.1f}W {'✓ OK' if abs(calc_pmax-pw)<=20 else '⚠ CHECK'}]")

    if specs.get("temp_coeff_pmax"):
        lines.append(f"Temp Coeff Pmax : {specs['temp_coeff_pmax']:.3f} %/°C")
    if specs.get("noct"):
        lines.append(f"NOCT            : {specs['noct']} °C")
    if specs.get("deg_y1_pct"):
        lines.append(f"Y1 Degradation  : {specs['deg_y1_pct']:.1f}%")
    if specs.get("deg_annual_pct"):
        lines.append(f"Annual Degr.    : {specs['deg_annual_pct']:.2f}%")
    if specs.get("warranty_power"):
        lines.append(f"Power Warranty  : {specs['warranty_power']} years")
    if specs.get("dimensions"):
        lines.append(f"Dimensions      : {specs['dimensions']} mm")
    if specs.get("weight_kg"):
        lines.append(f"Weight          : {specs['weight_kg']:.1f} kg")
    if specs.get("cell_count"):
        lines.append(f"Cells           : {specs['cell_count']}")
    if specs.get("bifacial"):
        lines.append("Bifacial        : Yes")
    if specs.get("_extraction_method"):
        lines.append(f"(Extracted via  : {specs['_extraction_method']})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    test_files = [
        (r"d:\SelectBestModule\Redren_Steorra_Mono_PERC_Bi-facial_580 To 610W (BIG DCR).pdf", "Mono PERC"),
        (r"d:\SelectBestModule\Waaree615DCR.pdf", "N-TOPCon"),
        (r"d:\SelectBestModule\Inox Datasheet-G12R-132cells.pdf", "Mono PERC"),
    ]
    for path, hint in test_files:
        if not os.path.exists(path):
            print(f"SKIP (not found): {path}")
            continue
        with open(path, "rb") as f:
            data = f.read()
        specs = extract_module_specs(data, hint)
        print(f"\n{'='*60}")
        print(f"FILE : {os.path.basename(path)}")
        print(f"{'='*60}")
        print(format_specs_for_display(specs))
