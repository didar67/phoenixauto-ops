"""Unit tests for app.utils.config_loader.ConfigLoader."""
import pytest

from app.utils.config_loader import ConfigLoader


@pytest.fixture
def loader(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "thresholds.yaml").write_text(
        """
thresholds:
  cpu_usage_percent: 75.0
  memory_usage_percent: 88.0

auto_healing:
  enabled: true
  dry_run: false
"""
    )
    env_file = tmp_path / ".env"
    env_file.write_text("TELEGRAM_BOT_TOKEN=abc123\n")

    return ConfigLoader(config_dir=str(config_dir), env_file=str(env_file))


class TestGet:
    def test_dot_notation_reads_nested_yaml_key(self, loader):
        assert loader.get("thresholds.cpu_usage_percent") == 75.0

    def test_missing_key_returns_supplied_default(self, loader):
        assert loader.get("thresholds.nonexistent", "fallback") == "fallback"

    def test_missing_key_without_default_returns_none(self, loader):
        assert loader.get("nonexistent.key") is None

    def test_partial_path_on_non_dict_value_returns_default(self, loader):
        # thresholds.cpu_usage_percent is a float, not a dict - walking
        # further into it (".foo") must not raise, just miss.
        assert loader.get("thresholds.cpu_usage_percent.foo", "safe") == "safe"


class TestGetThreshold:
    def test_prefers_thresholds_namespace_over_top_level(self, loader):
        assert loader.get_threshold("cpu_usage_percent") == 75.0

    def test_falls_back_to_top_level_key_when_not_under_thresholds(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "thresholds.yaml").write_text("load_average_limit: 3.5\n")
        loader = ConfigLoader(config_dir=str(config_dir), env_file=str(tmp_path / ".env"))

        assert loader.get_threshold("load_average_limit") == 3.5

    def test_returns_hardcoded_default_when_key_missing_everywhere(self, loader):
        assert loader.get_threshold("disk_usage_percent", default=99.9) == 99.9

    def test_return_value_is_always_a_float(self, loader):
        assert isinstance(loader.get_threshold("cpu_usage_percent"), float)


class TestMissingConfigFile:
    def test_missing_yaml_and_missing_example_yields_empty_config(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()  # thresholds.yaml intentionally not created

        loader = ConfigLoader(config_dir=str(config_dir), env_file=str(tmp_path / ".env"))

        assert loader.get_all() == {}
        assert loader.get_threshold("cpu_usage_percent", default=50.0) == 50.0
        