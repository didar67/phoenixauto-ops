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
            self.logger.error("Scripts directory not found: %s", self.scripts_dir)
            raise FileNotFoundError("Scripts directory missing")

    def restart_service(self, service_name: str) -> bool:
        """Restart a systemd service using shell script."""
        script = self.scripts_dir / "service_manager.sh"
        return self._safe_execute(
            f"restart {service_name}",
            self._run_shell_script,
            script,
            "restart",
            service_name
        )

    def kill_process(self, process_name: str) -> bool:
        """Kill processes by name using pkill (SIGTERM)."""
        return self._safe_execute(
            f"kill {process_name}",
            self._run_system_command,
            "pkill",
            "-f",  # match full command line
            process_name
        )

    def clear_cache(self) -> bool:
        """Clear system page cache using cleanup script."""
        script = self.scripts_dir / "cleanup.sh"
        return self._safe_execute(
            "clear_cache",
            self._run_shell_script,
            script
        )

    def log_rotate(self) -> bool:
        """Force log rotation using cleanup script."""
        script = self.scripts_dir / "cleanup.sh"
        return self._safe_execute(
            "log_rotate",
            self._run_shell_script,
            script
        )

    def _run_shell_script(self, script_path: Path, *args: str) -> bool:
        """Run shell script with proper error handling and timeout."""
        if not script_path.exists():
            self.logger.error("Shell script not found: %s", script_path)
            raise FileNotFoundError(f"Script missing: {script_path}")

        cmd = [str(script_path)] + list(args)
        return self._execute_command(cmd, f"Shell script {script_path.name}")

    def _run_system_command(self, *cmd: str) -> bool:
        """Run generic system command with error handling and timeout."""
        cmd_list = list(cmd)
        return self._execute_command(cmd_list, f"System command {' '.join(cmd_list)}")

    def _execute_command(self, cmd: List[str], action_desc: str) -> bool:
        """Common command execution with timeout and logging."""
        if self.dry_run:
            self.logger.info("[DRY-RUN] Would execute: %s", " ".join(cmd))
            return True

        try:
            self.logger.debug("Executing: %s", " ".join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            if result.stderr:
                self.logger.debug("Command stderr: %s", result.stderr.strip())            
                return True
        except subprocess.TimeoutExpired:
            self.logger.error("Command timed out after 30s: %s", action_desc)
            raise
        except subprocess.CalledProcessError as e:
            self.logger.error("Command failed (code %d): %s", e.returncode, e.stderr.strip())
            raise
        except FileNotFoundError as e:
            self.logger.error("Command not found: %s", str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error executing %s: %s", action_desc, str(e))
            raise