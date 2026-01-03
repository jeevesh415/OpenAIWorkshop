#!/usr/bin/env pwsh
# Deploy MCP to Azure Container Apps

param(
    [string]$ResourceGroup = "rg-testv2HA",
    [string]$Location = "northcentralus",
    [string]$ACREndpoint = "cricwwbtncyhx5a.azurecr.io",
    [string]$ContainerAppName = "contoso-mcp",
    [string]$ImageName = "contoso-mcp",
    [string]$EnvName = "cae-testv2HA"
)

Write-Host "========================================================"
Write-Host "DEPLOYING MCP TO AZURE CONTAINER APPS"
Write-Host "========================================================"
Write-Host ""

# Step 1: Create Container App Environment (if needed)
Write-Host "1. Checking Container App Environment..."
$EnvExists = az containerapp env list --resource-group $ResourceGroup --query "[?name=='$EnvName']" --output json | ConvertFrom-Json
if (-not $EnvExists -or $EnvExists.Count -eq 0) {
    Write-Host "   Creating Container App Environment: $EnvName..."
    az containerapp env create `
        --name $EnvName `
        --resource-group $ResourceGroup `
        --location $Location
    Write-Host "✓ Container App Environment created"
} else {
    Write-Host "✓ Container App Environment already exists: $EnvName"
}

# Step 2: Create or update Container App
Write-Host ""
Write-Host "2. Creating/updating Container App: $ContainerAppName..."
$AcrImage = "$ACREndpoint/$ImageName:latest"

az containerapp create `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --environment $EnvName `
    --image $AcrImage `
    --target-port 8000 `
    --ingress external `
    --registry-server $ACREndpoint `
    --registry-identity system `
    --cpu 0.5 `
    --memory 1Gi `
    --query properties.configuration.ingress.fqdn `
    --output tsv

if ($LASTEXITCODE -ne 0) {
    # If create fails, try update instead (container app might already exist)
    Write-Host "   Updating existing Container App..."
    az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroup `
        --image $AcrImage
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Container App creation/update failed"
        exit 1
    }
}
Write-Host "✓ Container App created/updated"

# Step 3: Get public URL
Write-Host ""
Write-Host "3. Retrieving public URL..."
$AppUrl = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn `
    --output tsv

if (-not $AppUrl) {
    Write-Host "✗ Failed to get FQDN"
    exit 1
}

Write-Host ""
Write-Host "========================================================"
Write-Host "✓ MCP DEPLOYED SUCCESSFULLY"
Write-Host "========================================================"
Write-Host ""
Write-Host "Public MCP URL:"
Write-Host "  https://$AppUrl/mcp"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Wait 30-60 seconds for container startup"
Write-Host "2. Update msft-docs-agent/main.py to use: https://$AppUrl/mcp"
Write-Host "3. Test with: curl https://$AppUrl/"
Write-Host "4. Run: azd up (from msft-docs-agent directory)"
Write-Host ""
