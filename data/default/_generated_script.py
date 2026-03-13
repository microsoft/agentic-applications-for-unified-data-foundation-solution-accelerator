import os
import json
import random
import pandas as pd
from fpdf import FPDF

output_dir = "C:/repos/accelerator/agentic-applications-for-unified-data-foundation-solution-accelerator/data/20260209_185526_telecommunications/"
config_dir = os.path.join(output_dir, "config")
tables_dir = os.path.join(output_dir, "tables")
documents_dir = os.path.join(output_dir, "documents")

os.makedirs(config_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)
os.makedirs(documents_dir, exist_ok=True)

NUM_TICKETS = 16
NUM_INSPECTIONS = 40

ticket_ids = [f'TICKET{str(i).zfill(3)}' for i in range(1, NUM_TICKETS + 1)]
inspection_ids = [f'INSPECTION{str(i).zfill(3)}' for i in range(1, NUM_INSPECTIONS + 1)]

tickets = pd.DataFrame({
    'ticket_id': ticket_ids,
    'customer_name': [f'Customer {i}' for i in range(1, NUM_TICKETS + 1)],
    'issue_description': [f'Issue description for ticket {i}' for i in range(1, NUM_TICKETS + 1)],
    'priority': random.choices(['Low', 'Medium', 'High'], k=NUM_TICKETS),
    'status': random.choices(['Open', 'In Progress', 'Closed'], k=NUM_TICKETS)
})

inspections = pd.DataFrame({
    'inspection_id': inspection_ids,
    'ticket_id': random.choices(ticket_ids, k=NUM_INSPECTIONS),
    'result': random.choices(['Pass', 'Fail'], weights=[70, 30], k=NUM_INSPECTIONS),
    'score': [random.randint(60, 100) for _ in range(NUM_INSPECTIONS)]
})

tickets.to_csv(os.path.join(tables_dir, 'tickets.csv'), index=False)
inspections.to_csv(os.path.join(tables_dir, 'inspections.csv'), index=False)

config = {
    "scenario": "telecommunications",
    "name": "Network Operations",
    "description": "Tracking outages and trouble tickets.",
    "tables": {
        "tickets": {
            "columns": ["ticket_id", "customer_name", "issue_description", "priority", "status"],
            "types": {"ticket_id": "String", "customer_name": "String", "issue_description": "String", "priority": "String", "status": "String"},
            "key": "ticket_id",
            "source_table": "tickets"
        },
        "inspections": {
            "columns": ["inspection_id", "ticket_id", "result", "score"],
            "types": {"inspection_id": "String", "ticket_id": "String", "result": "String", "score": "BigInt"},
            "key": "inspection_id",
            "source_table": "inspections"
        }
    },
    "relationships": [
        {"name": "ticket_inspection", "from": "inspections", "to": "tickets", "fromKey": "ticket_id", "toKey": "ticket_id"}
    ]
}

with open(os.path.join(config_dir, "ontology_config.json"), "w") as f:
    json.dump(config, f, indent=4)

policy_sections_1 = [
    ("1. Ticket Handling Procedures", 
     "All customer tickets must be acknowledged within 1 hour to ensure timely response. "
     "Closed tickets should provide feedback to clients, ensuring ongoing communication."),
    ("2. Priority Definitions",
     "Tickets classified as 'High' must be resolved within 4 hours. Medium priority tickets are to be resolved within 24 hours, "
     "while low priority issues should not exceed a resolution period of 72 hours."),
]

policy_sections_2 = [
    ("1. Quality Control Standards", 
     "All inspections must achieve a minimum score of 80 out of 100. Inspections falling below this threshold will require "
     "immediate review and corrective action."),
    ("2. Review Procedures",
     "Failed inspections require follow-up assessments within 48 hours. Teams must document corrective actions taken."),
]

def create_pdf(title, sections, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    for heading, content in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        content = content.encode('ascii', 'replace').decode('ascii')
        pdf.multi_cell(0, 6, content)
        pdf.ln(5)
    pdf.output(os.path.join(documents_dir, filename))

create_pdf("Ticket Management Policy", policy_sections_1, "ticket_management_policy.pdf")
create_pdf("Inspection Procedures", policy_sections_2, "inspection_procedures.pdf")

with open(os.path.join(config_dir, "sample_questions.txt"), "w") as f:
    f.write("=== SQL QUESTIONS (Fabric Data) ===\n")
    f.write("1. How many tickets have priority = 'High'?\n")
    f.write("2. What is the average score from inspections?\n")
    f.write("3. Show tickets grouped by status.\n")
    f.write("4. Which ticket has the highest priority?\n")
    f.write("5. How does inspection result distribution compare across ticket statuses?\n")
    f.write("\n")
    f.write("=== DOCUMENT QUESTIONS (AI Search) ===\n")
    f.write("1. What are the requirements for handling customer tickets?\n")
    f.write("2. How quickly should high priority tickets be resolved?\n")
    f.write("3. What constitutes a failed inspection?\n")
    f.write("4. What actions are required for tickets not meeting feedback standards?\n")
    f.write("5. How often must failed inspections be reviewed?\n")
    f.write("\n")
    f.write("=== COMBINED INSIGHT QUESTIONS ===\n")
    f.write("1. Are we meeting our resolution targets for high priority tickets according to our Ticket Management Policy?\n")
    f.write("2. Do any inspections violate quality control standards in our Inspection Procedures?\n")
    f.write("3. Are there any tickets that require follow-up assessments based on our Inspection Procedures?\n")
    f.write("4. What is our average inspection score, and does it meet the minimum standard outlined in our Quality Control Standards?\n")
    f.write("5. How many tickets are open and exceeding response targets set in our Ticket Management Policy?\n")

print("Data generation and output files creation complete.")