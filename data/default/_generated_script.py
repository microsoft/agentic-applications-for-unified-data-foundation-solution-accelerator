import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF

# Define counts
NUM_OUTAGES = 16
NUM_TICKETS = 40

# Output directory
output_dir = "C:/Work/15_fabric_ontology/data/20260203_112459_telecommunications"
config_dir = os.path.join(output_dir, "config")
tables_dir = os.path.join(output_dir, "tables")
documents_dir = os.path.join(output_dir, "documents")

# Create folders
os.makedirs(config_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)
os.makedirs(documents_dir, exist_ok=True)

# Generate primary table: network outages
outages = pd.DataFrame({
    'outage_id': [f'OUT{str(i).zfill(3)}' for i in range(1, NUM_OUTAGES + 1)],
    'outage_start': [(datetime(2024, 1, 1) + timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S') for _ in range(NUM_OUTAGES)],
    'duration_minutes': [random.randint(30, 480) for _ in range(NUM_OUTAGES)],
    'impact_level': random.choices(['Low', 'Medium', 'High'], weights=[50, 30, 20], k=NUM_OUTAGES)
})

outages.to_csv(os.path.join(tables_dir, "network_outages.csv"), index=False)

# Generate secondary table: trouble tickets
tickets = pd.DataFrame({
    'ticket_id': [f'TIC{str(i).zfill(3)}' for i in range(1, NUM_TICKETS + 1)],
    'ticket_created': [(datetime(2024, 1, 1) + timedelta(days=random.randint(0, 60))).strftime('%Y-%m-%d') for _ in range(NUM_TICKETS)],
    'resolution_time': [random.randint(1, 72) for _ in range(NUM_TICKETS)], # In hours
    'outage_id': [f'OUT{str(random.randint(1, NUM_OUTAGES)).zfill(3)}' for _ in range(NUM_TICKETS)],
    'customer_impact': random.choices(['None', 'Minor', 'Major'], weights=[40, 50, 10], k=NUM_TICKETS)
})

tickets.to_csv(os.path.join(tables_dir, "trouble_tickets.csv"), index=False)

# Create the ontology_config.json
config = {
    "scenario": "telecommunications",
    "name": "Network Management",
    "description": "Tracking outages and managing customer impacts",
    "tables": {
        "network_outages": {
            "columns": ["outage_id", "outage_start", "duration_minutes", "impact_level"],
            "types": {"outage_id": "String", "outage_start": "DateTime", "duration_minutes": "BigInt", "impact_level": "String"},
            "key": "outage_id",
            "source_table": "network_outages"
        },
        "trouble_tickets": {
            "columns": ["ticket_id", "ticket_created", "resolution_time", "outage_id", "customer_impact"],
            "types": {"ticket_id": "String", "ticket_created": "Date", "resolution_time": "BigInt", "outage_id": "String", "customer_impact": "String"},
            "key": "ticket_id", 
            "source_table": "trouble_tickets"
        }
    },
    "relationships": [
        {"name": "ticket_outage", "from": "trouble_tickets", "to": "network_outages", "fromKey": "outage_id", "toKey": "outage_id"}
    ]
}

with open(os.path.join(config_dir, "ontology_config.json"), "w") as f:
    json.dump(config, f, indent=4)

# Create sample_questions.txt
questions = """=== SQL QUESTIONS (Fabric Data) ===
- How many outages occurred last month?
- What is the average duration of outages?
- Which outage caused the most customer impact?
- How many trouble tickets were created for each outage?
- What is the average resolution time for tickets?

=== DOCUMENT QUESTIONS (AI Search) ===
- What are the policies for notifying customers of outages?
- How is customer impact classified in our documentation?
- What is the response time required for outages?
- What steps must be taken to escalate an outage?
- How often should outage reports be generated?

=== COMBINED INSIGHT QUESTIONS ===
- Which outages exceeded the maximum duration defined in our policy?
- What percentage of tickets were resolved in less time than our SLA?
- How many outages were rated as 'High' impact based on our threshold?
- Which tickets experienced delays longer than our expected resolution times?
- What was the average customer impact during the last 30 days compared to policy standards?
"""

with open(os.path.join(config_dir, "sample_questions.txt"), "w") as f:
    f.write(questions)

# Function to create PDFs
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

# Create PDF policy documents
sections1 = [
    ("1. Outage Notification Policy", 
     "In the event of a significant network outage, it is essential to notify impacted customers within 30 minutes. "
     "Notifications should be sent via SMS and email for maximum reach. Levels of notification depend on impact: "
     "'Major' outages will require direct communications, while 'Minor' ones can be handled through website updates."),
    ("2. Customer Impact Classification",
     "Customer impact is classified into three levels: None, Minor, and Major. "
     "'Minor' reflects limited service disruptions affecting a small number of users, whereas 'Major' indicates a significant disruption affecting a large customer base. "
     "This classification guides response strategies and customer communications."),
    ("3. Outage Reporting Frequency",
     "Outage reports must be generated and reviewed on a weekly basis. Reports should include total outages, average duration, and customer impact ratings. "
     "This data is crucial for assessing the overall health of the network and guiding improvement efforts.")
]

create_pdf("Outage Management Policies", sections1, "outage_management_policies.pdf")

sections2 = [
    ("1. Ticket Escalation Process",
     "If a trouble ticket is unresolved after 24 hours, it should be escalated to a supervisor. Supervisors have an additional 24 hours to resolve issues. "
     "For tickets that remain unresolved after this period, further escalation to the management team is mandatory."),
    ("2. Resolution Time Standards",
     "All tickets should ideally be resolved within 72 hours. A timely resolution is a critical aspect of customer satisfaction. "
     "Any ticket exceeding this timeline must be flagged for management review and action."),
    ("3. Customer Feedback Mechanism",
     "It is imperative to gather customer feedback on ticket resolution. Follow-up surveys should be sent within one week of ticket closure, with a target response rate of 60%. "
     "Feedback will be reviewed bi-weekly to identify areas for service improvement.")
]

create_pdf("Trouble Ticket Management Policies", sections2, "ticket_management_policies.pdf")

sections3 = [
    ("1. Compliance and Service Level Agreements",
     "Service Level Agreements (SLAs) define minimum service quality levels. For outages, resolutions must not exceed a maximum duration of four hours for 'Major' impacts. "
     "Regular audits should be conducted to ensure compliance with these SLAs."),
    ("2. Reporting and Documentation",
     "All outages and tickets must be documented with specified details including resolution times, customer impacts, and escalations. "
     "Documentation is crucial for ensuring accountability and transparency in our operations."),
    ("3. Response Time Expectations",
     "Customer service representatives must respond to outage inquiries within one hour during business hours. Outside of business hours, responses should occur within three hours. "
     "This commitment to prompt responses helps maintain customer trust.")
]

create_pdf("Policies for Customer Service and Accountability", sections3, "customer_service_policies.pdf")

print("Data and documents generated successfully.")