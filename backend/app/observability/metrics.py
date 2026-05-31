
from prometheus_client import Counter, Histogram

REQUEST_COUNTER = Counter(
    'snaji_requests_total',
    'Total de pedidos processados'
)

ANALYSIS_DURATION = Histogram(
    'snaji_analysis_duration_seconds',
    'Duração das análises jurídicas'
)
