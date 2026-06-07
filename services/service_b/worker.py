import logging
import random
import time
from kafka_handler import KafkaLoggingHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s service-b %(message)s",
)

logger = logging.getLogger("service-b")

kafka_handler = KafkaLoggingHandler(
    bootstrap_servers="kafka:9092",
    topic="raw-logs"
)
logger.addHandler(kafka_handler)

JOB_TYPES = [
    "send_email",
    "resize_image",
    "generate_report",
    "sync_database",
    "cleanup_temp_files",
]

FAILURE_RATES = {
    "send_email":           0.05,
    "resize_image":         0.02,
    "generate_report":      0.08,
    "sync_database":        0.03,
    "cleanup_temp_files":   0.01,
}

memory_leak_mode = False
memory_usage_mb = 512

def process_job(job_type: str) -> None:
    duration = int(random.gauss(800,150))
    duration = max(duration, 100)

    failure_roll = random.random()
    failure_rate = FAILURE_RATES[job_type]

    if memory_leak_mode:
        global memory_usage_mb
        memory_usage_mb += random.randint(10,30)
        logger.warning(
            f"Memory usage: {memory_usage_mb}MB | job={job_type}"
        )

    if failure_roll < failure_rate:
        logger.error(
            f"Job failed | job={job_type} duration={duration}ms "
            f"error=UnexpectedNullPointerException"
        )
    else:
        logger.info(
            f"Job completed | job={job_type} duration={duration}ms"
        )

def main():
    logger.info("Worker started - waiting for jobs")
    while True:
        job = random.choice(JOB_TYPES)
        process_job(job)
        time.sleep(random.uniform(0.5, 1.2))

if __name__ == "__main__":
    main()
