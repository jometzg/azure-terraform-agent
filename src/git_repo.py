"""Git repository management for fetching Terraform files."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

import git


@dataclass
class RepoConfig:
    """Configuration for Git repository access."""
    
    url: str
    branch: Optional[str] = None
    tag: Optional[str] = None
    commit: Optional[str] = None
    subdirectory: Optional[str] = None
    pat: Optional[str] = None


class GitRepository:
    """Manages Git repository operations for fetching Terraform files."""
    
    def __init__(self, config: RepoConfig):
        """Initialize with repository configuration.
        
        Args:
            config: Repository configuration including URL, branch, and credentials.
        """
        self.config = config
        self._temp_dir: Optional[str] = None
        self._repo: Optional[git.Repo] = None
    
    def _get_authenticated_url(self) -> str:
        """Get URL with embedded PAT for private repos.
        
        Returns:
            URL with authentication if PAT is provided, otherwise original URL.
        """
        if not self.config.pat:
            return self.config.url
        
        parsed = urlparse(self.config.url)
        if parsed.scheme in ("http", "https"):
            # Embed PAT in URL: https://PAT@github.com/...
            netloc = f"{self.config.pat}@{parsed.netloc}"
            authenticated = parsed._replace(netloc=netloc)
            return urlunparse(authenticated)
        
        return self.config.url
    
    def clone(self) -> Path:
        """Clone the repository to a temporary directory.
        
        Returns:
            Path to the cloned repository (or subdirectory if specified).
            
        Raises:
            git.GitCommandError: If cloning fails.
        """
        self._temp_dir = tempfile.mkdtemp(prefix="terraform_")
        
        # Determine which ref to checkout
        ref = self.config.branch or self.config.tag or "main"
        
        # Clone the repository
        self._repo = git.Repo.clone_from(
            self._get_authenticated_url(),
            self._temp_dir,
            branch=ref if not self.config.tag else None,
            depth=1,  # Shallow clone for efficiency
        )
        
        # If tag specified, checkout the tag
        if self.config.tag:
            self._repo.git.checkout(self.config.tag)
        
        # If specific commit specified, checkout that commit
        if self.config.commit:
            self._repo.git.checkout(self.config.commit)
        
        # Return path to subdirectory if specified
        base_path = Path(self._temp_dir)
        if self.config.subdirectory:
            target_path = base_path / self.config.subdirectory
            if not target_path.exists():
                raise FileNotFoundError(
                    f"Subdirectory '{self.config.subdirectory}' not found in repository"
                )
            return target_path
        
        return base_path
    
    def cleanup(self) -> None:
        """Remove the temporary directory."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
            self._repo = None
    
    def __enter__(self) -> Path:
        """Context manager entry - clone the repo."""
        return self.clone()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup."""
        self.cleanup()


def clone_terraform_repo(
    url: str,
    branch: Optional[str] = None,
    tag: Optional[str] = None,
    subdirectory: Optional[str] = None,
    pat: Optional[str] = None,
) -> GitRepository:
    """Create a GitRepository instance for cloning Terraform files.
    
    Args:
        url: Git repository URL (HTTPS or SSH).
        branch: Branch name to checkout (default: main).
        tag: Tag to checkout (overrides branch).
        subdirectory: Path within repo containing Terraform files.
        pat: Personal Access Token for private repos.
        
    Returns:
        GitRepository instance ready to be used as context manager.
        
    Example:
        with clone_terraform_repo("https://github.com/org/infra.git", subdirectory="terraform") as path:
            # path is now a Path to the terraform directory
            for tf_file in path.glob("*.tf"):
                print(tf_file)
    """
    config = RepoConfig(
        url=url,
        branch=branch,
        tag=tag,
        subdirectory=subdirectory,
        pat=pat,
    )
    return GitRepository(config)
