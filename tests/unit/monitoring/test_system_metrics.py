"""Unit tests for app.monitoring.system.SystemMetrics."""
import pytest

from app.monitoring.system import SystemMetrics


@pytest.fixture
def collector(patch_config):
    patch_config(
        threshold_values={
            "cpu_usage_percent": 80.0,
            "memory_usage_percent": 85.0,
            "disk_usage_percent": 90.0,
            "load_average_limit": 4.0,
        }
    )
    return SystemMetrics()


class TestCollect:
    def test_collect_returns_all_four_metrics(self, collector, mocker):
        mocker.patch("app.monitoring.system.psutil.cpu_percent", return_value=42.0)
        mocker.patch(
            "app.monitoring.system.psutil.virtual_memory",
            return_value=mocker.Mock(percent=55.0),
        )
        mocker.patch(
            "app.monitoring.system.psutil.disk_usage",
            return_value=mocker.Mock(percent=61.0),
        )
        mocker.patch("app.monitoring.system.psutil.getloadavg", return_value=(1.2, 1.1, 0.9))

        metrics = collector.collect()

        assert metrics == {
            "cpu_usage_percent": 42.0,
            "memory_usage_percent": 55.0,
            "disk_usage_percent": 61.0,
            "load_average": 1.2,
        }

    def test_collect_swallows_psutil_failure_per_metric(self, collector, mocker):
        # _safe_execute() in BaseMetricCollector is what's under test here -
        # one broken metric source should not take the whole cycle down.
        mocker.patch(
            "app.monitoring.system.psutil.cpu_percent",
            side_effect=OSError("cpu stat unavailable"),
        )
        mocker.patch(
            "app.monitoring.system.psutil.virtual_memory",
            return_value=mocker.Mock(percent=55.0),
        )
        mocker.patch(
            "app.monitoring.system.psutil.disk_usage",
            return_value=mocker.Mock(percent=61.0),
        )
        mocker.patch("app.monitoring.system.psutil.getloadavg", return_value=(1.2, 1.1, 0.9))

        metrics = collector.collect()

        assert metrics["cpu_usage_percent"] is None
        assert metrics["memory_usage_percent"] == 55.0


class TestIsHealthy:
    def test_healthy_when_all_metrics_under_threshold(self, collector):
        metrics = {
            "cpu_usage_percent": 40.0,
            "memory_usage_percent": 50.0,
            "disk_usage_percent": 60.0,
            "load_average": 1.0,
        }
        assert collector.is_healthy(metrics) is True

    def test_unhealthy_when_disk_breaches_threshold(self, collector):
        metrics = {
            "cpu_usage_percent": 40.0,
            "memory_usage_percent": 50.0,
            "disk_usage_percent": 95.0,  # threshold is 90.0
            "load_average": 1.0,
        }
        assert collector.is_healthy(metrics) is False

    def test_is_healthy_collects_when_no_metrics_passed(self, collector, mocker):
        # Guards the "reuse this cycle's snapshot" contract documented on
        # SystemMetrics.is_healthy() - omitting metrics must still work by
        # falling back to a fresh collect().
        spy = mocker.patch.object(
            collector,
            "collect",
            return_value={
                "cpu_usage_percent": 10.0,
                "memory_usage_percent": 10.0,
                "disk_usage_percent": 10.0,
                "load_average": 0.1,
            },
        )

        assert collector.is_healthy() is True
        spy.assert_called_once()
        