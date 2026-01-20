"""Azure resource scanning using management SDK."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient


@dataclass
class AzureResource:
    """Represents an Azure resource with its properties."""
    
    name: str
    resource_type: str
    location: str
    resource_group: str
    resource_id: str
    tags: Dict[str, str] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    sku: Optional[Dict[str, Any]] = None
    kind: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "resource_type": self.resource_type,
            "location": self.location,
            "resource_group": self.resource_group,
            "resource_id": self.resource_id,
            "tags": self.tags,
            "properties": self.properties,
            "sku": self.sku,
            "kind": self.kind,
        }


class AzureScanner:
    """Scans Azure resources in a resource group."""
    
    def __init__(self, subscription_id: str, credential: Optional[DefaultAzureCredential] = None):
        """Initialize scanner with Azure credentials.
        
        Args:
            subscription_id: Azure subscription ID.
            credential: Azure credential (uses DefaultAzureCredential if not provided).
        """
        self.subscription_id = subscription_id
        self.credential = credential or DefaultAzureCredential()
        
        # Initialize management clients
        self._resource_client = ResourceManagementClient(
            self.credential, self.subscription_id
        )
        self._compute_client = ComputeManagementClient(
            self.credential, self.subscription_id
        )
        self._network_client = NetworkManagementClient(
            self.credential, self.subscription_id
        )
        self._storage_client = StorageManagementClient(
            self.credential, self.subscription_id
        )
        self._keyvault_client = KeyVaultManagementClient(
            self.credential, self.subscription_id
        )
    
    def scan_resource_group(self, resource_group_name: str) -> List[AzureResource]:
        """Scan all supported resources in a resource group.
        
        Args:
            resource_group_name: Name of the resource group to scan.
            
        Returns:
            List of AzureResource objects with full details.
        """
        resources: List[AzureResource] = []
        
        # Scan each resource type
        resources.extend(self._scan_storage_accounts(resource_group_name))
        resources.extend(self._scan_virtual_networks(resource_group_name))
        resources.extend(self._scan_network_security_groups(resource_group_name))
        resources.extend(self._scan_virtual_machines(resource_group_name))
        resources.extend(self._scan_key_vaults(resource_group_name))
        
        return resources
    
    def _scan_storage_accounts(self, resource_group_name: str) -> List[AzureResource]:
        """Scan storage accounts in the resource group."""
        resources = []
        
        try:
            for account in self._storage_client.storage_accounts.list_by_resource_group(
                resource_group_name
            ):
                resources.append(
                    AzureResource(
                        name=account.name,
                        resource_type="Microsoft.Storage/storageAccounts",
                        location=account.location,
                        resource_group=resource_group_name,
                        resource_id=account.id,
                        tags=dict(account.tags) if account.tags else {},
                        properties={
                            "account_tier": account.sku.tier if account.sku else None,
                            "account_replication_type": account.sku.name.split("_")[-1] if account.sku else None,
                            "access_tier": account.access_tier,
                            "enable_https_traffic_only": account.enable_https_traffic_only,
                            "min_tls_version": account.minimum_tls_version,
                            "allow_blob_public_access": account.allow_blob_public_access,
                            "network_rules": self._serialize_network_rules(account.network_rule_set),
                            "blob_properties": self._get_blob_properties(resource_group_name, account.name),
                        },
                        sku={
                            "name": account.sku.name if account.sku else None,
                            "tier": account.sku.tier if account.sku else None,
                        },
                        kind=account.kind,
                    )
                )
        except Exception as e:
            print(f"Error scanning storage accounts: {e}")
        
        return resources
    
    def _serialize_network_rules(self, network_rules) -> Optional[Dict[str, Any]]:
        """Serialize network rule set to dictionary."""
        if not network_rules:
            return None
        return {
            "default_action": network_rules.default_action,
            "bypass": network_rules.bypass,
            "ip_rules": [{"value": r.ip_address_or_range} for r in (network_rules.ip_rules or [])],
            "virtual_network_rules": [
                {"subnet_id": r.virtual_network_resource_id}
                for r in (network_rules.virtual_network_rules or [])
            ],
        }
    
    def _get_blob_properties(self, resource_group_name: str, account_name: str) -> Dict[str, Any]:
        """Get blob service properties for a storage account."""
        try:
            props = self._storage_client.blob_services.get_service_properties(
                resource_group_name, account_name
            )
            return {
                "versioning_enabled": props.is_versioning_enabled,
                "delete_retention_days": (
                    props.delete_retention_policy.days
                    if props.delete_retention_policy and props.delete_retention_policy.enabled
                    else None
                ),
            }
        except Exception:
            return {}
    
    def _scan_virtual_networks(self, resource_group_name: str) -> List[AzureResource]:
        """Scan virtual networks in the resource group."""
        resources = []
        
        try:
            for vnet in self._network_client.virtual_networks.list(resource_group_name):
                subnets = []
                for subnet in vnet.subnets or []:
                    subnets.append({
                        "name": subnet.name,
                        "address_prefix": subnet.address_prefix,
                        "address_prefixes": subnet.address_prefixes,
                        "network_security_group_id": (
                            subnet.network_security_group.id
                            if subnet.network_security_group
                            else None
                        ),
                    })
                
                resources.append(
                    AzureResource(
                        name=vnet.name,
                        resource_type="Microsoft.Network/virtualNetworks",
                        location=vnet.location,
                        resource_group=resource_group_name,
                        resource_id=vnet.id,
                        tags=dict(vnet.tags) if vnet.tags else {},
                        properties={
                            "address_space": vnet.address_space.address_prefixes if vnet.address_space else [],
                            "subnets": subnets,
                            "dns_servers": (
                                vnet.dhcp_options.dns_servers
                                if vnet.dhcp_options
                                else []
                            ),
                            "enable_ddos_protection": vnet.enable_ddos_protection,
                        },
                    )
                )
        except Exception as e:
            print(f"Error scanning virtual networks: {e}")
        
        return resources
    
    def _scan_network_security_groups(self, resource_group_name: str) -> List[AzureResource]:
        """Scan network security groups in the resource group."""
        resources = []
        
        try:
            for nsg in self._network_client.network_security_groups.list(resource_group_name):
                security_rules = []
                for rule in nsg.security_rules or []:
                    security_rules.append({
                        "name": rule.name,
                        "priority": rule.priority,
                        "direction": rule.direction,
                        "access": rule.access,
                        "protocol": rule.protocol,
                        "source_port_range": rule.source_port_range,
                        "destination_port_range": rule.destination_port_range,
                        "source_address_prefix": rule.source_address_prefix,
                        "destination_address_prefix": rule.destination_address_prefix,
                    })
                
                resources.append(
                    AzureResource(
                        name=nsg.name,
                        resource_type="Microsoft.Network/networkSecurityGroups",
                        location=nsg.location,
                        resource_group=resource_group_name,
                        resource_id=nsg.id,
                        tags=dict(nsg.tags) if nsg.tags else {},
                        properties={
                            "security_rules": security_rules,
                        },
                    )
                )
        except Exception as e:
            print(f"Error scanning network security groups: {e}")
        
        return resources
    
    def _scan_virtual_machines(self, resource_group_name: str) -> List[AzureResource]:
        """Scan virtual machines in the resource group."""
        resources = []
        
        try:
            for vm in self._compute_client.virtual_machines.list(resource_group_name):
                # Get instance view for additional details
                instance_view = None
                try:
                    instance_view = self._compute_client.virtual_machines.instance_view(
                        resource_group_name, vm.name
                    )
                except Exception:
                    pass
                
                os_profile = {}
                if vm.os_profile:
                    os_profile = {
                        "computer_name": vm.os_profile.computer_name,
                        "admin_username": vm.os_profile.admin_username,
                        "linux_configuration": (
                            {
                                "disable_password_authentication": (
                                    vm.os_profile.linux_configuration.disable_password_authentication
                                    if vm.os_profile.linux_configuration
                                    else None
                                ),
                            }
                            if vm.os_profile.linux_configuration
                            else None
                        ),
                    }
                
                storage_profile = {}
                if vm.storage_profile:
                    storage_profile = {
                        "os_disk": {
                            "name": vm.storage_profile.os_disk.name if vm.storage_profile.os_disk else None,
                            "caching": vm.storage_profile.os_disk.caching if vm.storage_profile.os_disk else None,
                            "create_option": (
                                vm.storage_profile.os_disk.create_option
                                if vm.storage_profile.os_disk
                                else None
                            ),
                            "disk_size_gb": (
                                vm.storage_profile.os_disk.disk_size_gb
                                if vm.storage_profile.os_disk
                                else None
                            ),
                        },
                        "image_reference": (
                            {
                                "publisher": vm.storage_profile.image_reference.publisher,
                                "offer": vm.storage_profile.image_reference.offer,
                                "sku": vm.storage_profile.image_reference.sku,
                                "version": vm.storage_profile.image_reference.version,
                            }
                            if vm.storage_profile.image_reference
                            else None
                        ),
                    }
                
                network_interfaces = []
                if vm.network_profile and vm.network_profile.network_interfaces:
                    for nic in vm.network_profile.network_interfaces:
                        network_interfaces.append({
                            "id": nic.id,
                            "primary": nic.primary,
                        })
                
                resources.append(
                    AzureResource(
                        name=vm.name,
                        resource_type="Microsoft.Compute/virtualMachines",
                        location=vm.location,
                        resource_group=resource_group_name,
                        resource_id=vm.id,
                        tags=dict(vm.tags) if vm.tags else {},
                        properties={
                            "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
                            "os_profile": os_profile,
                            "storage_profile": storage_profile,
                            "network_interfaces": network_interfaces,
                            "power_state": self._get_power_state(instance_view),
                        },
                        sku={"name": vm.hardware_profile.vm_size} if vm.hardware_profile else None,
                    )
                )
        except Exception as e:
            print(f"Error scanning virtual machines: {e}")
        
        return resources
    
    def _get_power_state(self, instance_view) -> Optional[str]:
        """Extract power state from VM instance view."""
        if not instance_view or not instance_view.statuses:
            return None
        for status in instance_view.statuses:
            if status.code and status.code.startswith("PowerState/"):
                return status.code.split("/")[-1]
        return None
    
    def _scan_key_vaults(self, resource_group_name: str) -> List[AzureResource]:
        """Scan key vaults in the resource group."""
        resources = []
        
        try:
            for vault in self._keyvault_client.vaults.list_by_resource_group(resource_group_name):
                access_policies = []
                if vault.properties and vault.properties.access_policies:
                    for policy in vault.properties.access_policies:
                        access_policies.append({
                            "tenant_id": str(policy.tenant_id),
                            "object_id": policy.object_id,
                            "permissions": {
                                "keys": list(policy.permissions.keys) if policy.permissions.keys else [],
                                "secrets": list(policy.permissions.secrets) if policy.permissions.secrets else [],
                                "certificates": (
                                    list(policy.permissions.certificates)
                                    if policy.permissions.certificates
                                    else []
                                ),
                            },
                        })
                
                resources.append(
                    AzureResource(
                        name=vault.name,
                        resource_type="Microsoft.KeyVault/vaults",
                        location=vault.location,
                        resource_group=resource_group_name,
                        resource_id=vault.id,
                        tags=dict(vault.tags) if vault.tags else {},
                        properties={
                            "tenant_id": str(vault.properties.tenant_id) if vault.properties else None,
                            "sku_name": vault.properties.sku.name if vault.properties and vault.properties.sku else None,
                            "soft_delete_enabled": (
                                vault.properties.enable_soft_delete
                                if vault.properties
                                else None
                            ),
                            "purge_protection_enabled": (
                                vault.properties.enable_purge_protection
                                if vault.properties
                                else None
                            ),
                            "enabled_for_deployment": (
                                vault.properties.enabled_for_deployment
                                if vault.properties
                                else None
                            ),
                            "enabled_for_disk_encryption": (
                                vault.properties.enabled_for_disk_encryption
                                if vault.properties
                                else None
                            ),
                            "enabled_for_template_deployment": (
                                vault.properties.enabled_for_template_deployment
                                if vault.properties
                                else None
                            ),
                            "access_policies": access_policies,
                            "network_acls": (
                                {
                                    "default_action": vault.properties.network_acls.default_action,
                                    "bypass": vault.properties.network_acls.bypass,
                                }
                                if vault.properties and vault.properties.network_acls
                                else None
                            ),
                        },
                        sku={
                            "name": vault.properties.sku.name if vault.properties and vault.properties.sku else None,
                            "family": vault.properties.sku.family if vault.properties and vault.properties.sku else None,
                        },
                    )
                )
        except Exception as e:
            print(f"Error scanning key vaults: {e}")
        
        return resources


def scan_azure_resources(
    subscription_id: str,
    resource_group_name: str,
) -> List[AzureResource]:
    """Scan all supported resources in an Azure resource group.
    
    Args:
        subscription_id: Azure subscription ID.
        resource_group_name: Name of the resource group to scan.
        
    Returns:
        List of AzureResource objects with full details.
        
    Example:
        resources = scan_azure_resources("sub-123", "my-resource-group")
        for resource in resources:
            print(f"{resource.resource_type}: {resource.name}")
    """
    scanner = AzureScanner(subscription_id)
    return scanner.scan_resource_group(resource_group_name)
