"""Command execution with user approval."""

import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .cli_generator import CliCommand


class ExecutionStatus(Enum):
    """Status of command execution."""
    
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionResult:
    """Result of command execution."""
    
    command: CliCommand
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    return_code: Optional[int] = None
    error_message: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "command": self.command.command,
            "description": self.command.description,
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "error_message": self.error_message,
        }


class CommandExecutor:
    """Executes Azure CLI commands with approval workflow."""
    
    def __init__(self, dry_run: bool = False):
        """Initialize the executor.
        
        Args:
            dry_run: If True, commands are validated but not executed.
        """
        self.dry_run = dry_run
        self._approved_commands: set = set()
        self._rejected_commands: set = set()
    
    def request_approval(self, commands: List[CliCommand]) -> List[dict]:
        """Request approval for a list of commands.
        
        Args:
            commands: Commands to request approval for.
            
        Returns:
            List of commands with approval status.
        """
        return [
            {
                "index": i,
                "command": cmd.command,
                "description": cmd.description,
                "action": cmd.action,
                "resource_name": cmd.resource_name,
                "risk_level": cmd.risk_level.value,
                "status": "pending_approval",
            }
            for i, cmd in enumerate(commands)
        ]
    
    def set_approval(self, command_index: int, approved: bool) -> None:
        """Set approval status for a command.
        
        Args:
            command_index: Index of the command.
            approved: Whether the command is approved.
        """
        if approved:
            self._approved_commands.add(command_index)
            self._rejected_commands.discard(command_index)
        else:
            self._rejected_commands.add(command_index)
            self._approved_commands.discard(command_index)
    
    def approve_all(self, commands: List[CliCommand]) -> None:
        """Approve all commands."""
        for i in range(len(commands)):
            self._approved_commands.add(i)
    
    def is_approved(self, command_index: int) -> bool:
        """Check if a command is approved."""
        return command_index in self._approved_commands
    
    def execute(self, commands: List[CliCommand]) -> List[ExecutionResult]:
        """Execute approved commands.
        
        Args:
            commands: List of commands to execute.
            
        Returns:
            List of execution results.
        """
        results = []
        
        for i, cmd in enumerate(commands):
            if i in self._rejected_commands:
                results.append(
                    ExecutionResult(
                        command=cmd,
                        status=ExecutionStatus.REJECTED,
                    )
                )
            elif i not in self._approved_commands:
                results.append(
                    ExecutionResult(
                        command=cmd,
                        status=ExecutionStatus.PENDING_APPROVAL,
                    )
                )
            elif self.dry_run:
                results.append(
                    ExecutionResult(
                        command=cmd,
                        status=ExecutionStatus.SKIPPED,
                        error_message="Dry run mode - command not executed",
                    )
                )
            else:
                result = self._execute_command(cmd)
                results.append(result)
        
        return results
    
    def execute_single(self, command: CliCommand, approved: bool = False) -> ExecutionResult:
        """Execute a single command.
        
        Args:
            command: Command to execute.
            approved: Whether the command is approved.
            
        Returns:
            Execution result.
        """
        if not approved:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.PENDING_APPROVAL,
            )
        
        if self.dry_run:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.SKIPPED,
                error_message="Dry run mode - command not executed",
            )
        
        return self._execute_command(command)
    
    def _execute_command(self, command: CliCommand) -> ExecutionResult:
        """Execute a single CLI command.
        
        Args:
            command: Command to execute.
            
        Returns:
            Execution result.
        """
        try:
            # Prepare command for execution (remove line continuations)
            cmd_str = command.command.replace(" \\\n    ", " ")
            
            # Execute using subprocess
            result = subprocess.run(
                cmd_str,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode == 0:
                return ExecutionResult(
                    command=command,
                    status=ExecutionStatus.SUCCESS,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                )
            else:
                return ExecutionResult(
                    command=command,
                    status=ExecutionStatus.FAILED,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    return_code=result.returncode,
                    error_message=f"Command failed with exit code {result.returncode}",
                )
        
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.FAILED,
                error_message="Command timed out after 5 minutes",
            )
        except Exception as e:
            return ExecutionResult(
                command=command,
                status=ExecutionStatus.FAILED,
                error_message=str(e),
            )


def execute_with_approval(
    commands: List[CliCommand],
    approved_indices: Optional[List[int]] = None,
    dry_run: bool = False,
) -> List[ExecutionResult]:
    """Execute commands with approval workflow.
    
    Args:
        commands: Commands to execute.
        approved_indices: Indices of approved commands. If None, all require approval.
        dry_run: If True, validate but don't execute.
        
    Returns:
        List of execution results.
    """
    executor = CommandExecutor(dry_run=dry_run)
    
    if approved_indices:
        for idx in approved_indices:
            executor.set_approval(idx, True)
    
    return executor.execute(commands)
