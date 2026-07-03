"""
Solar Module Datasheet Parser
Automatically extracts specifications from manufacturer PDF datasheets
Supports text-based PDFs and image-based PDFs (via OCR)
"""
import re, os, sys
import io, tempfile
from PIL import Image

# --- Text extraction ---

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF bytes. Returns (text, method_used)."""
    # Try pypdf first
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

    # Try pdfminer
    try:
        from pdfminer.high_level import extract_text as pm_extract
        text = pm_extract(io.BytesIO(pdf_bytes))
        if len(text.strip()) > 100:
            return text, "pdfminer"
    except Exception:
        pass

    # Fallback: OCR with PyMuPDF + tesseract
    try:
        import fitz
        import pytesseract
        if os.name == 'nt':
            pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

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
    except Exception as e:
        pass

    return "", "none"

# --- Intelligent specification extraction ---

def parse_specs(text, technology_hint=None):
    """Parse extracted text and return dict of module specifications."""
    specs = {}

    # --- Power variants (Wp) ---
    all_powers = set()
    lines = text.split('\n')

    # Strategy A: Find electrical data table rows and extract Pmax from them
    for line in lines:
        decimals = [float(n) for n in re.findall(r'\b(\d+\.\d+)\b', line)]
        elec_vals = [d for d in decimals if 8 <= d <= 60]
        if len(elec_vals) >= 4:
            ints = [int(n) for n in re.findall(r'\b(\d+)\b', line) if 300 <= int(n) <= 800]
            for v in ints:
                all_powers.add(v)

    # Strategy B: Find power values after Pmax / Power keywords
    for pat in [
        r'(?:Pmax|Max\s*Power|Maximum\s*Power)\s*(?:\(Wp?\)|\(Pmax\))?[:\s]*(\d+)\s*W',
        r'(\d+)\s*Wp?\s*(?:\(STC\)|@\s*STC)',
        r'[-\s](\d{3})\s*[Ww](?:p)?\b',
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
            val = int(m.group(1))
            if 300 <= val <= 800:
                all_powers.add(val)

    # Strategy C: Find power values in model names (e.g. "G12R-600", "G12R 600W")
    for m in re.finditer(r'[A-Za-z0-9]+[-\s](\d{3})(?:[Ww](?:p)?)?(?:\s|,|$|\))', text):
        val = int(m.group(1))
        if 300 <= val <= 800:
            all_powers.add(val)

    if all_powers:
        sorted_powers = sorted(all_powers)
        if len(sorted_powers) > 1:
            max_gap_idx = 0
            max_gap = 0
            for i in range(len(sorted_powers) - 1):
                gap = sorted_powers[i+1] - sorted_powers[i]
                if gap > max_gap:
                    max_gap = gap
                    max_gap_idx = i
            if max_gap > 50:
                specs["power_options"] = sorted_powers[max_gap_idx+1:]
            else:
                specs["power_options"] = sorted_powers
        else:
            specs["power_options"] = sorted_powers
        specs["power_wp"] = max(specs["power_options"])
    else:
        specs["power_options"] = []
        specs["power_wp"] = None

    # --- Per-power data extraction ---
    # Extract electrical parameters from datasheet tables.
    power = specs.get("power_wp")
    if power is not None:
        power_str = str(power)
        lines = text.split('\n')

        def extract_nums_from_line(line):
            """Extract numeric values from a line, removing model-name embedded numbers."""
            # Remove model-name-like prefixes (e.g., BiN-21-615 → strip to get clean numbers)
            clean = re.sub(r'[A-Za-z]+[-\d]*\s', '', line)
            nums = re.findall(r'(\d+\.?\d*)', clean)
            return [float(n) for n in nums]

        def find_electrical_row(floats):
            """Find Vmp, Imp, Isc, Voc, Eff from a list of floats."""
            # Try interleaved STC/NOCT format first:
            # Pmax_STC Pmax_NOCT Vmp_STC Vmp_NOCT Imp_STC Imp_NOCT Isc_STC Isc_NOCT Voc_STC Voc_NOCT Eff
            # Skip leading power values (300-800 range)
            data = [n for n in floats if n < 300 or not (300 <= n <= 800)]
            # Actually keep Pmax values but identify them
            # STC Vmp is usually ~30-55V, Imp ~10-18A, Isc ~11-19A, Voc ~37-56V
            # Look for pairs where first is STC, second is NOCT (NOCT values are slightly lower)
            for i in range(len(floats) - 10):
                chunk = floats[i:i+11]
                # Check if first two are power (300-800)
                pw1, pw2 = chunk[0], chunk[1]
                v_s, v_n = chunk[2], chunk[3]
                i_s, i_n = chunk[4], chunk[5]
                isc_s, isc_n = chunk[6], chunk[7]
                voc_s, voc_n = chunk[8], chunk[9]
                eff = chunk[10]
                # Vmp NOCT < Vmp STC, Imp NOCT < Imp STC, etc.
                if (300 <= pw1 <= 800 and 300 <= pw2 <= 800 and
                    25 <= v_s <= 55 and 20 <= v_n <= 50 and v_n < v_s and
                    8 <= i_s <= 20 and 6 <= i_n <= 18 and i_n < i_s and
                    8 <= isc_s <= 22 and 6 <= isc_n <= 20 and isc_n < isc_s and
                    35 <= voc_s <= 60 and 30 <= voc_n <= 55 and voc_n < voc_s and
                    18 <= eff <= 26):
                    return v_s, i_s, isc_s, voc_s, eff

            # Try simple format: [Pmax] Vmp Imp Isc Voc Eff
            feasible = [n for n in floats if 8 <= n <= 60]
            for idx in range(len(feasible) - 4):
                v, imp_, isc_, voc = feasible[idx:idx+4]
                if 25 <= v <= 55 and 8 <= imp_ <= 20 and 8 <= isc_ <= 22 and 35 <= voc <= 60:
                    eff = feasible[idx+4] if (idx+4 < len(feasible) and 18 <= feasible[idx+4] <= 26) else None
                    return v, imp_, isc_, voc, eff
            return None

        found_row = False
        # Strategy 1: Find header line, then data
        for i, line in enumerate(lines):
            if re.search(r'Pmax.*Vmp.*Imp.*Isc.*Voc', line, re.IGNORECASE):
                for j in range(i+1, min(i+15, len(lines))):
                    if power_str in lines[j]:
                        floats = extract_nums_from_line(lines[j])
                        if len(floats) >= 8:
                            result = find_electrical_row(floats)
                            if result:
                                specs["vmp"], specs["imp"], specs["isc"], specs["voc"], eff = result
                                if eff: specs["efficiency_pct"] = eff
                                found_row = True
                                break
                if found_row:
                    break

        # Strategy 2: Scan all data lines
        if not found_row:
            for line in lines:
                if power_str not in line:
                    continue
                floats = extract_nums_from_line(line)
                if len(floats) >= 5:
                    result = find_electrical_row(floats)
                    if result:
                        specs["vmp"], specs["imp"], specs["isc"], specs["voc"], eff = result
                        if eff: specs["efficiency_pct"] = eff
                        found_row = True
                        break

    # --- Separate efficiency extraction ---
    if "efficiency_pct" not in specs or not specs["efficiency_pct"]:
        eff_patterns = [
            r'(?:Module\s*)?Eff(?:iciency)?\.?\s*(?:\(%\)|\(STC\)|:)?\s*(\d+\.?\d*)',
            r'(\d+\.\d+)\s*%\s*(?:Module\s*Eff)',
        ]
        for pat in eff_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 15 <= val <= 30:
                    specs["efficiency_pct"] = val
                    break

    if "efficiency_pct" not in specs:
        # Try table row with %
        eff_matches = re.findall(r'(\d+\.\d+)\s*%', text)
        for v in eff_matches:
            val = float(v)
            if 15 <= val <= 30:
                specs["efficiency_pct"] = val
                break

    # --- Cell Technology ---
    tech_patterns = [
        (r'Mono\s*PERC|p-PERC|p\s*type\s*PERC', "Mono PERC"),
        (r'N[-\s]?Type\s*TOPCon|N-TOPCon|n\s*type\s*TOPCon|TOPCon', "N-TOPCon"),
        (r'HJT|HIT|Heterojunction', "HJT"),
        (r'Poly\s*PERC|Multi\s*PERC', "Poly PERC"),
    ]
    for pat, tech in tech_patterns:
        if re.search(pat, text, re.IGNORECASE):
            specs["technology"] = tech
            break
    if "technology" not in specs:
        specs["technology"] = technology_hint or "Mono PERC"

    # --- Temperature Coefficients ---
    # Pmax
    tc_patterns = [
        (r'Temperature\s*Co[-\s]*efficient\s*(?:of\s*)?P(?:max|mpp?)\s*(?:\(γ|\(Pmax|\(P\).*?)?[:\s]*[-\u2212]?(\d+\.?\d*)',
         "temp_coeff_pmax"),
        (r'Pmax\s*Temperature\s*Co[-\s]*efficient[:\s]*[-\u2212]?(\d+\.?\d*)', "temp_coeff_pmax"),
        (r'γ.*?[-\u2212](\d+\.?\d*)', "temp_coeff_pmax"),
        (r'[-\u2212]0\.\d{2}\s*%/°?C', None),  # generic pattern
    ]
    for pat, key in tc_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if key is None:
                continue
            val = float(m.group(1))
            if 0.1 <= val <= 0.5:
                specs["temp_coeff_pmax"] = -val
                break

    if "temp_coeff_pmax" not in specs:
        # Try to find any -0.XX%/C pattern
        m = re.search(r'[-\u2212](\d+\.\d+)\s*%/°?C', text)
        if m:
            val = float(m.group(1))
            if 0.2 <= val <= 0.5:
                specs["temp_coeff_pmax"] = -val

    # Voc temp coefficient
    voc_tc = re.search(r'(?:Temp.*Voc|Voc.*Temp|Temperature.*Voc).*?[-\u2212](\d+\.\d+)', text, re.IGNORECASE)
    if voc_tc:
        specs["temp_coeff_voc"] = -float(voc_tc.group(1))

    # Isc temp coefficient
    isc_tc = re.search(r'(?:Temp.*Isc|Isc.*Temp|Temperature.*Isc).*?[+\-](\d+\.?\d*)', text, re.IGNORECASE)
    if isc_tc:
        specs["temp_coeff_isc"] = float(isc_tc.group(1))

    # --- NOCT ---
    noct_m = re.search(r'NOCT[:\s]*(\d+)\s*[°±]', text, re.IGNORECASE)
    if noct_m:
        specs["noct"] = int(noct_m.group(1))

    # --- Warranty ---
    prod_w = re.search(r'(\d+)\s*Years?\s*Product\s*(?:Warranty|Guarantee)', text, re.IGNORECASE)
    if prod_w:
        specs["warranty_product"] = int(prod_w.group(1))
    perf_w = re.search(r'(\d+)\s*Years?\s*(?:Linear\s*)?Power\s*(?:Output\s*)?(?:Warranty|Guarantee|Performance)', text, re.IGNORECASE)
    if perf_w:
        specs["warranty_power"] = int(perf_w.group(1))

    # --- Degradation ---
    deg_y1 = re.search(r'(?:Year\s*[1I]|First\s*Year).*?(\d+\.?\d*)\s*%', text, re.IGNORECASE)
    if deg_y1:
        v = float(deg_y1.group(1))
        if 0.5 <= v <= 5:
            specs["deg_y1_pct"] = v
    deg_ann = re.search(r'(?:Annual|Subsequent).*?(\d+\.?\d*)\s*%\s*(?:per\s*year|annual|p\.a\.)', text, re.IGNORECASE)
    if deg_ann:
        v = float(deg_ann.group(1))
        if 0.1 <= v <= 1.0:
            specs["deg_annual_pct"] = v
    # Try linear performance warranty pattern: 2% Y1 then 0.55% etc.
    if "deg_annual_pct" not in specs:
        deg_lin = re.search(r'(\d+\.?\d*)\s*%\s*(?:per\s*year|annual|p\.?a\.?)\s*(?:after|then|thereafter)', text, re.IGNORECASE)
        if deg_lin:
            v = float(deg_lin.group(1))
            if 0.1 <= v <= 1.0:
                specs["deg_annual_pct"] = v

    # --- Dimensions ---
    dim_m = re.search(r'(\d{4})\s*[xX×*]\s*(\d{4})\s*[xX×*]\s*(\d{2,3})', text)
    if dim_m:
        specs["dimensions"] = f'{dim_m.group(1)}x{dim_m.group(2)}x{dim_m.group(3)}'
        specs["length"] = int(dim_m.group(1))
        specs["width"] = int(dim_m.group(2))
        specs["thickness"] = int(dim_m.group(3))

    # --- Weight ---
    wt_m = re.search(r'(\d+\.?\d*)\s*(?:kgs?|kg|Kg|KG)', text)
    if wt_m:
        v = float(wt_m.group(1))
        if 15 <= v <= 50:
            specs["weight_kg"] = v

    # --- Manufacturer ---
    mfr = ""
    # 1. Try domain name pattern (e.g., www.waaree.com -> Waaree)
    dm = re.search(r'(?:www\.)?([A-Za-z]+)\.(?:com|co\.in|in)', text)
    if dm:
        candidate = dm.group(1)
        if candidate[0].isupper() or len(candidate) >= 4:
            mfr = candidate[0].upper() + candidate[1:] if candidate[0].islower() else candidate
    # 2. Look for "Energy"/"Energies" company suffix
    if not mfr:
        em = re.search(r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Energy|Energies|Technologies|Pvt\.?\s*Ltd|Industries|Power)', text)
        if em:
            mfr = em.group(1).strip()
    # 3. Fallback: first capitalized multi-word line that isn't a spec keyword
    if not mfr:
        lines = text.strip().split('\n')
        skip_keywords = r'Watt|Volt|Amp|Cell|Module|Panel|Model|Temp|Graph|I-V|Current|Voltage|Power|Warranty|Dimension|Weight|Operating|Mechanical|Electrical'
        for line in lines[:20]:
            line = line.strip()
            if not line or len(line) < 4 or re.match(r'^\d', line):
                continue
            if re.search(skip_keywords, line, re.IGNORECASE):
                continue
            m = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', line)
            if m:
                mfr = m.group(1).strip()
                if len(mfr) >= 4 and len(mfr) < 30:
                    break
    if mfr:
        specs["manufacturer"] = mfr

    # --- Cell count ---
    cell_m = re.search(r'(\d+)\s*(?:Cells?|cells?)\s*[,/]', text)
    if cell_m:
        specs["cell_count"] = int(cell_m.group(1))
    else:
        cell_m2 = re.search(r'(\d+)\s*(?:HC|BB|half.?cut|Half.?Cut)', text, re.IGNORECASE)
        if cell_m2:
            specs["cell_count"] = int(cell_m2.group(1))

    # --- Bifacial ---
    if re.search(r'Bi[-\s]*facial|Bifacial|bi.?facial', text, re.IGNORECASE):
        specs["bifacial"] = True
    else:
        specs["bifacial"] = False

    # --- Technology-specific defaults for missing values ---
    tech = specs.get("technology", "Mono PERC")
    if "temp_coeff_pmax" not in specs:
        if tech == "N-TOPCon":
            specs["temp_coeff_pmax"] = -0.30
        else:  # PERC default
            specs["temp_coeff_pmax"] = -0.35
    if "temp_coeff_voc" not in specs:
        specs["temp_coeff_voc"] = -0.26 if tech == "N-TOPCon" else -0.27
    if "temp_coeff_isc" not in specs:
        specs["temp_coeff_isc"] = 0.046 if tech == "N-TOPCon" else 0.050
    if "noct" not in specs:
        specs["noct"] = 43
    if "deg_y1_pct" not in specs:
        specs["deg_y1_pct"] = 1.0 if tech == "N-TOPCon" else 2.0
    if "deg_annual_pct" not in specs:
        specs["deg_annual_pct"] = 0.40 if tech == "N-TOPCon" else 0.55
    if "warranty_product" not in specs:
        specs["warranty_product"] = 12
    if "warranty_power" not in specs:
        specs["warranty_power"] = 30 if tech == "N-TOPCon" else 27

    return specs


def extract_module_specs(pdf_bytes, technology_hint=None):
    """High-level function: extract text from PDF, parse specs, return structured data."""
    text, method = extract_text_from_pdf(pdf_bytes)
    specs = parse_specs(text, technology_hint)
    specs["_extraction_method"] = method
    specs["_raw_text_length"] = len(text)
    return specs


def format_specs_for_display(specs):
    """Format specs for human-readable display."""
    lines = []
    if specs.get("manufacturer"):
        lines.append(f"Manufacturer: {specs['manufacturer']}")
    if specs.get("power_options"):
        lines.append(f"Power Options (Wp): {specs['power_options']}")
    if specs.get("power_wp"):
        lines.append(f"Selected Power: {specs['power_wp']} Wp")
    if specs.get("efficiency_pct"):
        lines.append(f"Efficiency: {specs['efficiency_pct']:.2f}%")
    if specs.get("technology"):
        lines.append(f"Technology: {specs['technology']}")
    if specs.get("vmp"):
        lines.append(f"Vmp: {specs['vmp']:.2f} V")
    if specs.get("imp"):
        lines.append(f"Imp: {specs['imp']:.2f} A")
    if specs.get("voc"):
        lines.append(f"Voc: {specs['voc']:.2f} V")
    if specs.get("isc"):
        lines.append(f"Isc: {specs['isc']:.2f} A")
    if specs.get("temp_coeff_pmax"):
        lines.append(f"Temp Coeff Pmax: {specs['temp_coeff_pmax']:.2f}%/C")
    if specs.get("noct"):
        lines.append(f"NOCT: {specs['noct']} C")
    if specs.get("deg_y1_pct"):
        lines.append(f"Y1 Degradation: {specs['deg_y1_pct']:.1f}%")
    if specs.get("deg_annual_pct"):
        lines.append(f"Annual Degradation: {specs['deg_annual_pct']:.2f}%")
    if specs.get("warranty_power"):
        lines.append(f"Power Warranty: {specs['warranty_power']} years")
    if specs.get("dimensions"):
        lines.append(f"Dimensions: {specs['dimensions']} mm")
    if specs.get("weight_kg"):
        lines.append(f"Weight: {specs['weight_kg']:.1f} kg")
    if specs.get("cell_count"):
        lines.append(f"Cells: {specs['cell_count']}")
    if specs.get("_extraction_method"):
        lines.append(f"(Extracted via: {specs['_extraction_method']})")
    return "\n".join(lines)


if __name__ == "__main__":
    # Test with both PDFs
    for path, hint in [
        (r"D:\Raghavan 19.6MW DCR Project\Redren_Steorra_Mono_PERC_Bi-facial_580 To 610W (BIG DCR).pdf", "Mono PERC"),
        (r"D:\Raghavan 19.6MW DCR Project\Waaree615DCR.pdf", "N-TOPCon"),
    ]:
        with open(path, "rb") as f:
            data = f.read()
        specs = extract_module_specs(data, hint)
        print(f"\n=== {os.path.basename(path)} ===")
        print(f"Method: {specs['_extraction_method']}")
        print(format_specs_for_display(specs))
