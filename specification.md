# Specification: Azure AI Foundry Terraform-Resource Comparison Agent

## Overview
An Azure AI Foundry agent that compares Azure resource groups against Terraform specifications and can align them.

## Requirements

### Core Functionality
1. **Language**: Python
2. **Azure Connection**: Connects to an Azure subscription
3. **Resource Group Scanning**: Takes a resource group name to scan
4. **Terraform Comparison**: Compares the resource group with a Terraform specification using AI-powered analysis
5. **Difference Reporting**: Generates a report on the differences
6. **CLI Suggestions**: Suggests Azure CLI commands needed to align the resource group to the specification
7. **Execution with Approval**: Can execute these changes to align the resource group with the specification, requiring user approval

## Design Decisions

| Area | Decision |
|------|----------|
| **Terraform Input** | Git repository URL (with support for branch/tag selection, private repos via PAT, and subdirectory paths) |
| **Comparison Target** | Terraform definitions (`.tf` files), not state files |
| **Supported Resource Types** | Storage Accounts, Virtual Networks, Network Security Groups, Virtual Machines, Key Vaults |
| **Drift Detection** | Full deep comparison of all properties |
| **Execution Safety** | Create and update operations only (no delete) |
| **Output Format** | Markdown report |
| **Authentication** | `DefaultAzureCredential` (supports both local Azure CLI and deployed Managed Identity) |
| **AI Foundry Project** | Needs to be provisioned (not existing) |

## Dependencies
