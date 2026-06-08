import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s drain-parser %(message)s"
)
logger = logging.getLogger("drain-parser")

def build_template_miner() -> TemplateMiner:
    config = TemplateMinerConfig()

    config.drain_sim_th                 = 0.4
    config.drain_depth                  = 4
    config.drain_max_children           = 100
    config.parametrize_numeric_tokens   = True

    return TemplateMiner(config=config)

def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        "raw-logs",
        bootstrap_servers="localhost:29092",
        group_id="drain-parser-group",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

def build_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers="localhost:29092",
        value_serializer = lambda v: json.dumps(v).encode("utf-8")
    )

def parse_logs(template_miner: TemplateMiner, raw_log: dict) -> dict:
    message = raw_log.get("message", "")
    result = template_miner.add_log_message(message)

    template = result["template_mined"]
    template_id = result["cluster_id"]
    is_new = result["change_type"] != "none"

    if is_new:
        logger.info(f"New template discovered | id={template_id} template='{template}'")

    return {
        **raw_log,
        "template":     template,
        "template_id":  template_id
    }

def main():
    logger.info("Drain parser starting...")

    template_miner = build_template_miner()
    consumer       = build_consumer()
    producer       = build_producer()

    logger.info("Connected to kafka. Consuming from raw-logs...")

    for message in consumer:
        raw_log         = message.value
        parsed_log      = parse_logs(template_miner, raw_log)
        producer.send("parsed-logs", value=parsed_log)

if __name__ == "__main__":
    main()