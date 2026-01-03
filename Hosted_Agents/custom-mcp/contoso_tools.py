"""Contoso Customer Service Utility Module  
  
Provides granular async functions for interacting with the Contoso  
customer database. Designed to be used by both MCP tools and AutoGen  
agents.  
"""  
  
import os  
import json  
import math  
import sqlite3  
from typing import List, Optional, Dict, Any  
from datetime import datetime  
from dotenv import load_dotenv  
  
# Load environment variables  
load_dotenv()  
  
# Database configuration  
DB_PATH = os.getenv("DB_PATH", "data/contoso.db")  
  
  
def get_db() -> sqlite3.Connection:  
    """Get a database connection with row factory."""  
    db = sqlite3.connect(DB_PATH)  
    db.row_factory = sqlite3.Row  
    return db  

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
except Exception as e:  
    print(f"Warning: Could not load Azure OpenAI (embeddings will use fallback): {e}")
    def get_embedding(text: str) -> List[float]:  
        """Fallback to zero vector when credentials are missing."""  
        return [0.0] * 1536  

# ========================================================================
# CUSTOMER FUNCTIONS
# ========================================================================

async def get_all_customers_async() -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT customer_id, first_name, last_name, email, loyalty_level FROM Customers"
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

async def get_customer_detail_async(customer_id: int) -> Dict[str, Any]:
    db = get_db()
    cust = db.execute(
        "SELECT * FROM Customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    if not cust:
        db.close()
        raise ValueError(f"Customer {customer_id} not found")
    subs = db.execute(
        "SELECT * FROM Subscriptions WHERE customer_id = ?", (customer_id,)
    ).fetchall()
    db.close()
    result = dict(cust)
    result['subscriptions'] = [dict(s) for s in subs]
    return result

# ========================================================================
# SUBSCRIPTION FUNCTIONS
# ========================================================================

async def get_subscription_detail_async(subscription_id: int) -> Dict[str, Any]:
    db = get_db()
    sub = db.execute(
        """SELECT s.*, p.name AS product_name, p.description AS product_description,
                  p.category, p.monthly_fee
           FROM Subscriptions s
           JOIN Products p ON p.product_id = s.product_id
           WHERE s.subscription_id = ?""",
        (subscription_id,),
    ).fetchone()
    if not sub:
        db.close()
        raise ValueError("Subscription not found")

    invoices_rows = db.execute(
        "SELECT invoice_id, invoice_date, amount, description, due_date "
        "FROM Invoices WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchall()

    invoices = []
    for inv in invoices_rows:
        pay_rows = db.execute(
            "SELECT * FROM Payments WHERE invoice_id = ?", (inv["invoice_id"],)
        ).fetchall()
        outstanding = inv["amount"] - sum(p["amount"] for p in pay_rows)
        invoices.append({
            **dict(inv),
            "payments": [dict(p) for p in pay_rows],
            "outstanding": outstanding,
        })

    service_incidents = db.execute(
        "SELECT * FROM ServiceIncidents WHERE subscription_id = ?",
        (subscription_id,),
    ).fetchall()

    db.close()
    result = dict(sub)
    result["invoices"] = invoices
    result["service_incidents"] = [dict(si) for si in service_incidents]
    return result

# ========================================================================
# INVOICE FUNCTIONS
# ========================================================================

async def get_invoice_payments_async(invoice_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM Payments WHERE invoice_id = ?", (invoice_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

async def pay_invoice_async(invoice_id: int, amount: float, method: str = "credit_card") -> Dict[str, Any]:
    db = get_db()
    inv = db.execute(
        "SELECT * FROM Invoices WHERE invoice_id = ?", (invoice_id,)
    ).fetchone()
    if not inv:
        db.close()
        raise ValueError("Invoice not found")

    db.execute(
        "INSERT INTO Payments (invoice_id, payment_date, amount, method, status) VALUES (?, ?, ?, ?, ?)",
        (invoice_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount, method, "completed"),
    )
    db.commit()

    payments = db.execute(
        "SELECT amount FROM Payments WHERE invoice_id = ?", (invoice_id,)
    ).fetchall()
    total_paid = sum(p["amount"] for p in payments)
    outstanding = inv["amount"] - total_paid

    db.close()
    return {
        "invoice_id": invoice_id,
        "amount_paid": amount,
        "total_paid": total_paid,
        "outstanding": outstanding,
        "status": "paid" if outstanding <= 0 else "partial",
    }

# ========================================================================
# DATA USAGE FUNCTIONS
# ========================================================================

async def get_data_usage_async(subscription_id: int, start_date: str, end_date: str, aggregate: bool = False) -> List[Dict[str, Any]] | Dict[str, Any]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM DataUsage WHERE subscription_id = ? AND usage_date BETWEEN ? AND ?",
        (subscription_id, start_date, end_date),
    ).fetchall()
    db.close()
    
    records = [dict(r) for r in rows]
    
    if aggregate:
        return {
            "subscription_id": subscription_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_data_mb": sum(r["data_used_mb"] for r in records),
            "total_voice_minutes": sum(r["voice_minutes"] for r in records),
            "total_sms": sum(r["sms_count"] for r in records),
            "days_counted": len(records),
        }
    return records

# ========================================================================
# BILLING FUNCTIONS
# ========================================================================

async def get_billing_summary_async(customer_id: int) -> Dict[str, Any]:
    db = get_db()
    subs = db.execute(
        "SELECT subscription_id FROM Subscriptions WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()

    total_outstanding = 0
    subscription_details = []

    for sub in subs:
        sub_id = sub["subscription_id"]
        invoices = db.execute(
            "SELECT amount FROM Invoices WHERE subscription_id = ?", (sub_id,)
        ).fetchall()
        payments = db.execute(
            "SELECT SUM(amount) as total FROM Payments WHERE invoice_id IN "
            "(SELECT invoice_id FROM Invoices WHERE subscription_id = ?)",
            (sub_id,),
        ).fetchone()

        total_invoice_amount = sum(inv["amount"] for inv in invoices)
        total_paid = payments["total"] if payments["total"] else 0
        outstanding = total_invoice_amount - total_paid

        subscription_details.append({
            "subscription_id": sub_id,
            "total_invoice_amount": total_invoice_amount,
            "total_paid": total_paid,
            "outstanding": outstanding,
        })
        total_outstanding += outstanding

    db.close()
    return {
        "customer_id": customer_id,
        "total_outstanding": total_outstanding,
        "subscription_details": subscription_details,
    }

async def get_invoice_payments_async(invoice_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM Payments WHERE invoice_id = ?", (invoice_id,)
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

# ========================================================================
# SECURITY FUNCTIONS
# ========================================================================

async def get_security_logs_async(customer_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT log_id, event_type, event_timestamp, description "
        "FROM SecurityLogs WHERE customer_id = ? ORDER BY event_timestamp DESC",
        (customer_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

async def unlock_account_async(customer_id: int) -> Dict[str, str]:
    db = get_db()
    db.execute(
        "INSERT INTO SecurityLogs (customer_id, event_type, event_timestamp, description) "
        "VALUES (?, ?, ?, ?)",
        (customer_id, "account_unlocked", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Account unlocked by support"),
    )
    db.commit()
    db.close()
    return {
        "customer_id": str(customer_id),
        "status": "unlocked",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

# ========================================================================
# PRODUCT FUNCTIONS
# ========================================================================

async def get_products_async(category: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    if category:
        rows = db.execute("SELECT * FROM Products WHERE category = ?", (category,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM Products").fetchall()
    db.close()
    return [dict(r) for r in rows]

async def get_product_detail_async(product_id: int) -> Dict[str, Any]:
    db = get_db()
    r = db.execute("SELECT * FROM Products WHERE product_id = ?", (product_id,)).fetchone()
    db.close()
    if not r:
        raise ValueError("Product not found")
    return dict(r)

# ========================================================================
# ORDER FUNCTIONS
# ========================================================================

async def get_customer_orders_async(customer_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        "SELECT * FROM Orders WHERE customer_id = ? ORDER BY order_date DESC",
        (customer_id,),
    ).fetchall()
    db.close()
    return [dict(r) for r in rows]

# ========================================================================
# PROMOTION FUNCTIONS
# ========================================================================

async def get_promotions_async() -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute("SELECT * FROM Promotions").fetchall()
    db.close()
    return [dict(r) for r in rows]

async def get_eligible_promotions_async(customer_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    cust = db.execute(
        "SELECT loyalty_level FROM Customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    if not cust:
        db.close()
        raise ValueError(f"Customer {customer_id} not found")

    today = datetime.now().strftime("%Y-%m-%d")
    promotions = db.execute(
        "SELECT * FROM Promotions WHERE start_date <= ? AND end_date >= ?",
        (today, today),
    ).fetchall()

    eligible = []
    for promo in promotions:
        if promo["criteria"] == f"loyalty_level = '{cust['loyalty_level']}'":
            eligible.append(dict(promo))
        elif promo["criteria"] == "all":
            eligible.append(dict(promo))

    db.close()
    return eligible

# ========================================================================
# KNOWLEDGE BASE FUNCTIONS
# ========================================================================

async def search_knowledge_base_async(query: str, topk: int = 3) -> List[Dict[str, Any]]:
    db = get_db()
    rows = db.execute("SELECT * FROM KnowledgeDocuments").fetchall()
    db.close()

    query_embedding = get_embedding(query)

    scored = []
    for doc in rows:
        doc_embedding = json.loads(doc["embedding"])
        similarity = sum(q * d for q, d in zip(query_embedding, doc_embedding)) / (
            math.sqrt(sum(q * q for q in query_embedding))
            * math.sqrt(sum(d * d for d in doc_embedding))
            + 1e-9
        )
        scored.append((dict(doc), similarity))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in scored[:topk]]

# ========================================================================
# SUPPORT TICKET FUNCTIONS
# ========================================================================

async def get_support_tickets_async(customer_id: int, open_only: bool = False) -> List[Dict[str, Any]]:
    db = get_db()
    if open_only:
        rows = db.execute(
            "SELECT * FROM SupportTickets WHERE customer_id = ? AND status != 'closed'",
            (customer_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM SupportTickets WHERE customer_id = ?", (customer_id,)
        ).fetchall()
    db.close()
    return [dict(r) for r in rows]

async def create_support_ticket_async(
    customer_id: int,
    subscription_id: int,
    category: str,
    priority: str,
    subject: str,
    description: str,
) -> Dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        "INSERT INTO SupportTickets (customer_id, subscription_id, category, priority, subject, description, status, opened_at, cs_agent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (customer_id, subscription_id, category, priority, subject, description, "open", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Support Team"),
    )
    db.commit()
    ticket_id = cursor.lastrowid
    db.close()

    return {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "category": category,
        "priority": priority,
        "subject": subject,
        "description": description,
        "status": "open",
        "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "closed_at": None,
        "cs_agent": "Support Team",
    }

# ========================================================================
# SUBSCRIPTION UPDATE FUNCTIONS
# ========================================================================

async def update_subscription_async(subscription_id: int, updates: Dict[str, Any]) -> dict:
    db = get_db()
    sub = db.execute(
        "SELECT * FROM Subscriptions WHERE subscription_id = ?", (subscription_id,)
    ).fetchone()
    if not sub:
        db.close()
        raise ValueError(f"Subscription {subscription_id} not found")

    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [subscription_id]

    db.execute(
        f"UPDATE Subscriptions SET {set_clause} WHERE subscription_id = ?",
        values,
    )
    db.commit()

    updated = db.execute(
        "SELECT * FROM Subscriptions WHERE subscription_id = ?", (subscription_id,)
    ).fetchone()
    db.close()

    return dict(updated)
