import json
import logging
import datetime
from kafka import KafkaProducer

class KafkaLoggingHandler(logging.Handler):

    def __init__(self, bootstrap_servers: str, topic: str):
        super().__init__()
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers = bootstrap_servers,
            value_serializer = lambda v: json.dumps(v).encode("utf-8"),
            acks = "all",
            retries=3
        )

    def emit(self, record: logging.LogRecord):
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
        self.producer.flush()
        self.producer.close()
        super().close()
