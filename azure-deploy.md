# Azure Deployment Guide for OSAA SMU Data App

## Prerequisites

1. **Azure Account**: Active Azure subscription
2. **Azure CLI**: Install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
3. **Git**: For version control
4. **Environment Variables**: Set up your environment variables

## Option 1: Azure App Service (Recommended)

### Step 1: Prepare Your Environment Variables

Create a `.env` file locally with your secrets:

```bash
# Azure OpenAI
azure=your_azure_openai_key
azure_endpoint=https://openai-osaa-v2.openai.azure.com/

# ACLED API
acled_email=your_acled_email
acled_key=your_acled_api_key

# App Password
app_password=your_app_password

# LangSmith (optional)
langsmith=your_langsmith_key
```

### Step 2: Set Up Azure Resources

```bash
# Login to Azure
az login

# Create a resource group
az group create --name osaa-smu-data-app-rg --location "East US"

# Create an App Service plan
az appservice plan create --name osaa-smu-data-app-plan --resource-group osaa-smu-data-app-rg --sku B1 --is-linux

# Create the web app
az webapp create --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg --plan osaa-smu-data-app-plan --runtime "PYTHON|3.10"

# Configure the startup command
az webapp config set --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg --startup-file "startup.sh"
```

### Step 3: Configure Environment Variables

```bash
# Set environment variables in Azure
az webapp config appsettings set --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg --settings \
  azure="your_azure_openai_key" \
  azure_endpoint="https://openai-osaa-v2.openai.azure.com/" \
  acled_email="your_acled_email" \
  acled_key="your_acled_api_key" \
  app_password="your_app_password" \
  langsmith="your_langsmith_key"
```

### Step 4: Deploy Your Code

```bash
# Deploy using Azure CLI
az webapp deployment source config-local-git --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg

# Get the deployment URL
az webapp deployment list-publishing-credentials --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg

# Deploy your code
git add .
git commit -m "Initial deployment"
git push azure main
```

## Option 2: Azure Container Instances (Alternative)

### Step 1: Create Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["streamlit", "run", "app.py", "--server.port=8000", "--server.address=0.0.0.0"]
```

### Step 2: Build and Deploy Container

```bash
# Build the container
docker build -t osaa-smu-data-app .

# Tag for Azure Container Registry
docker tag osaa-smu-data-app yourregistry.azurecr.io/osaa-smu-data-app:latest

# Push to registry
docker push yourregistry.azurecr.io/osaa-smu-data-app:latest

# Deploy to Container Instances
az container create \
  --resource-group osaa-smu-data-app-rg \
  --name osaa-smu-data-app-container \
  --image yourregistry.azurecr.io/osaa-smu-data-app:latest \
  --dns-name-label osaa-smu-data-app \
  --ports 8000 \
  --environment-variables \
    azure="your_azure_openai_key" \
    azure_endpoint="https://openai-osaa-v2.openai.azure.com/" \
    acled_email="your_acled_email" \
    acled_key="your_acled_api_key" \
    app_password="your_app_password"
```

## Option 3: Azure Functions (For Serverless)

### Step 1: Create Function App

```bash
# Create storage account
az storage account create --name osaasmudataapp --resource-group osaa-smu-data-app-rg --location "East US" --sku Standard_LRS

# Create function app
az functionapp create --name osaa-smu-data-app-func --resource-group osaa-smu-data-app-rg --consumption-plan-location "East US" --runtime python --runtime-version 3.10 --functions-version 4 --storage-account osaasmudataapp --os-type linux
```

## Security Considerations

### 1. Use Azure Key Vault for Secrets

```bash
# Create Key Vault
az keyvault create --name osaa-smu-keyvault --resource-group osaa-smu-data-app-rg --location "East US"

# Store secrets
az keyvault secret set --vault-name osaa-smu-keyvault --name "azure-openai-key" --value "your_key"
az keyvault secret set --vault-name osaa-smu-keyvault --name "acled-api-key" --value "your_key"
az keyvault secret set --vault-name osaa-smu-keyvault --name "app-password" --value "your_password"
```

### 2. Configure Managed Identity

```bash
# Enable managed identity
az webapp identity assign --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg

# Grant access to Key Vault
az keyvault set-policy --name osaa-smu-keyvault --object-id <managed-identity-object-id> --secret-permissions get list
```

## Monitoring and Logging

### 1. Enable Application Insights

```bash
# Create Application Insights
az monitor app-insights component create --app osaa-smu-data-app-insights --location "East US" --resource-group osaa-smu-data-app-rg --application-type web

# Connect to web app
az webapp config appsettings set --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg --settings \
  APPINSIGHTS_INSTRUMENTATIONKEY="your_instrumentation_key"
```

### 2. Set Up Logging

```bash
# Enable application logging
az webapp log config --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg --application-logging filesystem --level information
```

## Scaling and Performance

### 1. Auto-scaling Rules

```bash
# Create auto-scaling rule
az monitor autoscale create \
  --resource-group osaa-smu-data-app-rg \
  --resource osaa-smu-data-app \
  --resource-type Microsoft.Web/sites \
  --name osaa-smu-data-app-autoscale \
  --min-count 1 \
  --max-count 10 \
  --count 1
```

### 2. Performance Optimization

- Use Azure CDN for static content
- Enable compression
- Configure caching headers
- Use Azure Redis Cache for session storage

## Troubleshooting

### Common Issues:

1. **Port Configuration**: Ensure port 8000 is configured correctly
2. **Environment Variables**: Verify all required variables are set
3. **Dependencies**: Check that all packages in requirements.txt are compatible
4. **Memory Issues**: Increase app service plan if needed

### Debug Commands:

```bash
# Check app logs
az webapp log tail --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg

# Check app status
az webapp show --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg

# Restart app
az webapp restart --name osaa-smu-data-app --resource-group osaa-smu-data-app-rg
```

## Cost Optimization

1. **Use Basic Plan**: Start with B1 plan for development
2. **Auto-shutdown**: Configure auto-shutdown for non-production environments
3. **Reserved Instances**: Use reserved instances for production workloads
4. **Monitor Usage**: Set up cost alerts and monitoring

## Next Steps

1. Set up CI/CD pipeline with GitHub Actions or Azure DevOps
2. Configure custom domain and SSL certificate
3. Set up backup and disaster recovery
4. Implement monitoring and alerting
5. Configure staging environments
