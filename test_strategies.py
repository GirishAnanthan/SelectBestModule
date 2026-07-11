import sys, re, io
sys.path.insert(0, 'D:\\SelectBestModule')
from pdf_parser import parse_specs, _normalise, _extract_electrical, _strategy_A_labelled_rows, _strategy_B_header_data, _strategy_C_interleaved, _strategy_D_heuristic, _detect_power_options

with open('D:\\SelectBestModule\\SoliFusion Solitech Topcon Modules.pdf', 'rb') as f:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(f.read()))
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
text = _normalise(text)
lines = text.split("\n")

print("=== Testing each strategy for electrical extraction ===")
for wp in [650, 640, 630, 610]:
    print("\n--- selected_wp = {} ---".format(wp))
    rA = _strategy_A_labelled_rows(lines, wp)
    print("  Strategy A: {}".format(rA if rA else "EMPTY"))
    rB = _strategy_B_header_data(lines, wp)
    print("  Strategy B: {}".format(rB if rB else "EMPTY"))
    rC = _strategy_C_interleaved(lines, wp)
    print("  Strategy C: {}".format(rC if rC else "EMPTY"))
    rD = _strategy_D_heuristic(lines, wp)
    print("  Strategy D: {}".format(rD if rD else "EMPTY"))

print("\n=== Key lines for STC table ===")
for i, line in enumerate(lines):
    if 'Electrical Characteristics (STC)' in line or 'Nominal Maximum Power' in line or 'Optimum Operating' in line or 'Module Efficiency' in line:
        print("  Line {:3d}: {!r}".format(i, line))
    # Also show lines with multiple decimals
    floats = re.findall(r'\b(\d+\.?\d*)\b', line)
    if len(floats) >= 4 and all(300 <= float(f) <= 750 if f.isdigit() else True for f in floats[:3]):
        print("  Line {:3d}: {!r}  [floats: {}]".format(i, line, floats))

print("\n=== Line-by-line around STC section (lines 85-115) ===")
for i, line in enumerate(lines):
    if 85 <= i <= 120:
        print("  Line {:3d}: {!r}".format(i, line))
