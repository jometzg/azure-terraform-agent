# Copilot Agent Instructions for Azure Terraform Comparison Agent

## Repository Overview

This is a **Python 3.9+** application that implements an Azure AI Foundry agent for comparing Azure resource groups with Terraform definitions. The agent scans Azure resources, parses Terraform `.tf` files from Git repositories, generates difference reports in Markdown, and can execute Azure CLI commands to align resources (with user approval).

**Size**: Small (~2000 lines of Python across 13 source files)  
**Type**: CLI application + AI Agent  
**Key Dependencies**: `azure-ai-projects`, `azure-identity`, `azure-mgmt-*`, `python-hcl2`, `gitpython`, `python-dotenv`

---

## Build & Run Commands

### Initial Setup (Required Once)

```powershell
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```powershell
# Interactive mode (requires .env configuration)
python -m src

# Command line mode
python -m src --subscription SUB_ID --resource-group RG_NAME --git-url https://github.com/org/repo

# Show help
python -m src --help
```

### Validating Changes

**Always run these checks before committing:**

```powershell
# 1. Verify all modules import successfully
python -c "from src.agent import create_agent; from src.terraform_parser import parse_terraform; from src.azure_scanner import scan_azure_resources; print('OK')"

# 2. Verify CLI runs (will fail gracefully if .env not configured)
python -m src --help
```

There are **no automated tests, linters, or CI pipelines** configured in this repository. Manual import validation is the primary verification method.

---

## Configuration Requirements

The application requires a `.env` file with Azure AI Foundry credentials. Copy from `.env.example`:

```bash
# Required
PROJECT_ENDPOINT=https://<ai-services>.services.ai.azure.com/api/projects/<project>
MODEL_DEPLOYMENT_NAME=gpt-4o

# Optional
AZURE_SUBSCRIPTION_ID=<subscription-id>
GIT_PAT=<personal-access-token>
```

**Critical**: The `PROJECT_ENDPOINT` environment variable is required. The application will raise `ValueError` if missing.

---

## Project Structure

```
agent/
├── src/                        # All source code
│   ├── __init__.py             # Package init, exports __version__
│   ├── __main__.py             # Entry point: python -m src
│   ├── main.py                 # CLI parsing, interactive/single-query modes
│   ├── agent.py                # AI Foundry agent setup, AGENT_INSTRUCTIONS
│   ├── agent_tools.py          # 8 tool functions exposed to the AI agent
│   ├── config.py               # Config dataclass, loads from .env
│   ├── azure_scanner.py        # Azure SDK calls for 5 resource types
│   ├── terraform_parser.py     # HCL2 parsing, resource extraction
│   ├── comparison_engine.py    # Deep property comparison logic
│   ├── cli_generator.py        # Azure CLI command generation
│   ├── report_generator.py     # Markdown report output
│   ├── executor.py             # Command execution with approval
│   └── git_repo.py             # Git clone with PAT support
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── .env                        # Local configuration (gitignored)
├── README.md                   # User documentation
├── specification.md            # Design specification
└── plan.md                     # Implementation plan
```

### Key Files by Function

| Task | Files to Modify |
|------|-----------------|
| Add new Azure resource type | `azure_scanner.py`, `terraform_parser.py`, `comparison_engine.py`, `cli_generator.py` |
| Change AI agent behavior | `agent.py` (AGENT_INSTRUCTIONS constant) |
| Add new tool function | `agent_tools.py`, then add to `AGENT_TOOLS` set |
| Modify CLI arguments | `main.py` |
| Change report format | `report_generator.py` |
| Update comparison logic | `comparison_engine.py` (PROPERTY_MAPPINGS dict) |

---

## Module Dependencies (Import Order)

```
config.py          → (no internal deps)
git_repo.py        → (no internal deps)
terraform_parser.py → (no internal deps)
azure_scanner.py   → (no internal deps)
comparison_engine.py → azure_scanner, terraform_parser
cli_generator.py   → comparison_engine
report_generator.py → cli_generator, comparison_engine
executor.py        → cli_generator
agent_tools.py     → all above modules
agent.py           → agent_tools, config
main.py            → agent, config, agent_tools
```

---

## Important SDK Details

### Azure AI Imports (Critical)

The correct import path for AI Foundry tools is:

```python
# CORRECT
from azure.ai.agents.models import FunctionTool, ToolSet
from azure.ai.projects import AIProjectClient

# WRONG - will cause ImportError
from azure.ai.projects.models import FunctionTool, ToolSet
```

### Supported Resource Types

The agent supports these Azure/Terraform mappings (defined in `terraform_parser.py`):

- `azurerm_storage_account` ↔ `Microsoft.Storage/storageAccounts`
- `azurerm_virtual_network` ↔ `Microsoft.Network/virtualNetworks`
- `azurerm_network_security_group` ↔ `Microsoft.Network/networkSecurityGroups`
- `azurerm_linux_virtual_machine` / `azurerm_windows_virtual_machine` ↔ `Microsoft.Compute/virtualMachines`
- `azurerm_key_vault` ↔ `Microsoft.KeyVault/vaults`

---

## Common Issues & Workarounds

| Issue | Cause | Solution |
|-------|-------|----------|
| `ImportError: cannot import name 'FunctionTool'` | Wrong import path | Import from `azure.ai.agents.models`, not `azure.ai.projects.models` |
| `ValueError: PROJECT_ENDPOINT environment variable is required` | Missing .env | Copy `.env.example` to `.env` and configure |
| Module import fails | Missing dependency | Run `pip install -r requirements.txt` |
| Azure auth fails | Not logged in | Run `az login` before starting agent |

---

## Adding New Features

### To add a new Azure resource type:

1. **azure_scanner.py**: Add `_scan_<resource>()` method to `AzureScanner` class
2. **terraform_parser.py**: Add mapping to `TERRAFORM_TO_AZURE_TYPE` and `SUPPORTED_TERRAFORM_TYPES`
3. **comparison_engine.py**: Add property mapping to `PROPERTY_MAPPINGS` dict
4. **cli_generator.py**: Add CLI command mapping to `CLI_COMMANDS` and `PROPERTY_MAPPINGS`

### To add a new agent tool:

1. Add function to `agent_tools.py` with docstring (used by AI for understanding)
2. Add function to `AGENT_TOOLS` set at bottom of file
3. Update `AGENT_INSTRUCTIONS` in `agent.py` to describe the new capability

---

## Trust These Instructions

These instructions have been validated against the actual codebase. Only perform additional searches if:
- The information appears incomplete for your specific task
- You encounter an error not documented here
- You need to understand implementation details within a specific function

The repository has no CI/CD, no test suite, and no linting configured. Your primary validation is successful module imports and `--help` execution.
