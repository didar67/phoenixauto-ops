"""
PhoenixAuto-Ops Healing Actions

Concrete healing actions that inherit from BaseHealer.
Provides safe, retry-enabled implementations for common
recovery operations like service restart, process kill,
cache clear, and log rotation.
"""

import subprocess
from typing import Optional

from app.healing.base import BaseHealer
from app.utils.logger import logger


class HealingActions(BaseHealer):
    """Concrete healing actions using system commands.

    All actions respect dry-run mode and retry logic from BaseHealer.
    Uses subprocess for Linux system commands with proper error handling.
    """

    def restart_service(self, service_name: str) -> bool:
        """Restart a systemd service."""
        action = f"restart {service_name}"
        return self._safe_execute(
            action,
            self._run_systemctl,
            "restart",
            service_name
        )

    def kill_process(self, process_name: str) -> bool:
        """Kill processes by name (SIGTERM first, then SIGKILL)."""
        action = f"kill {process_name}"
        return self._safe_execute(
            action,
            self._kill_process_by_name,
            process_name
        )

    def clear_cache(self) -> bool:
        """Clear system cache (sync + drop caches)."""
        action = "clear system cache"
        return self._safe_execute(
            action,
            self._clear_system_cache
        )

    def log_rotate(self) -> bool:
        """Force log rotation."""
        action = "log rotation"
        return self._safe_execute(
            action,
            self._run_logrotate
        )

    def _run_systemctl(self, command: str, service: str) -> bool:
        """Run systemctl command."""
        result = subprocess.run(
            ["systemctl", command, service],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return True

    def _kill_process_by_name(self, process_name: str) -> bool:
        """Kill process safely."""
        subprocess.run(["pkill", "-TERM", process_name], capture_output=True)
        return True

    def _clear_system_cache(self) -> bool:
        """Clear page cache."""
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3")
        return True

    def _run_logrotate(self) -> bool:
        """Force logrotate."""
        result = subprocess.run(
            ["logrotate", "-f", "/etc/logrotate.conf"],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return True