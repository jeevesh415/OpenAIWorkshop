#!/usr/bin/env python3
"""
Creates Cosmos DB database and containers for Contoso MCP service.
Populates with 250 random customers + 9 deterministic scenarios similar to create_db.py.

This script creates containers with:
- Vector embeddings for KnowledgeDocuments
- Full-text indexing where appropriate
- Proper partitioning strategies for each entity type
"""

import os
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import AzureCliCredential

# ──────────────────────────────────  RNG SETUP  ──────────────────────────
SEED = 42
random.seed(SEED)
fake = Faker()
fake.seed_instance(SEED)

# Load environment variables
load_dotenv()

# ─────────────────────────────  OpenAI Embeddings  ───────────────────────
def try_import_openai():
    try:
        from openai import AzureOpenAI
        return AzureOpenAI
    except Exception:
        return None

AzureOpenAI = try_import_openai()

def get_embedding(text: str):
    """Return embedding list[float]; dummy zeros when Azure creds unavailable."""
    if (
        AzureOpenAI is None
        or not os.getenv("AZURE_OPENAI_API_KEY")
        or not os.getenv("AZURE_OPENAI_ENDPOINT")
    ):
        return [0.0] * 1536
    
    client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

# ─────────────────────────────  GLOBALS  ─────────────────────────────────
BASE_DATE = datetime.now()

# Cosmos DB Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
print(COSMOS_ENDPOINT)
COSMOS_DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "contoso")

# Container names
CONTAINERS = {
    "customers": "Customers",
    "products": "Products",
    "subscriptions": "Subscriptions",
    "invoices": "Invoices",
    "payments": "Payments",
    "promotions": "Promotions",
    "security_logs": "SecurityLogs",
    "orders": "Orders",
    "support_tickets": "SupportTickets",
    "data_usage": "DataUsage",
    "service_incidents": "ServiceIncidents",
    "knowledge_documents": "KnowledgeDocuments"
}

##############################################################################
#                         COSMOS DB SETUP                                    #
##############################################################################

def get_cosmos_client():
    """Initialize Cosmos DB client using current Azure CLI credentials."""
    print(f"Connecting to Cosmos DB at: {COSMOS_ENDPOINT}")
    
    # Use Azure CLI credential (current user login) - required when disableLocalAuth=true
    print("Using Azure CLI credential (current user login)")
    credential = AzureCliCredential()
    
    client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    return client

def create_database(client: CosmosClient, database_name: str):
    """Create database if it doesn't exist."""
    print(f"\nChecking database: {database_name}")
    try:
        # Try to get existing database first
        database = client.get_database_client(database_name)
        # Test if it exists by reading properties
        database.read()
        print(f"  - Database '{database_name}' already exists")
    except exceptions.CosmosResourceNotFoundError:
        # Database doesn't exist, create it
        print(f"Creating database: {database_name}")
        database = client.create_database(id=database_name)
        print(f"✓ Database '{database_name}' created")
    except exceptions.CosmosResourceExistsError:
        database = client.get_database_client(database_name)
        print(f"  - Database '{database_name}' already exists")
    return database

def create_customers_container(database, container_name: str):
    """
    Create customers container.
    Partition key: /id (customer_id as string)
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    indexing_policy = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/_etag/?"}]
    }
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/id"),
        indexing_policy=indexing_policy
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /id")
    return container

def create_products_container(database, container_name: str):
    """
    Create products container.
    Partition key: /id (product_id as string)
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /id")
    return container

def create_subscriptions_container(database, container_name: str):
    """
    Create subscriptions container.
    Partition key: /customer_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/customer_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /customer_id")
    return container

def create_invoices_container(database, container_name: str):
    """
    Create invoices container.
    Partition key: /subscription_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/subscription_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /subscription_id")
    return container

def create_payments_container(database, container_name: str):
    """
    Create payments container.
    Partition key: /invoice_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/invoice_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /invoice_id")
    return container

def create_promotions_container(database, container_name: str):
    """
    Create promotions container.
    Partition key: /product_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/product_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /product_id")
    return container

def create_security_logs_container(database, container_name: str):
    """
    Create security logs container.
    Partition key: /customer_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/customer_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /customer_id")
    return container

def create_orders_container(database, container_name: str):
    """
    Create orders container.
    Partition key: /customer_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/customer_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /customer_id")
    return container

def create_support_tickets_container(database, container_name: str):
    """
    Create support tickets container with full-text indexing.
    Partition key: /customer_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    # Full-text policy for subject and description
    full_text_policy = {
        "defaultLanguage": "en-US",
        "fullTextPaths": [
            {"path": "/subject", "language": "en-US"},
            {"path": "/description", "language": "en-US"}
        ]
    }
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/customer_id"),
        full_text_policy=full_text_policy
    )
    
    print(f"✓ Container '{container_name}' created with:")
    print(f"  - Partition key: /customer_id")
    print(f"  - Full-text indexing on subject, description")
    return container

def create_data_usage_container(database, container_name: str):
    """
    Create data usage container.
    Partition key: /subscription_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/subscription_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /subscription_id")
    return container

def create_service_incidents_container(database, container_name: str):
    """
    Create service incidents container.
    Partition key: /subscription_id
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/subscription_id")
    )
    
    print(f"✓ Container '{container_name}' created with partition key: /subscription_id")
    return container

def create_knowledge_documents_container(database, container_name: str):
    """
    Create knowledge documents container with:
    - 1 vector embedding (content_vector)
    - Full-text indexing on content
    Partition key: /id (document_id as string)
    """
    print(f"\nCreating container: {container_name}")
    
    try:
        container = database.get_container_client(container_name)
        database.delete_container(container_name)
        print(f"  - Dropped existing container")
    except exceptions.CosmosResourceNotFoundError:
        print(f"  - Container doesn't exist, creating new")
    
    # Vector embedding policy
    vector_embedding_policy = {
        "vectorEmbeddings": [
            {
                "path": "/content_vector",
                "dataType": "float32",
                "distanceFunction": "cosine",
                "dimensions": 1536
            }
        ]
    }
    
    # Indexing policy
    indexing_policy = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [
            {"path": "/_etag/?"},
            {"path": "/content_vector/*"}
        ],
        "vectorIndexes": [
            {"path": "/content_vector", "type": "diskANN"}
        ]
    }
    
    # Full-text policy
    full_text_policy = {
        "defaultLanguage": "en-US",
        "fullTextPaths": [
            {"path": "/content", "language": "en-US"},
            {"path": "/title", "language": "en-US"}
        ]
    }
    
    container = database.create_container(
        id=container_name,
        partition_key=PartitionKey(path="/id"),
        indexing_policy=indexing_policy,
        vector_embedding_policy=vector_embedding_policy,
        full_text_policy=full_text_policy
    )
    
    print(f"✓ Container '{container_name}' created with:")
    print(f"  - Vector embedding (content_vector, 1536 dimensions)")
    print(f"  - Full-text indexing on content, title")
    print(f"  - Partition key: /id")
    return container

##############################################################################
#                              DATA SEEDING                                  #
##############################################################################

def populate_data(database, markdown_file="customer_scenarios.md"):
    """Populate all containers with data."""
    
    print("\n" + "="*70)
    print("POPULATING DATA")
    print("="*70)
    
    # Get container clients
    customers_container = database.get_container_client(CONTAINERS["customers"])
    products_container = database.get_container_client(CONTAINERS["products"])
    subscriptions_container = database.get_container_client(CONTAINERS["subscriptions"])
    invoices_container = database.get_container_client(CONTAINERS["invoices"])
    payments_container = database.get_container_client(CONTAINERS["payments"])
    promotions_container = database.get_container_client(CONTAINERS["promotions"])
    security_logs_container = database.get_container_client(CONTAINERS["security_logs"])
    orders_container = database.get_container_client(CONTAINERS["orders"])
    support_tickets_container = database.get_container_client(CONTAINERS["support_tickets"])
    data_usage_container = database.get_container_client(CONTAINERS["data_usage"])
    service_incidents_container = database.get_container_client(CONTAINERS["service_incidents"])
    knowledge_documents_container = database.get_container_client(CONTAINERS["knowledge_documents"])
    
    # Counters for auto-increment IDs
    customer_counter = 1
    product_counter = 1
    subscription_counter = 1
    invoice_counter = 1
    payment_counter = 1
    promotion_counter = 1
    security_log_counter = 1
    order_counter = 1
    ticket_counter = 1
    usage_counter = 1
    incident_counter = 1
    document_counter = 1
    
    # ========================= 1. RANDOM "NOISE" DATA ======================
    print("\n[1/2] Generating random noise data...")
    
    loyalty_levels = ["Bronze", "Silver", "Gold"]
    all_customer_ids = []
    
    # Customers
    print("  - Creating 250 customers...")
    for i in range(250):
        customer_id = str(customer_counter)
        customer = {
            "id": customer_id,
            "customer_id": customer_counter,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.email(),
            "phone": fake.phone_number()[:20],
            "address": fake.address().replace("\n", ", "),
            "loyalty_level": random.choice(loyalty_levels)
        }
        customers_container.create_item(body=customer)
        all_customer_ids.append(customer_counter)
        customer_counter += 1
    
    # Products
    print("  - Creating products...")
    products = [
        ("Contoso Mobile Plan", "Unlimited talk & text; data-cap varies by tier.", "mobile", 50.00),
        ("Contoso Internet Plan", "Fiber or cable internet with several speed tiers.", "internet", 60.00),
        ("Contoso Bundle Plan", "Discount when you bundle mobile + internet.", "bundle", 90.00),
        ("Contoso International Roaming", "Add-on for travellers.", "addon", 20.00),
    ]
    product_ids = {}
    for name, desc, cat, fee in products:
        product_id = str(product_counter)
        product = {
            "id": product_id,
            "product_id": product_counter,
            "name": name,
            "description": desc,
            "category": cat,
            "monthly_fee": fee
        }
        products_container.create_item(body=product)
        product_ids[name] = product_counter
        product_counter += 1
    
    # Subscriptions
    print("  - Creating subscriptions...")
    subscription_ids = []
    speed_choices = ["50Mbps", "100Mbps", "300Mbps", "1Gbps"]
    service_statuses = ["normal", "slow", "offline"]
    
    for cid in all_customer_ids:
        num_subs = random.randint(1, 2)
        for _ in range(num_subs):
            product_name = random.choice(list(product_ids.keys()))
            pid = product_ids[product_name]
            
            start = BASE_DATE - timedelta(days=random.randint(30, 730))
            
            subscription = {
                "id": str(subscription_counter),
                "subscription_id": subscription_counter,
                "customer_id": cid,
                "product_id": pid,
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": (start + timedelta(days=365)).strftime("%Y-%m-%d"),
                "status": random.choice(["active", "suspended", "cancelled"]),
                "roaming_enabled": random.randint(0, 1),
                "service_status": random.choice(service_statuses),
                "speed_tier": random.choice(speed_choices) if "Internet" in product_name else None,
                "data_cap_gb": random.choice([10, 20, 50, 100]) if "Mobile" in product_name else None,
                "autopay_enabled": random.randint(0, 1)
            }
            subscriptions_container.create_item(body=subscription)
            subscription_ids.append(subscription_counter)
            subscription_counter += 1
    
    # Invoices + Payments
    print("  - Creating invoices and payments...")
    payment_methods = ["credit_card", "ach", "paypal", "apple_pay"]
    
    for sub_id in subscription_ids:
        # Get subscription to get partition key
        sub_items = list(subscriptions_container.query_items(
            query="SELECT * FROM c WHERE c.subscription_id = @sub_id",
            parameters=[{"name": "@sub_id", "value": sub_id}],
            enable_cross_partition_query=True
        ))
        if not sub_items:
            continue
        sub = sub_items[0]
        
        num_invoices = random.randint(1, 6)
        for m in range(num_invoices):
            inv_date = BASE_DATE - timedelta(days=30 * m)
            amount = round(random.uniform(40, 120), 2)
            
            invoice = {
                "id": str(invoice_counter),
                "invoice_id": invoice_counter,
                "subscription_id": sub_id,
                "invoice_date": inv_date.strftime("%Y-%m-%d"),
                "amount": amount,
                "description": f"Monthly charge for subscription {sub_id}",
                "due_date": (inv_date + timedelta(days=15)).strftime("%Y-%m-%d")
            }
            invoices_container.create_item(body=invoice)
            
            # Random payments
            if random.random() > 0.3:
                num_payments = random.randint(1, 2)
                paid_so_far = 0.0
                for _ in range(num_payments):
                    pay_amt = round(min(amount - paid_so_far, random.uniform(10, amount)), 2)
                    paid_so_far += pay_amt
                    
                    payment = {
                        "id": str(payment_counter),
                        "payment_id": payment_counter,
                        "invoice_id": invoice_counter,
                        "payment_date": (inv_date + timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d"),
                        "amount": pay_amt,
                        "method": random.choice(payment_methods),
                        "status": "completed" if abs(paid_so_far - amount) < 0.01 else "partial"
                    }
                    payments_container.create_item(body=payment)
                    payment_counter += 1
            
            invoice_counter += 1
    
    # DataUsage
    print("  - Creating data usage records...")
    for sub_id in subscription_ids[:50]:  # Limit to first 50 for performance
        # Get subscription
        sub_items = list(subscriptions_container.query_items(
            query="SELECT * FROM c WHERE c.subscription_id = @sub_id",
            parameters=[{"name": "@sub_id", "value": sub_id}],
            enable_cross_partition_query=True
        ))
        if not sub_items:
            continue
        
        for d in range(28):
            usage_date = BASE_DATE - timedelta(days=d)
            usage = {
                "id": str(usage_counter),
                "usage_id": usage_counter,
                "subscription_id": sub_id,
                "usage_date": usage_date.strftime("%Y-%m-%d"),
                "data_used_mb": random.randint(100, 2000),
                "voice_minutes": random.randint(10, 500),
                "sms_count": random.randint(5, 100)
            }
            data_usage_container.create_item(body=usage)
            usage_counter += 1
    
    # Support Tickets
    print("  - Creating support tickets...")
    categories = ["billing", "technical", "account", "call_drop", "sms_issue"]
    priorities = ["low", "normal", "high", "urgent"]
    
    for _ in range(120):
        cid = random.choice(all_customer_ids)
        
        # Get a subscription for this customer
        subs = list(subscriptions_container.query_items(
            query="SELECT * FROM c WHERE c.customer_id = @cid",
            parameters=[{"name": "@cid", "value": cid}],
            enable_cross_partition_query=True
        ))
        sub_id = subs[0]["subscription_id"] if subs else None
        
        opened = BASE_DATE - timedelta(days=random.randint(0, 90))
        is_closed = random.random() > 0.4
        
        ticket = {
            "id": str(ticket_counter),
            "ticket_id": ticket_counter,
            "customer_id": cid,
            "subscription_id": sub_id,
            "category": random.choice(categories),
            "opened_at": opened.strftime("%Y-%m-%d"),
            "closed_at": (opened + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d") if is_closed else None,
            "status": "closed" if is_closed else "open",
            "priority": random.choice(priorities),
            "subject": fake.sentence(nb_words=6),
            "description": fake.text(max_nb_chars=200),
            "cs_agent": fake.name()
        }
        support_tickets_container.create_item(body=ticket)
        ticket_counter += 1
    
    # Promotions
    print("  - Creating promotions...")
    promotion_data = [
        (
            product_ids["Contoso Mobile Plan"],
            "Mobile Loyalty Discount",
            "10% discount for Gold members on the mobile plan.",
            "loyalty_level = 'Gold'",
            "2023-01-01",
            "2023-12-31",
            10,
        ),
        (
            product_ids["Contoso Internet Plan"],
            "New Internet Sign-up Bonus",
            "15% off for new internet subscribers.",
            "subscription_start within last 90 days",
            "2023-06-01",
            "2023-09-30",
            15,
        ),
        (
            product_ids["Contoso Bundle Plan"],
            "Bundle Saver Deal",
            "Save 20% when bundling services.",
            "any customer",
            "2024-01-01",
            "2024-06-30",
            20,
        ),
        (
            product_ids["Contoso Mobile Plan"],
            "Summer2025 Teaser Promo",
            "Early-bird discount starting next summer.",
            "loyalty_level = 'Gold'",
            "2025-06-01",
            "2025-08-31",
            15,
        ),
    ]
    
    for prod_id, name, desc, eligibility, start, end, discount in promotion_data:
        promotion = {
            "id": str(promotion_counter),
            "promotion_id": promotion_counter,
            "product_id": prod_id,
            "name": name,
            "description": desc,
            "eligibility_criteria": eligibility,
            "start_date": start,
            "end_date": end,
            "discount_percent": discount
        }
        promotions_container.create_item(body=promotion)
        promotion_counter += 1
    
    # Security Logs
    print("  - Creating security logs...")
    event_types = ["login_attempt", "account_locked"]
    
    for _ in range(40):
        cid = random.choice(all_customer_ids)
        event_time = BASE_DATE - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
        
        log = {
            "id": str(security_log_counter),
            "log_id": security_log_counter,
            "customer_id": cid,
            "event_type": random.choice(event_types),
            "event_timestamp": event_time.strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Security event: {random.choice(event_types)}"
        }
        security_logs_container.create_item(body=log)
        security_log_counter += 1
    
    # Orders
    print("  - Creating orders...")
    order_statuses = ["delivered", "completed", "pending", "returned"]
    
    for _ in range(120):
        cid = random.choice(all_customer_ids)
        prod_name = random.choice(list(product_ids.keys()))
        pid = product_ids[prod_name]
        
        order = {
            "id": str(order_counter),
            "order_id": order_counter,
            "customer_id": cid,
            "product_id": pid,
            "order_date": (BASE_DATE - timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
            "amount": round(random.uniform(20, 150), 2),
            "order_status": random.choice(order_statuses)
        }
        orders_container.create_item(body=order)
        order_counter += 1
    
    # Service incidents
    print("  - Creating service incidents...")
    for _ in range(60):
        sub_id = random.choice(subscription_ids)
        
        incident = {
            "id": str(incident_counter),
            "incident_id": incident_counter,
            "subscription_id": sub_id,
            "incident_date": (BASE_DATE - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d"),
            "description": fake.sentence(),
            "resolution_status": random.choice(["resolved", "investigating", "pending"])
        }
        service_incidents_container.create_item(body=incident)
        incident_counter += 1
    
    print("\n✓ Random noise data creation complete")
    
    # ========================= 2. DETERMINISTIC SCENARIOS ===================
    print("\n[2/2] Creating deterministic scenarios...")
    
    md = open(markdown_file, "w", encoding="utf-8")
    md.write("# Customer Scenarios – Answer Key Included\n\n")
    
    def write_md_block(idx, title, cust_id, name, email, phone, addr, loyalty, desc, solution_md):
        md.write(f"## Scenario {idx}: {title}\n\n")
        md.write(f"**Customer ID**: {cust_id}  \n")
        md.write(f"**Name**: {name}  \n")
        md.write(f"**Email**: {email}  \n")
        md.write(f"**Phone**: {phone}  \n")
        md.write(f"**Address**: {addr}  \n")
        md.write(f"**Loyalty**: {loyalty}  \n\n")
        md.write(f"**Challenge**: {desc}\n\n")
        md.write(f"**Solution**:\n{solution_md}\n---\n\n")
    
    # Helper functions
    def add_customer(**kw):
        nonlocal customer_counter
        customer_id = str(customer_counter)
        customer = {
            "id": customer_id,
            "customer_id": customer_counter,
            "first_name": kw["first"],
            "last_name": kw["last"],
            "email": kw["email"],
            "phone": kw["phone"],
            "address": kw["addr"],
            "loyalty_level": kw["loyalty"]
        }
        customers_container.create_item(body=customer)
        cid = customer_counter
        customer_counter += 1
        return cid
    
    def add_subscription(cust_id, **kw):
        nonlocal subscription_counter
        prod_name = kw["product"]
        pid = product_ids[prod_name]
        
        start = BASE_DATE - timedelta(days=60)
        end = BASE_DATE + timedelta(days=300)
        
        subscription = {
            "id": str(subscription_counter),
            "subscription_id": subscription_counter,
            "customer_id": cust_id,
            "product_id": pid,
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "status": kw.get("status", "active"),
            "roaming_enabled": kw.get("roaming", 0),
            "service_status": kw.get("service_status", "normal"),
            "speed_tier": kw.get("speed_tier"),
            "data_cap_gb": kw.get("data_cap_gb"),
            "autopay_enabled": kw.get("autopay", 1)
        }
        subscriptions_container.create_item(body=subscription)
        sid = subscription_counter
        subscription_counter += 1
        return sid
    
    def add_invoice(sub_id, *, amount, desc, when_days, mark_unpaid=True):
        nonlocal invoice_counter
        inv_date = BASE_DATE + timedelta(days=when_days)
        
        invoice = {
            "id": str(invoice_counter),
            "invoice_id": invoice_counter,
            "subscription_id": sub_id,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "amount": amount,
            "description": desc,
            "due_date": (inv_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }
        invoices_container.create_item(body=invoice)
        iid = invoice_counter
        invoice_counter += 1
        return iid
    
    # ─────────────────────────  SCENARIO 1  ─────────────────────────────
    print("  - Scenario 1: Invoice Higher Than Usual")
    sc1_cust = add_customer(
        first="John", last="Doe", email="scenario1@example.com",
        phone="555-0001", addr="123 Main St, City", loyalty="Silver"
    )
    sc1_sub = add_subscription(
        sc1_cust, product="Contoso Internet Plan", status="active",
        roaming=0, service_status="normal", speed_tier="300Mbps", data_cap_gb=10
    )
    
    # Prior normal invoice
    add_invoice(sc1_sub, amount=60.00, desc="Standard monthly charge", when_days=-30, mark_unpaid=False)
    
    # Surprise overage invoice
    inv_over = add_invoice(sc1_sub, amount=150.00, desc="Unexpected overage charges", when_days=-1)
    
    # Partial payment
    payment = {
        "id": str(payment_counter),
        "payment_id": payment_counter,
        "invoice_id": inv_over,
        "payment_date": (BASE_DATE + timedelta(days=3)).strftime("%Y-%m-%d"),
        "amount": 50.00,
        "method": "credit_card",
        "status": "partial"
    }
    payments_container.create_item(body=payment)
    payment_counter += 1
    
    # Seed large DataUsage
    for d in range(28, 0, -1):
        usage = {
            "id": str(usage_counter),
            "usage_id": usage_counter,
            "subscription_id": sc1_sub,
            "usage_date": (BASE_DATE - timedelta(days=d)).strftime("%Y-%m-%d"),
            "data_used_mb": random.randint(700, 900),
            "voice_minutes": 0,
            "sms_count": 0
        }
        data_usage_container.create_item(body=usage)
        usage_counter += 1
    
    write_md_block(
        1, "Invoice Higher Than Usual", sc1_cust, "John Doe",
        "scenario1@example.com", "555-0001", "123 Main St, City", "Silver",
        "Latest invoice shows $150, 2.5× the usual amount.",
        """
1. SELECT last 6 invoices → detect $150 outlier (std-dev or >50% above mean).
2. Cross-check DataUsage for same billing cycle → find ~22 GB vs plan's 10 GB cap.
3. Quote **Data Overage Policy – "may retroactively upgrade within 15 days"**.
4. Offer: (a) file invoice-adjustment; (b) upgrade plan & credit overage pro-rata.
5. Note that $50 already paid; $100 balance remains.
"""
    )
    
    # ─────────────────────────  SCENARIO 2  ─────────────────────────────
    print("  - Scenario 2: Internet Slower Than Before")
    sc2_cust = add_customer(
        first="Jane", last="Doe", email="scenario2@example.com",
        phone="555-0002", addr="234 Elm St, Town", loyalty="Gold"
    )
    sc2_sub = add_subscription(
        sc2_cust, product="Contoso Internet Plan", status="active",
        roaming=0, service_status="slow", speed_tier="1Gbps"
    )
    
    # Insert open ServiceIncident
    incident = {
        "id": str(incident_counter),
        "incident_id": incident_counter,
        "subscription_id": sc2_sub,
        "incident_date": (BASE_DATE - timedelta(days=2)).strftime("%Y-%m-%d"),
        "description": "Customer reports slow speeds for 3 days.",
        "resolution_status": "investigating"
    }
    service_incidents_container.create_item(body=incident)
    incident_counter += 1
    
    # Insert DataUsage rows showing very low usage
    for d in range(3):
        usage = {
            "id": str(usage_counter),
            "usage_id": usage_counter,
            "subscription_id": sc2_sub,
            "usage_date": (BASE_DATE - timedelta(days=d)).strftime("%Y-%m-%d"),
            "data_used_mb": random.randint(50, 150),
            "voice_minutes": 0,
            "sms_count": 0
        }
        data_usage_container.create_item(body=usage)
        usage_counter += 1
    
    write_md_block(
        2, "Internet Slower Than Before", sc2_cust, "Jane Doe",
        "scenario2@example.com", "555-0002", "234 Elm St, Town", "Gold",
        "Throughput much lower than advertised 1 Gbps tier.",
        """
1. Confirm Subscriptions.service_status = 'slow'.
2. Query ServiceIncidents – open ticket still 'investigating'.
3. Use KB: **Troubleshooting Slow Internet – Basic Steps**.
4. Ask customer to run speed-test, reboot; escalate if still <25% of tier.
"""
    )
    
    # ─────────────────────────  SCENARIO 3  ─────────────────────────────
    print("  - Scenario 3: Travelling Abroad – Needs Roaming")
    sc3_cust = add_customer(
        first="Mark", last="Doe", email="scenario3@example.com",
        phone="555-0003", addr="345 Oak St, Village", loyalty="Bronze"
    )
    sc3_sub = add_subscription(
        sc3_cust, product="Contoso Mobile Plan", status="active",
        roaming=0, service_status="normal"
    )
    
    write_md_block(
        3, "Travelling Abroad – Needs Roaming", sc3_cust, "Mark Doe",
        "scenario3@example.com", "555-0003", "345 Oak St, Village", "Bronze",
        "Leaving for Spain in 2 days, unsure how to enable roaming.",
        """
1. Subscriptions.roaming_enabled = 0 → verify not active.
2. Check product offerings → suggest 'International Roaming' add-on.
3. Quote **International Roaming Options Explained**: must activate ≥3 days ahead.
4. Offer immediate activation with pro-rated charges.
"""
    )
    
    # ─────────────────────────  SCENARIO 4  ─────────────────────────────
    print("  - Scenario 4: Account Locked After Failed Logins")
    sc4_cust = add_customer(
        first="Alice", last="Doe", email="scenario4@example.com",
        phone="555-0004", addr="456 Pine St, Hamlet", loyalty="Gold"
    )
    sc4_sub = add_subscription(
        sc4_cust, product="Contoso Mobile Plan", status="active",
        roaming=0, service_status="normal"
    )
    
    # Flood of login_attempts then account_locked
    for i in range(8):
        log = {
            "id": str(security_log_counter),
            "log_id": security_log_counter,
            "customer_id": sc4_cust,
            "event_type": "login_attempt",
            "event_timestamp": (BASE_DATE - timedelta(minutes=30 - i*2)).strftime("%Y-%m-%d %H:%M:%S"),
            "description": f"Failed login attempt #{i+1}"
        }
        security_logs_container.create_item(body=log)
        security_log_counter += 1
    
    log = {
        "id": str(security_log_counter),
        "log_id": security_log_counter,
        "customer_id": sc4_cust,
        "event_type": "account_locked",
        "event_timestamp": (BASE_DATE - timedelta(minutes=12)).strftime("%Y-%m-%d %H:%M:%S"),
        "description": "Exceeded login attempts; account locked"
    }
    security_logs_container.create_item(body=log)
    security_log_counter += 1
    
    write_md_block(
        4, "Account Locked After Failed Logins", sc4_cust, "Alice Doe",
        "scenario4@example.com", "555-0004", "456 Pine St, Hamlet", "Gold",
        "Can't log in; sees 'Account Locked' message.",
        """
1. Query SecurityLogs → 8 failed attempts + 1 account_locked event.
2. Verify customer identity (last 4 of SSN, DOB, etc.).
3. Quote **Account Security Policy – Unlock Procedure**.
4. Call unlock_account tool.
5. Recommend password reset & 2FA setup.
"""
    )
    
    md.close()
    print(f"\n✓ Deterministic scenarios created")
    print(f"✓ Markdown file written: {markdown_file}")
    
    # ========================= 3. KNOWLEDGE BASE ===================
    print("\n[3/3] Creating knowledge base documents...")
    
    kb_docs = [
        {
            "title": "Data Overage Policy",
            "doc_type": "policy",
            "content": "Customers who exceed their data cap may be charged overage fees. However, within 15 days of the invoice date, customers may request a retroactive plan upgrade to avoid overage charges. The upgrade will be pro-rated."
        },
        {
            "title": "Troubleshooting Slow Internet – Basic Steps",
            "doc_type": "procedure",
            "content": "1. Ask customer to run a speed test. 2. If speed is less than 25% of their tier, reboot the modem. 3. Check for service incidents in the area. 4. Escalate to technical support if issue persists."
        },
        {
            "title": "International Roaming Options Explained",
            "doc_type": "policy",
            "content": "International roaming must be activated at least 3 days before travel. Daily rates vary by region. Customers can enable roaming through their account portal or by calling customer service."
        },
        {
            "title": "Account Security Policy – Unlock Procedure",
            "doc_type": "policy",
            "content": "Accounts are locked after 5 failed login attempts. To unlock, verify customer identity using: 1) Last 4 of SSN, 2) Date of birth, 3) Billing address. After verification, use the unlock_account tool. Recommend password reset and 2FA setup."
        },
        {
            "title": "Billing Dispute Resolution Process",
            "doc_type": "procedure",
            "content": "1. Review invoice details with customer. 2. Check for usage anomalies or service changes. 3. If dispute is valid, create adjustment ticket. 4. Adjustment will be applied to next invoice within 1-2 billing cycles."
        }
    ]
    
    for doc_data in kb_docs:
        # Generate embedding for content
        print(f"  - Generating embedding for: {doc_data['title']}")
        content_vector = get_embedding(doc_data["content"])
        
        doc = {
            "id": str(document_counter),
            "document_id": document_counter,
            "title": doc_data["title"],
            "doc_type": doc_data["doc_type"],
            "content": doc_data["content"],
            "content_vector": content_vector
        }
        knowledge_documents_container.create_item(body=doc)
        document_counter += 1
    
    print("\n✓ Knowledge base documents created")
    
    print("\n" + "="*70)
    print("DATA POPULATION COMPLETE!")
    print("="*70)
    print(f"Total customers: {customer_counter - 1}")
    print(f"Total subscriptions: {subscription_counter - 1}")
    print(f"Total invoices: {invoice_counter - 1}")
    print(f"Total payments: {payment_counter - 1}")
    print(f"Total support tickets: {ticket_counter - 1}")
    print(f"Total knowledge documents: {document_counter - 1}")

##############################################################################
#                                MAIN                                        #
##############################################################################

def main():
    print("="*70)
    print("COSMOS DB SETUP FOR CONTOSO MCP SERVICE")
    print("="*70)
    
    # Initialize Cosmos client
    client = get_cosmos_client()
    
    # Create database
    database = create_database(client, COSMOS_DATABASE_NAME)
    
    # Create all containers
    print("\n" + "="*70)
    print("CREATING CONTAINERS")
    print("="*70)
    
    create_customers_container(database, CONTAINERS["customers"])
    create_products_container(database, CONTAINERS["products"])
    create_subscriptions_container(database, CONTAINERS["subscriptions"])
    create_invoices_container(database, CONTAINERS["invoices"])
    create_payments_container(database, CONTAINERS["payments"])
    create_promotions_container(database, CONTAINERS["promotions"])
    create_security_logs_container(database, CONTAINERS["security_logs"])
    create_orders_container(database, CONTAINERS["orders"])
    create_support_tickets_container(database, CONTAINERS["support_tickets"])
    create_data_usage_container(database, CONTAINERS["data_usage"])
    create_service_incidents_container(database, CONTAINERS["service_incidents"])
    create_knowledge_documents_container(database, CONTAINERS["knowledge_documents"])
    
    print("\n✓ All containers created successfully!")
    
    # Populate data
    populate_data(database)
    
    print("\n" + "="*70)
    print("SETUP COMPLETE!")
    print("="*70)
    print(f"\nCosmos DB Database: {COSMOS_DATABASE_NAME}")
    print(f"Endpoint: {COSMOS_ENDPOINT}")
    print("\nYou can now use the Cosmos DB version of the MCP service.")

if __name__ == "__main__":
    main()
