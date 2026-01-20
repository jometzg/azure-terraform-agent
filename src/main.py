"""Main entry point for the Terraform-Azure comparison agent."""

import argparse
import sys
from typing import Optional

from .agent import TerraformComparisonAgent, create_agent
from .config import Config


def interactive_mode(agent: TerraformComparisonAgent) -> None:
    """Run the agent in interactive mode.
    
    Args:
        agent: Initialized agent instance.
    """
    print("\n" + "=" * 60)
    print("Azure Terraform Comparison Agent")
    print("=" * 60)
    print("\nI can help you compare Azure resource groups with Terraform")
    print("definitions and suggest commands to align them.")
    print("\nCommands:")
    print("  /quit, /exit  - Exit the agent")
    print("  /clear        - Clear session state")
    print("  /status       - Show session status")
    print("  /help         - Show this help")
    print("\n" + "-" * 60 + "\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ("/quit", "/exit"):
                print("\nGoodbye!")
                break
            
            if user_input.lower() == "/clear":
                from .agent_tools import clear_session
                result = clear_session()
                print(f"Agent: {result}")
                continue
            
            if user_input.lower() == "/status":
                from .agent_tools import get_session_state
                result = get_session_state()
                print(f"Agent: {result}")
                continue
            
            if user_input.lower() == "/help":
                print("\nAvailable commands:")
                print("  /quit, /exit  - Exit the agent")
                print("  /clear        - Clear session state")
                print("  /status       - Show session status")
                print("  /help         - Show this help")
                print("\nOr type a message to interact with the agent.")
                continue
            
            # Send to agent
            response = agent.send_message(user_input)
            print(f"\nAgent: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


def single_query_mode(
    agent: TerraformComparisonAgent,
    subscription_id: str,
    resource_group: str,
    git_url: str,
    branch: Optional[str] = None,
    subdirectory: Optional[str] = None,
    output_report: Optional[str] = None,
) -> None:
    """Run a single comparison query.
    
    Args:
        agent: Initialized agent instance.
        subscription_id: Azure subscription ID.
        resource_group: Resource group to scan.
        git_url: Git repository URL.
        branch: Optional branch name.
        subdirectory: Optional subdirectory.
        output_report: Optional output file for report.
    """
    query = f"""Please compare the Azure resource group '{resource_group}' 
in subscription '{subscription_id}' with the Terraform definitions from '{git_url}'"""
    
    if branch:
        query += f" (branch: {branch})"
    if subdirectory:
        query += f" (subdirectory: {subdirectory})"
    
    query += ". Generate a detailed report of the differences."
    
    if output_report:
        query += f" Save the report to '{output_report}'."
    
    print(f"Query: {query}\n")
    print("-" * 60)
    
    response = agent.send_message(query)
    print(f"\n{response}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Azure Terraform Comparison Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python -m src.main
  
  # Single query mode
  python -m src.main --subscription SUB_ID --resource-group my-rg \\
    --git-url https://github.com/org/infra --subdirectory terraform
  
  # With report output
  python -m src.main --subscription SUB_ID --resource-group my-rg \\
    --git-url https://github.com/org/infra --output report.md
""",
    )
    
    parser.add_argument(
        "--subscription", "-s",
        help="Azure subscription ID",
    )
    parser.add_argument(
        "--resource-group", "-g",
        help="Azure resource group to scan",
    )
    parser.add_argument(
        "--git-url", "-u",
        help="Git repository URL for Terraform files",
    )
    parser.add_argument(
        "--branch", "-b",
        help="Git branch to checkout",
    )
    parser.add_argument(
        "--subdirectory", "-d",
        help="Subdirectory containing Terraform files",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for the Markdown report",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Force interactive mode even with other arguments",
    )
    
    args = parser.parse_args()
    
    # Create agent
    try:
        agent = create_agent()
        agent.create_agent()
        agent.start_conversation()
    except Exception as e:
        print(f"Error initializing agent: {e}")
        print("\nMake sure you have:")
        print("1. Set PROJECT_ENDPOINT environment variable")
        print("2. Set MODEL_DEPLOYMENT_NAME environment variable")
        print("3. Authenticated with Azure (az login)")
        return 1
    
    try:
        # Determine mode
        has_query_args = args.subscription and args.resource_group and args.git_url
        
        if args.interactive or not has_query_args:
            interactive_mode(agent)
        else:
            single_query_mode(
                agent,
                args.subscription,
                args.resource_group,
                args.git_url,
                args.branch,
                args.subdirectory,
                args.output,
            )
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    finally:
        agent.cleanup()


if __name__ == "__main__":
    sys.exit(main())
