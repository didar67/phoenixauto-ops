"""
Shared pytest fixtures for PhoenixAuto-Ops.

Most components pull config through the singleton `config` object created
at import time in app/utils/config_loader.py (it reads .env and
config/thresholds.yaml straight off disk). Rather than juggling real config
files per test, we monkeypatch the singleton's get()/get_threshold() so
unit tests stay independent of whatever happens to be in the local .env
or thresholds.yaml on a given machine.
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.config_loader import config as app_config


@pytest.fixture
def patch_config(monkeypatch):
    """Stub ConfigLoader.get() / get_threshold() for the duration of a test.

    Usage:
        patch_config(
            get_values={"telegram.bot_token": "x"},
            threshold_values={"cpu_usage_percent": 80.0},
        )
    """

    def _apply(get_values=None, threshold_values=None):
        get_values = get_values or {}
        threshold_values = threshold_values or {}

        def fake_get(key, default=None):
            return get_values.get(key, default)

        def fake_get_threshold(metric_key, default=80.0):
            return threshold_values.get(metric_key, default)

        monkeypatch.setattr(app_config, "get", fake_get)
        monkeypatch.setattr(app_config, "get_threshold", fake_get_threshold)

    return _apply
