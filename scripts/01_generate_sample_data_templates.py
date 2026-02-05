"""
01 - Generate Sample Data for Industry Scenario
Generates CSV files, PDF documents, and ontology configuration for testing.

Usage:
    python 01_generate_sample_data.py [--scenario <SCENARIO>] [--size small|medium|large]

Scenarios:
    1. retail        - E-commerce products and customer orders (default)
    2. manufacturing - Production lines, equipment, and quality metrics
    3. saas          - Software subscriptions and usage analytics
    4. supply_chain  - Suppliers, purchase orders, and inventory
    5. real_estate   - Property listings and agent performance

Output:
    - CSV files for structured data (for Fabric Ontology)
    - PDF files for unstructured data (for AI Search)
    - ontology_config.json (for script 02)
    - sample_questions.txt (for testing)
"""

import argparse
import os
import json
import random
from datetime import datetime, timedelta

# PDF generation
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    print("Note: fpdf2 not installed. Run 'pip install fpdf2' to generate PDF files.")

# ============================================================================
# Parse Arguments
# ============================================================================

p = argparse.ArgumentParser(description="Generate sample data for industry scenario")
p.add_argument("--scenario", default="retail", choices=["retail", "manufacturing", "saas", "supply_chain", "real_estate"],
               help="Industry scenario (default: retail)")
p.add_argument("--size", default="small", choices=["small", "medium", "large"],
               help="Data size: small=~20 rows, medium=~100 rows, large=~500 rows")
args = p.parse_args()

scenario = args.scenario
size = args.size

# Size configuration
SIZE_CONFIG = {
    "small": {"primary": 16, "secondary": 40},      # ~50 mins lab
    "medium": {"primary": 50, "secondary": 200},    # Extended lab
    "large": {"primary": 200, "secondary": 1000}    # Full demo
}
config = SIZE_CONFIG[size]

# Output directories
script_dir = os.path.dirname(os.path.abspath(__file__))
base_data_dir = os.path.join(script_dir, "..", "data")
os.makedirs(base_data_dir, exist_ok=True)

# Create timestamped folder to preserve previous runs
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
data_dir = os.path.join(base_data_dir, f"{timestamp}_{scenario}")

# Create subfolders for organized structure
config_dir = os.path.join(data_dir, "config")
tables_dir = os.path.join(data_dir, "tables")
docs_dir = os.path.join(data_dir, "documents")
os.makedirs(config_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)
os.makedirs(docs_dir, exist_ok=True)

print(f"\n{'='*60}")
print(f"Generating {size.upper()} sample data for: {scenario.upper()}")
print(f"{'='*60}")

# ============================================================================
# Scenario Definitions
# ============================================================================

SCENARIOS = {
    "retail": {
        "name": "E-Commerce",
        "description": "Online store with products, customer orders, and revenue analytics",
        "tables": {
            "products": {
                "columns": ["productId", "productName", "category", "brand", "unitPrice", "stockLevel", "reorderPoint"],
                "types": {"productId": "String", "productName": "String", "category": "String", "brand": "String", "unitPrice": "Double", "stockLevel": "BigInt", "reorderPoint": "BigInt"},
                "key": "productId"
            },
            "orders": {
                "columns": ["orderId", "productId", "customerId", "quantity", "totalAmount", "orderDate", "region", "channel"],
                "types": {"orderId": "String", "productId": "String", "customerId": "String", "quantity": "BigInt", "totalAmount": "Double", "orderDate": "String", "region": "String", "channel": "String"},
                "key": "orderId"
            }
        },
        "relationships": [
            {"name": "contains_product", "from": "orders", "to": "products", "fromKey": "productId", "toKey": "productId"}
        ],
        "data_generator": "generate_retail_data"
    },
    "manufacturing": {
        "name": "Manufacturing",
        "description": "Production lines, equipment performance, and quality metrics",
        "tables": {
            "equipment": {
                "columns": ["equipmentId", "equipmentName", "productionLine", "manufacturer", "installDate", "status", "efficiency"],
                "types": {"equipmentId": "String", "equipmentName": "String", "productionLine": "String", "manufacturer": "String", "installDate": "String", "status": "String", "efficiency": "Double"},
                "key": "equipmentId"
            },
            "production_runs": {
                "columns": ["runId", "equipmentId", "productCode", "unitsProduced", "defectCount", "runDate", "shift", "operatorId"],
                "types": {"runId": "String", "equipmentId": "String", "productCode": "String", "unitsProduced": "BigInt", "defectCount": "BigInt", "runDate": "String", "shift": "String", "operatorId": "String"},
                "key": "runId"
            }
        },
        "relationships": [
            {"name": "uses_equipment", "from": "production_runs", "to": "equipment", "fromKey": "equipmentId", "toKey": "equipmentId"}
        ],
        "data_generator": "generate_manufacturing_data"
    },
    "saas": {
        "name": "SaaS Analytics",
        "description": "Software subscriptions, customer usage, and revenue metrics",
        "tables": {
            "customers": {
                "columns": ["customerId", "companyName", "industry", "plan", "mrr", "startDate", "accountManager", "healthScore"],
                "types": {"customerId": "String", "companyName": "String", "industry": "String", "plan": "String", "mrr": "Double", "startDate": "String", "accountManager": "String", "healthScore": "BigInt"},
                "key": "customerId"
            },
            "usage_events": {
                "columns": ["eventId", "customerId", "feature", "eventCount", "eventDate", "userCount", "sessionMinutes"],
                "types": {"eventId": "String", "customerId": "String", "feature": "String", "eventCount": "BigInt", "eventDate": "String", "userCount": "BigInt", "sessionMinutes": "BigInt"},
                "key": "eventId"
            }
        },
        "relationships": [
            {"name": "by_customer", "from": "usage_events", "to": "customers", "fromKey": "customerId", "toKey": "customerId"}
        ],
        "data_generator": "generate_saas_data"
    },
    "supply_chain": {
        "name": "Supply Chain",
        "description": "Suppliers, purchase orders, and inventory management",
        "tables": {
            "suppliers": {
                "columns": ["supplierId", "supplierName", "country", "category", "rating", "leadTimeDays", "paymentTerms"],
                "types": {"supplierId": "String", "supplierName": "String", "country": "String", "category": "String", "rating": "Double", "leadTimeDays": "BigInt", "paymentTerms": "String"},
                "key": "supplierId"
            },
            "purchase_orders": {
                "columns": ["poNumber", "supplierId", "itemDescription", "quantity", "unitCost", "totalCost", "orderDate", "status"],
                "types": {"poNumber": "String", "supplierId": "String", "itemDescription": "String", "quantity": "BigInt", "unitCost": "Double", "totalCost": "Double", "orderDate": "String", "status": "String"},
                "key": "poNumber"
            }
        },
        "relationships": [
            {"name": "from_supplier", "from": "purchase_orders", "to": "suppliers", "fromKey": "supplierId", "toKey": "supplierId"}
        ],
        "data_generator": "generate_supply_chain_data"
    },
    "real_estate": {
        "name": "Real Estate",
        "description": "Property listings, sales performance, and market analytics",
        "tables": {
            "properties": {
                "columns": ["propertyId", "address", "city", "propertyType", "bedrooms", "squareFeet", "listPrice", "status"],
                "types": {"propertyId": "String", "address": "String", "city": "String", "propertyType": "String", "bedrooms": "BigInt", "squareFeet": "BigInt", "listPrice": "Double", "status": "String"},
                "key": "propertyId"
            },
            "transactions": {
                "columns": ["transactionId", "propertyId", "agentId", "salePrice", "saleDate", "daysOnMarket", "buyerType"],
                "types": {"transactionId": "String", "propertyId": "String", "agentId": "String", "salePrice": "Double", "saleDate": "String", "daysOnMarket": "BigInt", "buyerType": "String"},
                "key": "transactionId"
            }
        },
        "relationships": [
            {"name": "for_property", "from": "transactions", "to": "properties", "fromKey": "propertyId", "toKey": "propertyId"}
        ],
        "data_generator": "generate_real_estate_data"
    }
}

# ============================================================================
# Data Generators
# ============================================================================

def generate_retail_data(config):
    """Generate e-commerce products and customer orders"""
    # Realistic product data
    product_catalog = [
        ("Wireless Noise-Canceling Headphones", "Electronics", "SoundMax"),
        ("4K Ultra HD Smart TV 55-inch", "Electronics", "ViewTech"),
        ("Portable Bluetooth Speaker", "Electronics", "AudioWave"),
        ("Smartwatch Pro Series", "Electronics", "TechFit"),
        ("Laptop Stand Adjustable", "Electronics", "ErgoDesk"),
        ("Organic Cotton T-Shirt", "Apparel", "EcoWear"),
        ("Running Shoes Performance", "Apparel", "SprintPro"),
        ("Waterproof Hiking Jacket", "Apparel", "TrailMaster"),
        ("Premium Denim Jeans", "Apparel", "UrbanStyle"),
        ("Merino Wool Sweater", "Apparel", "NordicKnit"),
        ("Stainless Steel Cookware Set", "Home & Kitchen", "ChefElite"),
        ("Robot Vacuum Cleaner", "Home & Kitchen", "CleanBot"),
        ("Air Purifier HEPA Filter", "Home & Kitchen", "PureAir"),
        ("Espresso Machine Premium", "Home & Kitchen", "BrewMaster"),
        ("Memory Foam Mattress Queen", "Home & Kitchen", "DreamRest"),
        ("Yoga Mat Premium", "Sports", "ZenFlex"),
        ("Adjustable Dumbbell Set", "Sports", "PowerLift"),
        ("Mountain Bike 27-Speed", "Sports", "TrailRider"),
        ("Tennis Racket Professional", "Sports", "CourtPro"),
        ("Camping Tent 4-Person", "Sports", "OutdoorLife"),
    ]
    
    regions = ["North America", "Europe", "Asia Pacific", "Latin America"]
    channels = ["Website", "Mobile App", "Marketplace", "Social Commerce"]
    
    products = []
    for i in range(min(config["primary"], len(product_catalog))):
        name, category, brand = product_catalog[i]
        products.append({
            "productId": f"SKU{i+1:05d}",
            "productName": name,
            "category": category,
            "brand": brand,
            "unitPrice": round(random.uniform(29.99, 1299.99), 2),
            "stockLevel": random.randint(50, 500),
            "reorderPoint": random.randint(20, 100)
        })
    
    orders = []
    for i in range(config["secondary"]):
        prod = random.choice(products)
        qty = random.randint(1, 5)
        orders.append({
            "orderId": f"ORD{i+1:06d}",
            "productId": prod["productId"],
            "customerId": f"CUST{random.randint(1, config['primary']*2):05d}",
            "quantity": qty,
            "totalAmount": round(prod["unitPrice"] * qty, 2),
            "orderDate": (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d"),
            "region": random.choice(regions),
            "channel": random.choice(channels)
        })
    
    return {"products": products, "orders": orders}

def generate_manufacturing_data(config):
    """Generate manufacturing equipment and production data"""
    equipment_types = [
        ("CNC Milling Machine", "Fanuc"),
        ("Laser Cutting System", "Trumpf"),
        ("Injection Molding Press", "Arburg"),
        ("Assembly Robot Arm", "KUKA"),
        ("Quality Inspection Station", "Keyence"),
        ("Conveyor System", "Dorner"),
        ("Packaging Machine", "Bosch"),
        ("3D Printer Industrial", "Stratasys"),
        ("Welding Robot", "ABB"),
        ("Paint Spray Booth", "Graco"),
    ]
    
    production_lines = ["Line A - Electronics", "Line B - Automotive", "Line C - Consumer Goods", "Line D - Aerospace"]
    shifts = ["Morning (6AM-2PM)", "Afternoon (2PM-10PM)", "Night (10PM-6AM)"]
    statuses = ["Operational", "Operational", "Operational", "Maintenance", "Idle"]
    product_codes = ["PROD-A100", "PROD-B200", "PROD-C300", "PROD-D400", "PROD-E500"]
    
    equipment = []
    for i in range(min(config["primary"], len(equipment_types) * 2)):
        eq_name, manufacturer = equipment_types[i % len(equipment_types)]
        equipment.append({
            "equipmentId": f"EQ{i+1:04d}",
            "equipmentName": f"{eq_name} #{i//len(equipment_types)+1}",
            "productionLine": random.choice(production_lines),
            "manufacturer": manufacturer,
            "installDate": (datetime.now() - timedelta(days=random.randint(365, 2000))).strftime("%Y-%m-%d"),
            "status": random.choice(statuses),
            "efficiency": round(random.uniform(0.75, 0.98), 2)
        })
    
    production_runs = []
    for i in range(config["secondary"]):
        eq = random.choice(equipment)
        units = random.randint(100, 1000)
        production_runs.append({
            "runId": f"RUN{i+1:06d}",
            "equipmentId": eq["equipmentId"],
            "productCode": random.choice(product_codes),
            "unitsProduced": units,
            "defectCount": random.randint(0, int(units * 0.05)),  # 0-5% defect rate
            "runDate": (datetime.now() - timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d"),
            "shift": random.choice(shifts),
            "operatorId": f"OP{random.randint(1, 20):03d}"
        })
    
    return {"equipment": equipment, "production_runs": production_runs}

def generate_saas_data(config):
    """Generate SaaS customer and usage data"""
    company_prefixes = ["Tech", "Data", "Cloud", "Smart", "Digital", "Global", "Prime", "Next", "Core", "Alpha"]
    company_suffixes = ["Solutions", "Systems", "Labs", "Analytics", "Dynamics", "Works", "Logic", "Innovations", "Hub", "Networks"]
    industries = ["Technology", "Financial Services", "Retail", "Manufacturing", "Media", "Professional Services"]
    plans = ["Starter", "Professional", "Enterprise", "Enterprise Plus"]
    plan_mrr = {"Starter": (99, 299), "Professional": (499, 999), "Enterprise": (1999, 4999), "Enterprise Plus": (5999, 14999)}
    account_managers = ["Sarah Chen", "Michael Rodriguez", "Emily Watson", "James Kim", "Lisa Thompson"]
    features = ["Dashboard", "Reports", "API Integration", "User Management", "Automation", "Analytics", "Export", "Collaboration"]
    
    customers = []
    for i in range(config["primary"]):
        plan = random.choice(plans)
        mrr_range = plan_mrr[plan]
        customers.append({
            "customerId": f"ACCT{i+1:05d}",
            "companyName": f"{random.choice(company_prefixes)} {random.choice(company_suffixes)}",
            "industry": random.choice(industries),
            "plan": plan,
            "mrr": round(random.uniform(*mrr_range), 2),
            "startDate": (datetime.now() - timedelta(days=random.randint(30, 730))).strftime("%Y-%m-%d"),
            "accountManager": random.choice(account_managers),
            "healthScore": random.randint(40, 100)
        })
    
    usage_events = []
    for i in range(config["secondary"]):
        cust = random.choice(customers)
        usage_events.append({
            "eventId": f"EVT{i+1:07d}",
            "customerId": cust["customerId"],
            "feature": random.choice(features),
            "eventCount": random.randint(10, 500),
            "eventDate": (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
            "userCount": random.randint(1, 50),
            "sessionMinutes": random.randint(5, 180)
        })
    
    return {"customers": customers, "usage_events": usage_events}

def generate_supply_chain_data(config):
    """Generate supply chain suppliers and purchase orders"""
    supplier_data = [
        ("Precision Components Ltd", "Germany", "Electronics"),
        ("Pacific Materials Co", "China", "Raw Materials"),
        ("Nordic Parts Supply", "Sweden", "Mechanical"),
        ("Delta Manufacturing", "USA", "Electronics"),
        ("Eastern Logistics Group", "Japan", "Packaging"),
        ("Global Steel Works", "India", "Raw Materials"),
        ("EuroTech Industries", "France", "Mechanical"),
        ("Atlas Plastics", "Mexico", "Packaging"),
        ("Summit Metals Inc", "Canada", "Raw Materials"),
        ("Coastal Components", "Taiwan", "Electronics"),
    ]
    
    payment_terms = ["Net 30", "Net 45", "Net 60", "Net 90", "2/10 Net 30"]
    statuses = ["Delivered", "Delivered", "In Transit", "Processing", "Pending"]
    items = [
        "Microprocessor Units", "Aluminum Sheets", "Hydraulic Pumps", "Circuit Boards",
        "Plastic Pellets", "Steel Rods", "Servo Motors", "Cardboard Boxes",
        "Copper Wire", "Ball Bearings", "LCD Displays", "Rubber Seals"
    ]
    
    suppliers = []
    for i in range(min(config["primary"], len(supplier_data))):
        name, country, category = supplier_data[i]
        suppliers.append({
            "supplierId": f"SUP{i+1:04d}",
            "supplierName": name,
            "country": country,
            "category": category,
            "rating": round(random.uniform(3.5, 5.0), 1),
            "leadTimeDays": random.randint(7, 45),
            "paymentTerms": random.choice(payment_terms)
        })
    
    purchase_orders = []
    for i in range(config["secondary"]):
        sup = random.choice(suppliers)
        qty = random.randint(100, 5000)
        unit_cost = round(random.uniform(5, 500), 2)
        purchase_orders.append({
            "poNumber": f"PO{i+1:06d}",
            "supplierId": sup["supplierId"],
            "itemDescription": random.choice(items),
            "quantity": qty,
            "unitCost": unit_cost,
            "totalCost": round(qty * unit_cost, 2),
            "orderDate": (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d"),
            "status": random.choice(statuses)
        })
    
    return {"suppliers": suppliers, "purchase_orders": purchase_orders}

def generate_real_estate_data(config):
    """Generate real estate listings and transactions"""
    cities = ["Austin", "Seattle", "Denver", "Nashville", "Phoenix", "Raleigh", "Portland", "Charlotte"]
    property_types = ["Single Family", "Condo", "Townhouse", "Multi-Family"]
    statuses = ["Active", "Active", "Pending", "Sold", "Sold"]
    buyer_types = ["First-Time Buyer", "Investor", "Relocating", "Upgrading", "Downsizing"]
    agents = ["Jennifer Adams", "Robert Martinez", "Amanda Wilson", "Christopher Lee", "Michelle Brown"]
    
    street_names = ["Oak", "Maple", "Cedar", "Pine", "Elm", "Birch", "Willow", "Cypress"]
    street_types = ["Street", "Avenue", "Drive", "Lane", "Court", "Place", "Way", "Boulevard"]
    
    properties = []
    for i in range(config["primary"]):
        city = random.choice(cities)
        prop_type = random.choice(property_types)
        sqft = random.randint(800, 4500)
        bedrooms = random.randint(1, 5)
        properties.append({
            "propertyId": f"MLS{i+1:06d}",
            "address": f"{random.randint(100, 9999)} {random.choice(street_names)} {random.choice(street_types)}",
            "city": city,
            "propertyType": prop_type,
            "bedrooms": bedrooms,
            "squareFeet": sqft,
            "listPrice": round(random.uniform(250000, 1500000), -3),  # Round to nearest 1000
            "status": random.choice(statuses)
        })
    
    transactions = []
    sold_properties = [p for p in properties if p["status"] == "Sold"]
    if not sold_properties:
        sold_properties = properties[:len(properties)//3]
    
    for i in range(min(config["secondary"], len(sold_properties) * 2)):
        prop = random.choice(sold_properties)
        list_price = prop["listPrice"]
        sale_variance = random.uniform(-0.05, 0.03)  # -5% to +3% of list
        transactions.append({
            "transactionId": f"TXN{i+1:06d}",
            "propertyId": prop["propertyId"],
            "agentId": f"AGT{agents.index(random.choice(agents))+1:03d}",
            "salePrice": round(list_price * (1 + sale_variance), -2),
            "saleDate": (datetime.now() - timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
            "daysOnMarket": random.randint(7, 120),
            "buyerType": random.choice(buyer_types)
        })
    
    return {"properties": properties, "transactions": transactions}

# ============================================================================
# PDF Document Definitions (Unstructured Data for AI Search)
# ============================================================================

PDF_DOCUMENTS = {
    "retail": [
        {
            "filename": "return_policy.pdf",
            "title": "E-Commerce Return and Refund Policy",
            "sections": [
                ("Return Window", "All products can be returned within 30 days of delivery. Electronics have a 15-day return window. Items must be in original condition with all packaging and accessories. Proof of purchase is required for all returns."),
                ("Refund Process", "Refunds are processed within 5-7 business days after receiving the returned item. Original payment method will be credited. Shipping costs are non-refundable unless the return is due to our error or a defective product."),
                ("Exchange Policy", "Exchanges are subject to product availability. If the desired item is unavailable, a full refund will be issued. Free exchange shipping on defective items. Size exchanges in Apparel are always free."),
                ("Non-Returnable Items", "Personalized items cannot be returned. Final sale items marked at checkout. Opened software and digital products. Items damaged through misuse or normal wear."),
                ("International Returns", "International customers are responsible for return shipping costs. Customs duties and taxes are non-refundable. Contact customer service for return authorization before shipping internationally."),
            ]
        },
        {
            "filename": "shipping_guide.pdf",
            "title": "Shipping and Delivery Guide",
            "sections": [
                ("Shipping Options", "Standard Shipping (5-7 business days) is free on orders over $50. Express Shipping (2-3 days) available for $12.99. Next-Day Delivery available for $24.99 on orders placed before 2 PM EST."),
                ("Regional Coverage", "North America: Full coverage with all shipping options. Europe: Standard and Express available, 7-14 business days. Asia Pacific: Standard shipping 10-21 business days. Latin America: Available to select countries."),
                ("Order Tracking", "Tracking numbers sent via email within 24 hours of shipment. Real-time updates available through our website and mobile app. SMS notifications available for Express and Next-Day orders."),
                ("Large Item Delivery", "Items over 50 lbs require special handling. White glove delivery available for furniture and large electronics. Appointment scheduling required for large item delivery."),
                ("Holiday Shipping", "Extended cutoff times during peak season. Holiday shipping surcharges may apply. Check website for guaranteed delivery dates during November-December."),
            ]
        },
        {
            "filename": "loyalty_rewards.pdf",
            "title": "Rewards Program Terms and Benefits",
            "sections": [
                ("Earning Points", "Earn 1 point per dollar spent on all purchases. Bonus points during promotional events. Double points on Electronics and Sports categories. Points are credited within 48 hours of delivery."),
                ("Membership Tiers", "Silver (0-1000 points): 5% off first purchase, birthday reward. Gold (1001-5000 points): 10% off all purchases, free Express shipping. Platinum (5001+ points): 15% off, free Next-Day shipping, early access to sales."),
                ("Redeeming Rewards", "500 points = $5 reward. Rewards can be combined with sales and promotions. Points expire 12 months after earning. Rewards expire 60 days after issuance."),
                ("Exclusive Benefits", "Members-only flash sales every month. Early access to new product launches. Exclusive member pricing on select items. Priority customer service line."),
                ("Partner Benefits", "Earn points at partner restaurants and hotels. Transfer points to airline miles programs. Special financing through partner credit card."),
            ]
        },
    ],
    "manufacturing": [
        {
            "filename": "quality_standards.pdf",
            "title": "Quality Control Standards and Procedures",
            "sections": [
                ("Quality Philosophy", "Our commitment to zero defects drives continuous improvement across all production lines. We adhere to ISO 9001:2015 standards and conduct regular third-party audits. Quality is everyone's responsibility."),
                ("Inspection Protocols", "First Article Inspection (FAI) required for all new production runs. In-process inspection at critical control points. Final inspection before packaging with statistical sampling. 100% inspection for aerospace and automotive components."),
                ("Defect Classification", "Critical defects: Safety hazard or non-functional - 0% acceptance rate. Major defects: Reduced usability - max 1% acceptance. Minor defects: Cosmetic issues - max 2.5% acceptance."),
                ("Equipment Calibration", "All measurement equipment calibrated quarterly. Calibration records maintained for 7 years. Out-of-calibration equipment immediately removed from service. Traceability to NIST standards required."),
                ("Corrective Actions", "8D methodology for problem solving. Root cause analysis required within 48 hours. Corrective actions verified within 30 days. Lessons learned shared across all production lines."),
            ]
        },
        {
            "filename": "maintenance_procedures.pdf",
            "title": "Equipment Maintenance Manual",
            "sections": [
                ("Preventive Maintenance", "Daily visual inspections by operators. Weekly lubrication and cleaning schedules. Monthly comprehensive inspections by maintenance team. Annual overhauls for critical equipment."),
                ("Predictive Maintenance", "Vibration analysis on rotating equipment quarterly. Thermal imaging for electrical systems monthly. Oil analysis for hydraulic systems every 500 hours. Ultrasonic testing for early failure detection."),
                ("Breakdown Response", "Immediate notification to maintenance team and shift supervisor. Safety lockout/tagout procedures must be followed. Root cause analysis within 24 hours of repair. Update maintenance records within 4 hours of completion."),
                ("Spare Parts Management", "Critical spares inventory maintained on-site. Minimum stock levels reviewed monthly. Vendor lead times tracked and updated quarterly. Emergency supplier agreements for critical components."),
                ("Efficiency Targets", "Overall Equipment Effectiveness (OEE) target: 85%. Planned downtime maximum: 5% of operating hours. Unplanned downtime target: less than 2%. Mean Time Between Failures (MTBF) tracked by equipment type."),
            ]
        },
        {
            "filename": "safety_guidelines.pdf",
            "title": "Manufacturing Safety Guidelines",
            "sections": [
                ("Personal Protective Equipment", "Safety glasses required in all production areas. Steel-toed boots mandatory. Hearing protection required where noise exceeds 85 dB. Cut-resistant gloves for material handling. High-visibility vests in forklift zones."),
                ("Machine Safety", "Guards must be in place before operation. Lockout/Tagout for all maintenance activities. Emergency stop buttons tested weekly. No loose clothing or jewelry near rotating equipment."),
                ("Material Handling", "Maximum lift weight: 50 lbs without assistance. Powered equipment required for loads over 50 lbs. Proper lifting technique training required annually. Clear pathways maintained at all times."),
                ("Emergency Procedures", "Emergency exits clearly marked and unobstructed. Fire extinguisher locations posted. Evacuation drills conducted quarterly. First aid stations in each production area. Emergency contact numbers posted prominently."),
                ("Incident Reporting", "All incidents reported within 1 hour. Near-miss reporting encouraged and anonymous. Safety committee reviews all incidents weekly. Corrective actions tracked to completion."),
            ]
        },
    ],
    "saas": [
        {
            "filename": "service_level_agreement.pdf",
            "title": "Service Level Agreement (SLA)",
            "sections": [
                ("Uptime Commitment", "We guarantee 99.9% uptime for all paid plans. Scheduled maintenance windows: Sundays 2-4 AM EST with 72-hour notice. Uptime calculated monthly excluding scheduled maintenance. Status page available at status.ourplatform.com."),
                ("Support Response Times", "Enterprise Plus: 15-minute response, 24/7 phone support. Enterprise: 1-hour response, business hours phone. Professional: 4-hour response, email and chat. Starter: 24-hour response, email only."),
                ("Service Credits", "99.0-99.9% uptime: 10% credit. 95.0-99.0% uptime: 25% credit. Below 95%: 50% credit. Credits applied to next invoice automatically. Maximum credit: one month's fees."),
                ("Data Protection", "Daily automated backups retained for 30 days. Point-in-time recovery available for Enterprise plans. Data encrypted at rest (AES-256) and in transit (TLS 1.3). Annual SOC 2 Type II audit conducted."),
                ("Support Escalation", "Level 1: Technical support team. Level 2: Senior engineers (4-hour escalation). Level 3: Engineering leadership (8-hour escalation). Executive escalation available for Enterprise Plus customers."),
            ]
        },
        {
            "filename": "api_documentation.pdf",
            "title": "API Integration Guide",
            "sections": [
                ("Authentication", "API uses OAuth 2.0 for authentication. Access tokens expire after 1 hour. Refresh tokens valid for 30 days. API keys available for server-to-server integration. Rate limits: Starter 100/min, Professional 500/min, Enterprise 2000/min."),
                ("Core Endpoints", "GET /api/v2/users - List all users with pagination. POST /api/v2/data - Submit data with JSON payload. GET /api/v2/reports - Generate reports with date range filters. DELETE /api/v2/records/{id} - Soft delete with 30-day recovery."),
                ("Webhooks", "Real-time event notifications to your endpoint. Events: user.created, data.updated, report.completed. Retry logic: 3 attempts with exponential backoff. Webhook signatures for security verification."),
                ("Best Practices", "Use pagination for large data sets. Implement exponential backoff for rate limits. Cache responses where appropriate. Use bulk endpoints for batch operations."),
                ("SDK Support", "Official SDKs: Python, JavaScript, Java, .NET. Community SDKs: Ruby, Go, PHP. Postman collection available for testing. Sandbox environment for development."),
            ]
        },
        {
            "filename": "customer_success_playbook.pdf",
            "title": "Customer Success Playbook",
            "sections": [
                ("Onboarding Journey", "Week 1: Kickoff call, account setup, user provisioning. Week 2-3: Training sessions on core features. Week 4: First value milestone checkpoint. Day 30: Business review and adoption metrics. Day 60: Advanced feature training."),
                ("Health Score Methodology", "Product usage (40%): DAU/MAU ratio, feature adoption. Engagement (30%): Support tickets, NPS responses, training completion. Financial (30%): Payment history, expansion conversations, contract terms."),
                ("At-Risk Playbook", "Health Score 40-60: Proactive outreach within 48 hours. Health Score below 40: Executive escalation and recovery plan. Key indicators: Declining logins, support ticket sentiment, missed meetings."),
                ("Expansion Signals", "High feature utilization approaching plan limits. Multiple users requesting advanced features. Positive feedback in support interactions. Growing user count within account."),
                ("Renewal Process", "90 days out: Renewal review meeting scheduled. 60 days: Proposal delivered with usage summary. 30 days: Contract negotiation finalized. Day 0: Renewal celebration and next-year goals."),
            ]
        },
    ],
    "supply_chain": [
        {
            "filename": "supplier_handbook.pdf",
            "title": "Supplier Requirements Handbook",
            "sections": [
                ("Quality Requirements", "ISO 9001 certification required for Tier 1 suppliers. First Article Approval required for all new parts. Certificate of Conformance with each shipment. Annual quality audits conducted by our team."),
                ("Delivery Standards", "On-time delivery target: 98%. Delivery windows: +/- 2 days of scheduled date. Advance Ship Notice (ASN) required 24 hours before shipment. Packaging specifications must be followed exactly."),
                ("Documentation", "Material Test Reports required for raw materials. Country of origin documentation for all shipments. Hazardous materials require SDS sheets. Invoice must match PO exactly for payment processing."),
                ("Communication Protocols", "Respond to inquiries within 24 business hours. Capacity constraints communicated 30 days in advance. Quality issues reported within 4 hours of discovery. Single point of contact assigned for each account."),
                ("Sustainability Standards", "Environmental compliance certifications required. Conflict minerals reporting for applicable materials. Packaging recyclability requirements. Carbon footprint reporting encouraged."),
            ]
        },
        {
            "filename": "inventory_policy.pdf",
            "title": "Inventory Management Policy",
            "sections": [
                ("Stock Levels", "Safety stock: 2 weeks supply for A-items. Reorder point calculated from lead time + safety stock. Maximum stock level: 6 weeks supply. Dead stock review conducted quarterly."),
                ("ABC Classification", "A-items (top 20% by value): Daily monitoring. B-items (next 30%): Weekly review. C-items (remaining 50%): Monthly review. Classification updated annually."),
                ("Counting Procedures", "A-items: Cycle count monthly. B-items: Cycle count quarterly. C-items: Annual physical inventory. Discrepancies over 2% require root cause analysis."),
                ("Obsolescence Management", "Slow-moving items flagged after 90 days no movement. Review board meets monthly for disposition. Options: Return to supplier, discount sale, scrap. Reserve established for excess and obsolete."),
                ("KPIs and Targets", "Inventory turns target: 8x annually. Fill rate target: 98.5%. Carrying cost target: 20% of inventory value. Accuracy target: 99% after cycle counts."),
            ]
        },
        {
            "filename": "procurement_guidelines.pdf",
            "title": "Procurement Process Guidelines",
            "sections": [
                ("Purchase Authority", "Under $1,000: Department manager approval. $1,000-$10,000: Director approval. $10,000-$50,000: VP approval. Over $50,000: Executive committee approval."),
                ("Vendor Selection", "Minimum 3 quotes for purchases over $5,000. Sole source justification required and documented. New vendors require qualification process. Preferred vendor list maintained and reviewed quarterly."),
                ("PO Process", "Requisition submitted through procurement system. Approvals routed automatically based on amount. PO issued within 24 hours of final approval. Changes require PO amendment with approvals."),
                ("Payment Terms", "Standard terms: Net 30. Early payment discount: 2% Net 10 evaluated monthly. Payment requires 3-way match: PO, receipt, invoice. Disputes escalated to procurement manager."),
                ("Contract Management", "Multi-year agreements reviewed annually. Price adjustments capped per contract terms. Performance metrics tracked quarterly. Renewal process begins 90 days before expiration."),
            ]
        },
    ],
    "real_estate": [
        {
            "filename": "market_analysis_guide.pdf",
            "title": "Real Estate Market Analysis Guide",
            "sections": [
                ("Comparable Analysis", "Select 3-5 comparable properties within 1 mile. Adjustments made for square footage, bedrooms, lot size. Recent sales (90 days) weighted more heavily. Consider days on market as demand indicator."),
                ("Pricing Strategy", "Competitive pricing: 2-5% below average for quick sale. Market pricing: At comparable average for balanced approach. Premium pricing: 5-10% above for unique features. Price reductions: Consider after 21 days without offers."),
                ("Market Indicators", "Absorption rate: Months of inventory at current pace. Price per square foot trends. Days on market averages. List-to-sale price ratios."),
                ("Seasonal Patterns", "Spring (March-May): Peak buying season, highest prices. Summer (June-August): Family-friendly moves, competitive. Fall (September-November): Serious buyers, negotiable. Winter (December-February): Lower volume, motivated parties."),
                ("Investment Analysis", "Cap rate benchmarks by property type and market. Cash-on-cash return expectations. 1% rule for rental property screening. Pro forma templates for multi-family evaluation."),
            ]
        },
        {
            "filename": "listing_agreement.pdf",
            "title": "Listing Agreement Terms and Conditions",
            "sections": [
                ("Agreement Duration", "Standard listing period: 6 months. Exclusive right to sell during agreement period. 30-day notice required for cancellation. Automatic renewal provisions if not cancelled."),
                ("Commission Structure", "Standard commission: 6% of sale price. Commission split between listing and buyer agents. Reduced commission for dual agency situations. Commission earned at closing."),
                ("Marketing Commitment", "Professional photography included. MLS listing within 48 hours of signing. Virtual tour and floor plan. Social media and digital marketing. Open houses as agreed."),
                ("Seller Obligations", "Property must be available for showings with reasonable notice. Material defects must be disclosed. Cooperate with appraisal and inspection processes. Maintain property condition through closing."),
                ("Termination Clauses", "Mutual agreement to terminate. Breach by either party. Sale to exempted buyer if specified. Listing agent may withdraw for cause."),
            ]
        },
        {
            "filename": "closing_checklist.pdf",
            "title": "Transaction Closing Checklist",
            "sections": [
                ("Pre-Closing Tasks", "Title search and insurance commitment. Home inspection completed and negotiations resolved. Appraisal completed and value confirmed. Loan approval and final underwriting. Walk-through scheduled 24-48 hours before closing."),
                ("Required Documents", "Government-issued ID for all parties. Proof of homeowners insurance. Certified funds for closing costs. Power of attorney if applicable. Trust documents if purchasing in trust."),
                ("Closing Day", "Review closing disclosure (3 days before). Sign all documents (allow 1-2 hours). Fund transfer verification. Key exchange and possession. Recording of deed (same or next day)."),
                ("Post-Closing", "Deed recorded with county. Title policy issued within 30 days. Change of address and utilities. Property tax notification. Keep closing documents permanently."),
                ("Common Issues", "Last-minute loan conditions. Walk-through discrepancies. Wire fraud prevention verification. Document errors requiring correction. Funding delays."),
            ]
        },
    ],
}

def generate_pdf_documents(scenario, docs_dir):
    """Generate PDF documents for the given scenario"""
    if not FPDF_AVAILABLE:
        print("\n⚠️  Skipping PDF generation (fpdf2 not installed)")
        print("   Install with: pip install fpdf2")
        return []
    
    documents = PDF_DOCUMENTS.get(scenario, [])
    if not documents:
        return []
    
    generated_files = []
    
    for doc in documents:
        filepath = os.path.join(docs_dir, doc["filename"])
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Title
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 15, doc["title"], ln=True, align="C")
        pdf.ln(10)
        
        # Sections
        for section_title, section_content in doc["sections"]:
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, section_title, ln=True)
            
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, section_content)
            pdf.ln(5)
        
        pdf.output(filepath)
        generated_files.append(doc["filename"])
    
    return generated_files

# ============================================================================
# Generate Data
# ============================================================================

scenario_def = SCENARIOS[scenario]
generator = globals()[scenario_def["data_generator"]]
data = generator(config)

# Write CSV files
print(f"\nGenerating CSV files in: {tables_dir}")
for table_name, rows in data.items():
    csv_path = os.path.join(tables_dir, f"{table_name}.csv")
    columns = scenario_def["tables"][table_name]["columns"]
    
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(",".join(columns) + "\n")
        for row in rows:
            values = [str(row.get(col, "")) for col in columns]
            f.write(",".join(values) + "\n")
    
    print(f"  [OK] {table_name}.csv ({len(rows)} rows)")

# ============================================================================
# Generate Ontology Configuration
# ============================================================================

ontology_config = {
    "scenario": scenario,
    "name": scenario_def["name"],
    "description": scenario_def["description"],
    "tables": {},
    "relationships": scenario_def["relationships"]
}

for table_name, table_def in scenario_def["tables"].items():
    ontology_config["tables"][table_name] = {
        "columns": table_def["columns"],
        "types": table_def["types"],
        "key": table_def["key"],
        "source_table": table_name
    }

config_path = os.path.join(config_dir, "ontology_config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump(ontology_config, f, indent=2)

print(f"  [OK] config/ontology_config.json")

# ============================================================================
# Generate Sample Questions
# ============================================================================

SAMPLE_QUESTIONS = {
    "retail": [
        "What is the total revenue by product category?",
        "Which products are below their reorder point?",
        "Show me the top 5 best-selling products by quantity",
        "What is the average order value by sales channel?",
        "Which region has the highest total sales?",
        "How many orders were placed through the Mobile App?",
        "What is the revenue trend by month?",
        "Which brand has the highest average unit price?",
        "List products with low stock levels (under 100 units)",
        "What is the total quantity sold per product with product details?",
    ],
    "manufacturing": [
        "What is the overall defect rate across all production runs?",
        "Which equipment has the highest efficiency rating?",
        "Show defect counts by production line",
        "Which shift has the highest production output?",
        "List equipment currently under maintenance",
        "What is the average units produced per equipment?",
        "Which product codes have the highest defect rates?",
        "Show production trends by month",
        "Which operators have the most production runs?",
        "What is the total output by production line with equipment details?",
    ],
    "saas": [
        "What is the total MRR by subscription plan?",
        "Which customers have health scores below 50?",
        "Show the top 10 customers by monthly recurring revenue",
        "What is the average feature usage by industry?",
        "Which features are most used across all customers?",
        "List Enterprise customers with declining usage",
        "What is the customer count by account manager?",
        "Show usage trends for the Dashboard feature",
        "Which customers have the highest session minutes?",
        "What is the total user count by customer plan?",
    ],
    "supply_chain": [
        "What is the total spend by supplier country?",
        "Which suppliers have ratings below 4.0?",
        "Show the top 5 suppliers by total purchase order value",
        "What is the average lead time by supplier category?",
        "List purchase orders still in Processing status",
        "Which items have the highest total order quantities?",
        "What is the total cost by payment terms?",
        "Show orders by status with supplier details",
        "Which suppliers have the most purchase orders?",
        "What is the monthly procurement spend trend?",
    ],
    "real_estate": [
        "What is the average list price by city?",
        "Which properties have been on market longest?",
        "Show total sales volume by property type",
        "What is the average days on market by city?",
        "List properties with price above $1 million",
        "Which agents have the most transactions?",
        "What is the average sale price vs list price ratio?",
        "Show the distribution of buyer types",
        "Which cities have the highest average price per square foot?",
        "What is the total sales volume by month?",
    ],
}

questions_path = os.path.join(config_dir, "sample_questions.txt")
with open(questions_path, "w", encoding="utf-8") as f:
    f.write(f"Sample Questions for {scenario_def['name']} Scenario\n")
    f.write("="*50 + "\n\n")
    for q in SAMPLE_QUESTIONS[scenario]:
        f.write(f"- {q}\n")

print(f"  [OK] config/sample_questions.txt")

# ============================================================================
# Generate PDF Documents (Unstructured Data)
# ============================================================================

print(f"\nGenerating PDF documents in: {docs_dir}")
pdf_files = generate_pdf_documents(scenario, docs_dir)
for pdf_file in pdf_files:
    print(f"  [OK] {pdf_file}")

if not pdf_files:
    print("  (No PDFs generated - install reportlab: pip install reportlab)")

# ============================================================================
# Summary
# ============================================================================

# Store the data folder path for easy copy/paste
data_folder_path = os.path.abspath(data_dir)

print(f"\n{'='*60}")
print("Data Generation Complete!")
print(f"{'='*60}")
print(f"""
Scenario: {scenario_def['name']}
Size: {size} ({config['primary']} primary, {config['secondary']} secondary records)

Data folder created:
  {data_folder_path}

Contents:
  Structured Data (for Fabric Ontology):
    - CSV files for each table
    - ontology_config.json

  Unstructured Data (for AI Search):
    - {len(pdf_files)} PDF documents in documents/

  Testing:
    - sample_questions.txt

Next steps:
  # Setup Fabric (lakehouse + ontology)
  python scripts/02_create_fabric_items.py
  
  # Load data to Fabric
  python scripts/03_load_fabric_data.py
""")

# ============================================================================
# Update .env with data folder path
# ============================================================================

env_path = os.path.join(script_dir, "..", ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        env_content = f.read()
    
    # Update DATA_FOLDER line
    lines = env_content.split("\n")
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("DATA_FOLDER="):
            lines[i] = f"DATA_FOLDER={data_folder_path}"
            updated = True
            break
    
    if not updated:
        # Add it if not found
        lines.append(f"DATA_FOLDER={data_folder_path}")
    
    with open(env_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"Updated .env with DATA_FOLDER={data_folder_path}")
else:
    print(f"Note: .env not found. Set DATA_FOLDER={data_folder_path} manually.")

if not FPDF_AVAILABLE:
    print("""
To generate PDF files for AI Search:
  pip install fpdf2
  python 01_generate_sample_data.py --scenario {scenario}
""".format(scenario=scenario))


