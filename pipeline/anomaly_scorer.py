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

CHECKPOINT_DIR  = "../ml/checkpoints"
SERVICES        = ["service-a", "service-b", "service-c"]
KAFKA_BOOTSTRAP = "localhost:29092"
PARSED_TOPIC    = "parsed-logs"
GROUP_ID        = "anomaly-scorer-group-v2"
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
        sessions[service]   = session
        thresholds[service] = threshold
        logger.info(
            f"Loaded model | service={service} threshold={threshold:.6f}"
        )

    return sessions, thresholds

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
    mse = np.mean((window_array[0, -1] - reconstruction[-1]) ** 2)
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
    sessions, thresholds = load_model()
    consumer           = build_consumer()

    windows: dict[str, deque] = defaultdict(
        lambda: deque(maxlen=WINDOW_SIZE)
    )

    logger.info(f"Consuming from {PARSED_TOPIC}...")

    for message in consumer:
        parsed_log = message.value
        service    = parsed_log.get("service", "unknown")

        if service not in sessions:
            consumer.commit()
            continue

        features   = extract_features(parsed_log)

        windows[service].append(features)

        if len(windows[service]) == WINDOW_SIZE:
            session   = sessions[service]
            threshold = thresholds[service]
            score     = score_window(session, windows[service])

            print(f"service={service} score={score:.6f} threshold={threshold:.6f}")

            if score > threshold:
                logger.warning(
                    f"ANOMALY DETECTED | "
                    f"service={service} "
                    f"score={score:.6f} | "
                    f"msg={parsed_log.get('message', '')[:50]}"
                )
                report_anomaly(parsed_log, score)

        consumer.commit()

if __name__ == "__main__":
    main()