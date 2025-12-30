param cosmosDbAccountName string = 'mcp-contoso-cosmos'
param userPrincipalId string

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' existing = {
  name: cosmosDbAccountName
}

// Role Assignment for Cosmos DB Built-in Data Contributor to current user
resource cosmosAccessRoleCU 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = {
  name: guid('00000000-0000-0000-0000-000000000002', userPrincipalId, cosmosDb.id)
  parent: cosmosDb
  properties: {
    principalId: userPrincipalId
    roleDefinitionId: resourceId('Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions', cosmosDb.name, '00000000-0000-0000-0000-000000000002')
    scope: cosmosDb.id
  }
}

output roleAssignmentId string = cosmosAccessRoleCU.id
output cosmosDbId string = cosmosDb.id
