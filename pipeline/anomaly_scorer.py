import json
import logging
import httpx
import numpy as np
import onnxruntime as ort
from collections import defaultdict, deque
import redis
import os

from feature_extractor import extract_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s anomaly-scorer %(message)s"
)
logger = logging.getLogger("anomaly-scorer")

CHECKPOINT_DIR  = "../ml/checkpoints"
SERVICES        = ["service-a", "service-b", "service-c"]
WINDOW_SIZE     = 50

FASTAPI_URL     = "http://localhost:8000/anomaly"

def load_model() -> tuple[
    dict[str, ort.InferenceSession],
    dict[str, float]
]:
    sessions   = {}
    thresholds = {}

    for service in SERVICES:
        svc_dir     = f"{CHECKPOINT_DIR}/{service}"
        session     = ort.InferenceSession(f"{svc_dir}/model.onnx")
        threshold   = float(np.load(f"{svc_dir}/threshold.npy"))
        # Increase threshold to reduce false positives without retraining
        if service == "service-a":
            threshold *= 2.5
        elif service == "service-b" or service == "service-c":
            threshold *= 1.5

        sessions[service]   = session
        thresholds[service] = threshold
        logger.info(
            f"Loaded model | service={service} threshold={threshold:.6f}"
        )

    return sessions, thresholds

def build_redis_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis.Redis.from_url(redis_url, decode_responses=True)

def score_window(
        session: ort.InferenceSession,
        window: deque
) -> float:
    window_array = np.array(list(window), dtype=np.float32)
    window_array = window_array[np.newaxis, :, :]
    output       = session.run(
        ["reconstruction"],
        {"log_window": window_array},
    )[0]
    reconstruction = output[0]
    mse = np.mean((window_array[0, -1] - reconstruction[-1]) ** 2)
    return float(mse)

def report_anomaly(
        parsed_log: dict,
        anomaly_score: float,
        is_anomaly: bool
) -> None:
    payload = {
        "service":          parsed_log.get("service"),
        "timestamp":        parsed_log.get("timestamp"),
        "level":            parsed_log.get("level"),
        "message":          parsed_log.get("message"),
        "template":         parsed_log.get("template"),
        "template_id":      parsed_log.get("template_id"),
        "anomaly_score":    anomaly_score,
        "is_anomaly":       is_anomaly,
    }
    try:
        responce = httpx.post(FASTAPI_URL, json=payload, timeout=5.0)
        responce.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to report anomaly: {e} - Response: {responce.text if 'responce' in locals() else ''}")

def main():
    logger.info("Anomaly scorer starting...")

    sessions, thresholds = load_model()
    r = build_redis_client()

    window_size = 50
    windows = {
        s: deque(maxlen=window_size) for s in SERVICES
    }
    
    logger.info("Listening for parsed logs on Redis 'parsed-logs' list...")

    while True:
        try:
            result = r.brpop("parsed-logs", timeout=5)
            if not result:
                continue
                
            _, parsed_json = result
            parsed_log = json.loads(parsed_json)
            
            service     = parsed_log.get("service")
            
            if service not in windows:
                continue

            features = extract_features(parsed_log)
            windows[service].append(features)

            if len(windows[service]) < window_size:
                continue
                
            session     = sessions.get(service)
            threshold   = thresholds.get(service)
            
            score       = score_window(session, windows[service])

            is_anomaly = score > threshold
            if is_anomaly:
                logger.warning(
                    f"ANOMALY DETECTED | "
                    f"service={service} "
                    f"score={score:.6f} | "
                    f"msg={parsed_log.get('message', '')[:50]}"
                )
            report_anomaly(parsed_log, score, is_anomaly)

        except Exception as e:
            logger.error(f"Error scoring log: {e}")

if __name__ == "__main__":
    main()