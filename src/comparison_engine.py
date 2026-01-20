"""Deep comparison engine for Azure resources and Terraform definitions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .azure_scanner import AzureResource
from .terraform_parser import TerraformResource, TERRAFORM_TO_AZURE_TYPE


class DifferenceType(Enum):
    """Types of differences found during comparison."""
    
    MISSING_IN_AZURE = "missing_in_azure"
    MISSING_IN_TERRAFORM = "missing_in_terraform"
    PROPERTY_DRIFT = "property_drift"


class RiskLevel(Enum):
    """Risk level for remediation actions."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class PropertyDifference:
    """Represents a difference in a specific property."""
    
    property_path: str
    terraform_value: Any
    azure_value: Any
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "property_path": self.property_path,
            "terraform_value": self.terraform_value,
            "azure_value": self.azure_value,
            "description": self.description,
        }


@dataclass
class ResourceDifference:
    """Represents a difference for a resource."""
    
    difference_type: DifferenceType
    resource_name: str
    resource_type: str
    terraform_type: Optional[str] = None
    terraform_resource: Optional[TerraformResource] = None
    azure_resource: Optional[AzureResource] = None
    property_differences: List[PropertyDifference] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "difference_type": self.difference_type.value,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "terraform_type": self.terraform_type,
            "risk_level": self.risk_level.value,
            "property_differences": [p.to_dict() for p in self.property_differences],
        }


@dataclass
class ComparisonResult:
    """Result of comparing Azure resources with Terraform definitions."""
    
    resource_group: str
    differences: List[ResourceDifference] = field(default_factory=list)
    azure_resource_count: int = 0
    terraform_resource_count: int = 0
    matched_count: int = 0
    
    @property
    def missing_in_azure(self) -> List[ResourceDifference]:
        """Resources defined in Terraform but not in Azure."""
        return [d for d in self.differences if d.difference_type == DifferenceType.MISSING_IN_AZURE]
    
    @property
    def missing_in_terraform(self) -> List[ResourceDifference]:
        """Resources in Azure but not defined in Terraform."""
        return [d for d in self.differences if d.difference_type == DifferenceType.MISSING_IN_TERRAFORM]
    
    @property
    def drifted(self) -> List[ResourceDifference]:
        """Resources with configuration drift."""
        return [d for d in self.differences if d.difference_type == DifferenceType.PROPERTY_DRIFT]
    
    @property
    def has_differences(self) -> bool:
        """Check if any differences were found."""
        return len(self.differences) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_group": self.resource_group,
            "summary": {
                "azure_resource_count": self.azure_resource_count,
                "terraform_resource_count": self.terraform_resource_count,
                "matched_count": self.matched_count,
                "missing_in_azure": len(self.missing_in_azure),
                "missing_in_terraform": len(self.missing_in_terraform),
                "drifted": len(self.drifted),
            },
            "differences": [d.to_dict() for d in self.differences],
        }


# Terraform to Azure property mappings for each resource type
PROPERTY_MAPPINGS = {
    "azurerm_storage_account": {
        "name": "name",
        "location": "location",
        "account_tier": "properties.account_tier",
        "account_replication_type": "properties.account_replication_type",
        "access_tier": "properties.access_tier",
        "enable_https_traffic_only": "properties.enable_https_traffic_only",
        "min_tls_version": "properties.min_tls_version",
        "allow_nested_items_to_be_public": "properties.allow_blob_public_access",
        "tags": "tags",
    },
    "azurerm_virtual_network": {
        "name": "name",
        "location": "location",
        "address_space": "properties.address_space",
        "dns_servers": "properties.dns_servers",
        "tags": "tags",
    },
    "azurerm_network_security_group": {
        "name": "name",
        "location": "location",
        "tags": "tags",
        # Security rules compared separately
    },
    "azurerm_linux_virtual_machine": {
        "name": "name",
        "location": "location",
        "size": "properties.vm_size",
        "admin_username": "properties.os_profile.admin_username",
        "computer_name": "properties.os_profile.computer_name",
        "tags": "tags",
    },
    "azurerm_windows_virtual_machine": {
        "name": "name",
        "location": "location",
        "size": "properties.vm_size",
        "admin_username": "properties.os_profile.admin_username",
        "computer_name": "properties.os_profile.computer_name",
        "tags": "tags",
    },
    "azurerm_key_vault": {
        "name": "name",
        "location": "location",
        "sku_name": "properties.sku_name",
        "soft_delete_retention_days": "properties.soft_delete_enabled",
        "purge_protection_enabled": "properties.purge_protection_enabled",
        "enabled_for_deployment": "properties.enabled_for_deployment",
        "enabled_for_disk_encryption": "properties.enabled_for_disk_encryption",
        "enabled_for_template_deployment": "properties.enabled_for_template_deployment",
        "tags": "tags",
    },
}


class ComparisonEngine:
    """Engine for deep comparison of Azure resources and Terraform definitions."""
    
    def __init__(self):
        """Initialize the comparison engine."""
        pass
    
    def compare(
        self,
        resource_group: str,
        azure_resources: List[AzureResource],
        terraform_resources: List[TerraformResource],
    ) -> ComparisonResult:
        """Compare Azure resources with Terraform definitions.
        
        Args:
            resource_group: Name of the resource group.
            azure_resources: List of resources from Azure.
            terraform_resources: List of resources from Terraform.
            
        Returns:
            ComparisonResult with all differences found.
        """
        result = ComparisonResult(
            resource_group=resource_group,
            azure_resource_count=len(azure_resources),
            terraform_resource_count=len(terraform_resources),
        )
        
        # Index Azure resources by type and name
        azure_index: Dict[str, Dict[str, AzureResource]] = {}
        for resource in azure_resources:
            if resource.resource_type not in azure_index:
                azure_index[resource.resource_type] = {}
            azure_index[resource.resource_type][resource.name.lower()] = resource
        
        # Index Terraform resources by Azure type and name
        terraform_index: Dict[str, Dict[str, TerraformResource]] = {}
        for resource in terraform_resources:
            azure_type = TERRAFORM_TO_AZURE_TYPE.get(
                resource.terraform_type, resource.terraform_type
            )
            if azure_type not in terraform_index:
                terraform_index[azure_type] = {}
            resource_name = resource.resource_name.lower() if resource.resource_name else resource.name.lower()
            terraform_index[azure_type][resource_name] = resource
        
        # Track matched resources
        matched_azure: Set[str] = set()
        matched_terraform: Set[str] = set()
        
        # Compare Terraform resources against Azure
        for tf_resource in terraform_resources:
            azure_type = TERRAFORM_TO_AZURE_TYPE.get(
                tf_resource.terraform_type, tf_resource.terraform_type
            )
            resource_name = tf_resource.resource_name.lower() if tf_resource.resource_name else tf_resource.name.lower()
            
            # Skip if resource name contains unresolved variables
            if "<variable:" in resource_name:
                continue
            
            azure_resource = azure_index.get(azure_type, {}).get(resource_name)
            
            if not azure_resource:
                # Resource missing in Azure
                result.differences.append(
                    ResourceDifference(
                        difference_type=DifferenceType.MISSING_IN_AZURE,
                        resource_name=tf_resource.resource_name or tf_resource.name,
                        resource_type=azure_type,
                        terraform_type=tf_resource.terraform_type,
                        terraform_resource=tf_resource,
                        risk_level=RiskLevel.MEDIUM,
                    )
                )
            else:
                # Resource exists - compare properties
                matched_azure.add(f"{azure_type}:{resource_name}")
                matched_terraform.add(f"{tf_resource.terraform_type}:{resource_name}")
                
                property_diffs = self._compare_properties(
                    tf_resource, azure_resource
                )
                
                if property_diffs:
                    result.differences.append(
                        ResourceDifference(
                            difference_type=DifferenceType.PROPERTY_DRIFT,
                            resource_name=azure_resource.name,
                            resource_type=azure_type,
                            terraform_type=tf_resource.terraform_type,
                            terraform_resource=tf_resource,
                            azure_resource=azure_resource,
                            property_differences=property_diffs,
                            risk_level=self._assess_risk(property_diffs),
                        )
                    )
                else:
                    result.matched_count += 1
        
        # Find resources in Azure but not in Terraform
        for azure_type, resources in azure_index.items():
            for resource_name, azure_resource in resources.items():
                key = f"{azure_type}:{resource_name}"
                if key not in matched_azure:
                    result.differences.append(
                        ResourceDifference(
                            difference_type=DifferenceType.MISSING_IN_TERRAFORM,
                            resource_name=azure_resource.name,
                            resource_type=azure_type,
                            azure_resource=azure_resource,
                            risk_level=RiskLevel.LOW,  # Informational
                        )
                    )
        
        return result
    
    def _compare_properties(
        self,
        terraform_resource: TerraformResource,
        azure_resource: AzureResource,
    ) -> List[PropertyDifference]:
        """Compare properties between Terraform and Azure resource.
        
        Args:
            terraform_resource: Terraform resource definition.
            azure_resource: Azure resource.
            
        Returns:
            List of property differences.
        """
        differences = []
        
        # Get property mapping for this resource type
        mapping = PROPERTY_MAPPINGS.get(terraform_resource.terraform_type, {})
        
        for tf_prop, azure_path in mapping.items():
            tf_value = terraform_resource.config.get(tf_prop)
            azure_value = self._get_nested_value(azure_resource, azure_path)
            
            # Skip if Terraform value is not set or is a variable
            if tf_value is None:
                continue
            if isinstance(tf_value, str) and "<variable:" in tf_value:
                continue
            
            # Normalize values for comparison
            tf_normalized = self._normalize_value(tf_value)
            azure_normalized = self._normalize_value(azure_value)
            
            if not self._values_equal(tf_normalized, azure_normalized):
                differences.append(
                    PropertyDifference(
                        property_path=tf_prop,
                        terraform_value=tf_value,
                        azure_value=azure_value,
                        description=f"Property '{tf_prop}' differs",
                    )
                )
        
        # Deep compare tags
        tf_tags = terraform_resource.config.get("tags", {})
        azure_tags = azure_resource.tags or {}
        tag_diffs = self._compare_tags(tf_tags, azure_tags)
        differences.extend(tag_diffs)
        
        return differences
    
    def _get_nested_value(self, resource: AzureResource, path: str) -> Any:
        """Get a nested value from an Azure resource using dot notation."""
        parts = path.split(".")
        value: Any = resource
        
        for part in parts:
            if isinstance(value, AzureResource):
                value = getattr(value, part, None)
            elif isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    def _normalize_value(self, value: Any) -> Any:
        """Normalize a value for comparison."""
        if value is None:
            return None
        if isinstance(value, str):
            return value.lower().strip()
        if isinstance(value, list):
            return sorted([self._normalize_value(v) for v in value])
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k, v in value.items()}
        return value
    
    def _values_equal(self, val1: Any, val2: Any) -> bool:
        """Check if two normalized values are equal."""
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False
        
        # Handle list comparison
        if isinstance(val1, list) and isinstance(val2, list):
            if len(val1) != len(val2):
                return False
            return all(self._values_equal(v1, v2) for v1, v2 in zip(val1, val2))
        
        # Handle dict comparison
        if isinstance(val1, dict) and isinstance(val2, dict):
            if set(val1.keys()) != set(val2.keys()):
                return False
            return all(self._values_equal(val1[k], val2[k]) for k in val1)
        
        return val1 == val2
    
    def _compare_tags(
        self, tf_tags: Dict[str, str], azure_tags: Dict[str, str]
    ) -> List[PropertyDifference]:
        """Compare tags between Terraform and Azure."""
        differences = []
        
        # Normalize tag keys for comparison
        tf_tags_lower = {k.lower(): v for k, v in (tf_tags or {}).items()}
        azure_tags_lower = {k.lower(): v for k, v in (azure_tags or {}).items()}
        
        all_keys = set(tf_tags_lower.keys()) | set(azure_tags_lower.keys())
        
        for key in all_keys:
            tf_value = tf_tags_lower.get(key)
            azure_value = azure_tags_lower.get(key)
            
            if tf_value != azure_value:
                if tf_value is None:
                    # Tag exists in Azure but not in Terraform - skip (info only)
                    pass
                elif azure_value is None:
                    differences.append(
                        PropertyDifference(
                            property_path=f"tags.{key}",
                            terraform_value=tf_value,
                            azure_value=None,
                            description=f"Tag '{key}' missing in Azure",
                        )
                    )
                else:
                    differences.append(
                        PropertyDifference(
                            property_path=f"tags.{key}",
                            terraform_value=tf_value,
                            azure_value=azure_value,
                            description=f"Tag '{key}' value differs",
                        )
                    )
        
        return differences
    
    def _assess_risk(self, differences: List[PropertyDifference]) -> RiskLevel:
        """Assess the risk level based on property differences."""
        high_risk_properties = {
            "network_rules", "access_policies", "security_rules",
            "admin_username", "admin_password", "sku_name", "size",
        }
        
        medium_risk_properties = {
            "location", "address_space", "subnets", "vm_size",
        }
        
        for diff in differences:
            prop_name = diff.property_path.split(".")[-1]
            if prop_name in high_risk_properties:
                return RiskLevel.HIGH
        
        for diff in differences:
            prop_name = diff.property_path.split(".")[-1]
            if prop_name in medium_risk_properties:
                return RiskLevel.MEDIUM
        
        return RiskLevel.LOW


def compare_resources(
    resource_group: str,
    azure_resources: List[AzureResource],
    terraform_resources: List[TerraformResource],
) -> ComparisonResult:
    """Compare Azure resources with Terraform definitions.
    
    Args:
        resource_group: Name of the resource group.
        azure_resources: List of resources from Azure.
        terraform_resources: List of resources from Terraform.
        
    Returns:
        ComparisonResult with all differences found.
    """
    engine = ComparisonEngine()
    return engine.compare(resource_group, azure_resources, terraform_resources)
