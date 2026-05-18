from prometheus_client import Counter, Histogram,generate_latest,CONTENT_TYPE_LATEST
from starlette_exporter import BaseHttPMiddleware
from fastapi import Request, Response,FastAPI
import time

#define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total number of HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_latency_seconds', 'Latency of HTTP requests in seconds', ['method', 'endpoint'])

class PrometheusMiddleware(BaseHttPMiddleware):

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        # process the request and measure latency
        response = await call_next(request)
        # calculate latency
        latency = time.time() - start_time

        # Update metrics
        REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe(latency)
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()


        return response
    
def setup_metrics_endpoint(self, app: FastAPI):
    """
    Setup prometheus metrics endpoint
    """
    #add prometheus metrics midlleware
    app.add_middleware(PrometheusMiddleware)

    #add metrics endpoint
    @app.get("/metrics24", include_in_schema=False)
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)