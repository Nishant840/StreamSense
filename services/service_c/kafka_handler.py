import json
import logging
import datetime
from kafka import KafkaProducer
import time

class KafkaLoggingHandler(logging.Handler):

    def __init__(self, bootstrap_servers: str, topic: str, retries: int = 5):
        super().__init__()
        self.topic = topic
        self.producer = None
        self._connect(bootstrap_servers, retries)

    def _connect(self, bootstrap_servers: str, retries: int):
        for attempt in range(1,retries+1):
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers = bootstrap_servers,
                    value_serializer = lambda v: json.dumps(v).encode("utf-8"),
                    acks="all",
                    retries=3,
                )
                print(f"[KafkaHandler] Connected to Kafka on attempt {attempt}")
                return
            except Exception as e:
                wait = 2 ** attempt
                print(f"[KafkaHandler] Attempt {attempt} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        
        print("[KafkaHandler] Could not connect to Kafka. Logs will not be shipped.")
        
    def emit(self, record: logging.LogRecord):
        if self.producer is None:
            return
        try:
            log_entry = {
                "timestamp" :    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "level"     :    record.levelname,
                "service"   :    record.name,
                "message"   :    record.getMessage(),
            }
            self.producer.send(self.topic, value=log_entry)
        except Exception:
            self.handleError(record)

    def close(self):
        if self.producer is not None:
            self.producer.flush()
            self.producer.close()
        super().close()
