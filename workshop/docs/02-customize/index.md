# Customize for your use case

This is where it gets exciting. Generate a complete working PoC tailored to your industry and use case in minutes.

## What you provide

Simply provide two inputs:

| Input | Description | Example |
|-------|-------------|---------|
| **Industry** | The business domain or vertical | Telecommunications, Retail, Manufacturing, Finance, Energy |
| **Use Case** | What the solution should help with | "Claims processing and policy management" |

!!! tip "Be descriptive"
    The more detail you provide in your use case, the better the generated content will match your scenario. For example:
    
    - ✓ "Property insurance with claims processing, policy management, and coverage verification"
    - ✗ "Insurance stuff"

## What gets generated

| Component | Generated Content |
|-----------|-------------------|
| **Documents** | Policies, procedures, FAQs specific to your industry |
| **Data** | Realistic CSV files with industry-appropriate entities |
| **Ontology** | Business rules and relationships for NL→SQL |
| **Sample Questions** | Questions to test the solution |

## Example Transformations

=== "Telecommunications"

    **Input:** "Network operations with outage tracking and trouble ticket management"
    
    | Generated | Description |
    |-----------|-------------|
    | `network_outages.csv` | Outage events, duration, impact level |
    | `trouble_tickets.csv` | Support tickets linked to outages |
    | `outage_management_policies.pdf` | Response procedures and SLAs |
    | `customer_service_policies.pdf` | Customer notification guidelines |
    
    **Sample Questions:**
    
    - "Which outages exceeded our maximum duration policy?"
    - "What are the escalation procedures for high-impact outages?"

=== "Retail"

    **Input:** "Fashion e-commerce with seasonal inventory and returns"
    
    | Generated | Description |
    |-----------|-------------|
    | `products.csv` | SKUs, categories, seasonal collections |
    | `orders.csv` | Customer orders with status |
    | `return_policy.pdf` | Return and exchange guidelines |
    | `shipping_guide.pdf` | Delivery options and timelines |
    
    **Sample Questions:**
    
    - "What's our return policy for sale items?"
    - "Which products from the spring collection have low stock?"

=== "Manufacturing"

    **Input:** "Automotive parts with quality control and suppliers"
    
    | Generated | Description |
    |-----------|-------------|
    | `equipment.csv` | Machines, maintenance schedules |
    | `suppliers.csv` | Vendor relationships, lead times |
    | `quality_standards.pdf` | QC procedures and thresholds |
    | `maintenance_guide.pdf` | Equipment maintenance protocols |
    
    **Sample Questions:**
    
    - "Which machines are overdue for maintenance?"
    - "What's our QC process for critical components?"

=== "Insurance"

    **Input:** "Property insurance with claims and policy management"
    
    | Generated | Description |
    |-----------|-------------|
    | `policies.csv` | Policy details, coverage, premiums |
    | `claims.csv` | Claim status, amounts, dates |
    | `claims_process.pdf` | How to file and process claims |
    | `coverage_guide.pdf` | Policy coverage explanations |
    
    **Sample Questions:**
    
    - "Which claims are approaching our SLA deadline?"
    - "What does our standard homeowner policy cover?"

=== "Finance"

    **Input:** "Regional bank with loans and compliance"
    
    | Generated | Description |
    |-----------|-------------|
    | `accounts.csv` | Customer accounts, balances |
    | `loans.csv` | Loan applications, status |
    | `lending_policy.pdf` | Approval criteria and rates |
    | `compliance_guide.pdf` | Regulatory requirements |
    
    **Sample Questions:**
    
    - "Which loan applications meet our approval criteria?"
    - "What are our compliance requirements for large transactions?"

=== "Energy"

    **Input:** "Power utility with grid monitoring and outage response"
    
    | Generated | Description |
    |-----------|-------------|
    | `substations.csv` | Grid infrastructure, capacity levels |
    | `outages.csv` | Power outages, affected areas, restoration times |
    | `safety_protocols.pdf` | Field crew safety procedures |
    | `emergency_response.pdf` | Outage escalation and communication |
    
    **Sample Questions:**
    
    - "Which substations are operating above 80% capacity?"
    - "What's our restoration priority for critical facilities?"

=== "Education"

    **Input:** "University with enrollment management and course scheduling"
    
    | Generated | Description |
    |-----------|-------------|
    | `students.csv` | Student records, enrollment status |
    | `courses.csv` | Course catalog, schedules, capacity |
    | `enrollment_policies.pdf` | Registration rules and deadlines |
    | `academic_handbook.pdf` | Academic standards and procedures |
    
    **Sample Questions:**
    
    - "Which courses are at risk of under-enrollment?"
    - "What are the prerequisites for advanced engineering courses?"

=== "Hospitality"

    **Input:** "Hotel chain with reservations and guest services"
    
    | Generated | Description |
    |-----------|-------------|
    | `reservations.csv` | Bookings, room types, guest details |
    | `rooms.csv` | Room inventory, status, amenities |
    | `guest_policies.pdf` | Check-in/out, cancellation rules |
    | `service_standards.pdf` | Guest experience guidelines |
    
    **Sample Questions:**
    
    - "Which rooms need turnover service for today's arrivals?"
    - "What's our policy for late checkout requests?"

=== "Logistics"

    **Input:** "Fleet management with delivery tracking and driver compliance"
    
    | Generated | Description |
    |-----------|-------------|
    | `vehicles.csv` | Fleet inventory, maintenance status |
    | `deliveries.csv` | Shipments, routes, delivery status |
    | `driver_policies.pdf` | Hours of service, safety requirements |
    | `routing_guidelines.pdf` | Route optimization procedures |
    
    **Sample Questions:**
    
    - "Which drivers are approaching hours-of-service limits?"
    - "What's our policy for delayed deliveries?"

!!! tip "The more specific, the better"
    The AI uses your description to generate appropriate entity names, realistic data relationships, industry-specific documents, and relevant sample questions.

---

[← Build solution](../01-deploy/04-run-scenario.md) | [Generate & Build →](02-generate.md)
