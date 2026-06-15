import logging
import redis
import os
from datetime import datetime, timezone

logger = logging.getLogger("redis-client")

REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
RETENTION_MS    = 24*60*60*1000 # 24hour in millisecond
AGGREGATION_MS  = 60*1000       # 1 minute buckets

SERVICES = ["service-a", "service-b", "service-c"]

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

def init_redis() -> None:
    r = get_redis()
    for service in SERVICES:
        key = f"anomaly_rate:{service}"
        try:
            r.ts().create(
                key,
                retention_msecs=RETENTION_MS,
                labels={"service": service, "metric":"anomaly_rate"},
            )
            logger.info(f"Created TimeSeries key: {key}")
        except Exception:
            logger.info(f"TimeSeries key already exists: {key}")

def record_anomaly(service: str, score: float) -> None:
    r   = get_redis()
    key = f"anomaly_rate:{service}"
    ts  = int(datetime.now(timezone.utc).timestamp()*1000)

    try:
        r.ts().add(
            key,
            ts,
            score,
            retention_msecs=RETENTION_MS,
        )
    except redis.exceptions.ResponseError as e:
        if "TSDB: key does not exist" in str(e):
            r.ts().create(key, retention_msecs=RETENTION_MS, labels={"service": service, "metric": "anomaly_rate"})
            r.ts().add(key, ts, score)
    except Exception as e:
        logger.error(f"Failed to record anomaly in Redis: {e}")

def get_anomaly_rate(
    service:    str,
    window_mins: int = 5,
) -> float:
    r       = get_redis()
    key     = f"anomaly_rate:{service}"
    now_ms  = int(datetime.now(timezone.utc).timestamp()*1000)
    from_ms = now_ms - (window_mins*60*1000)

    try:
        samples = r.ts().range(key, from_ms, now_ms)
        return len(samples)
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
    key     = f"anomaly_rate:{service}"
    now_ms  = int(datetime.now(timezone.utc).timestamp()*1000)
    from_ms = now_ms - (24*60*60*1000)

    try:
        samples = r.ts().range(key, from_ms, now_ms)
        if samples:
            last_ts_ms = samples[-1][0]
            last_ts    = datetime.fromtimestamp(
                last_ts_ms/1000,
                tz=timezone.utc,
            )
            return last_ts.isoformat()
        return None
    except Exception as e:
        logger.error(f"Failed to get last anomaly time: {e}")
        return None