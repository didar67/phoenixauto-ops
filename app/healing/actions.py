"""
PhoenixAuto-Ops Healing Actions
===============================

Concrete healing actions that call secure shell scripts or system commands.
All operations respect dry-run mode, retry logic, and logging from BaseHealer.
"""

import subprocess
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
        """Kill processes matching process_name via pkill (SIGTERM)."""
        return self._safe_execute(
            f"kill {process_name}",
            self._run_pkill,
            process_name,
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

    def _run_pkill(self, process_name: str) -> bool:
        """Run pkill -f, treating 'no matching process' as success.

        pkill's own exit code 1 means "no processes matched" - not a real
        failure, and the common case here since a previous cycle's kill
        may have already cleared the target before this one runs. Only
        exit codes >1 (actual pkill errors, e.g. bad syntax) should go
        through the retry/failure path that _safe_execute() wraps around
        this call.
        """
        if self.dry_run:
            self.logger.info(f"[DRY-RUN] Would execute: pkill -f {process_name}")
            return True

        cmd = ["pkill", "-f", process_name]
        try:
            self.logger.debug(f"Executing: {' '.join(cmd)}")
            # `cmd` is constructed only from trusted, allowlisted healing actions.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # nosec B603

            if result.returncode == 0:
                self.logger.debug("pkill matched and signaled at least one process")
                return True
            if result.returncode == 1:
                self.logger.info(f"No matching process found for: {process_name}")
                return True

            self.logger.error(f"pkill failed (code {result.returncode}): {result.stderr.strip()}")
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            self.logger.error(f"pkill timed out after 30s for: {process_name}")
            raise

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
            self.logger.error(f"Command failed (code {e.returncode}): {e.stderr}")
            raise
        except FileNotFoundError as e:
            self.logger.error(f"Command not found: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error executing {action_desc}: {e}")
            raise
