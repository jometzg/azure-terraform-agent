"""Agent tool functions for Azure AI Foundry."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from .azure_scanner import AzureResource, scan_azure_resources
from .cli_generator import CliCommand, generate_cli_commands
from .comparison_engine import ComparisonResult, compare_resources
from .executor import ExecutionResult, execute_with_approval
from .git_repo import clone_terraform_repo
from .report_generator import generate_markdown_report
from .terraform_parser import TerraformConfig, TerraformResource, parse_terraform


# Global state for the agent session
_session_state: Dict[str, Any] = {}


def scan_resource_group(
    subscription_id: str,
    resource_group_name: str,
) -> str:
    """Scan all supported resources in an Azure resource group.
    
    This function connects to Azure and retrieves detailed information about
    all supported resources (Storage Accounts, Virtual Networks, NSGs, VMs,
    and Key Vaults) in the specified resource group.
    
    Args:
        subscription_id: The Azure subscription ID.
        resource_group_name: The name of the resource group to scan.
        
    Returns:
        JSON string containing the list of resources with their properties.
    """
    try:
        resources = scan_azure_resources(subscription_id, resource_group_name)
        
        # Store in session for later use
        _session_state["azure_resources"] = resources
        _session_state["resource_group"] = resource_group_name
        _session_state["subscription_id"] = subscription_id
        
        return json.dumps({
            "status": "success",
            "resource_group": resource_group_name,
            "resource_count": len(resources),
            "resources": [r.to_dict() for r in resources],
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def fetch_terraform_from_git(
    git_url: str,
    branch: Optional[str] = None,
    tag: Optional[str] = None,
    subdirectory: Optional[str] = None,
    pat: Optional[str] = None,
) -> str:
    """Fetch and parse Terraform definitions from a Git repository.
    
    This function clones the specified Git repository and parses all .tf files
    to extract Azure resource definitions.
    
    Args:
        git_url: The Git repository URL (HTTPS or SSH).
        branch: Optional branch name to checkout (default: main).
        tag: Optional tag to checkout (overrides branch).
        subdirectory: Optional path within repo containing Terraform files.
        pat: Personal Access Token for private repositories.
        
    Returns:
        JSON string containing parsed Terraform resource definitions.
    """
    try:
        # Use PAT from environment if not provided
        if not pat:
            pat = os.getenv("GIT_PAT")
        
        with clone_terraform_repo(
            url=git_url,
            branch=branch,
            tag=tag,
            subdirectory=subdirectory,
            pat=pat,
        ) as tf_path:
            config = parse_terraform(tf_path)
            
            # Store in session
            _session_state["terraform_config"] = config
            _session_state["terraform_source"] = git_url
            
            supported = config.get_supported_resources()
            
            return json.dumps({
                "status": "success",
                "source": git_url,
                "total_resources": len(config.resources),
                "supported_resources": len(supported),
                "variables_count": len(config.variables),
                "resources": [
                    {
                        "terraform_type": r.terraform_type,
                        "name": r.name,
                        "resource_name": r.resource_name,
                        "location": r.location,
                        "azure_type": r.azure_type,
                    }
                    for r in supported
                ],
            }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def compare_azure_with_terraform() -> str:
    """Compare Azure resources with Terraform definitions.
    
    This function compares the previously scanned Azure resources with the
    parsed Terraform definitions to identify differences including:
    - Resources missing in Azure (defined in Terraform but not deployed)
    - Resources missing in Terraform (exist in Azure but not defined)
    - Configuration drift (resources exist but with different properties)
    
    Requires scan_resource_group and fetch_terraform_from_git to be called first.
    
    Returns:
        JSON string containing the comparison result with all differences.
    """
    try:
        # Check session state
        if "azure_resources" not in _session_state:
            return json.dumps({
                "status": "error",
                "error": "No Azure resources scanned. Call scan_resource_group first.",
            })
        
        if "terraform_config" not in _session_state:
            return json.dumps({
                "status": "error",
                "error": "No Terraform config loaded. Call fetch_terraform_from_git first.",
            })
        
        azure_resources: List[AzureResource] = _session_state["azure_resources"]
        terraform_config: TerraformConfig = _session_state["terraform_config"]
        resource_group: str = _session_state["resource_group"]
        
        # Get only supported Terraform resources
        terraform_resources = terraform_config.get_supported_resources()
        
        # Run comparison
        result = compare_resources(resource_group, azure_resources, terraform_resources)
        
        # Store result
        _session_state["comparison_result"] = result
        
        return json.dumps({
            "status": "success",
            "has_differences": result.has_differences,
            "summary": {
                "azure_resources": result.azure_resource_count,
                "terraform_resources": result.terraform_resource_count,
                "matched": result.matched_count,
                "missing_in_azure": len(result.missing_in_azure),
                "missing_in_terraform": len(result.missing_in_terraform),
                "drifted": len(result.drifted),
            },
            "differences": result.to_dict()["differences"],
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def generate_alignment_commands() -> str:
    """Generate Azure CLI commands to align resources with Terraform.
    
    This function generates the necessary Azure CLI commands to create or
    update resources in Azure to match the Terraform definitions.
    Note: Delete operations are not generated for safety.
    
    Requires compare_azure_with_terraform to be called first.
    
    Returns:
        JSON string containing the list of CLI commands to execute.
    """
    try:
        if "comparison_result" not in _session_state:
            return json.dumps({
                "status": "error",
                "error": "No comparison result. Call compare_azure_with_terraform first.",
            })
        
        result: ComparisonResult = _session_state["comparison_result"]
        subscription_id = _session_state.get("subscription_id")
        
        commands = generate_cli_commands(result, subscription_id)
        
        # Store commands
        _session_state["commands"] = commands
        
        return json.dumps({
            "status": "success",
            "command_count": len(commands),
            "commands": [
                {
                    "index": i,
                    "action": cmd.action,
                    "resource_name": cmd.resource_name,
                    "description": cmd.description,
                    "risk_level": cmd.risk_level.value,
                    "command": cmd.command,
                }
                for i, cmd in enumerate(commands)
            ],
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def generate_report(output_path: Optional[str] = None) -> str:
    """Generate a Markdown report of the comparison and suggested commands.
    
    This function creates a comprehensive Markdown report including:
    - Summary of the comparison
    - Resource inventory
    - Detailed differences
    - Suggested CLI commands
    
    Args:
        output_path: Optional file path to save the report. If not provided,
                    returns the report content.
                    
    Returns:
        JSON string with status and report content or file path.
    """
    try:
        if "comparison_result" not in _session_state:
            return json.dumps({
                "status": "error",
                "error": "No comparison result. Run comparison first.",
            })
        
        result: ComparisonResult = _session_state["comparison_result"]
        commands: List[CliCommand] = _session_state.get("commands", [])
        terraform_source: str = _session_state.get("terraform_source", "Unknown")
        
        report = generate_markdown_report(result, commands, terraform_source)
        
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report, encoding="utf-8")
            
            return json.dumps({
                "status": "success",
                "message": f"Report saved to {output_path}",
                "file_path": str(path.absolute()),
            })
        
        return json.dumps({
            "status": "success",
            "report": report,
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def execute_commands(
    command_indices: Optional[List[int]] = None,
    dry_run: bool = False,
) -> str:
    """Execute approved CLI commands to align Azure resources.
    
    This function executes the specified CLI commands after user approval.
    Commands can be run in dry-run mode for validation without actual execution.
    
    Args:
        command_indices: List of command indices to execute. If None, requires
                        explicit approval for each command.
        dry_run: If True, validate commands without executing them.
        
    Returns:
        JSON string with execution results for each command.
    """
    try:
        if "commands" not in _session_state:
            return json.dumps({
                "status": "error",
                "error": "No commands generated. Call generate_alignment_commands first.",
            })
        
        commands: List[CliCommand] = _session_state["commands"]
        
        if not command_indices:
            # Return commands pending approval
            return json.dumps({
                "status": "pending_approval",
                "message": "Please specify which commands to execute by their indices.",
                "commands": [
                    {
                        "index": i,
                        "description": cmd.description,
                        "risk_level": cmd.risk_level.value,
                        "command": cmd.command,
                    }
                    for i, cmd in enumerate(commands)
                ],
            })
        
        # Validate indices
        invalid = [i for i in command_indices if i < 0 or i >= len(commands)]
        if invalid:
            return json.dumps({
                "status": "error",
                "error": f"Invalid command indices: {invalid}",
            })
        
        # Execute approved commands
        results = execute_with_approval(commands, command_indices, dry_run)
        
        # Filter to only requested commands
        filtered_results = [r for i, r in enumerate(results) if i in command_indices]
        
        success_count = sum(1 for r in filtered_results if r.status.value == "success")
        failed_count = sum(1 for r in filtered_results if r.status.value == "failed")
        
        return json.dumps({
            "status": "completed",
            "dry_run": dry_run,
            "summary": {
                "total": len(filtered_results),
                "success": success_count,
                "failed": failed_count,
            },
            "results": [r.to_dict() for r in filtered_results],
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
        })


def get_session_state() -> str:
    """Get the current session state.
    
    Returns information about what has been scanned, compared, and generated
    in the current session.
    
    Returns:
        JSON string with session state summary.
    """
    return json.dumps({
        "has_azure_resources": "azure_resources" in _session_state,
        "azure_resource_count": len(_session_state.get("azure_resources", [])),
        "resource_group": _session_state.get("resource_group"),
        "subscription_id": _session_state.get("subscription_id"),
        "has_terraform_config": "terraform_config" in _session_state,
        "terraform_source": _session_state.get("terraform_source"),
        "has_comparison_result": "comparison_result" in _session_state,
        "has_commands": "commands" in _session_state,
        "command_count": len(_session_state.get("commands", [])),
    }, indent=2)


def clear_session() -> str:
    """Clear the current session state.
    
    Returns:
        JSON string confirming session cleared.
    """
    _session_state.clear()
    return json.dumps({
        "status": "success",
        "message": "Session state cleared.",
    })


# Export all tool functions for the agent
AGENT_TOOLS = {
    scan_resource_group,
    fetch_terraform_from_git,
    compare_azure_with_terraform,
    generate_alignment_commands,
    generate_report,
    execute_commands,
    get_session_state,
    clear_session,
}
