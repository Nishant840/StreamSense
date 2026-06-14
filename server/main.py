import asyncio

import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas        import LogEvent, AnomalyResponse, ServiceStatus, WebSocketMessage
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

import httpx

@app.post("/inject/{service}/{anomaly_type}")
async def inject_anomaly(service: str, anomaly_type: str):
    port_map = {
        "service-a": 8002,
        "service-b": 8003,
        "service-c": 8004
    }
    
    if service not in port_map:
        return {"error": "Invalid service"}
        
    port = port_map[service]
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"http://localhost:{port}/inject/{anomaly_type}", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Failed to inject anomaly to {service}: {e}")
        return {"error": str(e)}

@app.get("/metrics")
async def metrics():
    total       = await asyncio.to_thread(get_anomaly_count)
    rates       = await asyncio.to_thread(get_anomaly_rates_all)
    per_service = {}
    for s in SERVICES:
        per_service[s] = await asyncio.to_thread(get_anomaly_count, s)

    thresholds = {}
    import numpy as np
    import os
    for s in SERVICES:
        t_path = f"../ml/checkpoints/{s}/threshold.npy"
        if os.path.exists(t_path):
            thresholds[s] = float(np.load(t_path))
        else:
            thresholds[s] = 0.0

    return {
        "total_anomalies":          total,
        "anomaly_rate_5min":        rates,
        "anomalies_per_service":    per_service,   
        "thresholds":               thresholds,
    }

@app.get("/anomalies", response_model=list[AnomalyResponse])
async def get_anomalies_endpoint(
    service: str | None = Query(default=None),
    limit:   int        = Query(default=50, le=200),
):
    return await asyncio.to_thread(get_anomalies, service, limit)

@app.get("/services", response_model=list[ServiceStatus])
async def get_services():
    rates    = await asyncio.to_thread(get_anomaly_rates_all)
    statuses = []

    for service in SERVICES:
        rate = rates.get(service, 0)

        if rate <= 30:
            status = "healthy"
        elif rate <= 80:
            status = "warning"
        else:
            status = "critical"
            
        last_time = await asyncio.to_thread(get_last_anomaly_time, service)

        statuses.append(ServiceStatus(
            service         = service,
            status          = status,
            anomaly_rate    = rate,
            last_anomaly    = last_time,
        ))
    
    return statuses

@app.post("/anomaly")
async def receive_log(event: LogEvent):
    row_id = None
    if event.is_anomaly:
        row_id  = await asyncio.to_thread(save_anomaly, event.model_dump())
        await asyncio.to_thread(record_anomaly, event.service, event.anomaly_score)

    ws_message = WebSocketMessage(
        type            = "log",
        service         = event.service,
        timestamp       = event.timestamp,
        level           = event.level,
        message         = event.message,
        anomaly_score   = event.anomaly_score,
        is_anomaly      = event.is_anomaly,
        template        = event.template,
    )

    await ws_manager.broadcast(ws_message.model_dump())

    if event.is_anomaly:
        logger.info(
            f"Anomaly received and broadcast | "
            f"id={row_id} service={event.service} score={event.anomaly_score:.4f}"
        )

    return {
        "id":       row_id,
        "status":   "recorded" if event.is_anomaly else "broadcasted"
    }

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        recent = await asyncio.to_thread(get_anomalies, None, 20)
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