# Cosmos DB Setup Scripts

This directory contains scripts to automate the complete setup of Azure Cosmos DB for the Contoso MCP service.

## What These Scripts Do

The setup scripts perform all necessary steps in the correct order:

1. **Verify Azure CLI Authentication** - Ensures you're logged in to Azure
2. **Create Resource Group** - Creates the resource group if it doesn't exist
3. **Deploy Cosmos DB Account** - Provisions Cosmos DB with:
   - NoSQL API with vector search capabilities
   - Serverless capacity mode
   - All 12 required containers with proper schemas
4. **Assign RBAC Role** - Grants your user account "Cosmos DB Data Contributor" role
5. **Wait for Propagation** - Allows time for role assignment to become active
6. **Update .env File** - Automatically updates connection details
7. **Populate Data** - Runs `create_cosmos_db.py` to seed the database with:
   - 250+ random customers
   - 9 deterministic test scenarios
   - Vector embeddings for knowledge documents

## Prerequisites

- Azure CLI installed and logged in (`az login`)
- Python 3.10+ with required packages (see `../pyproject.toml`)
- Azure subscription with permissions to create resources

## Usage

### PowerShell (Windows)

```powershell
cd mcp/data
.\setup_cosmos.ps1
```

With custom parameters:
```powershell
.\setup_cosmos.ps1 -ResourceGroup "my-rg" -Location "eastus" -AccountName "my-cosmos" -DatabaseName "mydb"
```

### Bash (Linux/macOS)

```bash
cd mcp/data
chmod +x setup_cosmos.sh
./setup_cosmos.sh
```

With custom parameters:
```bash
./setup_cosmos.sh my-rg eastus my-cosmos mydb
```

## Default Values

- **Resource Group**: `mcp-demo-rg`
- **Location**: `westus`
- **Account Name**: `mcp-contoso-cosmos`
- **Database Name**: `contoso`

## Execution Time

The complete setup typically takes **5-8 minutes**:
- Cosmos DB deployment: 3-5 minutes
- RBAC propagation: 30 seconds
- Data population: 2-3 minutes (depending on OpenAI API latency for embeddings)

## What Gets Created

### Azure Resources
- Resource Group (if new)
- Cosmos DB Account with:
  - NoSQL API
  - Vector search enabled
  - Serverless capacity
  - Local auth disabled (AAD only)

### Containers (12 total)
1. **Customers** - Customer profiles
2. **Products** - Product catalog
3. **Subscriptions** - Customer subscriptions
4. **Invoices** - Billing invoices
5. **Payments** - Payment records
6. **Promotions** - Active promotions
7. **SecurityLogs** - Security events
8. **Orders** - Product orders
9. **SupportTickets** - Customer support tickets
10. **DataUsage** - Data consumption metrics
11. **ServiceIncidents** - Service outages/incidents
12. **KnowledgeDocuments** - KB articles with vector embeddings

### Data Population
- **250+ random customers** with realistic profiles
- **9 deterministic test scenarios** from `customer_scenarios.md`:
  1. Alice Johnson - Billing dispute
  2. Bob Smith - Data overage
  3. Carol White - Account locked
  4. Dave Brown - Upgrade inquiry
  5. Eve Davis - Service outage
  6. Frank Miller - Promotion eligibility
  7. Grace Wilson - Multiple invoices
  8. Henry Moore - Cancellation
  9. Ivy Taylor - Complex multi-issue

## Authentication

The scripts use **Azure CLI credentials** (your current user). This means:
- You must be logged in: `az login`
- No service principal required
- Your user gets RBAC role automatically
- Same credentials used by `create_cosmos_db.py`

## Troubleshooting

### "Not logged in to Azure CLI"
```bash
az login
```

### "Role assignment not working"
Wait a bit longer - RBAC can take up to 5 minutes to propagate. You can manually wait and re-run:
```powershell
python create_cosmos_db.py
```

### "Cosmos DB account already exists"
The script will use the existing account. To start fresh:
```bash
az group delete --name mcp-demo-rg --yes
```

### "Python package missing"
Install dependencies:
```bash
cd mcp
pip install -e .
```

## Manual Steps (if needed)

If you prefer to run steps manually:

```bash
# 1. Create resource group
az group create --name mcp-demo-rg --location westus

# 2. Deploy Cosmos DB
az deployment group create \
  --resource-group mcp-demo-rg \
  --template-file cosmosdb.bicep

# 3. Assign role (replace with your user principal ID)
az deployment group create \
  --resource-group mcp-demo-rg \
  --template-file cosmosdb-rbac.bicep \
  --parameters userPrincipalId=<your-user-id>

# 4. Wait 30 seconds for RBAC propagation
sleep 30

# 5. Populate data
python create_cosmos_db.py
```

## Files in This Directory

- **setup_cosmos.ps1** - PowerShell automation script (Windows)
- **setup_cosmos.sh** - Bash automation script (Linux/macOS)
- **cosmosdb.bicep** - Cosmos DB account and containers template
- **cosmosdb-rbac.bicep** - RBAC role assignment template
- **create_cosmos_db.py** - Data population script
- **contoso.db** - Original SQLite database (reference)
- **customer_scenarios.md** - Test scenario definitions
- **kb.json** - Knowledge base articles for embeddings

## Next Steps

After setup completes:

1. **Verify data** - Check Azure Portal to see containers and items
2. **Update mcp_service.py** - Modify to use Cosmos DB instead of SQLite
3. **Test MCP service** - Run and verify all tools work with Cosmos DB
4. **Deploy** - Consider deploying MCP service to Azure Container Apps or App Service

## Cost Considerations

Using **serverless capacity mode**:
- Pay only for Request Units (RUs) consumed
- No minimum charge when idle
- Good for development and testing
- Vector searches consume more RUs than regular queries

Estimated costs for testing:
- Data population: ~$0.05-0.10 (one-time)
- Light development usage: ~$1-5/month
- Delete resources when not needed: `az group delete --name mcp-demo-rg`

## Related Documentation

- [Azure Cosmos DB Documentation](https://docs.microsoft.com/azure/cosmos-db/)
- [Vector Search in Cosmos DB](https://docs.microsoft.com/azure/cosmos-db/vector-search)
- [Cosmos DB RBAC](https://docs.microsoft.com/azure/cosmos-db/role-based-access-control)
- [MCP Service Documentation](../README.md)
