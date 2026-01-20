# Azure Terraform Comparison Agent

An Azure AI Foundry agent that compares Azure resource groups with Terraform definitions, generates difference reports, and can execute alignment commands with user approval.

## Features

- 🔍 **Scan Azure Resources**: Retrieve detailed information about Storage Accounts, Virtual Networks, NSGs, VMs, and Key Vaults
- 📁 **Fetch Terraform from Git**: Clone repositories with branch/tag support and PAT authentication for private repos
- 📊 **Deep Comparison**: Full property-level comparison with drift detection
- 📝 **Markdown Reports**: Comprehensive reports with summaries, differences, and suggested commands
- ⚡ **CLI Command Generation**: Generate Azure CLI commands to align resources (create/update only)
- ✅ **Approval Workflow**: Execute changes only with explicit user approval

## Prerequisites

1. **Azure AI Foundry Project**: You need an Azure AI Services resource with a deployed model (e.g., GPT-4o)
2. **Azure CLI**: Installed and authenticated (`az login`)
3. **Python 3.9+**: With pip for package installation

## Installation

```bash
# Clone this repository
cd agent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required: Azure AI Foundry endpoint
PROJECT_ENDPOINT=https://<your-ai-services>.services.ai.azure.com/api/projects/<your-project>

# Required: Model deployment name
MODEL_DEPLOYMENT_NAME=gpt-4o

# Optional: Azure subscription (can also use az login context)
AZURE_SUBSCRIPTION_ID=<your-subscription-id>

# Optional: For private Git repositories
GIT_PAT=<your-personal-access-token>
```

## Usage

### Interactive Mode

```bash
python -m src.main
```

Then interact with the agent:

```
You: Compare my-resource-group in subscription abc-123 with terraform from https://github.com/myorg/infra

Agent: I'll help you compare the resources. Let me start by scanning the Azure resource group...
```

### Command Line Mode

```bash
python -m src.main \
  --subscription abc-123-def \
  --resource-group my-resource-group \
  --git-url https://github.com/myorg/infrastructure \
  --branch main \
  --subdirectory terraform/azure \
  --output comparison-report.md
```

### Programmatic Usage

```python
from src.agent import create_agent

# Create and initialize agent
agent = create_agent()
agent.create_agent()
agent.start_conversation()

# Send queries
response = agent.send_message(
    "Compare resource group 'prod-rg' with Terraform from "
    "https://github.com/myorg/infra subdirectory 'terraform'"
)
print(response)

# Cleanup
agent.cleanup()
```

## Supported Resource Types

| Azure Resource Type | Terraform Type |
|---------------------|----------------|
| Storage Accounts | `azurerm_storage_account` |
| Virtual Networks | `azurerm_virtual_network` |
| Subnets | `azurerm_subnet` |
| Network Security Groups | `azurerm_network_security_group` |
| Linux Virtual Machines | `azurerm_linux_virtual_machine` |
| Windows Virtual Machines | `azurerm_windows_virtual_machine` |
| Key Vaults | `azurerm_key_vault` |

## Security

- **No Delete Operations**: The agent only generates create and update commands for safety
- **Approval Required**: All CLI commands require explicit user approval before execution
- **DefaultAzureCredential**: Supports multiple authentication methods (CLI, Managed Identity, etc.)
- **Private Repos**: Use Personal Access Tokens for private Git repositories

## Project Structure

```
agent/
├── src/
│   ├── __init__.py
│   ├── agent.py           # Main AI Foundry agent
│   ├── agent_tools.py     # Tool functions for the agent
│   ├── azure_scanner.py   # Azure resource scanning
│   ├── cli_generator.py   # Azure CLI command generation
│   ├── comparison_engine.py # Deep comparison logic
│   ├── config.py          # Configuration management
│   ├── executor.py        # Command execution with approval
│   ├── git_repo.py        # Git repository operations
│   ├── main.py           # CLI entry point
│   ├── report_generator.py # Markdown report generation
│   └── terraform_parser.py # Terraform .tf file parsing
├── requirements.txt
├── .env.example
├── plan.md
├── specification.md
└── README.md
```

## Provisioning Azure AI Foundry

If you don't have an Azure AI Foundry project, create one:

```bash
# Create resource group
az group create --name ai-foundry-rg --location eastus

# Create Azure AI Services
az cognitiveservices account create \
  --name my-ai-services \
  --resource-group ai-foundry-rg \
  --kind AIServices \
  --sku S0 \
  --location eastus

# Deploy a model (e.g., GPT-4o)
az cognitiveservices account deployment create \
  --name my-ai-services \
  --resource-group ai-foundry-rg \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-05-13" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name Standard
```

Then set your PROJECT_ENDPOINT to:
`https://my-ai-services.services.ai.azure.com/api/projects/default`

## License

MIT
