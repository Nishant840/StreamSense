import os
import logging
from datetime import datetime, timezone
import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redis-client")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SERVICES = ["service-a", "service-b", "service-c"]
RETENTION_MS = 60 * 60 * 1000  # 1 hour

_redis_client = None

def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
    return _redis_client

def init_redis():
    r = get_redis()
    logger.info("Connected to Redis successfully.")

def record_anomaly(service: str, score: float) -> None:
    r   = get_redis()
    key = f"anomaly_zset:{service}"
    ts  = int(datetime.now(timezone.utc).timestamp() * 1000)

    try:
        # ZADD key score member
        # member must be unique, so we use ts:score
        member = f"{ts}:{score}"
        r.zadd(key, {member: ts})
        # Remove items older than retention
        r.zremrangebyscore(key, 0, ts - RETENTION_MS)
    except Exception as e:
        logger.error(f"Failed to record anomaly in Redis: {e}")

def get_anomaly_rate(
    service:    str,
    window_mins: int = 5,
) -> float:
    r       = get_redis()
    key     = f"anomaly_zset:{service}"
    now_ms  = int(datetime.now(timezone.utc).timestamp() * 1000)
    from_ms = now_ms - (window_mins * 60 * 1000)

    try:
        count = r.zcount(key, from_ms, now_ms)
        return float(count)
    except Exception as e:
        logger.error(f"Failed to get anomaly rate: {e}")
        return 0.0
    
def get_anomaly_rates_all() -> dict[str, float]:
    return {
        service: get_anomaly_rate(service)
        for service in SERVICES
    }

def get_last_anomaly_time(service: str) -> str | None:
    r       = get_redis()
    key     = f"anomaly_zset:{service}"

    try:
        # Get the highest score (most recent timestamp)
        samples = r.zrange(key, -1, -1, withscores=True)
        if samples:
            member, last_ts_ms = samples[0]
            last_ts    = datetime.fromtimestamp(
                last_ts_ms / 1000.0,
                tz=timezone.utc,
            )
            return last_ts.isoformat()
        return None
    except Exception as e:
        logger.error(f"Failed to get last anomaly time: {e}")
        return None
