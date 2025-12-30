# Contoso Customer Support Agent

A production-ready AI agent for Contoso customer support, powered by a custom Model Context Protocol (MCP) service with access to customer data, billing information, orders, and subscriptions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Container Apps                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐              ┌──────────────────────┐   │
│  │    Agent         │              │   Contoso MCP        │   │
│  │ (GPT-4o-mini)    │◄──HTTPS──►│  FastMCP Service      │   │
│  │                  │              │ - 17+ Customer Tools │   │
│  │ - Customer Q&A   │              │ - SQLite Database    │   │
│  │ - Billing Help   │              │ - 250+ Customers     │   │
│  │ - Order Support  │              └──────────────────────┘   │
│  │ - Subscriptions  │              │ /data/contoso.db     │   │
│  └──────────────────┘              └──────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Custom MCP Service**: FastMCP-based service with 17+ tools for customer data access
- **SQLite Database**: Pre-loaded with 250+ Contoso test customers
- **Azure Deployment**: Fully containerized and deployed to Azure Container Apps
- **Secure HTTPS**: All communications encrypted and authenticated
- **Managed Identity**: Azure-native authentication, no credential management

## Components

### 1. Custom MCP (`/custom-mcp`)
- **FastMCP Server** with HTTP transport
- **Contoso Tools** (contoso_tools.py):
  - get_customer_detail
  - get_all_customers
  - update_customer_profile
  - get_customer_orders
  - pay_invoice
  - get_subscription_info
  - And more...
- **SQLite Database** (contoso.db): 1.4 MB, bundled in Docker image
- **Deployment**: Azure Container Apps public endpoint

### 2. Agent (`/my-hosted-agent`)
- **Azure AI Agent** configured for customer support
- **Prompt Engineering**: Tuned for Contoso customer service scenarios
- **MCP Integration**: Connects to custom Contoso MCP via HTTPS
- **Azure Deployment**: Deployed via `azd up`

## Prerequisites

- Azure subscription
- [Azure Developer CLI (azd)](https://aka.ms/install-azd)
- Docker (for local testing)
- Python 3.11+

## Deployment

### Deploy MCP Service

```bash
cd custom-mcp
pwsh deploy-container-app.ps1
```

### Deploy Agent

```bash
cd my-hosted-agent
azd up
```

## Testing

### Using Azure Portal Agent Playground

1. After `azd up`, visit the Agent playground URL provided in the output
2. Test with queries like:
   - "Tell me the details of customer with ID 1"
   - "What are the orders for customer 5?"
   - "Show me pending invoices for customer 3"

### Using Azure SDK (Python)

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

client = AIProjectClient(
    endpoint="https://ai-account-icwwbtncyhx5a.services.ai.azure.com/api/projects/ai-project-testv2HA",
    credential=DefaultAzureCredential(),
)

agent = client.agents.get("msft-learn-mcp-agent")
openai_client = client.get_openai_client()

response = openai_client.responses.create(
    input=[{"role": "user", "content": "Tell me about customer 1"}],
    extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
)

print(response.output_text)
```

## File Structure

```
hosted-agent-workshop/
├── custom-mcp/                     # Custom MCP service
│   ├── main.py                     # FastMCP server
│   ├── contoso_tools.py            # Customer tools
│   ├── Dockerfile                  # Container image
│   ├── requirements.txt            # Python dependencies
│   └── data/
│       └── contoso.db              # Customer database
├── my-hosted-agent/                # Agent deployment
│   ├── azure.yaml                  # Deployment config
│   ├── README.md                   # Agent documentation
│   ├── src/
│   │   └── msft-learn-mcp-agent/
│   │       └── main.py             # Agent code
│   └── infra/                      # Infrastructure as code
│       ├── main.bicep
│       ├── main.parameters.json
│       └── core/                   # Azure resource definitions
├── deploy-container-app.ps1        # MCP deployment script
└── README.md                       # This file
```

## Configuration

### Azure AI Project Endpoint
Set in `my-hosted-agent/azure.yaml`:
```yaml
environment_variables:
  - name: AZURE_AI_PROJECT_ENDPOINT
    value: "https://ai-account-icwwbtncyhx5a.services.ai.azure.com/api/projects/ai-project-testv2HA"
```

### MCP URL
Configured in `my-hosted-agent/src/msft-learn-mcp-agent/main.py`:
```python
url="https://contoso-mcp.gentlesky-f07b735a.northcentralus.azurecontainerapps.io/mcp"
```

## Production Considerations

- **Database**: Replace `contoso.db` with production customer data
- **Scaling**: Configure min/max replicas in `azure.yaml`
- **Security**: Use Azure Key Vault for secrets
- **Monitoring**: Application Insights logs in Azure portal
- **Authentication**: Uses Azure Managed Identity (no API keys needed)

## Support

For issues or questions, check:
- Azure Container Apps logs: `az containerapp logs show -n contoso-mcp -g rg-testv2HA`
- Agent playground in Azure Portal
- Application Insights metrics

  - select your subscription when prompted.
  - select `North Central US` region.
  - select `GlobalStandard` for mode SKU.
  - deployment name of model cab be left as default. (gpt-4o-mini)
  - container memory, CPU, and replicas can be left as default. (2GB, 1 CPU, 1 min replica and 3 max replicas)

4. Provision Microsoft Foundry and the sample agent:

    ```shell
    azd up
    ```

5. Open Microsoft [Foundry portal](https://ai.azure.com) and test the agent
  - Note: azd up creates new Microsoft Foundry account. Navigate to your Microsoft Foundry (should be listed under resource group `rg-<username>-hosted-agent` you specified in step 1).

## Resource Clean-up

- **Deleting Resources:**
  To delete all associated resources and shut down the application, execute the following command:
  
    ```bash
    azd down
    ```

    Please note that this process may take up to 20 minutes to complete.

⚠️ Alternatively, you can delete the resource group directly from the Azure Portal to clean up resources.
