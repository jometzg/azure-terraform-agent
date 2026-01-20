"""Terraform definition parser using python-hcl2."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import hcl2


# Mapping from Terraform resource types to Azure resource types
TERRAFORM_TO_AZURE_TYPE = {
    "azurerm_resource_group": "Microsoft.Resources/resourceGroups",
    "azurerm_storage_account": "Microsoft.Storage/storageAccounts",
    "azurerm_storage_container": "Microsoft.Storage/storageAccounts/blobServices/containers",
    "azurerm_virtual_network": "Microsoft.Network/virtualNetworks",
    "azurerm_subnet": "Microsoft.Network/virtualNetworks/subnets",
    "azurerm_network_security_group": "Microsoft.Network/networkSecurityGroups",
    "azurerm_network_security_rule": "Microsoft.Network/networkSecurityGroups/securityRules",
    "azurerm_public_ip": "Microsoft.Network/publicIPAddresses",
    "azurerm_network_interface": "Microsoft.Network/networkInterfaces",
    "azurerm_linux_virtual_machine": "Microsoft.Compute/virtualMachines",
    "azurerm_windows_virtual_machine": "Microsoft.Compute/virtualMachines",
    "azurerm_virtual_machine": "Microsoft.Compute/virtualMachines",
    "azurerm_key_vault": "Microsoft.KeyVault/vaults",
    "azurerm_key_vault_secret": "Microsoft.KeyVault/vaults/secrets",
    "azurerm_key_vault_key": "Microsoft.KeyVault/vaults/keys",
}

# Supported resource types for scanning
SUPPORTED_TERRAFORM_TYPES = {
    "azurerm_storage_account",
    "azurerm_virtual_network",
    "azurerm_subnet",
    "azurerm_network_security_group",
    "azurerm_linux_virtual_machine",
    "azurerm_windows_virtual_machine",
    "azurerm_key_vault",
}


@dataclass
class TerraformVariable:
    """Represents a Terraform variable."""
    
    name: str
    default: Optional[Any] = None
    description: Optional[str] = None
    type: Optional[str] = None


@dataclass
class TerraformResource:
    """Represents a Terraform resource definition."""
    
    terraform_type: str
    name: str
    config: Dict[str, Any]
    azure_type: str = ""
    resource_name: str = ""  # The actual Azure resource name from config
    location: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set derived fields after initialization."""
        self.azure_type = TERRAFORM_TO_AZURE_TYPE.get(
            self.terraform_type, self.terraform_type
        )
        # Extract common properties
        self.resource_name = self._resolve_value(self.config.get("name", self.name))
        self.location = self._resolve_value(self.config.get("location", ""))
        self.tags = self.config.get("tags", {})
    
    def _resolve_value(self, value: Any) -> str:
        """Resolve a value, handling variable references."""
        if isinstance(value, str):
            # Check for variable references like ${var.name}
            if "${" in value:
                return f"<variable: {value}>"
            return value
        elif isinstance(value, list) and len(value) == 1:
            return self._resolve_value(value[0])
        return str(value) if value else ""


@dataclass
class TerraformConfig:
    """Parsed Terraform configuration."""
    
    resources: List[TerraformResource] = field(default_factory=list)
    variables: Dict[str, TerraformVariable] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    
    def get_resources_by_type(self, terraform_type: str) -> List[TerraformResource]:
        """Get all resources of a specific Terraform type."""
        return [r for r in self.resources if r.terraform_type == terraform_type]
    
    def get_supported_resources(self) -> List[TerraformResource]:
        """Get only resources of supported types."""
        return [r for r in self.resources if r.terraform_type in SUPPORTED_TERRAFORM_TYPES]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "resources": [
                {
                    "terraform_type": r.terraform_type,
                    "name": r.name,
                    "azure_type": r.azure_type,
                    "resource_name": r.resource_name,
                    "location": r.location,
                    "tags": r.tags,
                    "config": r.config,
                }
                for r in self.resources
            ],
            "variables": {
                name: {
                    "default": var.default,
                    "description": var.description,
                    "type": var.type,
                }
                for name, var in self.variables.items()
            },
            "locals": self.locals,
        }


class TerraformParser:
    """Parser for Terraform .tf files."""
    
    def __init__(self, tfvars: Optional[Dict[str, Any]] = None):
        """Initialize parser with optional variable values.
        
        Args:
            tfvars: Dictionary of variable values for substitution.
        """
        self.tfvars = tfvars or {}
    
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a single Terraform file.
        
        Args:
            file_path: Path to the .tf file.
            
        Returns:
            Parsed HCL configuration as dictionary.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return hcl2.load(f)
    
    def parse_directory(self, directory: Path) -> TerraformConfig:
        """Parse all Terraform files in a directory.
        
        Args:
            directory: Path to directory containing .tf files.
            
        Returns:
            TerraformConfig with all parsed resources and variables.
        """
        config = TerraformConfig()
        
        # First pass: collect variables and locals
        for tf_file in directory.glob("*.tf"):
            parsed = self.parse_file(tf_file)
            
            # Extract variables
            for var_block in parsed.get("variable", []):
                for var_name, var_config in var_block.items():
                    config.variables[var_name] = TerraformVariable(
                        name=var_name,
                        default=var_config.get("default"),
                        description=var_config.get("description"),
                        type=str(var_config.get("type", "")),
                    )
            
            # Extract locals
            for locals_block in parsed.get("locals", []):
                config.locals.update(locals_block)
        
        # Also parse .tfvars files
        for tfvars_file in directory.glob("*.tfvars"):
            try:
                parsed_vars = self.parse_file(tfvars_file)
                self.tfvars.update(parsed_vars)
            except Exception:
                pass  # Skip invalid tfvars files
        
        # Second pass: collect resources
        for tf_file in directory.glob("*.tf"):
            parsed = self.parse_file(tf_file)
            
            # Extract resources
            for resource_block in parsed.get("resource", []):
                for resource_type, resources in resource_block.items():
                    for resource_name, resource_config in resources.items():
                        # Resolve variables in config
                        resolved_config = self._resolve_config(
                            resource_config, config.variables
                        )
                        
                        config.resources.append(
                            TerraformResource(
                                terraform_type=resource_type,
                                name=resource_name,
                                config=resolved_config,
                            )
                        )
        
        return config
    
    def _resolve_config(
        self,
        config: Dict[str, Any],
        variables: Dict[str, TerraformVariable],
    ) -> Dict[str, Any]:
        """Resolve variable references in configuration.
        
        Args:
            config: Resource configuration dictionary.
            variables: Available variables.
            
        Returns:
            Configuration with variables resolved where possible.
        """
        resolved = {}
        for key, value in config.items():
            resolved[key] = self._resolve_value(value, variables)
        return resolved
    
    def _resolve_value(
        self,
        value: Any,
        variables: Dict[str, TerraformVariable],
    ) -> Any:
        """Resolve a single value, substituting variables where possible."""
        if isinstance(value, str):
            # Handle ${var.name} references
            if value.startswith("${var.") and value.endswith("}"):
                var_name = value[6:-1]  # Extract variable name
                if var_name in self.tfvars:
                    return self.tfvars[var_name]
                elif var_name in variables and variables[var_name].default is not None:
                    return variables[var_name].default
            # Handle ${local.name} references
            elif value.startswith("${local.") and value.endswith("}"):
                # Keep as-is for now, could be extended
                pass
            return value
        elif isinstance(value, list):
            return [self._resolve_value(v, variables) for v in value]
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, variables) for k, v in value.items()}
        return value


def parse_terraform(
    directory: Path,
    tfvars: Optional[Dict[str, Any]] = None,
) -> TerraformConfig:
    """Parse Terraform files from a directory.
    
    Args:
        directory: Path to directory containing .tf files.
        tfvars: Optional variable values for substitution.
        
    Returns:
        TerraformConfig with parsed resources.
        
    Example:
        config = parse_terraform(Path("./terraform"))
        for resource in config.get_supported_resources():
            print(f"{resource.terraform_type}: {resource.resource_name}")
    """
    parser = TerraformParser(tfvars=tfvars)
    return parser.parse_directory(directory)
