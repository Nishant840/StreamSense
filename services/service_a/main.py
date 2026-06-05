import logging
import random
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

logging.basicConfig(
    level = logging.INFO,
    format="%(asctime)s %(levelname)s service-a %(message)s",
)
logger = logging.getLogger("service-a")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(emit_logs())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

ENDPOINTS = ["/api/users", "/api/orders", "/api/products", "/api/auth"]
STATUS_CODES = [200, 200, 200, 200, 201, 400, 404, 500]

response_time_multiplier = 1

async def emit_logs():
    while True:
        endpoint = random.choice(ENDPOINTS)
        status = random.choice(STATUS_CODES)
        latency = int(random.gauss(120,30) * response_time_multiplier)
        latency = max(10,latency)

        if status >= 500:
            logger.error(
                f"Request failed | endpoint={endpoint} status={status} latency={latency}ms"
            )
        elif status >= 400:
            logger.warning(
                f"Client error | endpoint={endpoint} status={status} latency={latency}ms"
            )
        else:
            logger.info(
                f"Request handled | endpoint={endpoint} status={status} latency={latency}ms"
            )

        await asyncio.sleep(random.uniform(0.3, 0.8))

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "service-a"
    }

@app.post("/inject/error-spike")
async def inject_error_spike():
    for _ in range(30):
        logger.error("Databse connection refused: timeout after 30s")
        await asyncio.sleep(0.1)
    return {
        "injected" "error-spike"
    }

@app.post("/inject/slowdown")
async def inject_slowdown():
    global response_time_multiplier
    response_time_multiplier = 10
    return {
        "injected": "slowdown",
        "multiplier": 10
    }

@app.post("/inject/reset")
async def inject_reset():
    global response_time_multiplier
    response_time_multiplier = 1
    return {
        "injected": "reset"
    }
