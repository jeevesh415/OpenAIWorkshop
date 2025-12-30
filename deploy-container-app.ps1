#!/usr/bin/env pwsh
# Deploy MCP Container App to Azure

$ResourceGroup = "rg-testv2HA"
$Location = "northcentralus"
$ACREndpoint = "cricwwbtncyhx5a.azurecr.io"
$ContainerAppName = "contoso-mcp"
$AcrImage = "$ACREndpoint/contoso-mcp:latest"
$EnvName = "cae-testv2HA"

Write-Host "========================================================"
Write-Host "DEPLOYING MCP CONTAINER APP TO AZURE"
Write-Host "========================================================"
Write-Host ""

# Step 1: Create Container App Environment
Write-Host "1. Creating/checking Container App Environment..."
az containerapp env create `
    --name $EnvName `
    --resource-group $ResourceGroup `
    --location $Location
Write-Host "✓ Container App Environment ready"

# Step 2: Create Container App
Write-Host ""
Write-Host "2. Creating Container App..."
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
    --memory 1Gi

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Container App creation failed"
    exit 1
}
Write-Host "✓ Container App created"

# Step 3: Get the public URL
Write-Host ""
Write-Host "3. Getting public URL..."
$AppUrl = az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn `
    --output tsv

Write-Host ""
Write-Host "========================================================"
Write-Host "✓ DEPLOYMENT COMPLETE"
Write-Host "========================================================"
Write-Host ""
Write-Host "Public MCP URL:"
Write-Host "  https://$AppUrl/mcp"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Wait 30-60 seconds for Container App to fully start"
Write-Host "2. Test with: curl https://$AppUrl/"
Write-Host "3. Update agent config to use: https://$AppUrl/mcp"
Write-Host ""
