import json
import logging
import numpy as np
from collections import deque
from kafka import KafkaConsumer
from feature_extractor import extract_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s collector %(message)s"
)
logger = logging.getLogger("collector")

WINDOW_SIZE     = 50
TARGET_WINDOWS  = 2000
OUTPUT_FILE     = "../ml/train_data.py"

def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        "parsed-logs",
        bootstrap_servers="localhost:29092",
        group_id="training-data-collector",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8"))
    )

def main():
    logger.info(f"Starting data collection | target={TARGET_WINDOWS} windows")

    consumer    = build_consumer()
    window      = deque(maxlen=WINDOW_SIZE)
    windows     = []

    for message in consumer:
        parsed_log = message.value
        features = extract_features(parsed_log)
        window.append(features)

        if len(window) == WINDOW_SIZE:
            windows.append(list(window))

            if len(windows) % 100 == 0:
                logger.info(f"Collected {len(windows)}/{TARGET_WINDOWS} windows")

            if len(windows) >= TARGET_WINDOWS:
                break

    data = np.array(windows, dtype=np.float32)
    np.save(OUTPUT_FILE, data)

    logger.info(f"Saved {data.shape} to {OUTPUT_FILE}")
    consumer.close()

if __name__ == "__main__":
    main()