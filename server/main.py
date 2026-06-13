import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas        import AnomalyEvent, AnomalyResponse, ServiceStatus, WebSocketMessage
from ws_manager     import WebSocketManager
from anomaly_store  import  init_db, save_anomaly, get_anomalies, get_anomaly_count
from redis_client   import  init_redis, record_anomaly, get_anomaly_rates_all, get_last_anomaly_time, SERVICES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("server")

ws_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting StreamSense server...")
    init_db()
    init_redis()
    logger.info("Server ready")
    yield
    logger.info("Shutting down...")

app = FastAPI(
    title="StreamSense",
    description="Real-time log anomaly detection API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "status":       "ok",
        "service":      "streamsense-server",
        "ws_clients":   ws_manager.connection_count,
    }

@app.get("/metrics")
async def metrics():
    total       = get_anomaly_count()
    rates       = get_anomaly_rates_all()
    per_service = {
        s: get_anomaly_count(s) for s in SERVICES
    }
    return {
        "total_anomalies":          total,
        "anomaly_rate_5min":        rates,
        "anomalies_per_service":    per_service,   
    }

@app.get("/anomalies", response_model=list[AnomalyResponse])
async def get_anomalies_endpoint(
    service: str | None = Query(default=None),
    limit:   int        = Query(default=50, le=200),
):
    return get_anomalies(service=service, limit=limit)

@app.get("/services", response_model=list[ServiceStatus])
async def get_services():
    rates    = get_anomaly_rates_all()
    statuses = []

    for service in SERVICES:
        rate = rates.get(service, 0)

        if rate == 0:
            status = "healthy"
        elif rate <= 3:
            status = "warning"
        else:
            status = "critical"

        statuses.append(ServiceStatus(
            service         = service,
            status          = status,
            anomaly_rate    = rate,
            last_anomaly    = get_last_anomaly_time(service),
        ))
    
    return statuses

@app.post("/anomaly")
async def receive_anomaly(event: AnomalyEvent):
    row_id  = save_anomaly(event)
    record_anomaly(event.service, event.anomaly_score)

    ws_message = WebSocketMessage(
        type            = "anomaly",
        service         = event.service,
        timestamp       = event.timestamp,
        level           = event.level,
        message         = event.message,
        anomaly_score   = event.anomaly_score,
        is_anomaly      = True,
        template        = event.template,
    )

    await ws_manager.broadcast(ws_message.model_dump())

    logger.info(
        f"Anomaly received and broadcast | "
        f"id={row_id} service={event.service} score={event.anomaly_score:.4f}"
    )

    return {
        "id":       row_id,
        "status":   "recorded"
    }

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        recent = get_anomalies(limit=20)
        for anomaly in reversed(recent):
            await ws_manager.send_personal(
                websocket,
                {
                    "type":             "anomaly",
                    "service":          anomaly.service,
                    "timestamp":        anomaly.timestamp,
                    "level":            anomaly.level,
                    "message":          anomaly.message,
                    "anomaly_score":    anomaly.anomaly_score,
                    "is_anomaly":       True,
                    "template":         anomaly.template,
                }
            )
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)