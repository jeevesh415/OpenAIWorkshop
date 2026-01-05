# Quickstart: Deploy Contoso Customer Support Agent

This guide walks you through deploying the Contoso Customer Support Agent to Azure Foundry in about 15-20 minutes.

## 📋 Prerequisites

Before you start, ensure you have:

1. **Azure Subscription** - [Create one free](https://azure.microsoft.com/free/)
2. **Azure Developer CLI (azd)** - [Install here](https://aka.ms/install-azd)
   - Windows: `winget install microsoft.azd`
   - macOS: `brew tap azure/azd && brew install azd`
   - Linux: `curl -fsSL https://aka.ms/install-azd.sh | bash`
3. **MCP Service URL** (Required for the agent to call tools)
   - If you have a custom MCP, host it in Azure Container Apps and copy the public ingress URL (append `/mcp`).
   - Example: `https://<your-app>.<region>.azurecontainerapps.io/mcp`
4. **Docker** (optional, for local testing) - [Install here](https://docs.docker.com/get-docker/)
5. **Python 3.9+** (optional, for local development)

## 🚀 Deployment Steps

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourorg/Hosted_Agents.git
cd Hosted_Agents
```

### Step 2: Initialize Azure Developer CLI

```bash
azd init --template .
```

When prompted:
- **Enter a new environment name**: `contoso-dev` (or your preferred name)
- This creates a `.azure/contoso-dev/` folder with your configuration

### Step 3: Configure Your Environment

Copy the example configuration file:

```bash
cp .env.example .env
```

Edit `.env` and update:
```bash
# Your Azure Subscription ID (find in Azure Portal)
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Choose a unique resource group name (e.g., rg-contoso-dev-001)
AZURE_RESOURCE_GROUP=rg-contoso-dev-001

# Azure region (e.g., eastus, northcentralus)
AZURE_LOCATION=northcentralus

# MCP service (if using a custom MCP)
# Provide the full URL with '/mcp' suffix
MCP_SERVICE_URL=https://<your-mcp-service-url>/mcp
```

### Step 4: Authenticate with Azure

```bash
azd auth login
```

This opens your browser to sign in. Once authenticated, return to the terminal.

### Step 5: Provision and Deploy

```bash
azd up
```

This will:
1. Create Azure resources (Foundry project, Container Registry, Container Apps, etc.)
2. Build Docker images for the agent and MCP service
3. Deploy both services to Azure
4. Display the MCP Service URL (you'll need this in the next step)

⏱️ **This takes 5-10 minutes.** Grab a coffee!

**⚠️ IMPORTANT - MCP Service URL**

When `azd up` completes, look for:
```
MCP Service deployed at:
https://contoso-mcp-<random-id>.northcentralus.azurecontainerapps.io
```

Save this URL - you'll need it in the next step!

### Step 6: Update Placeholder Values

Now that deployment is complete, you MUST replace placeholder values with your actual Azure resources:

1. **Update `.env` file** (if not already set):
   ```bash
   # Replace <your-mcp-service-url> with your custom MCP URL
   MCP_SERVICE_URL=https://contoso-mcp-<random-id>.northcentralus.azurecontainerapps.io/mcp
   ```

2. **Update `contoso-support-agent/main.py`** (only if you prefer hardcoding the URL):
   ```bash
   # Find line with "<your-mcp-service-url>" and replace with your actual URL
   url=os.environ.get("MCP_SERVICE_URL", "<your-mcp-service-url>/mcp")
   ```

3. **Redeploy with updated values**:
   ```bash
   azd up
   ```

### Step 7: Test Your Agent

Once redeployment completes, you'll see:

```
Foundry Project: https://ai.azure.com/projects/<project-id>
```

1. Open the URL in your browser
2. Sign in with your Azure account
3. Click on your agent
4. Type a test query:
   - "What are my orders?"
   - "What is my account balance?"
   - "Show me my subscription details"
5. The agent will use the MCP service to query the example data and respond

## 🔧 Local Testing (Optional)

Want to test locally before deploying? Follow these steps:

### 1. Start the MCP Service

```bash
cd custom-mcp
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env if needed

# Start the service
python mcp_service.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Test MCP in Another Terminal

```bash
curl http://localhost:8000/mcp/tools
```

You should see the list of available tools.

### 3. Test the Agent

In a third terminal:

```bash
cd contoso-support-agent
pip install -r requirements.txt

# Set environment variables (Windows PowerShell examples below)
# $env:AZURE_AI_PROJECT_ENDPOINT="http://localhost:8080"
# $env:AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o-mini"
# $env:MCP_SERVICE_URL="http://localhost:8000/mcp"

python main.py
```

## 📚 Next Steps

### Customize for Your Use Case

1. **Update Agent Instructions**
   - Edit: `contoso-support-agent/main.py`
   - Change the `instructions` parameter to fit your domain

2. **Implement Your Tools**
   - Edit: `custom-mcp/contoso_tools.py`
   - Replace example functions with your business logic

3. **Use Your Data**
   - Replace: `custom-mcp/data/contoso.db`
   - Either import your data to SQLite, or modify tools to call your database/API

4. **Redeploy**
   ```bash
   azd up
   ```

### Monitor and Debug

**View Logs**:
```bash
azd monitor
```

This opens Application Insights showing logs from your agent and MCP service.

**Check Deployment Status**:
```bash
azd show
```

### Scale for Production

When ready for production:

1. **Enable Security** - See security checklist in README.md
2. **Configure Monitoring** - Set up alerts in Application Insights
3. **Set Resource Limits** - Update `infra/main.parameters.json` for CPU/memory
4. **Enable HTTPS** - Use Azure Application Gateway or Front Door
5. **Add Authentication** - Implement MCP token validation

## 🆘 Troubleshooting

### "azd command not found"
- Make sure you installed Azure Developer CLI: `azd version`
- If installed, restart your terminal

### "Authentication failed"
```bash
azd auth logout
azd auth login
```

### "Deployment failed with resource conflict"
- Try a different resource group name
- Make sure it doesn't already exist in your subscription

### "Agent can't reach MCP service"
- Check MCP service URL in agent logs (App Insights)
- Verify MCP container is running: `az container logs ...`
- Ensure Network/firewall allows the connection

### "Tools returning errors"
- Check MCP service logs in Application Insights
- Verify database file exists: `custom-mcp/data/contoso.db`
- Test MCP locally first (see Local Testing section)

### "Still having issues?"
1. Check the deployment logs: `azd monitor`
2. Review [Azure Foundry docs](https://learn.microsoft.com/en-us/azure/ai-foundry)
3. Open an issue on GitHub with error logs

## 🧹 Cleanup

To delete all Azure resources (prevents future charges):

```bash
azd down
```

⚠️ **This will delete ALL resources in your resource group!**

## 📖 Additional Resources

- [Azure Foundry Documentation](https://aka.ms/azure-ai-foundry)
- [Agent Framework Guide](https://github.com/microsoft/agent-framework)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Azure Developer CLI Docs](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/)

---

**Having trouble?** See the main [README.md](README.md) or open an issue on GitHub!
