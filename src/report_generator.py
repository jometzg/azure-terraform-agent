"""Markdown report generator for comparison results."""

from datetime import datetime
from typing import List, Optional

from .cli_generator import CliCommand
from .comparison_engine import (
    ComparisonResult,
    DifferenceType,
    ResourceDifference,
    RiskLevel,
)


class MarkdownReportGenerator:
    """Generates Markdown reports from comparison results."""
    
    def __init__(
        self,
        comparison_result: ComparisonResult,
        commands: List[CliCommand],
        terraform_source: str,
    ):
        """Initialize the report generator.
        
        Args:
            comparison_result: Result from comparison engine.
            commands: Generated CLI commands.
            terraform_source: Source of Terraform files (e.g., Git URL).
        """
        self.result = comparison_result
        self.commands = commands
        self.terraform_source = terraform_source
    
    def generate(self) -> str:
        """Generate the full Markdown report.
        
        Returns:
            Complete Markdown report as string.
        """
        sections = [
            self._generate_header(),
            self._generate_summary(),
            self._generate_resource_inventory(),
            self._generate_differences_section(),
            self._generate_commands_section(),
            self._generate_footer(),
        ]
        
        return "\n\n".join(sections)
    
    def _generate_header(self) -> str:
        """Generate report header."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        return f"""# Azure Resource Comparison Report

**Generated:** {timestamp}  
**Resource Group:** `{self.result.resource_group}`  
**Terraform Source:** `{self.terraform_source}`"""
    
    def _generate_summary(self) -> str:
        """Generate summary section."""
        status_emoji = "✅" if not self.result.has_differences else "⚠️"
        
        summary = f"""## Summary {status_emoji}

| Metric | Count |
|--------|-------|
| Azure Resources Scanned | {self.result.azure_resource_count} |
| Terraform Resources Defined | {self.result.terraform_resource_count} |
| Resources Matched | {self.result.matched_count} |
| Missing in Azure | {len(self.result.missing_in_azure)} |
| Missing in Terraform | {len(self.result.missing_in_terraform)} |
| Configuration Drift | {len(self.result.drifted)} |"""
        
        if not self.result.has_differences:
            summary += "\n\n✅ **All resources are in sync!**"
        else:
            # Risk summary
            high_risk = sum(1 for d in self.result.differences if d.risk_level == RiskLevel.HIGH)
            medium_risk = sum(1 for d in self.result.differences if d.risk_level == RiskLevel.MEDIUM)
            low_risk = sum(1 for d in self.result.differences if d.risk_level == RiskLevel.LOW)
            
            summary += f"""

### Risk Assessment

| Risk Level | Count |
|------------|-------|
| 🔴 High | {high_risk} |
| 🟡 Medium | {medium_risk} |
| 🟢 Low | {low_risk} |"""
        
        return summary
    
    def _generate_resource_inventory(self) -> str:
        """Generate resource inventory section."""
        # Group resources by type
        azure_by_type: dict = {}
        for diff in self.result.differences:
            if diff.azure_resource:
                rt = diff.resource_type
                if rt not in azure_by_type:
                    azure_by_type[rt] = []
                azure_by_type[rt].append(diff.azure_resource.name)
        
        # Also count matched resources
        for diff in self.result.differences:
            if diff.difference_type == DifferenceType.PROPERTY_DRIFT:
                rt = diff.resource_type
                if rt not in azure_by_type:
                    azure_by_type[rt] = []
                if diff.resource_name not in azure_by_type[rt]:
                    azure_by_type[rt].append(diff.resource_name)
        
        inventory = "## Resource Inventory\n\n### Azure Resources\n\n"
        
        if azure_by_type:
            inventory += "| Resource Type | Resources |\n|---------------|----------|\n"
            for rt, names in sorted(azure_by_type.items()):
                inventory += f"| `{rt}` | {', '.join(sorted(set(names)))} |\n"
        else:
            inventory += "*No resources found in Azure.*\n"
        
        return inventory
    
    def _generate_differences_section(self) -> str:
        """Generate detailed differences section."""
        if not self.result.has_differences:
            return "## Differences\n\n*No differences found.*"
        
        sections = ["## Differences"]
        
        # Missing in Azure
        if self.result.missing_in_azure:
            sections.append(self._format_missing_in_azure())
        
        # Configuration Drift
        if self.result.drifted:
            sections.append(self._format_drift())
        
        # Missing in Terraform (informational)
        if self.result.missing_in_terraform:
            sections.append(self._format_missing_in_terraform())
        
        return "\n\n".join(sections)
    
    def _format_missing_in_azure(self) -> str:
        """Format missing in Azure section."""
        section = "### ❌ Missing in Azure\n\n"
        section += "These resources are defined in Terraform but do not exist in Azure:\n\n"
        section += "| Resource | Terraform Type | Location |\n"
        section += "|----------|----------------|----------|\n"
        
        for diff in self.result.missing_in_azure:
            location = diff.terraform_resource.location if diff.terraform_resource else "N/A"
            section += f"| `{diff.resource_name}` | `{diff.terraform_type}` | {location} |\n"
        
        return section
    
    def _format_drift(self) -> str:
        """Format configuration drift section."""
        section = "### ⚡ Configuration Drift\n\n"
        section += "These resources exist but have different configurations:\n\n"
        
        for diff in self.result.drifted:
            risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[diff.risk_level.value]
            section += f"#### {risk_emoji} `{diff.resource_name}` ({diff.terraform_type})\n\n"
            section += "| Property | Terraform Value | Azure Value |\n"
            section += "|----------|-----------------|-------------|\n"
            
            for prop_diff in diff.property_differences:
                tf_val = self._format_value(prop_diff.terraform_value)
                az_val = self._format_value(prop_diff.azure_value)
                section += f"| `{prop_diff.property_path}` | {tf_val} | {az_val} |\n"
            
            section += "\n"
        
        return section
    
    def _format_missing_in_terraform(self) -> str:
        """Format missing in Terraform section (informational)."""
        section = "### ℹ️ Resources Not in Terraform\n\n"
        section += "These resources exist in Azure but are not defined in the Terraform files:\n\n"
        section += "| Resource | Type | Location |\n"
        section += "|----------|------|----------|\n"
        
        for diff in self.result.missing_in_terraform:
            location = diff.azure_resource.location if diff.azure_resource else "N/A"
            section += f"| `{diff.resource_name}` | `{diff.resource_type}` | {location} |\n"
        
        section += "\n> **Note:** These resources are not managed by the compared Terraform configuration. "
        section += "No action will be taken for these resources."
        
        return section
    
    def _format_value(self, value) -> str:
        """Format a value for display in Markdown table."""
        if value is None:
            return "*not set*"
        if isinstance(value, bool):
            return "✓" if value else "✗"
        if isinstance(value, dict):
            if not value:
                return "*empty*"
            return ", ".join(f"{k}={v}" for k, v in list(value.items())[:3])
        if isinstance(value, list):
            if not value:
                return "*empty*"
            return ", ".join(str(v) for v in value[:3])
        
        str_val = str(value)
        if len(str_val) > 50:
            return str_val[:47] + "..."
        return str_val
    
    def _generate_commands_section(self) -> str:
        """Generate CLI commands section."""
        if not self.commands:
            return "## Suggested CLI Commands\n\n*No commands needed - resources are in sync.*"
        
        section = "## Suggested CLI Commands\n\n"
        section += "Execute these commands to align Azure resources with Terraform definitions:\n\n"
        section += "> ⚠️ **Warning:** Review each command carefully before execution.\n\n"
        
        # Group by action
        create_cmds = [c for c in self.commands if c.action == "create"]
        update_cmds = [c for c in self.commands if c.action == "update"]
        
        if create_cmds:
            section += "### Create Resources\n\n"
            for cmd in create_cmds:
                risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[cmd.risk_level.value]
                section += f"#### {risk_emoji} {cmd.description}\n\n"
                section += f"```bash\n{cmd.command}\n```\n\n"
        
        if update_cmds:
            section += "### Update Resources\n\n"
            for cmd in update_cmds:
                risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[cmd.risk_level.value]
                section += f"#### {risk_emoji} {cmd.description}\n\n"
                section += f"```bash\n{cmd.command}\n```\n\n"
        
        return section
    
    def _generate_footer(self) -> str:
        """Generate report footer."""
        return """---

## Next Steps

1. **Review** the differences and suggested commands carefully
2. **Approve** commands you want to execute
3. **Run** the agent's execute function with approved commands

> This report was generated by the Azure Terraform Comparison Agent.
> For questions or issues, consult your infrastructure team."""


def generate_markdown_report(
    comparison_result: ComparisonResult,
    commands: List[CliCommand],
    terraform_source: str,
) -> str:
    """Generate a Markdown report from comparison results.
    
    Args:
        comparison_result: Result from comparison engine.
        commands: Generated CLI commands.
        terraform_source: Source of Terraform files.
        
    Returns:
        Complete Markdown report as string.
    """
    generator = MarkdownReportGenerator(comparison_result, commands, terraform_source)
    return generator.generate()
