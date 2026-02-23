<#
.SYNOPSIS
    Provisions an Azure Durable Task Scheduler (DTS) resource and task hub
    for the Fraud Detection Workshop demo.

.DESCRIPTION
    This script:
    1. Installs the `durabletask` Azure CLI extension (if missing)
    2. Creates a resource group (if it doesn't already exist)
    3. Creates a DTS Scheduler (Consumption SKU — free-tier preview)
    4. Creates a Task Hub inside the scheduler
    5. Assigns "Durable Task Data Contributor" RBAC to the current user
    6. Outputs the DTS_ENDPOINT and DTS_TASKHUB values for .env

.PARAMETER ResourceGroup
    Name of the Azure resource group. Default: "rg-fraud-workshop"

.PARAMETER Location
    Azure region. Default: "northcentralus"
    Supported regions: northcentralus, westus2, westus3, eastus, etc.

.PARAMETER SchedulerName
    Name of the DTS Scheduler. Default: "dts-fraud-workshop"

.PARAMETER TaskHubName
    Name of the Task Hub. Default: "fraud-detection"

.PARAMETER SkuName
    SKU for the scheduler. Default: "consumption" (free preview).
    Use "dedicated" for production (takes ~15min to provision).

.EXAMPLE
    .\provision_dts.ps1
    .\provision_dts.ps1 -Location eastus -SchedulerName my-scheduler
    .\provision_dts.ps1 -SkuName dedicated
#>

param(
    [string]$ResourceGroup = "rg-fraud-workshop",
    [string]$Location = "northcentralus",
    [string]$SchedulerName = "dts-fraud-workshop",
    [string]$TaskHubName = "fraud-detection",
    [string]$SkuName = "consumption"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Azure Durable Task Scheduler Provisioning" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 0. Verify Azure CLI login ───────────────────────────────────────────────
Write-Host "[0/5] Checking Azure CLI login..." -ForegroundColor Yellow
try {
    $account = az account show --output json 2>&1 | ConvertFrom-Json
    $subscriptionId = $account.id
    $userName = $account.user.name
    Write-Host "  Logged in as: $userName" -ForegroundColor Green
    Write-Host "  Subscription: $($account.name) ($subscriptionId)" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR: Not logged in. Run 'az login' first." -ForegroundColor Red
    exit 1
}

# ── 1. Install durabletask CLI extension ─────────────────────────────────────
Write-Host ""
Write-Host "[1/5] Installing durabletask CLI extension..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
$extCheck = az extension show --name durabletask --query "name" -o tsv 2>$null
$ErrorActionPreference = "Stop"
if ($extCheck -eq "durabletask") {
    Write-Host "  Already installed." -ForegroundColor Green
}
else {
    az extension add --name durabletask --yes 2>$null
    Write-Host "  Installed." -ForegroundColor Green
}
$ErrorActionPreference = "Stop"

# ── 2. Create resource group ────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Creating resource group '$ResourceGroup' in '$Location'..." -ForegroundColor Yellow
$rgExists = az group exists --name $ResourceGroup 2>$null
if ($rgExists -eq "true") {
    Write-Host "  Resource group already exists." -ForegroundColor Green
}
else {
    az group create --name $ResourceGroup --location $Location --output none
    Write-Host "  Created." -ForegroundColor Green
}

# ── 3. Create DTS Scheduler ────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Creating DTS Scheduler '$SchedulerName' ($SkuName SKU)..." -ForegroundColor Yellow
Write-Host "  This may take 5-15 minutes..." -ForegroundColor DarkYellow

$schedulerArgs = @(
    "durabletask", "scheduler", "create",
    "--name", $SchedulerName,
    "--resource-group", $ResourceGroup,
    "--location", $Location,
    "--ip-allowlist", "[0.0.0.0/0]",
    "--sku-name", $SkuName
)
if ($SkuName -eq "dedicated") {
    $schedulerArgs += @("--sku-capacity", "1")
}

$ErrorActionPreference = "Continue"
$schedulerJson = az @schedulerArgs --output json 2>&1 | Where-Object { $_ -notmatch "^WARNING:" -and $_ -notmatch "^$" }
$ErrorActionPreference = "Stop"

$scheduler = $schedulerJson | Out-String | ConvertFrom-Json

$endpoint = $scheduler.properties.endpoint
if (-not $endpoint) {
    # If creation returned quickly, the scheduler may already exist — try show
    $ErrorActionPreference = "Continue"
    $schedulerJson = az durabletask scheduler show --name $SchedulerName --resource-group $ResourceGroup --output json 2>&1 | Where-Object { $_ -notmatch "^WARNING:" }
    $ErrorActionPreference = "Stop"
    $scheduler = $schedulerJson | Out-String | ConvertFrom-Json
    $endpoint = $scheduler.properties.endpoint
}

Write-Host "  Scheduler endpoint: $endpoint" -ForegroundColor Green
Write-Host "  Provisioning state: $($scheduler.properties.provisioningState)" -ForegroundColor Green

# ── 4. Create Task Hub ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Creating Task Hub '$TaskHubName'..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
az durabletask taskhub create --resource-group $ResourceGroup --scheduler-name $SchedulerName --name $TaskHubName --output none 2>$null
$ErrorActionPreference = "Stop"
Write-Host "  Created." -ForegroundColor Green

# ── 5. Assign RBAC to current user ──────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Assigning 'Durable Task Data Contributor' role to $userName..." -ForegroundColor Yellow

$scope = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.DurableTask/schedulers/$SchedulerName"

# Get current user's object ID
$ErrorActionPreference = "Continue"
$assignee = az ad signed-in-user show --query "id" -o tsv 2>$null
$ErrorActionPreference = "Stop"

if ($assignee) {
    Write-Host "  User object ID: $assignee" -ForegroundColor Gray
    $ErrorActionPreference = "Continue"
    $existing = az role assignment list --assignee $assignee --scope $scope --role "Durable Task Data Contributor" --query "length(@)" -o tsv 2>$null
    $ErrorActionPreference = "Stop"
    if ($existing -gt 0) {
        Write-Host "  Role already assigned." -ForegroundColor Green
    }
    else {
        # Use --assignee-object-id + --assignee-principal-type for guest/EXT# users
        $ErrorActionPreference = "Continue"
        az role assignment create `
            --assignee-object-id $assignee `
            --assignee-principal-type "User" `
            --role "Durable Task Data Contributor" `
            --scope $scope `
            --output none 2>&1 | Where-Object { $_ -notmatch "^WARNING:" }
        $ErrorActionPreference = "Stop"
        Write-Host "  Role assigned. (RBAC propagation may take 5-10 minutes)" -ForegroundColor Green
    }
}
else {
    Write-Host "  WARNING: Could not determine user object ID. Assign the role manually:" -ForegroundColor DarkYellow
    Write-Host "    az role assignment create --assignee-object-id <oid> --assignee-principal-type User --role 'Durable Task Data Contributor' --scope '$scope'" -ForegroundColor DarkYellow
}

# ── Summary ──────────────────────────────────────────────────────────────────
$dashboardUrl = "https://dashboard.durabletask.io/?endpoint=$endpoint&taskhub=$TaskHubName"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " PROVISIONING COMPLETE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add these to your .env file:" -ForegroundColor Green
Write-Host ""
Write-Host "  DTS_ENDPOINT=$endpoint" -ForegroundColor White
Write-Host "  DTS_TASKHUB=$TaskHubName" -ForegroundColor White
Write-Host ""
Write-Host "Dashboard: $dashboardUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "To tear down later:" -ForegroundColor DarkYellow
Write-Host "  az group delete --name $ResourceGroup --yes --no-wait" -ForegroundColor DarkYellow
Write-Host ""
