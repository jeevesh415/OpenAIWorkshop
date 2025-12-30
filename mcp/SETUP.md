# MCP Service Setup Guide

Complete guide for setting up and running the Contoso MCP (Model Context Protocol) service with either SQLite or Azure Cosmos DB backend.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Option 1: SQLite (Local Development)](#option-1-sqlite-local-development)
- [Option 2: Cosmos DB (Cloud Production)](#option-2-cosmos-db-cloud-production)
- [Environment Configuration](#environment-configuration)
- [Running the Service](#running-the-service)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

**For local development (SQLite):**
```bash
cd mcp
uv sync
uv run python mcp_service.py
```

**For cloud/production (Cosmos DB):**
```bash
cd mcp/data
.\setup_cosmos.ps1        # Windows PowerShell
# or
./setup_cosmos.sh         # Linux/macOS

cd ..
uv run python mcp_service_cosmos.py
```

---

## Prerequisites

### All Setups Require:
- **Python 3.10+**
- **uv package manager** - Install from [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)
- **Azure OpenAI** - For embeddings (text-embedding-ada-002)

### For Cosmos DB Setup (Additional):
- **Azure CLI** - Install from [https://aka.ms/azure-cli](https://aka.ms/azure-cli)
- **Azure Subscription** - With permissions to create resources
- **Azure account** - Logged in via `az login`

---

## Option 1: SQLite (Local Development)

Best for: Development, testing, learning, demos without Azure dependencies.

### 1. Install Dependencies

```bash
cd mcp
uv sync
```

This creates a virtual environment and installs all required packages from `pyproject.toml`.

### 2. Create SQLite Database

The SQLite database with sample data is pre-populated:

```bash
# If you need to recreate it:
python data/create_db.py
```

This creates `data/contoso.db` with:
- 250+ random customers
- 9 deterministic test scenarios
- Sample products, subscriptions, invoices, etc.
- Knowledge base articles with embeddings

### 3. Configure Environment

Create a `.env` file in the `mcp` directory:

```ini
# Azure OpenAI (for embeddings)
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
AZURE_OPENAI_API_KEY="your-api-key"
AZURE_OPENAI_API_VERSION="2024-02-15-preview"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-ada-002"

# Database
DB_PATH="data/contoso.db"

# Authentication (disable for local dev)
DISABLE_AUTH="true"
```

### 4. Run the Service

```bash
uv run python mcp_service.py
```

The service will start on `http://localhost:8000/mcp`

**Key Features:**
- ✅ File-based storage (no cloud required)
- ✅ Fast startup
- ✅ Easy to reset/recreate
- ✅ Good for development and testing

**Limitations:**
- ❌ Single machine only
- ❌ Python-based vector search (slower)
- ❌ Not suitable for production scale

---

## Option 2: Cosmos DB (Cloud Production)

Best for: Production deployments, cloud-scale operations, multi-region scenarios.

### 1. Automated Setup (Recommended)

We provide scripts that automate the entire Cosmos DB setup process.

#### Windows (PowerShell)

```powershell
cd mcp/data
.\setup_cosmos.ps1
```

**With custom parameters:**
```powershell
.\setup_cosmos.ps1 -ResourceGroup "my-rg" -Location "eastus" -AccountName "my-cosmos" -DatabaseName "contoso"
```

#### Linux/macOS (Bash)

```bash
cd mcp/data
chmod +x setup_cosmos.sh
./setup_cosmos.sh
```

**With custom parameters:**
```bash
./setup_cosmos.sh my-rg eastus my-cosmos contoso
```

#### What the Script Does

The setup script performs all steps automatically:

1. **Verifies Azure CLI authentication**
2. **Creates resource group** (default: `mcp-demo-rg` in `westus`)
3. **Deploys Cosmos DB account** with:
   - NoSQL API with vector search enabled
   - Serverless capacity mode (pay-per-use)
   - All 12 containers with proper schemas
   - DisableLocalAuth = true (AAD only)
4. **Assigns RBAC role** - Grants "Cosmos DB Data Contributor" to your user
5. **Waits for role propagation** (30 seconds)
6. **Updates .env file** - Adds Cosmos DB connection details
7. **Populates data** - Seeds database with:
   - 250+ random customers
   - 9 deterministic test scenarios
   - Vector embeddings for knowledge base

**Execution time:** 5-8 minutes total

#### Default Values

| Parameter | Default Value |
|-----------|--------------|
| Resource Group | `mcp-demo-rg` |
| Location | `westus` |
| Account Name | `mcp-contoso-cosmos` |
| Database Name | `contoso` |

### 2. Manual Setup (Alternative)

If you prefer manual control:

#### Step 1: Login to Azure

```bash
az login
```

#### Step 2: Create Resource Group

```bash
az group create --name mcp-demo-rg --location westus
```

#### Step 3: Deploy Cosmos DB Account

```bash
cd mcp/data
az deployment group create \
  --resource-group mcp-demo-rg \
  --template-file cosmosdb.bicep
```

This creates:
- Cosmos DB account with NoSQL API
- Vector search capabilities enabled
- All 12 containers with partition keys and indexes

#### Step 4: Assign RBAC Role

Get your user principal ID:
```bash
az ad signed-in-user show --query id -o tsv
```

Deploy RBAC assignment:
```bash
az deployment group create \
  --resource-group mcp-demo-rg \
  --template-file cosmosdb-rbac.bicep \
  --parameters userPrincipalId=<your-user-principal-id>
```

#### Step 5: Get Connection Details

```bash
az cosmosdb show \
  --name mcp-contoso-cosmos \
  --resource-group mcp-demo-rg \
  --query documentEndpoint -o tsv
```

#### Step 6: Update .env File

Add to your `.env`:
```ini
COSMOS_ENDPOINT="https://mcp-contoso-cosmos.documents.azure.com:443/"
COSMOS_DATABASE_NAME="contoso"
```

#### Step 7: Wait for RBAC Propagation

```bash
# Wait 30-60 seconds for role assignment to propagate
sleep 30
```

#### Step 8: Populate Data

```bash
cd mcp
uv sync
uv run python data/create_cosmos_db.py
```

### 3. Verify Setup

Check containers in Azure Portal or via CLI:

```bash
az cosmosdb sql container list \
  --account-name mcp-contoso-cosmos \
  --resource-group mcp-demo-rg \
  --database-name contoso \
  --query "[].name" -o table
```

You should see 12 containers:
- Customers
- Products
- Subscriptions
- Invoices
- Payments
- Promotions
- SecurityLogs
- Orders
- SupportTickets
- DataUsage
- ServiceIncidents
- KnowledgeDocuments

### 4. Run Cosmos DB Service

```bash
cd mcp
uv run python mcp_service_cosmos.py
```

**Key Features:**
- ✅ Cloud-scale storage and performance
- ✅ Native vector search with diskANN indexing
- ✅ Multi-region replication (optional)
- ✅ Automatic backups and SLA
- ✅ AAD authentication (no keys in code)

**Cosmos DB-Specific Details:**
- **Partition strategy**: Each container has optimized partition keys
- **Vector indexing**: KnowledgeDocuments uses 1536-dimension embeddings
- **Authentication**: Azure CLI credentials (AzureCliCredential)
- **Cross-partition queries**: Enabled for flexibility

---

## Environment Configuration

### Complete .env Template

```ini
# ============================================================================
# Azure OpenAI (Required for both SQLite and Cosmos DB)
# ============================================================================
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
AZURE_OPENAI_API_KEY="your-api-key"
AZURE_OPENAI_API_VERSION="2024-02-15-preview"
AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-ada-002"
OPENAI_MODEL_NAME="gpt-4"

# ============================================================================
# Database Configuration
# ============================================================================
# For SQLite:
DB_PATH="data/contoso.db"

# For Cosmos DB (add these after running setup script):
COSMOS_ENDPOINT="https://mcp-contoso-cosmos.documents.azure.com:443/"
COSMOS_DATABASE_NAME="contoso"

# ============================================================================
# Authentication & Authorization
# ============================================================================
# Disable auth for local development
DISABLE_AUTH="true"

# For production with Azure AD:
# DISABLE_AUTH="false"
# AAD_TENANT_ID="your-tenant-id"
# MCP_API_AUDIENCE="your-api-audience"
# PUBLIC_BASE_URL="https://your-domain.com"
# SECURITY_ROLE="security"
# QUERY_ROLE="query"

# ============================================================================
# Optional: MCP Server Configuration
# ============================================================================
# MCP_SERVER_URI="http://localhost:8000/mcp"
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | - | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | Yes | - | Azure OpenAI API key |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Yes | - | Embedding model deployment name |
| `DB_PATH` | SQLite only | `data/contoso.db` | Path to SQLite database |
| `COSMOS_ENDPOINT` | Cosmos only | - | Cosmos DB account endpoint |
| `COSMOS_DATABASE_NAME` | Cosmos only | `contoso` | Cosmos DB database name |
| `DISABLE_AUTH` | No | `false` | Set to `true` for local dev |

---

## Running the Service

### SQLite Version

```bash
cd mcp
uv run python mcp_service.py
```

### Cosmos DB Version

```bash
cd mcp
uv run python mcp_service_cosmos.py
```

### Using uv with OneDrive

If your project is in OneDrive, set link mode to avoid hardlink errors:

```bash
# PowerShell
$env:UV_LINK_MODE="copy"
uv run python mcp_service_cosmos.py

# Or create uv.toml in the mcp directory:
echo "link-mode = \"copy\"" > uv.toml
```

### Running in Background

**Windows:**
```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd mcp; uv run python mcp_service.py"
```

**Linux/macOS:**
```bash
cd mcp
nohup uv run python mcp_service.py > mcp.log 2>&1 &
```

### Service Endpoints

Once running, the service exposes:

- **`http://localhost:8000/mcp`** - Main MCP endpoint
- **`http://localhost:8000/docs`** - FastAPI auto-generated docs
- **`http://localhost:8000/mcp/.well-known/oauth-protected-resource`** - OAuth metadata

---

## Testing

### Test with curl

```bash
# List all customers
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_all_customers",
    "arguments": {}
  }'

# Get customer detail
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_customer_detail",
    "arguments": {"customer_id": 1}
  }'

# Vector search (knowledge base)
curl -X POST http://localhost:8000/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_knowledge_base",
    "arguments": {"query": "refund policy", "topk": 3}
  }'
```

### Test with MCP Inspector

1. Install MCP Inspector: [https://github.com/modelcontextprotocol/inspector](https://github.com/modelcontextprotocol/inspector)
2. Connect to: `http://localhost:8000/mcp`
3. Browse available tools and test them interactively

### Test Scenarios

The database includes 9 pre-defined test scenarios:

1. **Alice Johnson** - Billing dispute resolution
2. **Bob Smith** - Data overage investigation
3. **Carol White** - Account locked, needs unlock
4. **Dave Brown** - Upgrade inquiry
5. **Eve Davis** - Service outage complaint
6. **Frank Miller** - Promotion eligibility check
7. **Grace Wilson** - Multiple unpaid invoices
8. **Henry Moore** - Cancellation request
9. **Ivy Taylor** - Complex multi-issue case

Use these customer IDs (1-9) to test various tool combinations.

---

## Troubleshooting

### Common Issues

#### "Failed to hardlink file" (OneDrive)

**Problem:** UV tries to use hardlinks but OneDrive doesn't support them.

**Solution:**
```bash
# Set environment variable
export UV_LINK_MODE=copy  # Linux/macOS
set UV_LINK_MODE=copy     # Windows CMD
$env:UV_LINK_MODE="copy"  # PowerShell

# Or create uv.toml
echo 'link-mode = "copy"' > uv.toml
```

#### "file is being used by another process" (Windows)

**Problem:** OneDrive is syncing .venv directory.

**Solution:**
1. Stop OneDrive sync temporarily
2. Delete `.venv` folder: `rmdir /s /q .venv`
3. Set UV_LINK_MODE=copy
4. Re-run: `uv sync`

#### "Not logged in to Azure CLI"

**Problem:** Cosmos DB setup requires Azure authentication.

**Solution:**
```bash
az login
az account show  # Verify login
```

#### "Forbidden" (403) - Cosmos DB

**Problem:** RBAC role not assigned or not propagated.

**Solution:**
```bash
# Wait 1-5 minutes for role propagation
# Or manually check role assignment:
az role assignment list \
  --scope "/subscriptions/{sub-id}/resourceGroups/mcp-demo-rg/providers/Microsoft.DocumentDB/databaseAccounts/mcp-contoso-cosmos" \
  --query "[?principalType=='User'].roleDefinitionName"
```

#### "Resource Not Found" (404) - Cosmos DB

**Problem:** Database or containers don't exist.

**Solution:**
```bash
cd mcp
uv run python data/create_cosmos_db.py
```

#### "Module not found" Errors

**Problem:** Dependencies not installed.

**Solution:**
```bash
cd mcp
uv sync --reinstall
```

#### Embedding Errors

**Problem:** Azure OpenAI credentials incorrect or quota exceeded.

**Solution:**
1. Verify `.env` has correct endpoint and key
2. Check deployment name matches: `text-embedding-ada-002`
3. Verify quota in Azure Portal

### Debugging Tips

**Enable verbose logging:**

```python
# Add to top of mcp_service.py or mcp_service_cosmos.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check Cosmos DB connectivity:**

```python
from contoso_tools_cosmos import get_cosmos_client, get_database
client = get_cosmos_client()
db = get_database()
print(f"Connected to: {db.id}")
```

**Verify SQLite database:**

```bash
sqlite3 data/contoso.db "SELECT COUNT(*) FROM Customers;"
```

### Getting Help

- **Documentation:** See [README.md](README.md) for architecture details
- **Cosmos DB Guide:** See [README_COSMOS.md](data/README_SETUP.md) for implementation details
- **Issues:** Open an issue in the repository
- **Azure Support:** Use Azure Portal support for Cosmos DB issues

---

## Cost Considerations

### SQLite
- **Cost:** Free (local storage only)
- **Best for:** Development, testing, demos

### Cosmos DB (Serverless Mode)

**One-time costs:**
- Data population: ~$0.05-0.10

**Monthly costs (development/testing):**
- Idle: $0 (no minimum charge)
- Light usage: $1-5/month
- Storage: ~$0.25/GB/month

**Request Units (RUs):**
- Point read (1KB): ~1 RU
- Simple query: 2-10 RUs
- Vector search: 10-50 RUs
- Write operation: 5-10 RUs

**Cost savings:**
```bash
# Delete resources when not needed
az group delete --name mcp-demo-rg --yes --no-wait
```

**Production scaling:**
- Consider provisioned throughput for predictable workloads
- Use autoscale for variable traffic
- Monitor with Azure Cost Management

---

## Next Steps

1. **Test all tools** - Verify each MCP tool works correctly
2. **Configure authentication** - Set up Azure AD for production
3. **Deploy to Azure** - Use Container Apps or App Service
4. **Set up monitoring** - Enable Application Insights
5. **API Management** - Add APIM gateway for multi-tenant support
6. **CI/CD Pipeline** - Automate deployments

See [README.md](README.md) for advanced topics including:
- Authentication and authorization
- APIM integration
- Multi-tenant support
- Agentic workflows
- Long-running operations

---

## Quick Reference

### File Structure

```
mcp/
├── SETUP.md                    # This file
├── README.md                   # Architecture and design docs
├── README_COSMOS.md            # Cosmos DB implementation details
├── pyproject.toml             # Python dependencies
├── uv.lock                    # Locked dependencies
├── .env                       # Environment variables (create this)
│
├── mcp_service.py             # SQLite-based service
├── mcp_service_cosmos.py      # Cosmos DB-based service
├── contoso_tools.py           # SQLite data access layer
├── contoso_tools_cosmos.py    # Cosmos DB data access layer
│
└── data/
    ├── setup_cosmos.ps1       # Automated Cosmos DB setup (PowerShell)
    ├── setup_cosmos.sh        # Automated Cosmos DB setup (Bash)
    ├── cosmosdb.bicep         # Cosmos DB infrastructure template
    ├── cosmosdb-rbac.bicep    # RBAC role assignment template
    ├── create_db.py           # SQLite database creation
    ├── create_cosmos_db.py    # Cosmos DB data population
    ├── contoso.db            # SQLite database (auto-generated)
    ├── customer_scenarios.md  # Test scenario definitions
    └── kb.json               # Knowledge base articles
```

### Command Cheat Sheet

```bash
# Install dependencies
cd mcp && uv sync

# Run SQLite version
uv run python mcp_service.py

# Run Cosmos DB version
uv run python mcp_service_cosmos.py

# Setup Cosmos DB (automated)
cd data && .\setup_cosmos.ps1

# Recreate SQLite database
python data/create_db.py

# Populate Cosmos DB
python data/create_cosmos_db.py

# Check Azure login
az login && az account show

# Delete Cosmos DB resources
az group delete --name mcp-demo-rg --yes
```

---

**Ready to start?** Choose your setup option above and follow the steps! 🚀
