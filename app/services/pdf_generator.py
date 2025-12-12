"""
PDF generation service using templates.
"""

import os
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any


class PDFGenerator:
    """Generates PDF documents from investment memorandums."""
    
    def __init__(self):
        """Initialize PDF generator."""
        template_dir = os.path.join(os.getcwd(), "templates")
        if not os.path.exists(template_dir):
            os.makedirs(template_dir, exist_ok=True)
        
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    def generate_pdf(self, memorandum: Dict[str, Any], output_path: str):
        """
        Generate PDF from memorandum dictionary.
        
        Args:
            memorandum: Investment memorandum dictionary (conforms to schema)
            output_path: Path where PDF should be saved
        """
        # Lazy import to avoid loading WeasyPrint in web service
        from weasyprint import HTML
        
        # Load template
        template = self.env.get_template("memorandum.html")
        
        # Render HTML
        html_content = template.render(memorandum=memorandum)
        
        # Generate PDF
        HTML(string=html_content).write_pdf(output_path)

