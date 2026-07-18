import fpdf
import traceback

pdf = fpdf.FPDF()
pdf.add_page()
try:
    pdf.add_font("DejaVuSans", "", r"C:\Windows\Fonts\Arial.ttf")
    pdf.add_font("DejaVuSans", "B", r"C:\Windows\Fonts\Arialbd.ttf")
    pdf.set_font("DejaVuSans", "B", 10)
    print("Success with DejaVuSans!")
except Exception as e:
    traceback.print_exc()
