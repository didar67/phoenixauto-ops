"""Unit tests for app.monitoring.network.NetworkMetrics."""
import pytest

from app.monitoring.network import NetworkMetrics


@pytest.fixture
def collector(patch_config, mocker):
    patch_config(threshold_values={"network.max_connections": 500})
    # _get_bytes_sent/_get_bytes_recv each sleep(1) to compute a delta -
    # stub it out so this module doesn't cost 4s of real wall-clock time.
    mocker.patch("app.monitoring.network.time.sleep")
    return NetworkMetrics()


class TestCollect:
    def test_bytes_sent_and_recv_computed_as_mb_delta(self, collector, mocker):
        io_before = mocker.Mock(bytes_sent=10 * 1024 * 1024, bytes_recv=5 * 1024 * 1024)
        io_after = mocker.Mock(bytes_sent=12 * 1024 * 1024, bytes_recv=6 * 1024 * 1024)
        mocker.patch(
            "app.monitoring.network.psutil.net_io_counters",
            side_effect=[io_before, io_after, io_before, io_after],
        )
        mocker.patch(
            "app.monitoring.network.psutil.net_connections",
            return_value=[mocker.Mock()] * 12,
        )

        metrics = collector.collect()

        assert metrics["network_bytes_sent_per_sec"] == pytest.approx(2.0)
        assert metrics["network_bytes_recv_per_sec"] == pytest.approx(1.0)
        assert metrics["network_connections"] == 12

    def test_connection_count_failure_defaults_to_zero(self, collector, mocker):
        mocker.patch(
            "app.monitoring.network.psutil.net_io_counters",
            return_value=mocker.Mock(bytes_sent=0, bytes_recv=0),
        )
        mocker.patch(
            "app.monitoring.network.psutil.net_connections",
            side_effect=PermissionError("requires elevated privileges"),
        )

        metrics = collector.collect()

        assert metrics["network_connections"] == 0


class TestIsHealthy:
    def test_unhealthy_when_connections_exceed_threshold(self, collector):
        assert collector.is_healthy({"network_connections": 600}) is False

    def test_healthy_when_connections_within_threshold(self, collector):
        assert collector.is_healthy({"network_connections": 120}) is True
        