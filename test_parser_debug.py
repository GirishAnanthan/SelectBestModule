import sys, re, io
sys.path.insert(0, 'D:\\SelectBestModule')
from pdf_parser import _normalise, _detect_power_options, _to_floats

with open('D:\\SelectBestModule\\SoliFusion Solitech Topcon Modules.pdf', 'rb') as f:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(f.read()))
    text = ''
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + '\n'

text = _normalise(text)
lines = text.split('\n')

print('=== Testing range regex ===')
range_m = re.search(r'(\d{3})\s*(?:To|to|~|-)\s*(\d{3})\s*W[pP]?', text)
print('Range match: {}'.format(range_m))
if range_m:
    print('  lo={}, hi={}'.format(range_m.group(1), range_m.group(2)))

print()
print('=== Lines containing Wp ===')
for i, line in enumerate(lines):
    if 'Wp' in line:
        print('  Line {}: {!r}'.format(i, line))

print()
print('=== STC table area (lines 40-80) ===')
for i, line in enumerate(lines):
    if 40 <= i <= 80:
        print('  Line {}: {!r}'.format(i, line))

print()
print('=== Temperature coefficient area (lines 20-40) ===')
for i, line in enumerate(lines):
    if 20 <= i <= 40:
        print('  Line {}: {!r}'.format(i, line))

print()
print('=== Efficiency patterns ===')
pats = [
    r'(?:Module\s*)?Eff(?:iciency)?\.?\s*(?:\(%\)|\(STC\)|:)?\s*(\d+\.?\d*)\s*%',
    r'(\d+\.\d+)\s*%\s*(?:Module\s*Eff)',
    r'Eff(?:iciency)?\s*[:\s]+(\d{2}\.\d+)',
]
for i, pat in enumerate(pats):
    m = re.search(pat, text, re.IGNORECASE)
    print('  Pat {}: {}'.format(i, m))
    if m:
        print('    Value: {!r}'.format(m.group(1)))

print()
print('=== Fallback efficiency: all %% values ===')
for v in re.findall(r'(\d+\.\d+)\s*%', text):
    print('  Found: {!r}'.format(v))

print()
print('=== Power options detection ===')
opts = _detect_power_options(text, lines)
print('  Result: {}'.format(opts))

print()
print('=== TC pattern matching ===')
tc_pats = [
    r'Temperature\s*Co[-\s]*efficient\s*(?:of\s*)?P(?:max|mpp?)\s*(?:\(γ|\(Pmax|\(P\).*?)?[:\s]*[-\u2212]?(\d+\.?\d*)',
    r'Pmax\s*Temperature\s*Co[-\s]*efficient[:\s]*[-\u2212]?(\d+\.?\d*)',
    r'γ.*?[-\u2212](\d+\.?\d*)',
    r'Power\s*Temp(?:erature)?\s*Coeff?\.?\s*[:\s]*[-\u2212](\d+\.?\d*)',
    r'Coefficient\s*of\s*Pmax\s*[:\s]*[-\u2212](\d+\.?\d*)',
]
for i, pat in enumerate(tc_pats):
    m = re.search(pat, text, re.IGNORECASE)
    print('  Pat {}: {}'.format(i, m))
    if m:
        print('    val={}'.format(m.group(1)))

print()
print('=== Fallback TC pattern ===')
m = re.search(r'[-\u2212](\d+\.\d+)\s*%/°?C', text)
print('  Match: {}'.format(m))
if m:
    print('  val={}'.format(m.group(1)))
    for mm in re.finditer(r'[-\u2212](\d+\.\d+)\s*%/°?C', text):
        print('  All matches: {!r} -> {}'.format(mm.group(0), mm.group(1)))
