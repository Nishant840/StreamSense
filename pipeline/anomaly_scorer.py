import json
import logging
import httpx
import numpy as np
import onnxruntime as ort
from collections import defaultdict, deque
from kafka import KafkaConsumer

from feature_extractor import extract_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s anomaly-scorer %(message)s"
)
logger = logging.getLogger("anomaly-scorer")

ONNX_PATH       = "../ml/checkpoints/model.onnx"
THRESHOLD_PATH  = "../ml/checkpoints/threshold.npy"
KAFKA_BOOTSTRAP = "localhost:29092"
PARSED_TOPIC    = "parsed-logs"
GROUP_ID        = "anomaly-scorer-group"
WINDOW_SIZE     = 50
FASTAPI_URL     = "http://localhost:8000/anomaly"


def load_model() -> tuple[ort.InferenceSession, float]:
    session     = ort.InferenceSession(ONNX_PATH)
    threshold   = float(np.load(THRESHOLD_PATH))
    logger.info(f"Model loaded | threshold={threshold:.6f}")
    return session, threshold

def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        PARSED_TOPIC,
        bootstrap_servers = KAFKA_BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=False,
        value_deserializer=lambda v: json.loads(v.decode("utf-8"))
    )

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
    mse = np.mean((window_array[0] - reconstruction) ** 2)
    return float(mse)

def report_anomaly(
        parsed_log: dict,
        anomaly_score: float
) -> None:
    payload = {
        "service":          parsed_log.get("service"),
        "timestamp":        parsed_log.get("timestamp"),
        "level":            parsed_log.get("level"),
        "message":          parsed_log.get("message"),
        "template":         parsed_log.get("template"),
        "template_id":      parsed_log.get("template_id"),
        "anomaly_score":    anomaly_score,    
    }
    try:
        responce = httpx.post(FASTAPI_URL, json=payload, timeout=5.0)
        responce.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to report anomaly: {e}")

def main():
    logger.info("Anomaly scorer starting...")
    session, threshold = load_model()
    consumer           = build_consumer()
    windows: dict[str, deque] = defaultdict(
        lambda: deque(maxlen=WINDOW_SIZE)
    )

    logger.info(f"Consuming from {PARSED_TOPIC}...")

    for message in consumer:
        parsed_log  = message.value
        service     = parsed_log.get("service", "unknown")
        features    = extract_features(parsed_log)

        windows[service].append(features)

        if len(windows[service]) == WINDOW_SIZE:
            score = score_window(session, windows[service])

            if score > threshold:
                logger.warning(
                    f"ANOMALY DETECTED | "
                    f"service={service} "
                    f"score={score:.6f} "
                    f"threshold={threshold:.6f}"
                )
                report_anomaly(parsed_log, score)
            else:
                logger.debug(
                    f"Normal | service={service} score={score:.6f}"
                )
        
        consumer.commit()

if __name__ == "__main__":
    main()