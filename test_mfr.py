import sys, re, io
sys.path.insert(0, 'D:\\SelectBestModule')
from pdf_parser import _normalise

with open('D:\\SelectBestModule\\SoliFusion Solitech Topcon Modules.pdf', 'rb') as f:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(f.read()))
    text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"
text = _normalise(text)

print("=== Searching for manufacturer patterns ===")
# Domain
dm = re.search(r'(?:www\.)?([A-Za-z]+)\.(?:com|co\.in|in)\b', text)
print("Domain match: {}".format(dm))
if dm:
    print("  Group 1: {!r}".format(dm.group(1)))

# Company suffix
em = re.search(
    r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+'
    r'(?:Energy|Energies|Technologies|Pvt\.?\s*Ltd|Industries|Power|Solar)',
    text,
)
print("Company suffix match: {}".format(em))
if em:
    print("  Group 1: {!r}".format(em.group(1)))

# Check first capitalized multi-word on early lines
lines = text.split("\n")
skip = (r"Watt|Volt|Amp|Cell|Module|Panel|Model|Temp|Graph|I-V|"
        r"Current|Voltage|Power|Warranty|Dimension|Weight|Operating|"
        r"Mechanical|Electrical|Specifications|Data|Sheet|Product")
print("\n=== First 25 lines: multi-word candidate check ===")
for i, line in enumerate(lines[:25]):
    line = line.strip()
    if not line or len(line) < 4 or re.match(r"^\d", line):
        continue
    if re.search(skip, line, re.IGNORECASE):
        continue
    m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", line)
    if m:
        candidate = m.group(1).strip()
        if 4 <= len(candidate) < 30:
            print("  Line {:2d}: {!r} -> candidate: {!r}".format(i, line, candidate))
