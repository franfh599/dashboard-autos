from fpdf import FPDF
from datetime import datetime

class PDFExporter:
    def __init__(self, title="Market Report"):
        self.pdf = FPDF()
        self.title = title
        self.pdf.add_page()
        self.pdf.set_font("Arial", "B", 16)
        self.pdf.cell(0, 10, title, ln=True, align="C")
        self.pdf.set_font("Arial", "", 10)
        self.pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    
    def add_section(self, title, content):
        """Add a section to the PDF"""
        self.pdf.ln(5)
        self.pdf.set_font("Arial", "B", 12)
        self.pdf.cell(0, 10, title, ln=True)
        self.pdf.set_font("Arial", "", 10)
        self.pdf.multi_cell(0, 5, content)
    
    def export(self, filename):
        """Export PDF to file"""
        self.pdf.output(filename)
        return filename
