"""
Generate PDF Deployment Guide
Creates a one-page PDF deployment guide for workshop participants.
"""

from fpdf import FPDF

class DeploymentGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.l_margin = 20
        self.r_margin = 20
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        self.set_font('Helvetica', 'B', 18)
        self.set_text_color(0, 112, 192)
        self.set_x(self.l_margin)
        self.cell(self.epw, 10, 'Foundry IQ + Fabric IQ Workshop', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(80, 80, 80)
        self.set_x(self.l_margin)
        self.cell(self.epw, 8, 'Deployment Guide', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(5)
    
    def section_title(self, title):
        self.set_x(self.l_margin)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0, 112, 192)
        self.cell(self.epw, 8, title, new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)
    
    def subsection(self, title):
        self.set_x(self.l_margin)
        self.set_font('Helvetica', 'B', 10)
        self.cell(self.epw, 6, title, new_x='LMARGIN', new_y='NEXT')
    
    def body_text(self, text):
        self.set_x(self.l_margin)
        self.set_font('Helvetica', '', 9)
        self.multi_cell(self.epw, 5, text)
    
    def code_block(self, code):
        self.set_x(self.l_margin)
        self.set_font('Courier', '', 8)
        self.set_fill_color(240, 240, 240)
        self.multi_cell(self.epw, 5, code, fill=True)
        self.set_font('Helvetica', '', 9)
    
    def bullet(self, text):
        self.set_x(self.l_margin)
        self.set_font('Helvetica', '', 9)
        self.cell(5, 5, '-')
        self.cell(self.epw - 5, 5, text, new_x='LMARGIN', new_y='NEXT')

def create_guide():
    pdf = DeploymentGuidePDF()
    pdf.add_page()
    
    # Prerequisites
    pdf.section_title('Prerequisites')
    pdf.bullet('Azure subscription with Contributor access')
    pdf.bullet('Microsoft Fabric workspace (F2+ capacity) with admin permissions')
    pdf.bullet('VS Code, Azure Developer CLI (aka.ms/azd), Python 3.10+, Git')
    pdf.ln(1)
    
    # Deployment Steps
    pdf.section_title('Deployment Steps')
    
    pdf.subsection('1. Clone Repository')
    pdf.code_block('git clone https://github.com/nchandhi/nc-iq-workshop.git && cd nc-iq-workshop')
    
    pdf.subsection('2. Login to Azure')
    pdf.code_block('azd auth login')
    
    pdf.subsection('3. Deploy Azure Resources (~7 min)')
    pdf.code_block('azd up')
    pdf.body_text('Environment: iq-workshop-yourname | Location: eastus2 or westus2')
    
    pdf.subsection('4. Configure Fabric')
    pdf.body_text('Go to app.fabric.microsoft.com > Open workspace > Copy Workspace ID from URL')
    
    pdf.subsection('5. Configure Environment')
    pdf.code_block('cp .env.example .env')
    pdf.body_text('Edit .env: Set FABRIC_WORKSPACE_ID and DATA_FOLDER=data/default')
    
    pdf.subsection('6. Setup Python')
    pdf.code_block('cd scripts && python -m venv .venv && .venv\\Scripts\\activate && pip install uv && uv pip install -r requirements.txt')
    
    pdf.subsection('7. Build Solution (~5 min)')
    pdf.code_block('python scripts/00_build_solution.py --from 02')
    
    pdf.subsection('8. Test the Agent')
    pdf.code_block('python scripts/08_test_foundry_agent.py')
    pdf.ln(1)
    
    # Sample Questions
    pdf.section_title('Sample Questions to Try')
    pdf.body_text('Structured: "How many outages last month?" | "Average resolution time?"')
    pdf.body_text('Unstructured: "What are the policies for notifying customers?"')
    pdf.body_text('Combined: "Which outages exceeded our policy thresholds?"')
    pdf.ln(1)
    
    # Customization
    pdf.section_title('Customize for Your Use Case')
    pdf.body_text('After testing the default scenario, build your own:')
    
    pdf.subsection('1. Run with your industry')
    pdf.code_block('python scripts/00_build_solution.py --clean --industry "Insurance" --usecase "Claims processing"')
    
    pdf.subsection('2. Or set in .env')
    pdf.code_block('INDUSTRY=Insurance\nUSECASE=Claims processing and policy management')
    pdf.body_text('Then run: python scripts/00_build_solution.py --clean')
    pdf.ln(1)
    
    pdf.body_text('Sample industries: Telecommunications, Insurance, Finance, Retail, Manufacturing, Energy')
    pdf.ln(1)
    
    # Troubleshooting
    pdf.section_title('Troubleshooting')
    pdf.body_text('Tip: Use GitHub Copilot Chat (Ctrl+I in VS Code) for help with errors.')
    pdf.ln(1)
    
    # Resources
    pdf.section_title('Resources')
    pdf.body_text('Workshop: nchandhi.github.io/nc-iq-workshop | Repo: github.com/nchandhi/nc-iq-workshop')
    
    return pdf

if __name__ == '__main__':
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    guides_dir = os.path.join(script_dir, '..', 'guides')
    os.makedirs(guides_dir, exist_ok=True)
    
    pdf = create_guide()
    output_path = os.path.join(guides_dir, 'deployment_guide.pdf')
    pdf.output(output_path)
    print(f'Created: {output_path}')
