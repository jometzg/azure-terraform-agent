"""Azure AI Foundry Agent for Terraform-Azure comparison."""

import os
from typing import Optional

from azure.ai.agents.models import FunctionTool, ToolSet
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from .agent_tools import AGENT_TOOLS
from .config import Config


AGENT_INSTRUCTIONS = """You are an Azure Infrastructure Comparison Agent. Your purpose is to help users compare their Azure resource groups with Terraform definitions and align them.

## Your Capabilities

1. **Scan Azure Resources**: Use `scan_resource_group()` to scan all supported resources in an Azure resource group. This retrieves detailed information about Storage Accounts, Virtual Networks, Network Security Groups, Virtual Machines, and Key Vaults.

2. **Fetch Terraform Definitions**: Use `fetch_terraform_from_git()` to clone a Git repository and parse Terraform .tf files. Supports branch/tag selection, private repos with PAT, and subdirectories.

3. **Compare Resources**: Use `compare_azure_with_terraform()` to identify differences between Azure state and Terraform definitions:
   - Resources missing in Azure (need to be created)
   - Resources missing in Terraform (informational only)
   - Configuration drift (properties differ)

4. **Generate CLI Commands**: Use `generate_alignment_commands()` to create Azure CLI commands that will align resources. Only create and update commands are generated (no deletes for safety).

5. **Generate Reports**: Use `generate_report()` to create a comprehensive Markdown report with summary, differences, and suggested commands.

6. **Execute Commands**: Use `execute_commands()` to run approved CLI commands. ALWAYS require explicit user approval before executing any commands.

## Workflow

When a user asks to compare resources, follow this workflow:

1. First, ask for:
   - Azure subscription ID
   - Resource group name to scan
   - Git repository URL for Terraform files
   - (Optional) Branch/tag and subdirectory

2. Scan the Azure resource group

3. Fetch and parse Terraform definitions

4. Run the comparison

5. Generate and present the report

6. If the user wants to make changes:
   - Generate CLI commands
   - Present commands with risk levels
   - REQUIRE explicit approval before execution
   - Execute only approved commands

## Safety Guidelines

- NEVER execute commands without explicit user approval
- ALWAYS explain what each command will do before execution
- Highlight HIGH risk operations clearly
- No DELETE operations are supported - inform users about this limitation
- If credentials or permissions fail, provide helpful troubleshooting guidance

## Session Management

- Use `get_session_state()` to check what has already been done in the current session
- Use `clear_session()` to start fresh if needed

Remember: You are helping infrastructure teams maintain consistency between their Infrastructure as Code and actual Azure resources. Be thorough, cautious, and helpful.
"""


class TerraformComparisonAgent:
    """Azure AI Foundry agent for Terraform-Azure comparison."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the agent.
        
        Args:
            config: Configuration object. If not provided, loads from environment.
        """
        self.config = config or Config.from_env()
        self.credential = DefaultAzureCredential()
        self._client: Optional[AIProjectClient] = None
        self._agent = None
        self._thread = None
    
    @property
    def client(self) -> AIProjectClient:
        """Get or create the AI Project client."""
        if self._client is None:
            self._client = AIProjectClient(
                credential=self.credential,
                endpoint=self.config.project_endpoint,
            )
        return self._client
    
    def create_agent(self) -> None:
        """Create the AI agent with tools."""
        # Create function tools from our tool functions
        functions = FunctionTool(functions=AGENT_TOOLS)
        
        # Create toolset and enable auto-execution
        toolset = ToolSet()
        toolset.add(functions)
        self.client.agents.enable_auto_function_calls(toolset)
        
        # Create the agent
        self._agent = self.client.agents.create_agent(
            model=self.config.model_deployment_name,
            name="terraform-azure-comparison-agent",
            instructions=AGENT_INSTRUCTIONS,
            toolset=toolset,
        )
        
        print(f"Agent created: {self._agent.id}")
    
    def start_conversation(self) -> None:
        """Start a new conversation thread."""
        self._thread = self.client.agents.threads.create()
        print(f"Thread created: {self._thread.id}")
    
    def send_message(self, message: str) -> str:
        """Send a message and get a response.
        
        Args:
            message: User message to send.
            
        Returns:
            Agent's response text.
        """
        if not self._agent:
            raise RuntimeError("Agent not created. Call create_agent() first.")
        
        if not self._thread:
            self.start_conversation()
        
        # Add user message
        self.client.agents.messages.create(
            thread_id=self._thread.id,
            role="user",
            content=message,
        )
        
        # Process the run (auto-executes tools)
        run = self.client.agents.runs.create_and_process(
            thread_id=self._thread.id,
            agent_id=self._agent.id,
        )
        
        # Get response messages
        messages = self.client.agents.messages.list(thread_id=self._thread.id)
        
        # Find the latest assistant message
        for msg in messages:
            if msg.role == "assistant" and msg.text_messages:
                return msg.text_messages[-1].text.value
        
        return "No response generated."
    
    def cleanup(self) -> None:
        """Clean up agent and thread."""
        if self._agent:
            try:
                self.client.agents.delete_agent(self._agent.id)
                print(f"Agent deleted: {self._agent.id}")
            except Exception as e:
                print(f"Error deleting agent: {e}")
        
        if self._thread:
            try:
                self.client.agents.threads.delete(self._thread.id)
                print(f"Thread deleted: {self._thread.id}")
            except Exception as e:
                print(f"Error deleting thread: {e}")


def create_agent() -> TerraformComparisonAgent:
    """Create and initialize the Terraform comparison agent.
    
    Returns:
        Initialized TerraformComparisonAgent ready for conversation.
        
    Example:
        agent = create_agent()
        agent.create_agent()
        response = agent.send_message("Compare my-rg with terraform from https://github.com/org/infra")
        print(response)
        agent.cleanup()
    """
    return TerraformComparisonAgent()
