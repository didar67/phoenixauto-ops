"""Unit tests for app.healing.actions.HealingActions."""
import subprocess

import pytest

from app.healing.actions import HealingActions


@pytest.fixture
def healer(patch_config):
    patch_config(
        get_values={
            "auto_healing.enabled": True,
            "auto_healing.max_retry_attempts": 3,
            "auto_healing.dry_run": False,
        }
    )
    return HealingActions()


class TestDryRun:
    def test_dry_run_logs_intent_without_calling_subprocess(self, patch_config, mocker):
        patch_config(
            get_values={
                "auto_healing.enabled": True,
                "auto_healing.max_retry_attempts": 3,
                "auto_healing.dry_run": True,
            }
        )
        healer = HealingActions()
        mock_run = mocker.patch("app.healing.actions.subprocess.run")

        result = healer.restart_service("nginx")

        assert result is True
        mock_run.assert_not_called()


class TestRestartService:
    def test_invokes_service_manager_script_with_restart_action(self, healer, mocker):
        mock_run = mocker.patch(
            "app.healing.actions.subprocess.run",
            return_value=mocker.Mock(returncode=0, stdout="", stderr=""),
        )

        result = healer.restart_service("nginx")

        assert result is True
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0].endswith("scripts/service_manager.sh")
        assert called_cmd[1:] == ["restart", "nginx"]

    def test_retries_on_failure_up_to_max_attempts(self, healer, mocker):
        mocker.patch("app.healing.base.sleep")  # skip the 2s backoff between retries
        mock_run = mocker.patch(
            "app.healing.actions.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "service_manager.sh", stderr="unit not found"),
        )

        with pytest.raises(subprocess.CalledProcessError):
            healer.restart_service("nonexistent-service")

        assert mock_run.call_count == 3  # matches auto_healing.max_retry_attempts


class TestKillProcess:
    def test_uses_pkill_with_full_command_line_match(self, healer, mocker):
        mock_run = mocker.patch(
            "app.healing.actions.subprocess.run",
            return_value=mocker.Mock(returncode=0, stdout="", stderr=""),
        )

        healer.kill_process("stuck-worker")

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd == ["pkill", "-f", "stuck-worker"]


class TestClearCache:
    def test_invokes_cleanup_script(self, healer, mocker):
        mock_run = mocker.patch(
            "app.healing.actions.subprocess.run",
            return_value=mocker.Mock(returncode=0, stdout="", stderr=""),
        )

        healer.clear_cache()

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0].endswith("scripts/cleanup.sh")


class TestCommandTimeout:
    def test_timeout_is_raised_not_swallowed(self, healer, mocker):
        mocker.patch("app.healing.base.sleep")
        mocker.patch(
            "app.healing.actions.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="cleanup.sh", timeout=30),
        )

        with pytest.raises(subprocess.TimeoutExpired):
            healer.clear_cache()
            