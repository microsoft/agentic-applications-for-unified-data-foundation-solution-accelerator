"""
Generate PDF Deployment Guide
Creates a one-page PDF deployment guide for workshop participants.
"""

from fpdf import FPDF
from fpdf.fonts import FontFace
import os

# Colors
BLUE = (0, 120, 212)       # Microsoft blue
DARK_GRAY = (50, 50, 50)
LIGHT_GRAY = (245, 245, 245)
WHITE = (255, 255, 255)

class DeploymentGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(15, 15, 15)
        self.set_auto_page_break(auto=True, margin=10)
        
        # Use Windows system fonts if available, otherwise fallback
        fonts_dir = "C:/Windows/Fonts"
        if os.path.exists(os.path.join(fonts_dir, "segoeui.ttf")):
            self.add_font('Segoe', '', os.path.join(fonts_dir, 'segoeui.ttf'))
            self.add_font('Segoe', 'B', os.path.join(fonts_dir, 'segoeuib.ttf'))
            self.add_font('Segoe', 'I', os.path.join(fonts_dir, 'segoeuii.ttf'))
            self.add_font('Consolas', '', os.path.join(fonts_dir, 'consola.ttf'))
            self.main_font = 'Segoe'
            self.code_font = 'Consolas'
        else:
            # Fallback to core fonts
            self.main_font = 'Helvetica'
            self.code_font = 'Courier'
    
    def header(self):
        # Blue header bar
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 22, 'F')
        
        # Title text - single line
        self.set_font(self.main_font, 'B', 12)
        self.set_text_color(*WHITE)
        self.set_xy(15, 8)
        self.cell(0, 6, 'Build faster with Solution Accelerators  |  Foundry IQ + Fabric IQ')
        
        self.ln(16)
    
    def section_header(self, title, num=None):
        self.ln(3)
        self.set_font(self.main_font, 'B', 11)
        self.set_text_color(*BLUE)
        if num:
            self.cell(0, 6, f'{num}. {title}', new_x='LMARGIN', new_y='NEXT')
        else:
            self.cell(0, 6, title, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(*DARK_GRAY)
    
    def step(self, num, title, code=None, note=None):
        # Step number + title on same line
        self.set_font(self.main_font, 'B', 9)
        self.set_text_color(*BLUE)
        self.set_x(15)
        self.cell(0, 5, f'{num}. {title}', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(*DARK_GRAY)
        
        # Code block - explicitly set regular style
        if code:
            self.set_x(20)
            self.set_font(self.code_font, '', 7)  # Empty string for regular style
            self.set_fill_color(*LIGHT_GRAY)
            self.multi_cell(175, 4, code, fill=True)
            self.set_font(self.main_font, '', 8)  # Reset to regular font
        
        # Note
        if note:
            self.set_x(20)
            self.set_font(self.main_font, 'I', 7)
            self.set_text_color(100, 100, 100)
            self.multi_cell(175, 4, note)
            self.set_text_color(*DARK_GRAY)
    
    def bullet_item(self, text):
        self.set_font(self.main_font, '', 8)
        self.set_text_color(*DARK_GRAY)
        self.set_x(15)
        self.cell(5, 4, '-')
        self.set_x(20)
        self.multi_cell(175, 4, text)
    
    def info_text(self, text):
        self.set_font(self.main_font, '', 8)
        self.set_text_color(*DARK_GRAY)
        self.set_x(15)
        self.multi_cell(180, 4, text)

def create_guide():
    pdf = DeploymentGuidePDF()
    pdf.add_page()
    
    # Prerequisites
    pdf.section_header('Prerequisites')
    pdf.bullet_item('Azure subscription with Contributor access')
    pdf.bullet_item('Microsoft Fabric workspace (F2+ capacity) with admin permissions')
    pdf.bullet_item('VS Code, Azure Developer CLI (aka.ms/azd), Python 3.10+, Git')
    
    # Deployment Steps
    pdf.section_header('Quick Start')
    
    pdf.step(1, 'Clone the repository',
        'git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git\ncd agentic-applications-for-unified-data-foundation-solution-accelerator')
    
    pdf.step(2, 'Deploy Azure resources (~7 min)',
        'azd auth login\nazd up',
        'Choose environment name and region (eastus2 or westus2 recommended). If needed: azd auth login --tenant-id <tenant-id>')
    
    pdf.step(3, 'Configure Fabric workspace',
        'cp .env.example .env',
        'Edit .env: Set FABRIC_WORKSPACE_ID from app.fabric.microsoft.com URL')
    
    pdf.step(4, 'Setup Python environment',
        'python -m venv .venv\n.venv\\Scripts\\activate   # or: source .venv/bin/activate\npip install uv && uv pip install -r scripts/requirements.txt')
    
    pdf.step(5, 'Build the solution (~5 min)',
        'python scripts/00_build_solution.py --from 02',
        'No Fabric? Use: python scripts/00_build_solution.py --from 04 --azure-only')
    
    pdf.step(6, 'Test the agent',
        'python scripts/08_test_agent.py')
    
    # Sample Questions
    pdf.section_header('Try These Questions')
    pdf.info_text('Structured: "How many outages occurred last month?" | "What is the average resolution time?"')
    pdf.info_text('Unstructured: "What are the policies for notifying customers of outages?"')
    pdf.info_text('Combined: "Which outages exceeded the maximum duration defined in our policy?"')
    
    # Customization
    pdf.section_header('Customize for Your Industry')
    pdf.set_font(pdf.code_font, '', 7)
    pdf.set_fill_color(*LIGHT_GRAY)
    pdf.multi_cell(0, 4, 'python scripts/00_build_solution.py --clean --industry "Insurance" --usecase "Claims processing"', fill=True)
    pdf.ln(1)
    pdf.info_text('Industries: Telecommunications | Insurance | Finance | Retail | Manufacturing | Energy')
    
    # Footer
    pdf.ln(3)
    pdf.set_draw_color(*BLUE)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(2)
    pdf.set_font(pdf.main_font, 'I', 7)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 4, 'Tip: Use GitHub Copilot Chat (Ctrl+I) for help with errors', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 4, 'Repository: github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator')
    
    return pdf

if __name__ == '__main__':
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    pdf = create_guide()
    output_path = os.path.join(script_dir, 'deployment_guide.pdf')
    pdf.output(output_path)
    print(f'Created: {output_path}')
