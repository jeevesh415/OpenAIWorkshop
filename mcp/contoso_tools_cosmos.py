"""Contoso Customer Service Utility Module - Cosmos DB Version

Provides granular async functions for interacting with the Contoso
customer database in Azure Cosmos DB. Designed to be used by both MCP 
tools and AutoGen agents.
"""

import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from azure.cosmos import CosmosClient, ContainerProxy, exceptions
from azure.identity import AzureCliCredential

# Load environment variables
load_dotenv()

# Cosmos DB Configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
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

# Global client (initialized lazily)
_cosmos_client = None
_database = None


def get_cosmos_client() -> CosmosClient:
    """Get or create Cosmos DB client using Azure CLI credentials."""
    global _cosmos_client
    if _cosmos_client is None:
        credential = AzureCliCredential()
        _cosmos_client = CosmosClient(COSMOS_ENDPOINT, credential=credential)
    return _cosmos_client


def get_database():
    """Get database client."""
    global _database
    if _database is None:
        client = get_cosmos_client()
        _database = client.get_database_client(COSMOS_DATABASE_NAME)
    return _database


def get_container(container_name: str) -> ContainerProxy:
    """Get a container client."""
    db = get_database()
    return db.get_container_client(container_name)


# Safe OpenAI import / dummy embedding
try:
    from openai import AzureOpenAI

    _client = AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    _emb_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    def get_embedding(text: str) -> List[float]:
        """Get embedding vector from Azure OpenAI."""
        text = text.replace("\n", " ")
        return _client.embeddings.create(input=[text], model=_emb_model).data[0].embedding

except Exception:
    def get_embedding(text: str) -> List[float]:
        """Fallback to zero vector when credentials are missing."""
        return [0.0] * 1536


def execute_vector_search(
    container: ContainerProxy,
    query_embedding: List[float],
    vector_field: str = "content_vector",
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute vector similarity search on a container.
    
    Args:
        container: CosmosDB container to search
        query_embedding: Query vector embedding
        vector_field: Name of the vector field to search (default: "content_vector")
        top_k: Number of results to return
        filters: Optional filters (e.g., {"user_id": "user123"})
        
    Returns:
        List of matching documents with similarity scores
    """
    # Build the query
    where_clause = ""
    if filters:
        conditions = [f"c.{key} = @{key}" for key in filters.keys()]
        where_clause = " WHERE " + " AND ".join(conditions)
    
    query = f"""
    SELECT TOP @top_k c.id, c.title, c.doc_type, c.content
    FROM c
    {where_clause}
    ORDER BY VectorDistance(c.{vector_field}, @embedding)
    """
    
    # Build parameters
    parameters = [
        {"name": "@embedding", "value": query_embedding},
        {"name": "@top_k", "value": top_k}
    ]
    
    if filters:
        for key, value in filters.items():
            parameters.append({"name": f"@{key}", "value": value})
    
    # Execute query
    results = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    return results


# ========================================================================
# CUSTOMER FUNCTIONS
# ========================================================================

async def get_all_customers_async() -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["customers"])
    query = "SELECT c.customer_id, c.first_name, c.last_name, c.email, c.loyalty_level FROM c"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items


async def get_customer_detail_async(customer_id: int) -> Dict[str, Any]:
    customers_container = get_container(CONTAINERS["customers"])
    subscriptions_container = get_container(CONTAINERS["subscriptions"])
    
    # Get customer
    query = "SELECT * FROM c WHERE c.customer_id = @customer_id"
    parameters = [{"name": "@customer_id", "value": customer_id}]
    customers = list(customers_container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not customers:
        raise ValueError(f"Customer {customer_id} not found")
    
    customer = customers[0]
    
    # Get subscriptions
    query = "SELECT * FROM c WHERE c.customer_id = @customer_id"
    subscriptions = list(subscriptions_container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    customer['subscriptions'] = subscriptions
    return customer


async def get_customer_orders_async(customer_id: int) -> List[Dict[str, Any]]:
    orders_container = get_container(CONTAINERS["orders"])
    products_container = get_container(CONTAINERS["products"])
    
    # Get orders for customer
    query = "SELECT * FROM c WHERE c.customer_id = @customer_id ORDER BY c.order_date DESC"
    parameters = [{"name": "@customer_id", "value": customer_id}]
    orders = list(orders_container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    # Enrich with product names
    result = []
    for order in orders:
        # Get product name
        product_query = "SELECT c.name FROM c WHERE c.product_id = @product_id"
        product_params = [{"name": "@product_id", "value": order["product_id"]}]
        products = list(products_container.query_items(
            query=product_query,
            parameters=product_params,
            enable_cross_partition_query=True
        ))
        
        product_name = products[0]["name"] if products else "Unknown"
        result.append({
            "order_id": order["order_id"],
            "order_date": order["order_date"],
            "product_name": product_name,
            "amount": order["amount"],
            "order_status": order["order_status"]
        })
    
    return result


# ========================================================================
# SUBSCRIPTION FUNCTIONS
# ========================================================================

async def get_subscription_detail_async(subscription_id: int) -> Dict[str, Any]:
    subscriptions_container = get_container(CONTAINERS["subscriptions"])
    products_container = get_container(CONTAINERS["products"])
    invoices_container = get_container(CONTAINERS["invoices"])
    payments_container = get_container(CONTAINERS["payments"])
    incidents_container = get_container(CONTAINERS["service_incidents"])
    
    # Get subscription
    query = "SELECT * FROM c WHERE c.subscription_id = @subscription_id"
    parameters = [{"name": "@subscription_id", "value": subscription_id}]
    subscriptions = list(subscriptions_container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not subscriptions:
        raise ValueError("Subscription not found")
    
    subscription = subscriptions[0]
    
    # Get product details
    product_query = "SELECT * FROM c WHERE c.product_id = @product_id"
    product_params = [{"name": "@product_id", "value": subscription["product_id"]}]
    products = list(products_container.query_items(
        query=product_query,
        parameters=product_params,
        enable_cross_partition_query=True
    ))
    
    if products:
        product = products[0]
        subscription["product_name"] = product["name"]
        subscription["product_description"] = product["description"]
        subscription["category"] = product["category"]
        subscription["monthly_fee"] = product["monthly_fee"]
    
    # Get invoices
    invoice_query = "SELECT * FROM c WHERE c.subscription_id = @subscription_id"
    invoices = list(invoices_container.query_items(
        query=invoice_query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    # Enrich invoices with payments
    enriched_invoices = []
    for invoice in invoices:
        payment_query = "SELECT * FROM c WHERE c.invoice_id = @invoice_id"
        payment_params = [{"name": "@invoice_id", "value": invoice["invoice_id"]}]
        payments = list(payments_container.query_items(
            query=payment_query,
            parameters=payment_params,
            enable_cross_partition_query=True
        ))
        
        total_paid = sum(p["amount"] for p in payments if p["status"] == "successful")
        invoice["payments"] = payments
        invoice["outstanding"] = max(invoice["amount"] - total_paid, 0.0)
        enriched_invoices.append(invoice)
    
    subscription["invoices"] = enriched_invoices
    
    # Get service incidents
    incident_query = "SELECT c.incident_id, c.incident_date, c.description, c.resolution_status FROM c WHERE c.subscription_id = @subscription_id"
    incidents = list(incidents_container.query_items(
        query=incident_query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    subscription["service_incidents"] = incidents
    return subscription


async def update_subscription_async(subscription_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    if not updates:
        raise ValueError("No fields supplied")
    
    data = {k: v for k, v in updates.items() if v is not None}
    if not data:
        raise ValueError("No valid fields to update")
    
    container = get_container(CONTAINERS["subscriptions"])
    
    # Get the subscription first to get its partition key
    query = "SELECT * FROM c WHERE c.subscription_id = @subscription_id"
    parameters = [{"name": "@subscription_id", "value": subscription_id}]
    subscriptions = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not subscriptions:
        raise ValueError("Subscription not found")
    
    subscription = subscriptions[0]
    
    # Update fields
    for key, value in data.items():
        subscription[key] = value
    
    # Replace the item
    container.replace_item(item=subscription["id"], body=subscription)
    
    return {"subscription_id": subscription_id, "updated_fields": list(data.keys())}


async def get_data_usage_async(subscription_id: int, start_date: str, end_date: str, aggregate: bool = False) -> List[Dict[str, Any]] | Dict[str, Any]:
    container = get_container(CONTAINERS["data_usage"])
    
    query = """
    SELECT c.usage_date, c.data_used_mb, c.voice_minutes, c.sms_count 
    FROM c 
    WHERE c.subscription_id = @subscription_id 
      AND c.usage_date >= @start_date 
      AND c.usage_date <= @end_date
    ORDER BY c.usage_date
    """
    parameters = [
        {"name": "@subscription_id", "value": subscription_id},
        {"name": "@start_date", "value": start_date},
        {"name": "@end_date", "value": end_date}
    ]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if aggregate:
        return {
            "subscription_id": subscription_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_mb": sum(r["data_used_mb"] for r in items),
            "total_voice_minutes": sum(r["voice_minutes"] for r in items),
            "total_sms": sum(r["sms_count"] for r in items),
        }
    
    return items


# ========================================================================
# BILLING FUNCTIONS
# ========================================================================

async def get_billing_summary_async(customer_id: int) -> Dict[str, Any]:
    subscriptions_container = get_container(CONTAINERS["subscriptions"])
    invoices_container = get_container(CONTAINERS["invoices"])
    payments_container = get_container(CONTAINERS["payments"])
    
    # Get all subscriptions for customer
    sub_query = "SELECT c.subscription_id FROM c WHERE c.customer_id = @customer_id"
    sub_params = [{"name": "@customer_id", "value": customer_id}]
    subscriptions = list(subscriptions_container.query_items(
        query=sub_query,
        parameters=sub_params,
        enable_cross_partition_query=True
    ))
    
    if not subscriptions:
        return {"customer_id": customer_id, "total_due": 0.0, "invoices": []}
    
    subscription_ids = [s["subscription_id"] for s in subscriptions]
    
    # Get all invoices for these subscriptions
    outstanding_list = []
    for sub_id in subscription_ids:
        inv_query = "SELECT * FROM c WHERE c.subscription_id = @subscription_id"
        inv_params = [{"name": "@subscription_id", "value": sub_id}]
        invoices = list(invoices_container.query_items(
            query=inv_query,
            parameters=inv_params,
            enable_cross_partition_query=True
        ))
        
        for invoice in invoices:
            # Get payments for this invoice
            pay_query = "SELECT c.amount FROM c WHERE c.invoice_id = @invoice_id AND c.status = 'successful'"
            pay_params = [{"name": "@invoice_id", "value": invoice["invoice_id"]}]
            payments = list(payments_container.query_items(
                query=pay_query,
                parameters=pay_params,
                enable_cross_partition_query=True
            ))
            
            paid = sum(p["amount"] for p in payments)
            outstanding = max(invoice["amount"] - paid, 0.0)
            outstanding_list.append({
                "invoice_id": invoice["invoice_id"],
                "outstanding": outstanding
            })
    
    total_due = sum(item["outstanding"] for item in outstanding_list)
    return {"customer_id": customer_id, "total_due": total_due, "invoices": outstanding_list}


async def get_invoice_payments_async(invoice_id: int) -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["payments"])
    query = "SELECT * FROM c WHERE c.invoice_id = @invoice_id"
    parameters = [{"name": "@invoice_id", "value": invoice_id}]
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    return items


async def pay_invoice_async(invoice_id: int, amount: float, method: str = "credit_card") -> Dict[str, Any]:
    invoices_container = get_container(CONTAINERS["invoices"])
    payments_container = get_container(CONTAINERS["payments"])
    
    # Get invoice
    inv_query = "SELECT * FROM c WHERE c.invoice_id = @invoice_id"
    inv_params = [{"name": "@invoice_id", "value": invoice_id}]
    invoices = list(invoices_container.query_items(
        query=inv_query,
        parameters=inv_params,
        enable_cross_partition_query=True
    ))
    
    if not invoices:
        raise ValueError("Invoice not found")
    
    invoice = invoices[0]
    
    # Get existing payments
    pay_query = "SELECT c.amount FROM c WHERE c.invoice_id = @invoice_id AND c.status = 'successful'"
    payments = list(payments_container.query_items(
        query=pay_query,
        parameters=inv_params,
        enable_cross_partition_query=True
    ))
    
    current_paid = sum(p["amount"] for p in payments)
    
    # Create new payment
    # Get max payment_id
    all_payments_query = "SELECT VALUE MAX(c.payment_id) FROM c"
    max_ids = list(payments_container.query_items(
        query=all_payments_query,
        enable_cross_partition_query=True
    ))
    max_payment_id = max_ids[0] if max_ids and max_ids[0] is not None else 0
    
    today = datetime.now().strftime("%Y-%m-%d")
    new_payment = {
        "id": f"payment_{max_payment_id + 1}",
        "payment_id": max_payment_id + 1,
        "invoice_id": invoice_id,
        "payment_date": today,
        "amount": amount,
        "method": method,
        "status": "successful"
    }
    
    payments_container.create_item(body=new_payment)
    
    outstanding = max(invoice["amount"] - (current_paid + amount), 0.0)
    return {"invoice_id": invoice_id, "outstanding": outstanding}


# ========================================================================
# SECURITY FUNCTIONS
# ========================================================================

async def get_security_logs_async(customer_id: int) -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["security_logs"])
    query = """
    SELECT c.log_id, c.event_type, c.event_timestamp, c.description 
    FROM c 
    WHERE c.customer_id = @customer_id 
    ORDER BY c.event_timestamp DESC
    """
    parameters = [{"name": "@customer_id", "value": customer_id}]
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    return items


async def unlock_account_async(customer_id: int) -> Dict[str, str]:
    container = get_container(CONTAINERS["security_logs"])
    
    # Check if account is locked
    query = """
    SELECT TOP 1 * 
    FROM c 
    WHERE c.customer_id = @customer_id AND c.event_type = 'account_locked' 
    ORDER BY c.event_timestamp DESC
    """
    parameters = [{"name": "@customer_id", "value": customer_id}]
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not items:
        raise ValueError("No recent lock event; nothing to do.")
    
    # Get max log_id
    max_query = "SELECT VALUE MAX(c.log_id) FROM c"
    max_ids = list(container.query_items(
        query=max_query,
        enable_cross_partition_query=True
    ))
    max_log_id = max_ids[0] if max_ids and max_ids[0] is not None else 0
    
    # Create unlock event
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    unlock_event = {
        "id": f"security_log_{max_log_id + 1}",
        "log_id": max_log_id + 1,
        "customer_id": customer_id,
        "event_type": "account_unlocked",
        "event_timestamp": now,
        "description": "Unlocked via API"
    }
    
    container.create_item(body=unlock_event)
    return {"message": "Account unlocked"}


# ========================================================================
# PRODUCT FUNCTIONS
# ========================================================================

async def get_products_async(category: Optional[str] = None) -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["products"])
    
    if category:
        query = "SELECT * FROM c WHERE c.category = @category"
        parameters = [{"name": "@category", "value": category}]
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
    else:
        query = "SELECT * FROM c"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
    
    return items


async def get_product_detail_async(product_id: int) -> Dict[str, Any]:
    container = get_container(CONTAINERS["products"])
    query = "SELECT * FROM c WHERE c.product_id = @product_id"
    parameters = [{"name": "@product_id", "value": product_id}]
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    if not items:
        raise ValueError("Product not found")
    
    return items[0]


# ========================================================================
# PROMOTION FUNCTIONS
# ========================================================================

async def get_promotions_async() -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["promotions"])
    query = "SELECT * FROM c"
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    return items


async def get_eligible_promotions_async(customer_id: int) -> List[Dict[str, Any]]:
    customers_container = get_container(CONTAINERS["customers"])
    promotions_container = get_container(CONTAINERS["promotions"])
    
    # Get customer loyalty level
    cust_query = "SELECT c.loyalty_level FROM c WHERE c.customer_id = @customer_id"
    cust_params = [{"name": "@customer_id", "value": customer_id}]
    customers = list(customers_container.query_items(
        query=cust_query,
        parameters=cust_params,
        enable_cross_partition_query=True
    ))
    
    if not customers:
        raise ValueError("Customer not found")
    
    loyalty = customers[0]["loyalty_level"]
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Get active promotions
    promo_query = "SELECT * FROM c WHERE c.start_date <= @today AND c.end_date >= @today"
    promo_params = [{"name": "@today", "value": today}]
    promotions = list(promotions_container.query_items(
        query=promo_query,
        parameters=promo_params,
        enable_cross_partition_query=True
    ))
    
    # Filter by eligibility
    eligible = []
    for promo in promotions:
        crit = promo.get("eligibility_criteria", "") or ""
        if f"loyalty_level = '{loyalty}'" in crit or "loyalty_level" not in crit:
            eligible.append(promo)
    
    return eligible


# ========================================================================
# SUPPORT FUNCTIONS
# ========================================================================

async def get_support_tickets_async(customer_id: int, open_only: bool = False) -> List[Dict[str, Any]]:
    container = get_container(CONTAINERS["support_tickets"])
    
    if open_only:
        query = "SELECT * FROM c WHERE c.customer_id = @customer_id AND c.status != 'closed'"
    else:
        query = "SELECT * FROM c WHERE c.customer_id = @customer_id"
    
    parameters = [{"name": "@customer_id", "value": customer_id}]
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    return items


async def create_support_ticket_async(customer_id: int, subscription_id: int, category: str, priority: str, subject: str, description: str) -> Dict[str, Any]:
    container = get_container(CONTAINERS["support_tickets"])
    
    # Get max ticket_id
    max_query = "SELECT VALUE MAX(c.ticket_id) FROM c"
    max_ids = list(container.query_items(
        query=max_query,
        enable_cross_partition_query=True
    ))
    max_ticket_id = max_ids[0] if max_ids and max_ids[0] is not None else 0
    
    opened = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_ticket = {
        "id": f"ticket_{max_ticket_id + 1}",
        "ticket_id": max_ticket_id + 1,
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "category": category,
        "opened_at": opened,
        "closed_at": None,
        "status": "open",
        "priority": priority,
        "subject": subject,
        "description": description,
        "cs_agent": "AI_Bot"
    }
    
    container.create_item(body=new_ticket)
    return new_ticket


# ========================================================================
# KNOWLEDGE BASE FUNCTIONS
# ========================================================================

async def search_knowledge_base_async(query: str, topk: int = 3) -> List[Dict[str, Any]]:
    query_emb = get_embedding(query)
    container = get_container(CONTAINERS["knowledge_documents"])
    
    # Use vector search
    results = execute_vector_search(
        container=container,
        query_embedding=query_emb,
        vector_field="content_vector",
        top_k=topk
    )
    
    # Return simplified results
    return [{"title": r["title"], "doc_type": r["doc_type"], "content": r["content"]} for r in results]
