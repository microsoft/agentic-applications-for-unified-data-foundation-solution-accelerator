import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF

output_dir = r"C:/repos/workshop/agentic-applications-for-unified-data-foundation-solution-accelerator/data/20260308_230015_telecommunications"
config_dir = os.path.join(output_dir, "config")
tables_dir = os.path.join(output_dir, "tables")
documents_dir = os.path.join(output_dir, "documents")

os.makedirs(config_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)
os.makedirs(documents_dir, exist_ok=True)

# Constants for row counts
NUM_CUSTOMERS = 200
NUM_TECHNICIANS = 200
NUM_NETWORK_NODES = 200
NUM_TICKETS = 1000
NUM_OUTAGES = 500
NUM_WORK_ORDERS = 400
NUM_MAINTENANCE_RECORDS = 300

# Helper for generating varied dates over roughly 6 months
def random_dates(num, start_date, end_date):
    delta_days = (end_date - start_date).days
    return [(start_date + timedelta(days=random.randint(0, delta_days))).strftime('%Y-%m-%d') for _ in range(num)]

base_start = datetime(2023, 10, 1)
base_end = datetime(2024, 3, 31)

# TABLE 1: customers
first_names = ['James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
               'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph', 'Jessica']
last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
customer_ids = [f'CUST{str(i).zfill(4)}' for i in range(1, NUM_CUSTOMERS + 1)]
customers = pd.DataFrame({
    'customer_id': customer_ids,
    'name': [f"{random.choice(first_names)} {random.choice(last_names)}" for _ in range(NUM_CUSTOMERS)],
    'city': [random.choice(['Springfield', 'Riverton', 'Lakeside', 'Hillsdale', 'Mapleton']) for _ in range(NUM_CUSTOMERS)],
    'signup_date': random_dates(NUM_CUSTOMERS, datetime(2022,1,1), datetime(2023,9,30))
})

# TABLE 2: technicians
technician_ids = [f'TECH{str(i).zfill(4)}' for i in range(1, NUM_TECHNICIANS + 1)]
departments = ['Installation', 'Repair', 'Maintenance', 'Network Support', 'Customer Service']
hire_dates = random_dates(NUM_TECHNICIANS, datetime(2015,1,1), datetime(2023,6,30))
technicians = pd.DataFrame({
    'technician_id': technician_ids,
    'name': [f"{random.choice(first_names)} {random.choice(last_names)}" for _ in range(NUM_TECHNICIANS)],
    'department': [departments[i % len(departments)] for i in range(NUM_TECHNICIANS)],
    'hire_date': hire_dates
})

# TABLE 3: network_nodes
node_types = ['Router', 'Switch', 'Hub', 'Fiber Node', 'Wireless Access Point']
statuses = ['Active', 'Inactive', 'Under Maintenance']
network_node_ids = [f'NODE{str(i).zfill(4)}' for i in range(1, NUM_NETWORK_NODES + 1)]
last_maintenance_dates = random_dates(NUM_NETWORK_NODES, datetime(2023,1,1), datetime(2024,3,15))
network_nodes = pd.DataFrame({
    'node_id': network_node_ids,
    'node_type': [node_types[i % len(node_types)] for i in range(NUM_NETWORK_NODES)],
    'location': [random.choice(['North', 'South', 'East', 'West', 'Central']) for _ in range(NUM_NETWORK_NODES)],
    'status': [statuses[i % len(statuses)] for i in range(NUM_NETWORK_NODES)],
    'last_maintenance_date': last_maintenance_dates
})

# TABLE 4: tickets
ticket_ids = [f'TICK{str(i).zfill(5)}' for i in range(1, NUM_TICKETS + 1)]
ticket_priorities = ['Low', 'Medium', 'High', 'Critical']
ticket_statuses = ['Open', 'In Progress', 'Resolved', 'Closed']
issue_types = ['Connectivity', 'Hardware Failure', 'Service Outage', 'Configuration', 'Billing']
ticket_dates_created = random_dates(NUM_TICKETS, datetime(2023,10,1), datetime(2024,3,30))
# Assigned technicians selected only from existing technicians
tickets = pd.DataFrame({
    'ticket_id': ticket_ids,
    'customer_id': [random.choice(customer_ids) for _ in range(NUM_TICKETS)],
    'technician_id': [random.choice(technician_ids) for _ in range(NUM_TICKETS)],
    'node_id': [random.choice(network_node_ids) for _ in range(NUM_TICKETS)],
    'priority': [ticket_priorities[i % len(ticket_priorities)] for i in range(NUM_TICKETS)],
    'status': [random.choices(ticket_statuses, weights=[20,30,35,15])[0] for _ in range(NUM_TICKETS)],
    'issue_type': [issue_types[i % len(issue_types)] for i in range(NUM_TICKETS)],
    'date_created': ticket_dates_created,
    'date_resolved': None  # To be filled below
})

# Calculate date_resolved with some tickets unresolved
date_resolved_list = []
for i in range(NUM_TICKETS):
    created_date = datetime.strptime(tickets.at[i, 'date_created'], '%Y-%m-%d')
    if tickets.at[i, 'status'] in ['Resolved', 'Closed']:
        resolved_delta = random.randint(1, 30)
        resolved_date = created_date + timedelta(days=resolved_delta)
        # Ensure resolved_date is not beyond base_end
        if resolved_date > base_end:
            resolved_date = base_end
        date_resolved_list.append(resolved_date.strftime('%Y-%m-%d'))
    else:
        date_resolved_list.append('')
tickets['date_resolved'] = date_resolved_list

# TABLE 5: outages
outage_ids = [f'OUT{str(i).zfill(5)}' for i in range(1, NUM_OUTAGES + 1)]
outage_durations = []
outage_nodes = []
outage_start_dates = []
outage_severities = ['Minor', 'Major', 'Critical']
for i in range(NUM_OUTAGES):
    node = random.choice(network_node_ids)
    outage_nodes.append(node)
    start_date = base_start + timedelta(days=random.randint(0, (base_end - base_start).days))
    outage_start_dates.append(start_date.strftime('%Y-%m-%d'))
    # Duration between 1 hour to 72 hours
    dur = random.randint(1, 72)
    outage_durations.append(dur)
    # Severity distributed weighted: Minor 50%, Major 35%, Critical 15%
severities_vals = random.choices(outage_severities, weights=[50,35,15], k=NUM_OUTAGES)

# Introduce violation for outage duration: 80% less than or equal 48 hours (threshold), 20% exceed 48 hours
for i in range(int(NUM_OUTAGES * 0.8), NUM_OUTAGES):
    outage_durations[i] = random.randint(49, 72)  # Violations >48

outages = pd.DataFrame({
    'outage_id': outage_ids,
    'node_id': outage_nodes,
    'start_date': outage_start_dates,
    'duration_hours': outage_durations,
    'severity': severities_vals
})

# TABLE 6: work_orders
work_order_ids = [f'WO{str(i).zfill(5)}' for i in range(1, NUM_WORK_ORDERS + 1)]
wo_types = ['Routine Maintenance', 'Emergency Repair', 'Installation', 'Inspection']
wo_statuses = ['Pending', 'In Progress', 'Completed']
wo_dates_created = random_dates(NUM_WORK_ORDERS, datetime(2023,10,1), datetime(2024,3,31))
assigned_technicians_wo = [random.choice(technician_ids) for _ in range(NUM_WORK_ORDERS)]
wo_dates_completed = []
wo_durations_hours = []

# Duration threshold policy: max 8 hours duration (violations > 8)
# Assign durations with 75% <=8, 25% >8
for i in range(NUM_WORK_ORDERS):
    if i < int(NUM_WORK_ORDERS * 0.75):
        dur = random.randint(1, 8)
    else:
        dur = random.randint(9, 20)  # Violations
    wo_durations_hours.append(dur)

# Completed dates based on created + duration (assuming 1 hour per duration hour for completion)
for i in range(NUM_WORK_ORDERS):
    created_dt = datetime.strptime(wo_dates_created[i], '%Y-%m-%d')
    if random.random() < 0.85:
        completed_dt = created_dt + timedelta(days=random.randint(0, 5))
        wo_dates_completed.append(completed_dt.strftime('%Y-%m-%d'))
    else:
        wo_dates_completed.append('')  # Not completed yet

work_orders = pd.DataFrame({
    'work_order_id': work_order_ids,
    'ticket_id': [random.choice(ticket_ids) for _ in range(NUM_WORK_ORDERS)],
    'technician_id': assigned_technicians_wo,
    'type': [wo_types[i % len(wo_types)] for i in range(NUM_WORK_ORDERS)],
    'status': [wo_statuses[i % len(wo_statuses)] for i in range(NUM_WORK_ORDERS)],
    'date_created': wo_dates_created,
    'date_completed': wo_dates_completed,
    'duration_hours': wo_durations_hours
})

# TABLE 7: maintenance_records
maintenance_ids = [f'MAINT{str(i).zfill(5)}' for i in range(1, NUM_MAINTENANCE_RECORDS + 1)]
maintenance_types = ['Inspection', 'Repair', 'Upgrade', 'Calibration']
technicians_for_maint = [random.choice(technician_ids) for _ in range(NUM_MAINTENANCE_RECORDS)]
nodes_for_maint = [random.choice(network_node_ids) for _ in range(NUM_MAINTENANCE_RECORDS)]
maint_start_dates = random_dates(NUM_MAINTENANCE_RECORDS, datetime(2023,10,1), datetime(2024,3,31))

# Last review policy: next maintenance due every 90 days (some violations past due)
# We will simulate last_maintenance_date (already in network_nodes) and create maintenance records with date performed
# We will create an "overdue" indicator by comparing date performed to last_maintenance_date + 90 days


maintenance_types_set = [maintenance_types[i % len(maintenance_types)] for i in range(NUM_MAINTENANCE_RECORDS)]

maintenance_records = pd.DataFrame({
    'maintenance_id': maintenance_ids,
    'node_id': nodes_for_maint,
    'technician_id': technicians_for_maint,
    'maintenance_type': maintenance_types_set,
    'date_performed': maint_start_dates
})

# TABLE 8: service_sla_metrics (extra table for example, 200 rows)
NUM_SLA = 200
sla_ids = [f'SLA{str(i).zfill(4)}' for i in range(1, NUM_SLA + 1)]
sla_ticket_ids = [random.choice(ticket_ids) for _ in range(NUM_SLA)]
# Response time hours: threshold max 48 hours, 75% below, 25% violations >48
sla_response_times = []
for i in range(NUM_SLA):
    if i < int(NUM_SLA * 0.75):
        sla_response_times.append(random.randint(1, 48))
    else:
        sla_response_times.append(random.randint(49, 96))
sla_resolution_times = []
# Resolution time hours threshold max 72 hours, 80% below, 20% violations >72
for i in range(NUM_SLA):
    if i < int(NUM_SLA * 0.8):
        sla_resolution_times.append(random.randint(1, 72))
    else:
        sla_resolution_times.append(random.randint(73, 120))

service_sla_metrics = pd.DataFrame({
    'sla_id': sla_ids,
    'ticket_id': sla_ticket_ids,
    'response_time_hours': sla_response_times,
    'resolution_time_hours': sla_resolution_times
})

# Save all tables to CSV
customers.to_csv(os.path.join(tables_dir, "customers.csv"), index=False)
technicians.to_csv(os.path.join(tables_dir, "technicians.csv"), index=False)
network_nodes.to_csv(os.path.join(tables_dir, "network_nodes.csv"), index=False)
tickets.to_csv(os.path.join(tables_dir, "tickets.csv"), index=False)
outages.to_csv(os.path.join(tables_dir, "outages.csv"), index=False)
work_orders.to_csv(os.path.join(tables_dir, "work_orders.csv"), index=False)
maintenance_records.to_csv(os.path.join(tables_dir, "maintenance_records.csv"), index=False)
service_sla_metrics.to_csv(os.path.join(tables_dir, "service_sla_metrics.csv"), index=False)

# Ontology Config
config = {
    "scenario": "telecommunications",
    "name": "Network Operations and Outage Tracking",
    "description": "Management of telecommunications network operations with outage tracking and trouble ticket management",
    "tables": {
        "customers": {
            "columns": ["customer_id", "name", "city", "signup_date"],
            "types": {"customer_id": "String", "name": "String", "city": "String", "signup_date": "Date"},
            "key": "customer_id",
            "source_table": "customers"
        },
        "technicians": {
            "columns": ["technician_id", "name", "department", "hire_date"],
            "types": {"technician_id": "String", "name": "String", "department": "String", "hire_date": "Date"},
            "key": "technician_id",
            "source_table": "technicians"
        },
        "network_nodes": {
            "columns": ["node_id", "node_type", "location", "status", "last_maintenance_date"],
            "types": {"node_id": "String", "node_type": "String", "location": "String", "status": "String", "last_maintenance_date": "Date"},
            "key": "node_id",
            "source_table": "network_nodes"
        },
        "tickets": {
            "columns": ["ticket_id", "customer_id", "technician_id", "node_id", "priority", "status", "issue_type", "date_created", "date_resolved"],
            "types": {"ticket_id": "String", "customer_id": "String", "technician_id": "String", "node_id": "String", "priority": "String", "status": "String", "issue_type": "String", "date_created": "Date", "date_resolved": "Date"},
            "key": "ticket_id",
            "source_table": "tickets"
        },
        "outages": {
            "columns": ["outage_id", "node_id", "start_date", "duration_hours", "severity"],
            "types": {"outage_id": "String", "node_id": "String", "start_date": "Date", "duration_hours": "BigInt", "severity": "String"},
            "key": "outage_id",
            "source_table": "outages"
        },
        "work_orders": {
            "columns": ["work_order_id", "ticket_id", "technician_id", "type", "status", "date_created", "date_completed", "duration_hours"],
            "types": {"work_order_id": "String", "ticket_id": "String", "technician_id": "String", "type": "String", "status": "String", "date_created": "Date", "date_completed": "Date", "duration_hours": "BigInt"},
            "key": "work_order_id",
            "source_table": "work_orders"
        },
        "maintenance_records": {
            "columns": ["maintenance_id", "node_id", "technician_id", "maintenance_type", "date_performed"],
            "types": {"maintenance_id": "String", "node_id": "String", "technician_id": "String", "maintenance_type": "String", "date_performed": "Date"},
            "key": "maintenance_id",
            "source_table": "maintenance_records"
        },
        "service_sla_metrics": {
            "columns": ["sla_id", "ticket_id", "response_time_hours", "resolution_time_hours"],
            "types": {"sla_id": "String", "ticket_id": "String", "response_time_hours": "BigInt", "resolution_time_hours": "BigInt"},
            "key": "sla_id",
            "source_table": "service_sla_metrics"
        }
    },
    "relationships": [
        {"name": "ticket_customer", "from": "tickets", "to": "customers", "fromKey": "customer_id", "toKey": "customer_id"},
        {"name": "ticket_technician", "from": "tickets", "to": "technicians", "fromKey": "technician_id", "toKey": "technician_id"},
        {"name": "ticket_node", "from": "tickets", "to": "network_nodes", "fromKey": "node_id", "toKey": "node_id"},
        {"name": "outage_node", "from": "outages", "to": "network_nodes", "fromKey": "node_id", "toKey": "node_id"},
        {"name": "workorder_ticket", "from": "work_orders", "to": "tickets", "fromKey": "ticket_id", "toKey": "ticket_id"},
        {"name": "workorder_technician", "from": "work_orders", "to": "technicians", "fromKey": "technician_id", "toKey": "technician_id"},
        {"name": "maintenance_node", "from": "maintenance_records", "to": "network_nodes", "fromKey": "node_id", "toKey": "node_id"},
        {"name": "maintenance_technician", "from": "maintenance_records", "to": "technicians", "fromKey": "technician_id", "toKey": "technician_id"},
        {"name": "sla_ticket", "from": "service_sla_metrics", "to": "tickets", "fromKey": "ticket_id", "toKey": "ticket_id"}
    ]
}

with open(os.path.join(config_dir, "ontology_config.json"), "w") as f:
    json.dump(config, f, indent=4)

# PDF CREATION FUNCTION
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

# PDF 1: Network Operations Policy
sections = [
    ("1. Incident Response Time",
     "All network incidents must be responded to within 48 hours from the moment they are reported. "
     "Any delay beyond this period could impact network performance and customer satisfaction. "
     "The Network Operations team is responsible for monitoring response times daily. "
     "Critical priority tickets must be addressed immediately and escalated if unresolved within 24 hours. "
     "Failure to meet these requirements will trigger a formal review process."),
    ("2. Ticket Resolution Time",
     "Tickets created for troubleshooting or issue resolution must be addressed within 72 hours, "
     "with the objective to close them promptly upon resolution confirmation. "
     "Resolution time tracking is mandatory for all technicians to ensure SLA adherence. "
     "Tickets exceeding this duration will be flagged for management attention. "
     "Extensions beyond 72 hours require documented justification and approval."),
    ("3. Priority Assignment Criteria",
     "Ticket priorities must be assigned according to impact and urgency. "
     "Critical priority applies to outages affecting multiple customers or vital infrastructure. "
     "High priority includes major service disruptions, Medium priority reflects individual customer impact, "
     "and Low priority refers to minor or cosmetic issues. "
     "Priorities must be reviewed weekly and adjusted as situations evolve."),
    ("4. Scheduled Maintenance Windows",
     "Scheduled maintenance must be performed during predefined maintenance windows between 12 AM and 6 AM local time to minimize service interruptions. "
     "All maintenance activities must be notified to affected customers at least 48 hours in advance. "
     "Emergency maintenance is allowed outside these windows but requires post-action reporting. "
     "Documentation of maintenance scope and duration is mandatory."),
    ("5. Outage Duration Thresholds",
     "Outages should not exceed 48 hours in duration to limit customer impact. "
     "Any outage extending beyond this threshold requires immediate escalation and customer communication. "
     "Post-outage analysis is to be completed within 5 business days. "
     "Sustained minimization of outage duration is critical for service reliability."),
    ("6. Technician Training and Certification",
     "All technicians must complete annual training on network technologies and operations procedures. "
     "Certification in relevant specialties is required for performing complex repairs. "
     "Training completion records must be submitted to management quarterly. "
     "Non-certified personnel shall not conduct critical maintenance without supervision."),
    ("7. Work Order Duration",
     "Work orders are expected to be completed within 8 hours unless otherwise documented. "
     "Work exceeding this duration must include detailed explanation and approval. "
     "Regular monitoring of work order times supports resource allocation and efficiency improvements. "
     "Unreasonably long work orders may trigger additional training or performance evaluation."),
    ("8. Quality Assurance Reviews",
     "Quality reviews of resolved tickets and completed work orders shall occur monthly. "
     "Reviews assess adherence to process, resolution quality, and customer feedback. "
     "Findings are used to inform training and process refinement. "
     "A minimum pass rate of 80 percent is required across all technicians.")
]
create_pdf("Network Operations Policy", sections, "network_operations_policy.pdf")

# PDF 2: Outage Management Guidelines
sections = [
    ("1. Outage Identification",
     "Outages must be identified promptly using automated monitoring tools that detect network anomalies and failures. "
     "Manual reporting is allowed but must be verified by system checks. "
     "All detected outages are to be logged immediately in the outage management system. "
     "Frequent false alarms should be investigated and addressed."),
    ("2. Communication Protocol",
     "Customers affected by outages must be notified within 2 hours of detection. "
     "Regular updates must be provided every 4 hours until resolution. "
     "Communication channels include email, SMS alerts, and the customer support portal. "
     "All communications must include estimated resolution times and cause explanations when known."),
    ("3. Outage Severity Classification",
     "Outages are classified by severity: Minor affects single users, Major impacts a service area, Critical affects core infrastructure. "
     "Severity determines response priorities and resource allocation. "
     "Classification must be revisited during incident updates as more information becomes available."),
    ("4. Restoration Targets",
     "The goal is to restore network services within 48 hours for all outages. "
     "Critical outages must be resolved within 24 hours whenever possible. "
     "Recovery plans should include fallback and redundancy steps. "
     "Any deviation from targets requires documented escalation and client notification."),
    ("5. Root Cause Analysis",
     "All outages require a root cause analysis to be completed within 7 days of resolution. "
     "The RCA reports outline causes, corrective actions, and preventive measures. "
     "Reports are reviewed by management to improve network resilience. "
     "Recurrent issues trigger intensified investigation and remedial projects."),
    ("6. Documentation Standards",
     "Outage records must include start and end times, affected nodes, impacted services, and severity level. "
     "Detailed logs of technician actions and communications are essential. "
     "Maintaining accurate records supports audits and customer inquiries. "
     "Data confidentiality and integrity must be preserved.")
]
create_pdf("Outage Management Guidelines", sections, "outage_management_guidelines.pdf")

# PDF 3: Technician Work Order Procedures
sections = [
    ("1. Work Order Creation",
     "Work orders are officially generated from tickets requiring field technician intervention. "
     "Each order must include clear descriptions, location details, and priority level. "
     "Orders must be assigned to technically qualified personnel according to scheduling and skills. "
     "Completeness of initial work order data facilitates effective and timely resolution."),
    ("2. Scheduling and Dispatch",
     "Dispatchers schedule work orders prioritizing critical and high-impact tasks first. "
     "Customer availability and technician location are considered to optimize travel times. "
     "Schedules must be flexible to accommodate emergency tasks. "
     "Technicians are required to confirm receipt and acceptance of work orders."),
    ("3. Execution and Reporting",
     "Technicians must document all actions taken during service visits, including equipment replaced and tests performed. "
     "Photos and diagnostic logs should be attached when applicable. "
     "Any deviations or additional findings outside the original scope require adjustment requests. "
     "Completion reports must be submitted within 24 hours of job closure."),
    ("4. Duration and Efficiency",
     "Work order durations are monitored to identify resource bottlenecks. "
     "While some variation is normal, prolonged tasks beyond 8 hours must undergo review. "
     "Technicians are encouraged to report delays promptly to enable schedule adjustments. "
     "Efficiency improvements are tracked and rewarded."),
    ("5. Safety and Compliance",
     "Safety guidelines must be followed at all times during field operations. "
     "Technicians must wear appropriate personal protective equipment and follow lockout/tagout procedures. "
     "Compliance with regulatory standards is mandatory. "
     "Incidents or near misses are to be reported immediately and investigated."),
    ("6. Quality Verification",
     "All completed work orders undergo quality verification by supervisors or quality assurance teams. "
     "Spot checks and audits ensure compliance with operational standards. "
     "Feedback from customers helps measure satisfaction and identify improvement areas. "
     "Technicians failing quality checks may require remedial training.")
]
create_pdf("Technician Work Order Procedures", sections, "technician_work_order_procedures.pdf")

# PDF 4: Maintenance Scheduling and Standards
sections = [
    ("1. Maintenance Frequency",
     "Network nodes require routine maintenance every 90 days to ensure optimal operation. "
     "Schedules are planned based on equipment type, usage intensity, and past failure history. "
     "Urgent maintenance is scheduled in response to detected faults or performance degradation. "
     "Deviation from scheduling requires documentation and justification."),
    ("2. Maintenance Types",
     "Scheduled activities include inspections, repairs, upgrades, and calibrations. "
     "Each type follows prescribed procedures and checklists to standardize quality. "
     "Records of completed tasks are maintained in the maintenance management system. "
     "Non-standard maintenance actions require supervisor approval."),
    ("3. Technician Qualifications",
     "Only trained and certified technicians perform maintenance tasks. "
     "Training programs focus on new technologies, safety, and quality standards. "
     "Continuous education is encouraged to maintain certification validity. "
     "Unqualified personnel must be supervised when involved in complex maintenance."),
    ("4. Equipment and Tools",
     "Technicians shall use approved tools and replacement parts to guarantee safety and functionality. "
     "Equipment calibration and maintenance of tools are mandatory. "
     "Use of unauthorized materials is forbidden and may void warranties. "
     "Toolkits must be inventoried and tracked."),
    ("5. Documentation and Reporting",
     "Maintenance activities must be logged with detailed descriptions, findings, and corrective actions. "
     "Reports are reviewed monthly to identify trends and recurring issues. "
     "Accurate documentation aids in regulatory compliance and audit readiness. "
     "Electronic submission of reports is standard."),
    ("6. Overdue Maintenance Handling",
     "Maintenance overdue beyond 30 days triggers automatic alerts to managers. "
     "Overdue items must be prioritized for immediate action to prevent outages. "
     "Repeat overdue occurrences are subject to performance reviews. "
     "Mitigation plans must be created for high-risk equipment."),
    ("7. Safety Procedures",
     "Strict adherence to safety protocols is required during all maintenance activities. "
     "Risk assessments must precede maintenance work. "
     "Emergency shutdown procedures are to be understood and accessible. "
     "Safety incidents must be reported and investigated without delay."),
    ("8. Quality Control",
     "Maintenance outcomes are subject to quality audits to verify effectiveness. "
     "Audit results inform process improvements and training focus. "
     "Key performance indicators track work quality and compliance rates. "
     "Failure to meet quality standards requires corrective actions and follow-ups.")
]
create_pdf("Maintenance Scheduling and Standards", sections, "maintenance_scheduling_and_standards.pdf")

# PDF 5: Service Level Agreement (SLA) Policies
sections = [
    ("1. Response Time Commitments",
     "Our SLA guarantees response to priority tickets within established timeframes—48 hours for standard issues and immediately for critical ones. "
     "Non-compliance results in compensation credits or service adjustments. "
     "Ongoing tracking mechanisms ensure transparency and accountability. "
     "Customers may escalate unresolved issues as per escalation protocols."),
    ("2. Resolution Timeframes",
     "Tickets are targeted to be resolved within 72 hours. "
     "Complex problems may require extended timelines with communicated justifications. "
     "Resolution time is crucial for customer satisfaction measurement. "
     "Extended resolution times must be logged and reviewed."),
    ("3. Availability Guarantees",
     "Network availability is guaranteed at 99.9% uptime monthly. "
     "Credit mechanisms apply if availability falls below this threshold. "
     "Scheduled maintenance outside peak hours is excluded from availability calculations. "
     "Transparency in availability reporting is provided monthly."),
    ("4. Penalty and Remedies",
     "Failure to meet SLA metrics can lead to monetary penalties or service discounts. "
     "Penalties apply per incident and may accumulate for repeated breaches. "
     "Remedy processes are initiated following review and confirmation. "
     "Customers are informed transparently on remediation actions."),
    ("5. Exclusions",
     "SLA commitments exclude outages caused by external factors such as force majeure events, customer equipment issues, or unauthorized network modifications. "
     "Customers are responsible for maintaining correct configurations as prescribed. "
     "Exclusion conditions are communicated during contract initiation."),
    ("6. Review and Renewal",
     "SLA policies are reviewed annually with stakeholder consultation. "
     "Amendments require mutual agreement documented in writing. "
     "Customers are notified in advance of any changes. "
     "Continuous improvement is a key SLA principle.")
]
create_pdf("Service Level Agreement Policies", sections, "sla_policies.pdf")

# PDF 6: Quality Assurance Manual
sections = [
    ("1. Quality Objectives",
     "The Quality Assurance team aims to maintain a minimum of 80 percent pass rate on all ticket and work order inspections. "
     "Quality standards encompass operational procedures, customer satisfaction, and compliance. "
     "Continuous monitoring and reporting support these objectives. "
     "Teams are recognized for sustained quality achievements."),
    ("2. Inspection Processes",
     "Periodic quality inspections of resolved tickets and maintenance records are conducted monthly. "
     "Inspections verify procedural adherence, correctness of resolution, and documentation quality. "
     "Deficiencies are documented with corrective action plans. "
     "Inspection results feed into training and process improvements."),
    ("3. Non-Conformance Handling",
     "Cases failing quality inspection are subject to root cause analysis. "
     "Action plans include retraining, process change, or disciplinary measures as appropriate. "
     "Non-conformance trends are reported to senior management quarterly. "
     "Timely corrective actions are mandatory to restore compliance."),
    ("4. Customer Feedback Integration",
     "Customer satisfaction surveys are incorporated into quality assessments. "
     "Feedback drives continual service enhancements and identifies focus areas. "
     "Negative feedback prompts follow-up actions including technical reviews. "
     "Transparency with customers builds trust and loyalty."),
    ("5. Documentation Standards",
     "All QA activities and findings are recorded in the Quality Management System. "
     "Documentation must be clear, complete, and accessible for audits. "
     "Records include inspection checklists, feedback, and corrective actions. "
     "Confidentiality is maintained for sensitive information."),
    ("6. Training and Development",
     "Quality findings guide focused training programs. "
     "Technicians with recurring quality issues receive targeted coaching. "
     "Training progress is tracked and linked to certification renewals. "
     "Quality culture is promoted throughout the organization."),
    ("7. Continuous Improvement",
     "QA outcomes are used to refine processes, tools, and policies. "
     "Lessons learned are disseminated monthly. "
     "Innovation and best practices are encouraged for ongoing excellence. "
     "Regular reviews ensure relevance and effectiveness of quality measures."),
    ("8. Performance Metrics",
     "Key performance indicators for quality include pass rates, defect rates, and turnaround times. "
     "Metrics are reported quarterly and benchmarked against industry standards. "
     "Deviations prompt immediate investigation and action. "
     "Data-driven decision making underpins QA activities.")
]
create_pdf("Quality Assurance Manual", sections, "quality_assurance_manual.pdf")

# PDF 7: Safety Standards and Protocol
sections = [
    ("1. General Safety Principles",
     "Safety of personnel and customers is paramount in all operational activities. "
     "Workers must adhere strictly to established safety protocols at all times. "
     "Hazard identification and mitigation are continuous responsibilities. "
     "Safety training and awareness campaigns are held regularly."),
    ("2. Personal Protective Equipment",
     "Appropriate personal protective equipment (PPE) must be worn related to the task. "
     "PPE includes helmets, gloves, safety glasses, and hi-visibility clothing. "
     "Proper use and maintenance of PPE are required. "
     "Non-compliance may result in disciplinary action."),
    ("3. Hazardous Materials Handling",
     "Only trained personnel handle hazardous materials associated with network hardware. "
     "Material Safety Data Sheets (MSDS) are to be available and reviewed. "
     "Proper storage, transport, and disposal procedures must be followed. "
     "Incidents involving hazardous materials require immediate reporting."),
    ("4. Emergency Procedures",
     "Emergency procedures for fire, electrical hazards, and accidents are documented and trained. "
     "Emergency exits and equipment locations are clearly marked. "
     "Regular drills are conducted to ensure preparedness. "
     "Incident reports must be filed for all emergencies."),
    ("5. Equipment Safety",
     "All tools and equipment must be inspected before use for safety compliance. "
     "Defective equipment must be removed and reported. "
     "Lockout/tagout procedures prevent accidents during maintenance. "
     "Use of unauthorized modifications is prohibited."),
    ("6. Incident Reporting",
     "All safety incidents, near misses, and unsafe conditions must be reported immediately. "
     "Reports are investigated to determine causes and prevent recurrence. "
     "Follow-ups include corrective action plans and communication. "
     "Data is analyzed for trends and safety improvements."),
    ("7. Training Requirements",
     "Mandatory safety training is required annually for all field and operations staff. "
     "Training covers general safety, specific hazards, and emergency response. "
     "Records of training completion are maintained. "
     "Refresher sessions are provided after incidents or process changes."),
    ("8. Compliance and Auditing",
     "Safety compliance is audited regularly by internal and external parties. "
     "Findings trigger corrective actions and process updates. "
     "Safety performance is a key management metric. "
     "Continuous improvement in safety culture is promoted.")
]
create_pdf("Safety Standards and Protocol", sections, "safety_standards_and_protocol.pdf")

# PDF 8: Customer Service and Communication Policy
sections = [
    ("1. Communication Principles",
     "Clear and timely communication with customers is a core value. "
     "All customer interactions must be professional, respectful, and solution-oriented. "
     "Communications include incident notifications, updates, and feedback requests. "
     "Accuracy and clarity are essential to build trust."),

    ("2. Incident Notification",
     "Customers must be notified within 2 hours of network incidents affecting their services. "
     "Notifications should include causes, impact, and expected resolution times. "
     "Multiple channels including email and SMS are used to maximize reach. "
     "Follow-up communications keep customers informed."),

    ("3. Escalation Procedures",
     "Customer issues unresolved within SLA timeframes may be escalated to higher management. "
     "Escalation protocols are documented and accessible to support teams. "
     "Escalation aims to resolve issues efficiently and maintain customer satisfaction. "
     "Feedback on escalation handling is used to improve processes."),

    ("4. Feedback Collection",
     "Regular feedback is solicited through surveys, calls, and online portals. "
     "Feedback data informs service improvements and identifies training needs. "
     "Negative feedback triggers timely follow-up and resolutions. "
     "Customer input is valued as a continuous improvement mechanism."),

    ("5. Complaint Management",
     "Complaints are logged and categorized to identify trends and root causes. "
     "Resolution timelines are monitored with escalation if delays occur. "
     "Transparency in complaint handling builds confidence. "
     "Staff are trained in complaint resolution best practices."),

    ("6. Training and Resources",
     "Customer service personnel receive ongoing training in communication skills and technical knowledge. "
     "Resource materials and FAQs support consistent messaging. "
     "Training includes handling difficult conversations and problem-solving. "
     "Performance is monitored via quality assessments and customer ratings."),

    ("7. Privacy and Confidentiality",
     "Customer data privacy is strictly maintained in all communications. "
     "Only authorized personnel access sensitive information. "
     "Policies comply with relevant data protection regulations. "
     "Breaches are taken seriously with defined response plans."),

    ("8. Documentation and Reporting",
     "All customer interactions and communications are logged accurately. "
     "Records support service continuity and audit requirements. "
     "Reporting on communication effectiveness is conducted quarterly. "
     "Data drives improvements in service delivery and customer experience.")
]
create_pdf("Customer Service and Communication Policy", sections, "customer_service_and_communication_policy.pdf")

# Sample_questions.txt generation
with open(os.path.join(config_dir, "sample_questions.txt"), "w") as f:
    f.write("=== SQL QUESTIONS (Fabric Data) ===\n")
    f.write("1. How many open tickets are currently assigned to technicians in the Repair department?\n")
    f.write("2. What is the average duration in hours of work orders classified as Emergency Repair?\n")
    f.write("3. Show the count of outages grouped by severity level for the last six months.\n")
    f.write("4. Which technician has the highest number of resolved tickets in the last three months?\n")
    f.write("5. What is the monthly trend of network node maintenance activities performed?\n")
    f.write("\n")
    f.write("=== DOCUMENT QUESTIONS (AI Search) ===\n")
    f.write("1. According to the Network Operations Policy, what is the maximum time allowed for ticket resolution?\n")
    f.write("2. What are the required safety procedures technicians must follow during field operations?\n")
    f.write("3. Which communication channels are specified for notifying customers about outages in the Outage Management Guidelines?\n")
    f.write("4. How often must network nodes undergo scheduled maintenance as described in the Maintenance Scheduling and Standards?\n")
    f.write("5. What penalties apply if SLA response time commitments are not met, according to the SLA Policies?\n")
    f.write("\n")
    f.write("=== COMBINED INSIGHT QUESTIONS ===\n")
    f.write("1. Are any outage durations exceeding the limits set in the Outage Duration Thresholds of the Network Operations Policy?\n")
    f.write("2. Which work orders have durations longer than allowed by the Work Order Duration section in the Technician Work Order Procedures?\n")
    f.write("3. Do any tickets have response times that violate the Response Time Commitments stated in the SLA Policies?\n")
    f.write("4. Which network nodes have not received maintenance within the 90-day period required by the Maintenance Scheduling and Standards?\n")
    f.write("5. Are there technicians whose quality inspection pass rates fall below the minimum threshold described in the Quality Assurance Manual?\n")

print("Data generation, config creation, PDFs, and sample questions complete.")