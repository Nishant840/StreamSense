import json
import logging
import datetime
import redis
import time
import os

class RedisLoggingHandler(logging.Handler):
    def __init__(self, redis_url: str, topic: str, retries: int = 5):
        super().__init__()
        self.topic = topic
        self.redis_client = None
        self._connect(redis_url, retries)

    def _connect(self, redis_url: str, retries: int):
        for attempt in range(1, retries+1):
            try:
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                print(f"[RedisHandler] Connected to Redis on attempt {attempt}")
                return
            except Exception as e:
                wait = 2 ** attempt
                print(f"[RedisHandler] Attempt {attempt} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        
        print("[RedisHandler] Could not connect to Redis. Logs will not be shipped.")
        
    def emit(self, record: logging.LogRecord):
        if self.redis_client is None:
            return
        try:
            log_entry = {
                "timestamp" :    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "level"     :    record.levelname,
                "service"   :    record.name,
                "message"   :    record.getMessage(),
            }
            # We use Redis Lists as a queue
            self.redis_client.lpush(self.topic, json.dumps(log_entry))
        except Exception:
            self.handleError(record)

    def close(self):
        if self.redis_client is not None:
            self.redis_client.close()
        super().close()
