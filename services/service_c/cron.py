import logging
import random
import time
import schedule
from kafka_handler import KafkaLoggingHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s service-c %(message)s"
)
logger = logging.getLogger("servie-c")

kafka_handler = KafkaLoggingHandler(
    bootstrap_servers="kafka:9092",
    topic="raw-logs"
)
logger.addHandler(kafka_handler)

cpu_usage = 0.0
memory_usage = 0.0
disk_usage = 0.0

def update_system_stats():
    global cpu_usage, memory_usage, disk_usage

    cpu_usage = max(0.0, min(100.0, cpu_usage + random.gauss(0, 3)))
    memory_usage = max(0.0, min(100.0, memory_usage + random.gauss(0, 1)))
    disk_usage = max(0.0, min(100.0, disk_usage + random.gauss(0, 0.2)))

#cron jobs
def job_health_check():
    update_system_stats()

    logger.info(
        f"Health check passed | "
        f"cpu={cpu_usage: .1f}% "
        f"memory={memory_usage: .1f}% "
        f"disk={disk_usage: .1f}%"
    )
    
    if cpu_usage > 85:
        logger.warning(f"High CPU usage detected | cpu={cpu_usage:.1f}%")
    
    if memory_usage > 80:
        logger.warning(f"High memory usage detected | memory={memory_usage:.1f}%")

    
def job_cleanup():
    files_cleaned   = random.randint(5,50)
    size_mb         = random.randint(10,100)
    success         = random.random() > 0.05

    if success:
        logger.info(
            f"Cleanup completed | files={files_cleaned} size={size_mb}MB"
        )
    else:
        logger.error(
            f"Cleanup failed | files={files_cleaned} "
            f"error=PermissionDeniedOnTempDirectory"
        )

def job_db_backup():
    duration_s  = int(random.gauss(45, 10))
    duration_s  = max(10, duration_s)
    success     = random.random() > 0.03

    if success:
        logger.info(
            f"Databse backup completed | duration={duration_s}s"
        )
    else:
        logger.error(
            f"Databse backup failed | duration={duration_s}s "
            f"error=ConnectionResetByPeer"
        )

def job_cache_refresh():
    keys_refreshed = random.randint(100, 10000)
    duration_ms = int(random.gauss(200, 40))
    duration_ms = max(50, duration_ms)

    logger.info(
        f"Cache refresh completed | keys={keys_refreshed} duration={duration_ms}ms"
    )

# Schedule jobs
schedule.every(10).seconds.do(job_health_check)
schedule.every(30).seconds.do(job_cleanup)
schedule.every(60).seconds.do(job_db_backup)
schedule.every(20).seconds.do(job_cache_refresh)

def main():
    logger.info("Cron scheduler started")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()