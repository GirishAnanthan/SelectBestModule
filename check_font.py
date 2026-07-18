import fpdf
import traceback
import sys

class SolarReport(fpdf.FPDF):
    def __init__(self, *args, font_family="Helvetica", **kwargs):
        super().__init__(*args, **kwargs)
        self.font_family = font_family

    def set_font(self, family=None, style="", size=0):
        if family == "Helvetica" and getattr(self, "font_family", "Helvetica") != "Helvetica":
            family = self.font_family
        return super().set_font(family, style, size)

try:
    pdf = SolarReport()
    pdf.font_family = "B" # Wait, what if someone accidentally set this?
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 10)
except Exception as e:
    traceback.print_exc()

try:
    pdf = SolarReport()
    pdf.add_page()
    pdf.set_font(family="Helvetica", style="B", size=10)
except Exception as e:
    traceback.print_exc()
