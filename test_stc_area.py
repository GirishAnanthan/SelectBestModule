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
lines = text.split("\n")

print("=== Full STC data section (lines 280-310) ===")
for i, line in enumerate(lines):
    if 280 <= i <= 310:
        print("  Line {:3d}: {!r}".format(i, line))

print("\n=== Also show the 610-650 data area (lines 130-160) ===")
for i, line in enumerate(lines):
    if 130 <= i <= 160:
        print("  Line {:3d}: {!r}".format(i, line))

print("\n=== Degradation area ===")
for i, line in enumerate(lines):
    if 'Degradation' in line or 'First Year' in line or 'Linear' in line:
        print("  Line {:3d}: {!r}".format(i, line))

print("\n=== Manufacturer area (lines 0-30) ===")
for i, line in enumerate(lines):
    if i <= 30:
        print("  Line {:3d}: {!r}".format(i, line))
