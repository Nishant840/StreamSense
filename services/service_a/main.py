import logging
import random
import asyncio
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from redis_handler import RedisLoggingHandler

logging.basicConfig(
    level = logging.INFO,
    format="%(asctime)s %(levelname)s service-a %(message)s",
)
logger = logging.getLogger("service-a")

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_handler = RedisLoggingHandler(
    redis_url=redis_url,
    topic="raw-logs"
)
logger.addHandler(redis_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(emit_logs())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

ENDPOINTS = ["/api/users", "/api/orders", "/api/products", "/api/auth"]
STATUS_CODES = [200, 200, 200, 200, 201, 400, 500, 503]



async def emit_logs():
    while True:
        endpoint = random.choice(ENDPOINTS)
        status = random.choice(STATUS_CODES)
        latency = int(random.gauss(120,30))
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
