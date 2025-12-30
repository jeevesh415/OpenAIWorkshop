#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Complete setup script for Cosmos DB - provisions account, assigns roles, and populates data.

.DESCRIPTION
    This script performs the following steps:
    1. Creates resource group (if it doesn't exist)
    2. Deploys Cosmos DB account with vector search capabilities
    3. Assigns RBAC role to current user
    4. Waits for role propagation
    5. Runs data population script

.PARAMETER ResourceGroup
    Name of the resource group (default: mcp-demo-rg)

.PARAMETER Location
    Azure region (default: westus)

.PARAMETER AccountName
    Cosmos DB account name (default: mcp-contoso-cosmos)

.PARAMETER DatabaseName
    Database name (default: contoso)

.EXAMPLE
    .\setup_cosmos.ps1
    .\setup_cosmos.ps1 -ResourceGroup "my-rg" -Location "eastus" -AccountName "my-cosmos"
#>

param(
    [string]$ResourceGroup = "mcp-demo-rg",
    [string]$Location = "westus",
    [string]$AccountName = "mcp-contoso-cosmos",
    [string]$DatabaseName = "contoso"
)

# Color output functions
function Write-Step {
    param([string]$Message)
    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "======================================================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-ErrorMessage {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Error handling
$ErrorActionPreference = "Stop"

try {
    Write-Step "COSMOS DB SETUP SCRIPT"
    Write-Info "Resource Group: $ResourceGroup"
    Write-Info "Location: $Location"
    Write-Info "Account Name: $AccountName"
    Write-Info "Database Name: $DatabaseName"

    # Step 1: Check Azure CLI is logged in
    Write-Step "Step 1: Verifying Azure CLI Authentication"
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        Write-ErrorMessage "Not logged in to Azure CLI"
        Write-Info "Please run: az login"
        exit 1
    }
    Write-Success "Logged in as: $($account.user.name)"
    Write-Info "Subscription: $($account.name) ($($account.id))"
    
    # Get current user principal ID
    $userPrincipalId = $account.user.name
    if ($account.user.type -eq "user") {
        $signedInUser = az ad signed-in-user show | ConvertFrom-Json
        $userPrincipalId = $signedInUser.id
    }
    Write-Info "User Principal ID: $userPrincipalId"

    # Step 2: Create Resource Group
    Write-Step "Step 2: Creating Resource Group"
    $rgExists = az group exists --name $ResourceGroup
    if ($rgExists -eq "true") {
        Write-Info "Resource group '$ResourceGroup' already exists"
    } else {
        Write-Info "Creating resource group '$ResourceGroup' in $Location..."
        az group create --name $ResourceGroup --location $Location --output none
        Write-Success "Resource group created"
    }

    # Step 3: Deploy Cosmos DB Account and Containers
    Write-Step "Step 3: Deploying Cosmos DB Account and Containers"
    Write-Info "This may take 3-5 minutes..."
    
    $deploymentName = "cosmosdb-$(Get-Date -Format 'yyyyMMddHHmmss')"
    az deployment group create `
        --resource-group $ResourceGroup `
        --name $deploymentName `
        --template-file "cosmosdb.bicep" `
        --output none
    
    Write-Success "Cosmos DB account and containers deployed"

    # Step 4: Assign RBAC Role to Current User
    Write-Step "Step 4: Assigning RBAC Role to Current User"
    Write-Info "Assigning Cosmos DB Data Contributor role..."
    
    $rbacDeploymentName = "cosmosdb-rbac-$(Get-Date -Format 'yyyyMMddHHmmss')"
    az deployment group create `
        --resource-group $ResourceGroup `
        --name $rbacDeploymentName `
        --template-file "cosmosdb-rbac.bicep" `
        --parameters userPrincipalId=$userPrincipalId `
        --output none
    
    Write-Success "RBAC role assigned"

    # Step 5: Get Cosmos DB Endpoint
    Write-Step "Step 5: Retrieving Cosmos DB Connection Details"
    $cosmosEndpoint = az cosmosdb show `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --query documentEndpoint `
        --output tsv
    
    Write-Info "Cosmos Endpoint: $cosmosEndpoint"

    # Step 6: Update .env file
    Write-Step "Step 6: Updating .env File"
    $envPath = Join-Path $PSScriptRoot ".." ".env"
    
    if (Test-Path $envPath) {
        $envContent = Get-Content $envPath -Raw
        
        # Update or add COSMOS_ENDPOINT
        if ($envContent -match 'COSMOS_ENDPOINT=') {
            $envContent = $envContent -replace 'COSMOS_ENDPOINT="[^"]*"', "COSMOS_ENDPOINT=`"$cosmosEndpoint`""
        } else {
            $envContent += "`nCOSMOS_ENDPOINT=`"$cosmosEndpoint`""
        }
        
        # Update or add COSMOS_DATABASE_NAME
        if ($envContent -match 'COSMOS_DATABASE_NAME=') {
            $envContent = $envContent -replace 'COSMOS_DATABASE_NAME="[^"]*"', "COSMOS_DATABASE_NAME=`"$DatabaseName`""
        } else {
            $envContent += "`nCOSMOS_DATABASE_NAME=`"$DatabaseName`""
        }
        
        $envContent | Set-Content $envPath -NoNewline
        Write-Success ".env file updated"
    } else {
        Write-Warning ".env file not found at $envPath"
    }

    # Step 7: Wait for RBAC Propagation
    Write-Step "Step 7: Waiting for RBAC Role Propagation"
    Write-Info "Waiting 30 seconds for role assignment to propagate..."
    Start-Sleep -Seconds 30
    Write-Success "Role should now be active"

    # Step 8: Populate Data
    Write-Step "Step 8: Populating Cosmos DB with Data"
    Write-Info "This may take several minutes to generate embeddings and insert data..."
    
    $scriptPath = Join-Path $PSScriptRoot "create_cosmos_db.py"
    python $scriptPath
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Data population completed successfully"
    } else {
        Write-ErrorMessage "Data population failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    # Final Summary
    Write-Step "SETUP COMPLETE!"
    Write-Success "Cosmos DB is ready to use"
    Write-Info ""
    Write-Info "Connection Details:"
    Write-Info "  Endpoint: $cosmosEndpoint"
    Write-Info "  Database: $DatabaseName"
    Write-Info "  Authentication: Azure CLI (Current User)"
    Write-Info ""
    Write-Info "Next steps:"
    Write-Info "  1. Update mcp_service.py to use Cosmos DB"
    Write-Info "  2. Test the MCP service with: python mcp_service.py"

} catch {
    Write-ErrorMessage "Setup failed: $_"
    exit 1
}
