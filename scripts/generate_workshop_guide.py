"""
Generate Workshop Guide PDF
Creates a professional PDF guide for the Fabric Ontology Lab workshop.

Usage:
    python scripts/generate_workshop_guide.py
    
Output:
    docs/Fabric_Ontology_Lab_Workshop_Guide.pdf
"""

import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime

# ============================================================================
# PDF Configuration
# ============================================================================

class WorkshopGuidePDF(FPDF):
    """Custom PDF class with header/footer"""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(128, 128, 128)
            self.cell(0, 6, "Foundry IQ + Fabric IQ - Hands-on Workshop", align="L")
            self.ln(2)
            self.set_draw_color(200, 200, 200)
            self.line(10, 18, 200, 18)
            self.ln(8)
    
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
    
    def chapter_title(self, title, level=1):
        """Add a chapter/section title"""
        if level == 1:
            self.set_font("Helvetica", "B", 18)
            self.set_text_color(0, 51, 102)
            self.ln(5)
            self.cell(0, 12, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_draw_color(0, 51, 102)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(8)
        elif level == 2:
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(51, 51, 51)
            self.ln(3)
            self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(2)
        else:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(51, 51, 51)
            self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(1)
    
    def body_text(self, text, markdown=False):
        """Add body text. Use markdown=True to support **bold** formatting."""
        self.set_font("Helvetica", "", 11)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 6, text, markdown=markdown)
        self.ln(2)
    
    def bullet_point(self, text, indent=10, markdown=False):
        """Add a bullet point. Use markdown=True to support **bold** formatting."""
        self.set_font("Helvetica", "", 11)
        self.set_text_color(51, 51, 51)
        self.set_x(indent + 10)
        self.cell(5, 6, chr(149))  # bullet character
        self.multi_cell(0, 6, text, markdown=markdown)
    
    def numbered_item(self, number, text, indent=10, markdown=False):
        """Add a numbered item. Use markdown=True to support **bold** formatting."""
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(0, 102, 153)
        self.set_x(indent + 10)
        self.cell(8, 6, f"{number}.")
        self.set_font("Helvetica", "", 11)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 6, text, markdown=markdown)
    
    def code_block(self, code, width=180):
        """Add a code block"""
        self.set_font("Courier", "", 10)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(51, 51, 51)
        self.set_x(15)
        
        # Calculate height needed
        lines = code.split('\n')
        height = len(lines) * 5 + 6
        
        # Draw background
        self.rect(15, self.get_y(), width, height, 'F')
        self.ln(3)
        
        for line in lines:
            self.set_x(18)
            self.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        self.ln(5)
    
    def info_box(self, title, text):
        """Add an info/tip box"""
        self.set_fill_color(230, 243, 255)
        self.set_draw_color(0, 102, 204)
        y_start = self.get_y()
        
        # Calculate height
        self.set_font("Helvetica", "", 10)
        # Rough estimate of lines needed
        lines_needed = len(text) / 80 + 2
        height = max(20, lines_needed * 5 + 10)
        
        self.rect(15, y_start, 180, height, 'DF')
        self.ln(3)
        self.set_x(20)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 51, 102)
        self.cell(0, 5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(20)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(51, 51, 51)
        self.multi_cell(170, 5, text)
        self.set_y(y_start + height + 5)


def generate_workshop_guide():
    """Generate the workshop guide PDF"""
    
    pdf = WorkshopGuidePDF()
    
    # ========================================================================
    # Cover Page
    # ========================================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(0, 51, 102)
    pdf.ln(40)
    pdf.cell(0, 12, "Build faster with Solution Accelerators", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(0, 102, 153)
    pdf.ln(5)
    pdf.cell(0, 15, "Foundry IQ + Fabric IQ", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(102, 102, 102)
    pdf.cell(0, 10, "Hands-on Workshop", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 8, "Build end-to-end AI solutions that unify", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, "enterprise data sources - then accelerate", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, "your PoCs with real customer data.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(60)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, f"Updated: {datetime.now().strftime('%B %d, %Y')}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # ========================================================================
    # Table of Contents
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("Table of Contents")
    
    toc_items = [
        ("1. Introduction", "What you will build"),
        ("2. Prerequisites", "What you need before starting"),
        ("3. Architecture Overview", "Understanding the components"),
        ("4. Part 1: Run with Sample Scenario", "Retail example walkthrough"),
        ("5. Part 2: Customize Your Own Scenario", "Create your industry solution"),
        ("6. Understanding the Build Process", "What each step does"),
        ("7. Testing Your Agent", "Interactive chat with your data"),
        ("8. Troubleshooting", "Common issues and solutions"),
    ]
    
    for title, desc in toc_items:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(80, 8, title)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(102, 102, 102)
        pdf.cell(0, 8, desc, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # ========================================================================
    # 1. Introduction
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("1. Introduction")
    
    pdf.body_text(
        "Welcome to the **Foundry IQ** + **Fabric IQ** hands-on workshop! In this workshop, you will "
        "build an end-to-end AI solution that unifies enterprise data sources - documents and "
        "structured data - into a single intelligent agent.",
        markdown=True
    )
    
    pdf.chapter_title("The Opportunity", level=2)
    pdf.body_text(
        "Organizations have valuable knowledge spread across documents (PDFs, policies, "
        "manuals) and structured systems (databases, data warehouses). By connecting these "
        "sources through AI, users can get unified answers from a single conversational interface."
    )
    pdf.ln(2)
    
    pdf.chapter_title("The Solution", level=2)
    pdf.body_text("**Foundry IQ** and **Fabric IQ** solve this by enabling an intelligent agent that:", markdown=True)
    pdf.bullet_point("Creates knowledge bases from documents with agentic retrieval (plan, iterate, reflect)")
    pdf.bullet_point("Defines business ontology to understand entities, relationships, and rules")
    pdf.bullet_point("Queries data using natural language over both documents and structured data")
    pdf.bullet_point("Unifies enterprise data sources into a single conversational interface")
    pdf.ln(3)
    
    pdf.chapter_title("What You Will Build", level=2)
    pdf.body_text("By the end of this workshop, you will have created:")
    pdf.bullet_point("**AI Agent** - Azure AI Foundry orchestrates tools and generates responses", markdown=True)
    pdf.bullet_point("**Knowledge Base** - **Foundry IQ** provides agentic retrieval over documents", markdown=True)
    pdf.bullet_point("**Business Ontology** - **Fabric IQ** defines entities, relationships, and NL-to-SQL", markdown=True)
    pdf.bullet_point("An end-to-end AI solution that unifies enterprise data sources")
    pdf.ln(3)
    
    pdf.chapter_title("Workshop Flow", level=2)
    pdf.body_text("This workshop is divided into two parts:")
    pdf.ln(2)
    pdf.numbered_item(1, "**Run with Sample Scenario** - Follow along with a pre-defined Retail scenario to understand how everything works.", markdown=True)
    pdf.numbered_item(2, "**Customize Your Own** - Use AI to generate data and documents for YOUR industry and use case.", markdown=True)
    pdf.ln(3)
    pdf.body_text(
        "Once you complete these two steps, you can plug in your own customer data "
        "and accelerate your Proof of Concept (PoC) engagements!"
    )
    
    # ========================================================================
    # 2. Prerequisites
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("2. Prerequisites")
    
    pdf.chapter_title("Prerequisites", level=2)
    pdf.bullet_point("**Azure Subscription** with Contributor access", markdown=True)
    pdf.bullet_point("**Microsoft Fabric Workspace** with capacity assigned", markdown=True)
    pdf.bullet_point("**VS Code** or access to create **GitHub Codespaces**", markdown=True)
    pdf.ln(5)
    
    pdf.body_text(
        "All other tools and resources will be set up during the workshop. "
        "The infrastructure deployment will create the necessary Azure AI Services, "
        "AI Search, and Storage resources automatically."
    )

    # ========================================================================
    # 3. Architecture Overview
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("3. Architecture Overview")
    
    pdf.body_text(
        "**Foundry IQ** and **Fabric IQ** work together to create an end-to-end AI solution "
        "that unifies enterprise data sources - documents and structured data - into a "
        "single intelligent agent.",
        markdown=True
    )
    pdf.ln(3)
    
    pdf.chapter_title("Components", level=2)
    
    pdf.chapter_title("Foundry IQ (Document Intelligence)", level=3)
    pdf.bullet_point("**Knowledge Base**: Agentic retrieval over documents (plan, iterate, reflect)", markdown=True)
    pdf.bullet_point("**AI Search Index**: Vectorized document chunks for semantic search", markdown=True)
    pdf.bullet_point("**Embedding Model**: Converts text to vectors (text-embedding-ada-002)", markdown=True)
    pdf.ln(2)
    
    pdf.chapter_title("Fabric IQ (Structured Data Intelligence)", level=3)
    pdf.bullet_point("**Fabric Lakehouse**: Stores structured data as Delta tables", markdown=True)
    pdf.bullet_point("**Business Ontology**: Defines entities, properties, and relationships", markdown=True)
    pdf.bullet_point("**Data Agent**: Translates natural language to SQL queries", markdown=True)
    pdf.ln(2)
    
    pdf.chapter_title("Orchestration Layer", level=3)
    pdf.bullet_point("**Azure AI Foundry Agent**: Orchestrates tools and generates responses", markdown=True)
    pdf.bullet_point("**Orchestrator Agent**: Determines which source(s) to query", markdown=True)
    pdf.ln(2)
    
    pdf.chapter_title("Data Flow", level=2)
    pdf.numbered_item(1, "User asks a question in natural language")
    pdf.numbered_item(2, "AI agent determines if the question needs structured data, documents, or both")
    pdf.numbered_item(3, "For structured data: **Fabric IQ** converts question to SQL via Ontology", markdown=True)
    pdf.numbered_item(4, "For documents: **Foundry IQ** retrieves relevant document chunks", markdown=True)
    pdf.numbered_item(5, "AI agent combines results and generates a natural language response")
    
    # ========================================================================
    # 4. Part 1: Run with Sample Scenario
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("4. Part 1: Run with Sample Scenario")
    
    pdf.body_text(
        "In this section, you will run the complete build process with a pre-defined "
        "Retail scenario. This helps you understand how each component works "
        "before creating your own custom scenario."
    )
    pdf.ln(3)
    
    pdf.chapter_title("The Retail Scenario", level=2)
    pdf.body_text(
        "Our sample scenario is a Retail system for inventory and sales "
        "tracking. It includes:"
    )
    pdf.bullet_point("Products table: Product catalog with prices and stock levels")
    pdf.bullet_point("Transactions table: Sales transactions with quantities and dates")
    pdf.bullet_point("Policy documents: Store policies and procedures (PDFs)")
    pdf.ln(3)
    
    pdf.chapter_title("Step 1: Run the Build Script", level=2)
    pdf.body_text(
        "The build script automates all steps. Run this single command:"
    )
    pdf.code_block(
        'python scripts/00_build_solution.py \\\n'
        '    --industry "Retail" \\\n'
        '    --usecase "Inventory and sales tracking"'
    )
    
    pdf.info_box(
        "Note",
        "This uses pre-generated sample data from the data/ folder. "
        "No AI generation is needed for the sample scenario."
    )
    pdf.ln(3)
    
    pdf.chapter_title("What the Build Script Does", level=2)
    pdf.numbered_item(1, "Loads sample data (products.csv, transactions.csv)")
    pdf.numbered_item(2, "Creates Fabric Lakehouse and uploads data as Delta tables")
    pdf.numbered_item(3, "Creates Fabric Ontology with entities and relationships")
    pdf.numbered_item(4, "Generates PDF documents from the data")
    pdf.numbered_item(5, "Creates the Fabric Data Agent")
    pdf.numbered_item(6, "Uploads documents to AI Search with embeddings")
    pdf.numbered_item(7, "Creates the Foundry orchestration agent")
    pdf.ln(3)
    
    pdf.chapter_title("Step 2: Test the Fabric Data Agent", level=2)
    pdf.body_text(
        "Once the Fabric Data Agent is created, open the Fabric UI and test it with "
        "natural language questions about your data."
    )
    pdf.ln(2)
    
    pdf.chapter_title("Step 3: Test the Full Agent", level=2)
    pdf.body_text("Once the build completes, test the full orchestration agent:")
    pdf.code_block("python scripts/08_test_foundry_agent.py")
    
    pdf.body_text("Try these sample questions:")
    pdf.bullet_point("How many products do we have?")
    pdf.bullet_point("Show me the top 5 products by sales")
    pdf.bullet_point("What is our return policy?")
    pdf.bullet_point("Which products are low in stock?")
    
    # ========================================================================
    # 5. Part 2: Customize Your Own Scenario
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("5. Part 2: Customize Your Own Scenario")
    
    pdf.body_text(
        "Now that you understand how the build process works, it is time to create "
        "your own custom scenario! The AI will generate realistic sample data "
        "and documents based on your industry and use case."
    )
    pdf.ln(3)
    
    pdf.chapter_title("Step 1: Choose Your Industry and Use Case", level=2)
    pdf.body_text("Think about what industry and use case you want to explore. Here are some ideas:")
    pdf.ln(2)
    
    # Sample scenarios table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 51, 102)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(50, 8, "Industry", border=1, fill=True, align="C")
    pdf.cell(130, 8, "Use Case", border=1, fill=True, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(51, 51, 51)
    
    scenarios = [
        ("Telecommunications", "Help support staff find outage info and answer policy questions"),
        ("Finance", "Enable advisors to assess loan eligibility and compliance requirements"),
        ("Education", "Let admins query enrollment data and academic policy questions"),
        ("Manufacturing", "Help technicians find equipment history and maintenance procedures"),
        ("Hospitality", "Enable front desk to check availability and answer guest inquiries"),
        ("Real Estate", "Help agents match properties to buyers and explain transaction steps"),
        ("Insurance", "Enable adjusters to review claims and coverage policy details"),
        ("Energy", "Help operators monitor assets and find safety protocol information"),
    ]
    
    for industry, usecase in scenarios:
        pdf.cell(50, 7, industry, border=1, align="C")
        pdf.cell(130, 7, usecase, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(5)
    
    pdf.chapter_title("Step 2: Run with AI Generation", level=2)
    pdf.body_text("Run the build script with your industry and use case:")
    pdf.code_block(
        'python scripts/00_build_solution.py --clean \\\n'
        '    --industry "YOUR_INDUSTRY" \\\n'
        '    --usecase "YOUR_USE_CASE"'
    )
    
    pdf.body_text("For example, to create an Insurance claims system:")
    pdf.code_block(
        'python scripts/00_build_solution.py --clean \\\n'
        '    --industry "Insurance" \\\n'
        '    --usecase "Claims processing and policy management"'
    )
    
    pdf.info_box(
        "Tip",
        "Be descriptive in your use case! The more detail you provide, "
        "the better the AI can generate relevant data and documents."
    )
    pdf.ln(3)
    
    pdf.chapter_title("Step 3: Switch Between Scenarios", level=2)
    pdf.body_text(
        "When you want to try a different scenario, use the --clean flag to "
        "create fresh Fabric artifacts:"
    )
    pdf.code_block(
        'python scripts/00_build_solution.py --ai --clean \\\n'
        '    --industry "Finance" \\\n'
        '    --usecase "Loan applications and credit scoring"'
    )
    
    pdf.body_text(
        "The --clean flag increments the artifact suffix (lakehouse_1 -> lakehouse_2) "
        "so you can have multiple scenarios without conflicts."
    )
    
    # ========================================================================
    # 6. Understanding the Build Process
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("6. Understanding the Build Process")
    
    pdf.body_text(
        "The build process consists of several scripts that work together. "
        "Understanding each step helps you troubleshoot issues and customize behavior."
    )
    pdf.ln(3)
    
    scripts = [
        ("00_build_solution.py", "Master orchestration script",
         "Runs all other scripts in sequence. Accepts --ai, --clean, --industry, and --usecase flags."),
        ("01_generate_sample_data.py", "AI data generation",
         "Uses GPT-4o-mini to generate realistic CSV data and PDF documents based on your scenario."),
        ("02_create_fabric_items.py", "Fabric Lakehouse and Ontology",
         "Creates the Lakehouse for data storage and Ontology for semantic understanding."),
        ("03_load_fabric_data.py", "Data loading",
         "Uploads CSV files to OneLake and loads them as Delta tables."),
        ("04_generate_agent_prompt.py", "Schema extraction",
         "Reads table schemas to generate prompts for the AI agent."),
        ("05_create_fabric_agent.py", "Fabric Data Agent",
         "Creates a Data Agent in Fabric that uses the Ontology to answer questions."),
        ("06_upload_to_search.py", "Document indexing",
         "Uploads PDF documents to AI Search with vector embeddings."),
        ("07_create_foundry_agent.py", "Foundry orchestration agent",
         "Creates the main AI agent that combines Fabric and Search tools."),
    ]
    
    for script, title, desc in scripts:
        pdf.chapter_title(script, level=3)
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(0, 102, 153)
        pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.body_text(desc)
    
    # ========================================================================
    # 7. Testing Your Agent
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("7. Testing Your Agent")
    
    pdf.body_text(
        "The test script provides an interactive chat interface to your AI agent. "
        "It shows you exactly how the agent processes your questions."
    )
    pdf.ln(3)
    
    pdf.chapter_title("Running the Test", level=2)
    pdf.code_block("python scripts/08_test_foundry_agent.py")
    
    pdf.chapter_title("Understanding the Output", level=2)
    pdf.body_text("When you ask a question, the agent shows:")
    pdf.bullet_point("Tool calls: Which tools (Fabric IQ, Foundry IQ) were used")
    pdf.bullet_point("SQL queries: The exact SQL generated by Fabric IQ")
    pdf.bullet_point("Search results: Document chunks retrieved by Foundry IQ")
    pdf.bullet_point("Final answer: The natural language response")
    pdf.ln(3)
    
    pdf.chapter_title("Sample Questions by Type", level=2)
    
    pdf.chapter_title("Structured Data Questions (uses Fabric IQ)", level=3)
    pdf.bullet_point("How many records are in the table?")
    pdf.bullet_point("Show me the top 5 items by value")
    pdf.bullet_point("What is the average/sum/count of X?")
    pdf.bullet_point("List all items where condition is met")
    pdf.ln(2)
    
    pdf.chapter_title("Unstructured Data Questions (uses Foundry IQ)", level=3)
    pdf.bullet_point("What is our policy on X?")
    pdf.bullet_point("Tell me about the procedures for Y")
    pdf.bullet_point("What guidelines exist for Z?")
    pdf.ln(2)
    
    pdf.chapter_title("Combined Questions (uses both)", level=3)
    pdf.bullet_point("Which customers have issues and what is the resolution policy?")
    pdf.bullet_point("Show me overdue items and explain the escalation process")
    
    # ========================================================================
    # 8. Troubleshooting
    # ========================================================================
    pdf.add_page()
    pdf.chapter_title("8. Troubleshooting")
    
    pdf.info_box(
        "Tip",
        "Use GitHub Copilot Chat (Ctrl+I in VS Code) for help with errors. "
        "Copilot can explain error messages and suggest fixes."
    )
    pdf.ln(3)
    
    issues = [
        ("Ontology stuck on 'Setting up'",
         "The Ontology creation can sometimes get stuck. Use --clean flag to create a new one with an incremented suffix.",
         "python scripts/00_build_solution.py --clean ..."),
        
        ("FABRIC_WORKSPACE_ID not set",
         "Make sure your .env file contains the Fabric workspace ID. Get it from the Fabric portal URL.",
         "FABRIC_WORKSPACE_ID=fb695e19-2010-..."),
        
        ("AI generation produces invalid data",
         "The AI retry mechanism will attempt 3 times. If it keeps failing, try simplifying your use case description.",
         "# Use simpler, more specific use case descriptions"),
        
        ("Rate limiting (429 errors)",
         "The scripts have built-in retry logic. If you see many 429 errors, wait a few minutes and try again.",
         "# Automatic retry with backoff is enabled"),
        
        ("Search returns no results",
         "Make sure step 06 completed successfully. Check that PDFs were generated and uploaded.",
         "python scripts/06_upload_to_search.py --data-folder <PATH>"),
        
        ("Fabric Data Agent not responding",
         "The Data Agent needs time to index the Ontology. Wait 2-3 minutes after creation before testing.",
         "# Wait for 'Agent is ready' message"),
    ]
    
    for title, desc, code in issues:
        pdf.chapter_title(title, level=2)
        pdf.body_text(desc)
        if code:
            pdf.code_block(code)
    
    # ========================================================================
    # Final Page
    # ========================================================================
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 15, "Congratulations!", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(51, 51, 51)
    pdf.multi_cell(0, 8, 
        "You have successfully completed the Foundry IQ + Fabric IQ hands-on workshop!\n\n"
        "You now know how to:\n"
        "- Use Fabric IQ to create business ontologies and query structured data\n"
        "- Use Foundry IQ to build knowledge bases over documents\n"
        "- Build AI agents with Azure AI Foundry\n"
        "- Build end-to-end AI solutions that unify enterprise data sources\n\n"
        "Next Step: Plug in your own customer data to accelerate your PoCs!",
        align="C"
    )
    
    pdf.ln(30)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 8, "For questions and feedback, visit the GitHub repository.", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    
    # ========================================================================
    # Save PDF
    # ========================================================================
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    output_path = os.path.join(docs_dir, "Foundry_IQ_Fabric_IQ_Workshop_Guide.pdf")
    pdf.output(output_path)
    
    print(f"\n{'='*60}")
    print("Workshop Guide Generated!")
    print(f"{'='*60}")
    print(f"\nOutput: {output_path}")
    print(f"Pages: {pdf.page_no()}")
    print("\nYou can now distribute this PDF to workshop attendees.")


if __name__ == "__main__":
    generate_workshop_guide()
