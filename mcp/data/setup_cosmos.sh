#!/bin/bash
#
# Complete setup script for Cosmos DB - provisions account, assigns roles, and populates data.
#
# This script performs the following steps:
# 1. Creates resource group (if it doesn't exist)
# 2. Deploys Cosmos DB account with vector search capabilities
# 3. Assigns RBAC role to current user
# 4. Waits for role propagation
# 5. Runs data population script
#
# Usage:
#   ./setup_cosmos.sh [RESOURCE_GROUP] [LOCATION] [ACCOUNT_NAME] [DATABASE_NAME]
#
# Examples:
#   ./setup_cosmos.sh
#   ./setup_cosmos.sh my-rg eastus my-cosmos contoso

set -e  # Exit on error

# Default parameters
RESOURCE_GROUP="${1:-mcp-demo-rg}"
LOCATION="${2:-westus}"
ACCOUNT_NAME="${3:-mcp-contoso-cosmos}"
DATABASE_NAME="${4:-contoso}"

# Color codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
WHITE='\033[0;37m'
NC='\033[0m' # No Color

# Output functions
print_step() {
    echo -e "\n${CYAN}======================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}======================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${WHITE}  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Change to script directory
cd "$(dirname "$0")"

print_step "COSMOS DB SETUP SCRIPT"
print_info "Resource Group: $RESOURCE_GROUP"
print_info "Location: $LOCATION"
print_info "Account Name: $ACCOUNT_NAME"
print_info "Database Name: $DATABASE_NAME"

# Step 1: Check Azure CLI is logged in
print_step "Step 1: Verifying Azure CLI Authentication"
if ! ACCOUNT_INFO=$(az account show 2>/dev/null); then
    print_error "Not logged in to Azure CLI"
    print_info "Please run: az login"
    exit 1
fi

USER_NAME=$(echo "$ACCOUNT_INFO" | jq -r '.user.name')
SUBSCRIPTION_NAME=$(echo "$ACCOUNT_INFO" | jq -r '.name')
SUBSCRIPTION_ID=$(echo "$ACCOUNT_INFO" | jq -r '.id')

print_success "Logged in as: $USER_NAME"
print_info "Subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# Get current user principal ID
USER_TYPE=$(echo "$ACCOUNT_INFO" | jq -r '.user.type')
if [ "$USER_TYPE" = "user" ]; then
    USER_PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)
else
    USER_PRINCIPAL_ID=$USER_NAME
fi
print_info "User Principal ID: $USER_PRINCIPAL_ID"

# Step 2: Create Resource Group
print_step "Step 2: Creating Resource Group"
if az group exists --name "$RESOURCE_GROUP" | grep -q "true"; then
    print_info "Resource group '$RESOURCE_GROUP' already exists"
else
    print_info "Creating resource group '$RESOURCE_GROUP' in $LOCATION..."
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
    print_success "Resource group created"
fi

# Step 3: Deploy Cosmos DB Account and Containers
print_step "Step 3: Deploying Cosmos DB Account and Containers"
print_info "This may take 3-5 minutes..."

DEPLOYMENT_NAME="cosmosdb-$(date +%Y%m%d%H%M%S)"
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$DEPLOYMENT_NAME" \
    --template-file "cosmosdb.bicep" \
    --output none

print_success "Cosmos DB account and containers deployed"

# Step 4: Assign RBAC Role to Current User
print_step "Step 4: Assigning RBAC Role to Current User"
print_info "Assigning Cosmos DB Data Contributor role..."

RBAC_DEPLOYMENT_NAME="cosmosdb-rbac-$(date +%Y%m%d%H%M%S)"
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$RBAC_DEPLOYMENT_NAME" \
    --template-file "cosmosdb-rbac.bicep" \
    --parameters userPrincipalId="$USER_PRINCIPAL_ID" \
    --output none

print_success "RBAC role assigned"

# Step 5: Get Cosmos DB Endpoint
print_step "Step 5: Retrieving Cosmos DB Connection Details"
COSMOS_ENDPOINT=$(az cosmosdb show \
    --name "$ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query documentEndpoint \
    --output tsv)

print_info "Cosmos Endpoint: $COSMOS_ENDPOINT"

# Step 6: Update .env file
print_step "Step 6: Updating .env File"
ENV_PATH="../.env"

if [ -f "$ENV_PATH" ]; then
    # Create backup
    cp "$ENV_PATH" "$ENV_PATH.bak"
    
    # Update or add COSMOS_ENDPOINT
    if grep -q "^COSMOS_ENDPOINT=" "$ENV_PATH"; then
        sed -i.tmp "s|^COSMOS_ENDPOINT=.*|COSMOS_ENDPOINT=\"$COSMOS_ENDPOINT\"|" "$ENV_PATH"
        rm -f "$ENV_PATH.tmp"
    else
        echo "COSMOS_ENDPOINT=\"$COSMOS_ENDPOINT\"" >> "$ENV_PATH"
    fi
    
    # Update or add COSMOS_DATABASE_NAME
    if grep -q "^COSMOS_DATABASE_NAME=" "$ENV_PATH"; then
        sed -i.tmp "s|^COSMOS_DATABASE_NAME=.*|COSMOS_DATABASE_NAME=\"$DATABASE_NAME\"|" "$ENV_PATH"
        rm -f "$ENV_PATH.tmp"
    else
        echo "COSMOS_DATABASE_NAME=\"$DATABASE_NAME\"" >> "$ENV_PATH"
    fi
    
    print_success ".env file updated (backup saved as .env.bak)"
else
    print_warning ".env file not found at $ENV_PATH"
fi

# Step 7: Wait for RBAC Propagation
print_step "Step 7: Waiting for RBAC Role Propagation"
print_info "Waiting 30 seconds for role assignment to propagate..."
sleep 30
print_success "Role should now be active"

# Step 8: Populate Data
print_step "Step 8: Populating Cosmos DB with Data"
print_info "This may take several minutes to generate embeddings and insert data..."

if python3 create_cosmos_db.py; then
    print_success "Data population completed successfully"
else
    print_error "Data population failed with exit code $?"
    exit 1
fi

# Final Summary
print_step "SETUP COMPLETE!"
print_success "Cosmos DB is ready to use"
print_info ""
print_info "Connection Details:"
print_info "  Endpoint: $COSMOS_ENDPOINT"
print_info "  Database: $DATABASE_NAME"
print_info "  Authentication: Azure CLI (Current User)"
print_info ""
print_info "Next steps:"
print_info "  1. Update mcp_service.py to use Cosmos DB"
print_info "  2. Test the MCP service with: python mcp_service.py"
