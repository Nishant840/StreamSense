import logging
import random
import time
import threading
from fastapi import FastAPI
import uvicorn
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
    "send_email":           0.15,
    "resize_image":         0.15,
    "generate_report":      0.15,
    "sync_database":        0.15,
    "cleanup_temp_files":   0.15,
}

def process_job(job_type: str) -> None:
    duration = int(random.gauss(800,150))
    duration = max(duration, 100)

    failure_roll = random.random()
    failure_rate = FAILURE_RATES[job_type]

    if failure_roll < failure_rate:
        logger.error(
            f"Job failed | job={job_type} duration={duration}ms "
            f"error=UnexpectedNullPointerException"
        )
    else:
        logger.info(
            f"Job completed | job={job_type} duration={duration}ms"
        )

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "service": "service-b"}

@app.post("/inject/error-spike")
def inject_error_spike():
    for _ in range(30):
        logger.error("Job failed | job=critical_task duration=0ms error=ManualInjectionSpike")
        time.sleep(0.1)
    return {"injected": "error-spike"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8001, log_config=None)

def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    logger.info("Worker started - waiting for jobs")
    while True:
        job = random.choice(JOB_TYPES)
        process_job(job)
        time.sleep(random.uniform(0.3, 0.8))

if __name__ == "__main__":
    main()
