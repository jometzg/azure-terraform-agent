"""Configuration management for the agent."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration."""
    
    # Azure AI Foundry
    project_endpoint: str
    model_deployment_name: str
    
    # Azure
    subscription_id: Optional[str] = None
    
    # Git
    git_pat: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        load_dotenv()
        
        project_endpoint = os.getenv("PROJECT_ENDPOINT")
        if not project_endpoint:
            raise ValueError("PROJECT_ENDPOINT environment variable is required")
        
        model_deployment_name = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o")
        
        return cls(
            project_endpoint=project_endpoint,
            model_deployment_name=model_deployment_name,
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
            git_pat=os.getenv("GIT_PAT"),
        )
