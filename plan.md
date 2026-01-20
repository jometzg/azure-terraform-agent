# Plan: Azure AI Foundry Terraform-Resource Comparison Agent

Build a Python-based Azure AI Foundry agent that scans Azure resource groups, compares them to Terraform definitions from a Git repository using full deep comparison, generates Markdown reports, and executes create/update commands with user approval.

## Steps

### 1. Set up project structure
Install dependencies: `azure-ai-projects`, `azure-mgmt-resource`, `azure-mgmt-compute`, `azure-mgmt-network`, `azure-mgmt-storage`, `azure-mgmt-keyvault`, `azure-identity`, `python-hcl2`, and `gitpython`.

### 2. Provision Azure AI Foundry project
Via Azure Portal or CLI — create an AI Services resource, project workspace, and deploy a GPT-4o model for the agent.

### 3. Implement Git repository module
Using `gitpython` to clone repos from URL, support branch/tag selection, private repo authentication via PAT, and subdirectory paths for Terraform files.

### 4. Implement Azure resource scanners
For each supported type (Storage, VNet, NSG, VMs, Key Vault) using type-specific management clients to retrieve full property details for deep comparison.

### 5. Implement Terraform definition parser
Using `python-hcl2` to extract `azurerm_storage_account`, `azurerm_virtual_network`, `azurerm_network_security_group`, `azurerm_linux_virtual_machine`, `azurerm_windows_virtual_machine`, and `azurerm_key_vault` blocks with all properties.

### 6. Create deep comparison engine
Match resources by name/type and compare all properties recursively, producing detailed drift reports with property-level differences.

### 7. Build CLI command generator
Produce `az` commands for create and update operations only (no delete), classified by risk level.

### 8. Implement Markdown report generator
Output: summary, resource inventory, differences table, suggested commands, and execution status.

### 9. Assemble the AI Foundry agent
With function tools using `DefaultAzureCredential`, approval workflow for command execution, and conversational interface.

## Open Considerations

1. **Terraform Variable Resolution** — Should the parser resolve variables/locals, or treat `${var.name}` as literal strings? Recommendation: basic variable substitution if `.tfvars` provided, otherwise flag as "variable-dependent".

2. **Property Mapping Complexity** — Full deep comparison requires mapping Terraform property names to Azure API property names (they differ). This adds development effort but ensures accuracy.

3. **CI/CD Integration** — Would you want this agent callable from a pipeline (headless mode) in future, or purely interactive? Affects approval workflow design.