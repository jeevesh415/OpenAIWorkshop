param location string = resourceGroup().location
param accountName string = 'mcp-contoso-cosmos'
param databaseName string = 'contoso'
param tags object = {}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: false  // Enable key-based authentication
    locations: [
      {
        failoverPriority: 0
        isZoneRedundant: false
        locationName: location
      }
    ]
    capabilities: [
      {
        name: 'EnableNoSQLVectorSearch'
      }
    ]
  }
  tags: tags
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDb
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
  tags: tags
}

// Customers container
resource customersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Customers'
  properties: {
    resource: {
      id: 'Customers'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Products container
resource productsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Products'
  properties: {
    resource: {
      id: 'Products'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Subscriptions container
resource subscriptionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Subscriptions'
  properties: {
    resource: {
      id: 'Subscriptions'
      partitionKey: {
        paths: ['/customer_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Invoices container
resource invoicesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Invoices'
  properties: {
    resource: {
      id: 'Invoices'
      partitionKey: {
        paths: ['/subscription_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Payments container
resource paymentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Payments'
  properties: {
    resource: {
      id: 'Payments'
      partitionKey: {
        paths: ['/invoice_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Promotions container
resource promotionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Promotions'
  properties: {
    resource: {
      id: 'Promotions'
      partitionKey: {
        paths: ['/product_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// SecurityLogs container
resource securityLogsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'SecurityLogs'
  properties: {
    resource: {
      id: 'SecurityLogs'
      partitionKey: {
        paths: ['/customer_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// Orders container
resource ordersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'Orders'
  properties: {
    resource: {
      id: 'Orders'
      partitionKey: {
        paths: ['/customer_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// SupportTickets container
resource supportTicketsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'SupportTickets'
  properties: {
    resource: {
      id: 'SupportTickets'
      partitionKey: {
        paths: ['/customer_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// DataUsage container
resource dataUsageContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'DataUsage'
  properties: {
    resource: {
      id: 'DataUsage'
      partitionKey: {
        paths: ['/subscription_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// ServiceIncidents container
resource serviceIncidentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'ServiceIncidents'
  properties: {
    resource: {
      id: 'ServiceIncidents'
      partitionKey: {
        paths: ['/subscription_id']
        kind: 'Hash'
        version: 2
      }
    }
  }
  tags: tags
}

// KnowledgeDocuments container with vector search
resource knowledgeDocumentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-12-01-preview' = {
  parent: database
  name: 'KnowledgeDocuments'
  properties: {
    resource: {
      id: 'KnowledgeDocuments'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
          {
            path: '/content_vector/*'
          }
        ]
        vectorIndexes: [
          {
            path: '/content_vector'
            type: 'diskANN'
          }
        ]
      }
      vectorEmbeddingPolicy: {
        vectorEmbeddings: [
          {
            path: '/content_vector'
            dataType: 'float32'
            distanceFunction: 'cosine'
            dimensions: 1536
          }
        ]
      }
    }
  }
  tags: tags
}

output endpoint string = cosmosDb.properties.documentEndpoint
output accountName string = cosmosDb.name
output databaseName string = database.name
output resourceId string = cosmosDb.id
