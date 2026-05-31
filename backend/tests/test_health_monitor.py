
from app.observability.health_monitor import HealthMonitor

def test_health():

    monitor = HealthMonitor()

    result = monitor.global_health()

    assert "database" in result
