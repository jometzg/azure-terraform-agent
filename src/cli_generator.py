"""CLI command generator for aligning Azure resources with Terraform."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .comparison_engine import (
    ComparisonResult,
    DifferenceType,
    PropertyDifference,
    ResourceDifference,
    RiskLevel,
)


@dataclass
class CliCommand:
    """Represents an Azure CLI command to execute."""
    
    command: str
    description: str
    action: str  # create, update
    resource_name: str
    resource_type: str
    risk_level: RiskLevel
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "command": self.command,
            "description": self.description,
            "action": self.action,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "risk_level": self.risk_level.value,
            "parameters": self.parameters,
        }


class CliCommandGenerator:
    """Generates Azure CLI commands to align resources."""
    
    # Terraform type to CLI command mapping
    CLI_COMMANDS = {
        "azurerm_storage_account": {
            "create": "az storage account create",
            "update": "az storage account update",
            "resource_name_param": "--name",
        },
        "azurerm_virtual_network": {
            "create": "az network vnet create",
            "update": "az network vnet update",
            "resource_name_param": "--name",
        },
        "azurerm_subnet": {
            "create": "az network vnet subnet create",
            "update": "az network vnet subnet update",
            "resource_name_param": "--name",
        },
        "azurerm_network_security_group": {
            "create": "az network nsg create",
            "update": "az network nsg update",
            "resource_name_param": "--name",
        },
        "azurerm_linux_virtual_machine": {
            "create": "az vm create",
            "update": "az vm update",
            "resource_name_param": "--name",
        },
        "azurerm_windows_virtual_machine": {
            "create": "az vm create",
            "update": "az vm update",
            "resource_name_param": "--name",
        },
        "azurerm_key_vault": {
            "create": "az keyvault create",
            "update": "az keyvault update",
            "resource_name_param": "--name",
        },
    }
    
    # Property to CLI parameter mapping
    PROPERTY_MAPPINGS = {
        "azurerm_storage_account": {
            "location": "--location",
            "account_tier": "--sku",  # Combined with replication
            "account_replication_type": "--sku",
            "access_tier": "--access-tier",
            "enable_https_traffic_only": "--https-only",
            "min_tls_version": "--min-tls-version",
            "allow_nested_items_to_be_public": "--allow-blob-public-access",
            "tags": "--tags",
        },
        "azurerm_virtual_network": {
            "location": "--location",
            "address_space": "--address-prefixes",
            "dns_servers": "--dns-servers",
            "tags": "--tags",
        },
        "azurerm_network_security_group": {
            "location": "--location",
            "tags": "--tags",
        },
        "azurerm_linux_virtual_machine": {
            "location": "--location",
            "size": "--size",
            "admin_username": "--admin-username",
            "tags": "--tags",
        },
        "azurerm_windows_virtual_machine": {
            "location": "--location",
            "size": "--size",
            "admin_username": "--admin-username",
            "tags": "--tags",
        },
        "azurerm_key_vault": {
            "location": "--location",
            "sku_name": "--sku",
            "enabled_for_deployment": "--enabled-for-deployment",
            "enabled_for_disk_encryption": "--enabled-for-disk-encryption",
            "enabled_for_template_deployment": "--enabled-for-template-deployment",
            "tags": "--tags",
        },
    }
    
    def __init__(self, resource_group: str, subscription_id: Optional[str] = None):
        """Initialize the command generator.
        
        Args:
            resource_group: Target resource group name.
            subscription_id: Optional subscription ID.
        """
        self.resource_group = resource_group
        self.subscription_id = subscription_id
    
    def generate_commands(self, comparison_result: ComparisonResult) -> List[CliCommand]:
        """Generate CLI commands from comparison result.
        
        Args:
            comparison_result: Result from comparison engine.
            
        Returns:
            List of CLI commands to execute.
        """
        commands = []
        
        for diff in comparison_result.differences:
            if diff.difference_type == DifferenceType.MISSING_IN_AZURE:
                # Generate create command
                cmd = self._generate_create_command(diff)
                if cmd:
                    commands.append(cmd)
            
            elif diff.difference_type == DifferenceType.PROPERTY_DRIFT:
                # Generate update command
                cmd = self._generate_update_command(diff)
                if cmd:
                    commands.append(cmd)
            
            # MISSING_IN_TERRAFORM - no command (informational only)
        
        return commands
    
    def _generate_create_command(self, diff: ResourceDifference) -> Optional[CliCommand]:
        """Generate a create command for a missing resource."""
        if not diff.terraform_type or not diff.terraform_resource:
            return None
        
        cmd_config = self.CLI_COMMANDS.get(diff.terraform_type)
        if not cmd_config:
            return None
        
        base_cmd = cmd_config["create"]
        name_param = cmd_config["resource_name_param"]
        
        # Build command parameters
        params = {
            name_param: diff.resource_name,
            "--resource-group": self.resource_group,
        }
        
        # Add subscription if specified
        if self.subscription_id:
            params["--subscription"] = self.subscription_id
        
        # Map Terraform properties to CLI parameters
        prop_mapping = self.PROPERTY_MAPPINGS.get(diff.terraform_type, {})
        tf_config = diff.terraform_resource.config
        
        for tf_prop, cli_param in prop_mapping.items():
            value = tf_config.get(tf_prop)
            if value is not None and not self._is_variable(value):
                params[cli_param] = self._format_param_value(value)
        
        # Handle special cases
        params = self._handle_special_cases(diff.terraform_type, tf_config, params)
        
        # Build command string
        cmd_str = self._build_command_string(base_cmd, params)
        
        return CliCommand(
            command=cmd_str,
            description=f"Create {diff.terraform_type} '{diff.resource_name}'",
            action="create",
            resource_name=diff.resource_name,
            resource_type=diff.resource_type,
            risk_level=RiskLevel.MEDIUM,
            parameters=params,
        )
    
    def _generate_update_command(self, diff: ResourceDifference) -> Optional[CliCommand]:
        """Generate an update command for drifted properties."""
        if not diff.terraform_type:
            return None
        
        cmd_config = self.CLI_COMMANDS.get(diff.terraform_type)
        if not cmd_config:
            return None
        
        base_cmd = cmd_config["update"]
        name_param = cmd_config["resource_name_param"]
        
        # Build command parameters - only include changed properties
        params = {
            name_param: diff.resource_name,
            "--resource-group": self.resource_group,
        }
        
        if self.subscription_id:
            params["--subscription"] = self.subscription_id
        
        # Map only the drifted properties
        prop_mapping = self.PROPERTY_MAPPINGS.get(diff.terraform_type, {})
        
        for prop_diff in diff.property_differences:
            prop_name = prop_diff.property_path.split(".")[-1]
            cli_param = prop_mapping.get(prop_name)
            
            if cli_param and prop_diff.terraform_value is not None:
                if not self._is_variable(prop_diff.terraform_value):
                    params[cli_param] = self._format_param_value(prop_diff.terraform_value)
        
        # Skip if no updatable parameters
        if len(params) <= 3:  # Only has name, rg, and maybe subscription
            return None
        
        cmd_str = self._build_command_string(base_cmd, params)
        
        # Describe what's being updated
        changed_props = [d.property_path for d in diff.property_differences]
        description = f"Update {diff.terraform_type} '{diff.resource_name}' - properties: {', '.join(changed_props)}"
        
        return CliCommand(
            command=cmd_str,
            description=description,
            action="update",
            resource_name=diff.resource_name,
            resource_type=diff.resource_type,
            risk_level=diff.risk_level,
            parameters=params,
        )
    
    def _is_variable(self, value: Any) -> bool:
        """Check if a value contains unresolved variables."""
        if isinstance(value, str):
            return "<variable:" in value or "${" in value
        return False
    
    def _format_param_value(self, value: Any) -> str:
        """Format a parameter value for CLI."""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, list):
            return " ".join(str(v) for v in value)
        if isinstance(value, dict):
            # Format tags as key=value pairs
            return " ".join(f"{k}={v}" for k, v in value.items())
        return str(value)
    
    def _handle_special_cases(
        self, terraform_type: str, config: Dict[str, Any], params: Dict[str, str]
    ) -> Dict[str, str]:
        """Handle special parameter mappings for specific resource types."""
        if terraform_type == "azurerm_storage_account":
            # Combine tier and replication into SKU
            tier = config.get("account_tier", "Standard")
            replication = config.get("account_replication_type", "LRS")
            if tier and replication:
                params["--sku"] = f"{tier}_{replication}"
        
        elif terraform_type in ("azurerm_linux_virtual_machine", "azurerm_windows_virtual_machine"):
            # Add image reference if present
            source_image = config.get("source_image_reference", {})
            if isinstance(source_image, list) and source_image:
                source_image = source_image[0]
            if isinstance(source_image, dict):
                publisher = source_image.get("publisher")
                offer = source_image.get("offer")
                sku = source_image.get("sku")
                version = source_image.get("version", "latest")
                if publisher and offer and sku:
                    params["--image"] = f"{publisher}:{offer}:{sku}:{version}"
        
        return params
    
    def _build_command_string(self, base_cmd: str, params: Dict[str, str]) -> str:
        """Build the complete command string."""
        parts = [base_cmd]
        
        for param, value in params.items():
            if " " in str(value):
                parts.append(f'{param} "{value}"')
            else:
                parts.append(f"{param} {value}")
        
        return " \\\n    ".join(parts)


def generate_cli_commands(
    comparison_result: ComparisonResult,
    subscription_id: Optional[str] = None,
) -> List[CliCommand]:
    """Generate Azure CLI commands from comparison result.
    
    Args:
        comparison_result: Result from comparison engine.
        subscription_id: Optional subscription ID.
        
    Returns:
        List of CLI commands to execute.
    """
    generator = CliCommandGenerator(
        resource_group=comparison_result.resource_group,
        subscription_id=subscription_id,
    )
    return generator.generate_commands(comparison_result)
