from fastmcp import FastMCP  
from fastmcp.server.middleware import Middleware, MiddlewareContext
from typing import Annotated, List, Optional, Dict, Any  
from pydantic import BaseModel  
import sqlite3, os, asyncio, logging, time  
from datetime import datetime  
from dotenv import load_dotenv  
from fastmcp.server.middleware import Middleware, MiddlewareContext 
from fastmcp.server.dependencies import get_access_token 
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.auth import RemoteAuthProvider  
from fastmcp.server.auth.providers.jwt import JWTVerifier  
from fastmcp.server.auth import AccessToken, TokenVerifier
from starlette.requests import Request 
from starlette.responses import JSONResponse
from fastmcp.utilities.logging import get_logger  

# Import common tools
from contoso_tools import *

logger = get_logger("auth.debug")  

# Suppress debug logging from FastMCP internals
logging.basicConfig(level=logging.INFO)
logging.getLogger("fakeredis").setLevel(logging.WARNING)
logging.getLogger("docket").setLevel(logging.WARNING)
logging.getLogger("docket.worker").setLevel(logging.WARNING) 

# ────────────────────────── FastMCP INITIALIZATION ──────────────────────

# Check if authentication should be disabled
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() in ("true", "1", "yes", "on")
USE_PASSTHROUGH_AUTH = os.getenv("USE_PASSTHROUGH_AUTH", "true").lower() in ("true", "1", "yes", "on")

# Configure JWT verification using Entra ID (issuer, audience, JWKS)
AAD_TENANT = os.getenv("AAD_TENANT_ID")
MCP_AUDIENCE = os.getenv("MCP_API_AUDIENCE")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

issuer = f"https://login.microsoftonline.com/{AAD_TENANT}/v2.0" if AAD_TENANT else None
jwks_uri = f"https://login.microsoftonline.com/{AAD_TENANT}/discovery/v2.0/keys" if AAD_TENANT else None

token_verifier = None
if not DISABLE_AUTH:
    if USE_PASSTHROUGH_AUTH:
        token_verifier = None  # Simplified for local testing
    elif jwks_uri and issuer:
        token_verifier = JWTVerifier(
            jwks_uri=jwks_uri,
            audience=None,
            algorithm="RS256",
        )

auth = None
if token_verifier and not DISABLE_AUTH:
    auth = RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[issuer] if issuer else [],
        base_url=PUBLIC_BASE_URL,
        resource_name="Contoso Customer API",
    )

mcp = FastMCP(
    name="Contoso Customer API as Tools",
    instructions=(
        "All customer, billing and knowledge data is accessible ONLY via the declared "
        "tools below.  Return values follow the pydantic schemas.  Always call the most "
        "specific tool that answers the user's question."
    ),
    auth=auth,
)

##############################################################################
#                              Pydantic MODELS                              #
##############################################################################

class CustomerSummary(BaseModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str
    loyalty_level: str

class CustomerDetail(BaseModel):
    customer_id: int
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    address: Optional[str]
    loyalty_level: str

class Payment(BaseModel):
    payment_id: int
    payment_date: Optional[str]
    amount: float
    method: str
    status: str

class Invoice(BaseModel):
    invoice_id: int
    invoice_date: str
    amount: float
    description: str
    due_date: str
    payments: List[Payment]
    outstanding: float

class ServiceIncident(BaseModel):
    incident_id: int
    incident_date: str
    description: str
    status: str

class SubscriptionDetail(BaseModel):
    subscription_id: int
    customer_id: int
    product_id: int
    status: str
    start_date: str
    invoices: List[Invoice]
    service_incidents: List[ServiceIncident]

class Promotion(BaseModel):
    promotion_id: int
    product_id: int
    name: str
    description: str
    criteria: str
    start_date: str
    end_date: str
    discount_percent: int

class KBDoc(BaseModel):
    doc_id: int
    title: str
    content: str
    category: str

class SecurityLog(BaseModel):
    log_id: int
    event_type: str
    event_timestamp: str
    description: str

class Order(BaseModel):
    order_id: int
    order_date: str
    product_name: str
    amount: float
    order_status: str

class DataUsageRecord(BaseModel):
    usage_date: str
    data_used_mb: int
    voice_minutes: int
    sms_count: int

class SupportTicket(BaseModel):
    ticket_id: int
    subscription_id: int
    category: str
    opened_at: str
    closed_at: Optional[str]
    status: str
    priority: str
    subject: str
    description: str
    cs_agent: str

class Product(BaseModel):
    product_id: int
    name: str
    description: str
    category: str
    monthly_fee: float

# ─── Authorization Middleware ───────────────────────────────────────────

SECURITY_ROLE = "security"
RESTRICTED_TOOLS_REQUIRING_ACCOUNT_SCOPE = {"unlock_account"}

class AuthZMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)
        if DISABLE_AUTH:
            return tools
        token = get_access_token()
        if token is None:
            return tools
        roles = token.claims.get("roles", [])
        if SECURITY_ROLE in roles:
            return tools
        filtered = [
            t for t in tools
            if t.key not in RESTRICTED_TOOLS_REQUIRING_ACCOUNT_SCOPE
        ]
        return filtered

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        if DISABLE_AUTH:
            return await call_next(context)
        token = get_access_token()
        if token is None:
            raise ToolError("Authentication required")
        roles = token.claims.get("roles", [])
        tool_name = context.message.name
        if SECURITY_ROLE in roles:
            return await call_next(context)
        if tool_name in RESTRICTED_TOOLS_REQUIRING_ACCOUNT_SCOPE:
            raise ToolError(
                f"Insufficient authorization to call '{tool_name}'. "
                f"Requires '{SECURITY_ROLE}'."
            )
        return await call_next(context)

mcp.add_middleware(AuthZMiddleware())

@mcp.custom_route("/mcp/.well-known/oauth-protected-resource", methods=["GET"])
async def _protected_resource_metadata(request: Request):
    """Endpoint to return OAuth protected resource metadata."""
    if DISABLE_AUTH:
        return JSONResponse({"error": "auth not enabled"}, status_code=404)
    server = request.app.state.fastmcp_server
    auth = getattr(server, "auth", None)
    if auth is None:
        return JSONResponse({"error": "auth not configured"}, status_code=404)
    resource = str(auth.resource_server_url).rstrip("/")
    auth_servers = getattr(auth, "authorization_servers", []) or []
    auth_servers = [str(x) for x in auth_servers]
    scopes = getattr(auth, "required_scopes", []) or []
    return JSONResponse(
        {
            "resource": resource,
            "authorization_servers": auth_servers,
            "scopes_supported": scopes,
        }
    )

##############################################################################
#                               TOOL ENDPOINTS                              #
##############################################################################

@mcp.tool(description="List all customers with basic info")
async def get_all_customers() -> List[CustomerSummary]:
    data = await get_all_customers_async()
    return [CustomerSummary(**r) for r in data]

@mcp.tool(description="Get a full customer profile including their subscriptions")
async def get_customer_detail(
    customer_id: Annotated[int, "Customer identifier value"],
) -> CustomerDetail:
    data = await get_customer_detail_async(customer_id)
    return CustomerDetail(**data)

@mcp.tool(
    description=(
        "Detailed subscription view → invoices (with payments) + service incidents."
    )
)
async def get_subscription_detail(
    subscription_id: Annotated[int, "Subscription identifier value"],
) -> SubscriptionDetail:
    data = await get_subscription_detail_async(subscription_id)
    invoices = []
    for inv_data in data['invoices']:
        payments = [Payment(**p) for p in inv_data['payments']]
        invoices.append(Invoice(**{**inv_data, 'payments': payments}))
    service_incidents = [ServiceIncident(**si) for si in data['service_incidents']]
    return SubscriptionDetail(**{**data, 'invoices': invoices, 'service_incidents': service_incidents})

@mcp.tool(description="Return invoice‑level payments list")
async def get_invoice_payments(
    invoice_id: Annotated[int, "Invoice identifier value"],
) -> List[Payment]:
    data = await get_invoice_payments_async(invoice_id)
    return [Payment(**r) for r in data]

@mcp.tool(description="Record a payment for a given invoice and get new outstanding balance")
async def pay_invoice(
    invoice_id: Annotated[int, "Invoice identifier value"],
    amount: Annotated[float, "Payment amount"],
    method: Annotated[str, "Payment method"] = "credit_card",
) -> Dict[str, Any]:
    return await pay_invoice_async(invoice_id, amount, method)

@mcp.tool(description="Daily data‑usage records for a subscription over a date range")
async def get_data_usage(
    subscription_id: Annotated[int, "Subscription identifier value"],
    start_date: Annotated[str, "Inclusive start date (YYYY-MM-DD)"],
    end_date: Annotated[str, "Inclusive end date (YYYY-MM-DD)"],
    aggregate: Annotated[bool, "Set to true for aggregate statistics"] = False,
) -> List[DataUsageRecord] | Dict[str, Any]:
    result = await get_data_usage_async(subscription_id, start_date, end_date, aggregate)
    if aggregate:
        return result
    return [DataUsageRecord(**r) for r in result]

@mcp.tool(description="List every active promotion (no filtering)")
async def get_promotions() -> List[Promotion]:
    data = await get_promotions_async()
    return [Promotion(**r) for r in data]

@mcp.tool(
    description="Promotions *eligible* for a given customer right now (evaluates basic loyalty/date criteria)."
)
async def get_eligible_promotions(
    customer_id: Annotated[int, "Customer identifier value"],
) -> List[Promotion]:
    data = await get_eligible_promotions_async(customer_id)
    return [Promotion(**r) for r in data]

@mcp.tool(description="Semantic search on policy / procedure knowledge documents")
async def search_knowledge_base(
    query: Annotated[str, "Natural language query"],
    topk: Annotated[int, "Number of top documents to return"] = 3,
) -> List[KBDoc]:
    data = await search_knowledge_base_async(query, topk)
    return [KBDoc(**r) for r in data]

@mcp.tool(description="Security events for a customer (newest first)")
async def get_security_logs(
    customer_id: Annotated[int, "Customer identifier value"],
) -> List[SecurityLog]:
    data = await get_security_logs_async(customer_id)
    return [SecurityLog(**r) for r in data]

@mcp.tool(description="All orders placed by a customer")
async def get_customer_orders(
    customer_id: Annotated[int, "Customer identifier value"],
) -> List[Order]:
    data = await get_customer_orders_async(customer_id)
    return [Order(**r) for r in data]

@mcp.tool(description="Retrieve support tickets for a customer (optionally filter by open status)")
async def get_support_tickets(
    customer_id: Annotated[int, "Customer identifier value"],
    open_only: Annotated[bool, "Filter to open tickets"] = False,
) -> List[SupportTicket]:
    data = await get_support_tickets_async(customer_id, open_only)
    return [SupportTicket(**r) for r in data]

@mcp.tool(description="Create a new support ticket for a customer")
async def create_support_ticket(
    customer_id: Annotated[int, "Customer identifier value"],
    subscription_id: Annotated[int, "Subscription identifier value"],
    category: Annotated[str, "Ticket category"],
    priority: Annotated[str, "Ticket priority"],
    subject: Annotated[str, "Ticket subject"],
    description: Annotated[str, "Ticket description"],
) -> SupportTicket:
    data = await create_support_ticket_async(customer_id, subscription_id, category, priority, subject, description)
    return SupportTicket(**data)

class Product(BaseModel):
    product_id: int
    name: str
    description: str
    category: str
    monthly_fee: float

@mcp.tool(description="List / search available products (optional category filter)")
async def get_products(
    category: Annotated[Optional[str], "Optional category filter"] = None,
) -> List[Product]:
    data = await get_products_async(category)
    return [Product(**r) for r in data]

@mcp.tool(description="Return a single product by ID")
async def get_product_detail(
    product_id: Annotated[int, "Product identifier value"],
) -> Product:
    data = await get_product_detail_async(product_id)
    return Product(**data)

@mcp.tool(description="Update one or more mutable fields on a subscription.")
async def update_subscription(
    subscription_id: Annotated[int, "Subscription identifier value"],
    status: Annotated[Optional[str], "New subscription status"] = None,
    service_status: Annotated[Optional[str], "New service status"] = None,
    product_id: Annotated[Optional[int], "Product identifier to switch to"] = None,
    start_date: Annotated[Optional[str], "Updated subscription start date (YYYY-MM-DD)"] = None,
    end_date: Annotated[Optional[str], "Updated subscription end date (YYYY-MM-DD)"] = None,
    autopay_enabled: Annotated[Optional[int], "Set autopay enabled flag (0 or 1)"] = None,
    roaming_enabled: Annotated[Optional[int], "Set roaming enabled flag (0 or 1)"] = None,
    speed_tier: Annotated[Optional[str], "New speed tier label"] = None,
    data_cap_gb: Annotated[Optional[int], "Updated data cap in GB"] = None,
) -> dict:
    updates: Dict[str, Any] = {}
    if status is not None:
        updates["status"] = status
    if service_status is not None:
        updates["service_status"] = service_status
    if product_id is not None:
        updates["product_id"] = product_id
    if start_date is not None:
        updates["start_date"] = start_date
    if end_date is not None:
        updates["end_date"] = end_date
    if autopay_enabled is not None:
        updates["autopay_enabled"] = autopay_enabled
    if roaming_enabled is not None:
        updates["roaming_enabled"] = roaming_enabled
    if speed_tier is not None:
        updates["speed_tier"] = speed_tier
    if data_cap_gb is not None:
        updates["data_cap_gb"] = data_cap_gb
    return await update_subscription_async(subscription_id, updates)

@mcp.tool(description="What does a customer currently owe across all subscriptions?")
async def get_billing_summary(
    customer_id: Annotated[int, "Customer identifier value"],
) -> Dict[str, Any]:
    return await get_billing_summary_async(customer_id)

##############################################################################
#                                RUN SERVER                                  #
##############################################################################

if __name__ == "__main__":
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=8000))
