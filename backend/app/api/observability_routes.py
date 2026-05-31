
from fastapi import APIRouter
from app.observability.health_monitor import HealthMonitor
from app.observability.legal_metrics import LegalMetrics

router = APIRouter()

monitor = HealthMonitor()
metrics = LegalMetrics()

@router.get("/health/full")
async def full_health():

    return monitor.global_health()

@router.get("/metrics/legal")
async def legal_metrics():

    return metrics.collect()
