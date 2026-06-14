import json
import logging
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import redis
import os

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

def build_redis_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.Redis.from_url(redis_url, decode_responses=True)

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
    r              = build_redis_client()
    
    logger.info("Listening for logs on Redis 'raw-logs' list...")

    while True:
        try:
            # brpop blocks until an item is available
            result = r.brpop("raw-logs", timeout=5)
            if not result:
                continue
                
            _, raw_json = result
            raw_log = json.loads(raw_json)
            
            parsed_log = parse_logs(template_miner, raw_log)
            
            r.lpush("parsed-logs", json.dumps(parsed_log))

        except Exception as e:
            logger.error(f"Error processing log: {e}")

if __name__ == "__main__":
    main()