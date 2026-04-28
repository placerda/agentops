// AgentOps E2E — per-run ephemeral resources.
//
// Deploys an Azure Container Apps app running the AgentOps E2E hello-agent
// (Microsoft Agent Framework + Azure OpenAI) so the http-aca scenario can
// exercise AgentOps' http-json invocation path against a real LLM.
//
// Auth flow (no secrets):
//   1. Create a User-Assigned Managed Identity (UAMI).
//   2. Grant UAMI:
//        - AcrPull on the long-lived ACR (so ACA can pull the image).
//        - Cognitive Services OpenAI User on AI Services (so the agent can
//          call Azure OpenAI via Entra ID, no API keys).
//   3. Attach the UAMI to the ACA app and use it as the registry identity.
//
// All per-run resources are named with a unique suffix derived from
// github.run_id so multiple workflow runs do not collide and teardown is a
// straight `az containerapp delete` + `az identity delete`.

targetScope = 'resourceGroup'

@description('Azure region for the ACA app + UAMI.')
param location string = resourceGroup().location

@description('Resource id of the long-lived Container Apps managed environment from bootstrap.bicep.')
param acaEnvironmentId string

@description('Unique suffix for this workflow run (e.g. github.run_id).')
param suffix string

@description('Fully qualified container image (e.g. <acr>.azurecr.io/agentops-e2e/hello-agent:run123).')
param image string

@description('Name (not id) of the long-lived ACR created by bootstrap.bicep — used to scope AcrPull.')
param acrName string

@description('Login server of the long-lived ACR (e.g. <acr>.azurecr.io) — used by the registry config.')
param acrLoginServer string

@description('Name of the AI Services / Foundry account from bootstrap.bicep — scope for Cognitive Services OpenAI User.')
param aiServicesName string

@description('Azure OpenAI endpoint URL (https://<account>.cognitiveservices.azure.com/ or .openai.azure.com/).')
param azureOpenAiEndpoint string

@description('Azure OpenAI deployment name (e.g. gpt-4o-mini).')
param azureOpenAiDeployment string

@description('Container target port. The hello-agent listens on 8080 by default.')
param targetPort int = 8080

var appName = 'aca-agent-${suffix}'
var uamiName = 'uami-${suffix}'

// Built-in role definition ids (subscription-scoped).
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

resource openAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, uami.id, 'CognitiveServicesOpenAIUser')
  scope: aiServices
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
  }
}

resource agentApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  dependsOn: [
    acrPullAssignment
    openAiUserAssignment
  ]
  properties: {
    managedEnvironmentId: acaEnvironmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: acrLoginServer
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'agent'
          image: image
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAiDeployment
            }
            {
              // DefaultAzureCredential needs the UAMI client id when more than
              // one identity could be picked up.
              name: 'AZURE_CLIENT_ID'
              value: uami.properties.clientId
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

@description('Public ingress URL for the hello-agent — used by the http-aca scenario.')
output agentUrl string = 'https://${agentApp.properties.configuration.ingress.fqdn}'

@description('App name (for teardown).')
output appName string = appName

@description('UAMI name (for teardown).')
output uamiName string = uamiName
