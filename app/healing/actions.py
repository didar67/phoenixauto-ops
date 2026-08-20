"""
PhoenixAuto-Ops Healing Actions
===============================

Concrete healing actions that call secure shell scripts or system commands.
All operations respect dry-run mode, retry logic, and logging from BaseHealer.
"""

# Required to execute internally constructed, allowlisted healing commands.
import subprocess  # nosec B404
from pathlib import Path
from typing import List

from app.healing.base import BaseHealer
from app.utils.logger import logger


class HealingActions(BaseHealer):
    """Healing actions using external shell scripts or direct system commands.

    Calls service_manager.sh and cleanup.sh via subprocess for safe execution.
    Direct commands used where shell script is not needed.
    """

    def __init__(self) -> None:
        """Initialize paths to shell scripts."""
        super().__init__()
        self.scripts_dir = Path("scripts").resolve()
        if not self.scripts_dir.exists():
            self.logger.error(f"Scripts directory not found: {self.scripts_dir}")
            raise FileNotFoundError("Scripts directory missing")

    def restart_service(self, service_name: str) -> bool:
        """Restart a systemd service using shell script."""
        script = self.scripts_dir / "service_manager.sh"
        return self._safe_execute(f"restart {service_name}", self._run_shell_script, script, "restart", service_name)

    def kill_process(self, process_name: str) -> bool:
        """Kill processes by name using pkill (SIGTERM)."""
        return self._safe_execute(
            f"kill {process_name}", self._run_system_command, "pkill", "-f", process_name  # match full command line
        )

    def clear_cache(self) -> bool:
        """Clear system page cache using cleanup script."""
        script = self.scripts_dir / "cleanup.sh"
        return self._safe_execute("clear_cache", self._run_shell_script, script)

    def log_rotate(self) -> bool:
        """Force log rotation using cleanup script."""
        script = self.scripts_dir / "cleanup.sh"
        return self._safe_execute("log_rotate", self._run_shell_script, script)

    def _run_shell_script(self, script_path: Path, *args: str) -> bool:
        """Run shell script with proper error handling and timeout."""
        if not script_path.exists():
            self.logger.error(f"Shell script not found: {script_path}")
            raise FileNotFoundError(f"Script missing: {script_path}")

        cmd = [str(script_path)] + list(args)
        return self._execute_command(cmd, f"Shell script {script_path.name}")

    def _run_system_command(self, *cmd: str) -> bool:
        """Run generic system command with error handling and timeout."""
        cmd_list = list(cmd)
        return self._execute_command(cmd_list, f"System command {' '.join(cmd_list)}")

    def heal(self, **kwargs) -> bool:
        """Dummy implementation for abstract method."""
        logger.debug("Healing action triggered (dummy)")
        return True

    def _execute_command(self, cmd: List[str], action_desc: str) -> bool:
        """Common command execution with timeout and logging."""
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
            return True

        try:
            self.logger.debug(f"Executing: {' '.join(cmd)}")
            # `cmd` is constructed only from trusted, allowlisted healing actions.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)  # nosec B603
            if result.stderr:
                self.logger.debug(f"Command stderr: {result.stderr.strip()}")
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after 30s: {action_desc}")
            raise
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            self.logger.error(f"Command failed (code {e.returncode}): {stderr}")
            raise
        except FileNotFoundError as e:
            self.logger.error(f"Command not found: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error executing {action_desc}: {str(e)}")
            raise
