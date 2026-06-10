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
TOTAL_WINDOWS  = 3000

TRAIN_SIZE = 2000
VAL_SIZE   = 500
EVAL_SIZE  = 500

TRAIN_OUTPUT     = "../ml/train_data.npy"
VAL_OUTPUT       = "../ml/val_data.npy"
EVAL_OUTPUT      = "../ml/eval_data.npy"

def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        "parsed-logs",
        bootstrap_servers="localhost:29092",
        group_id="training-data-collector-v2",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8"))
    )

def main():
    logger.info(
        f"Starting data collection | "
        f"total={TOTAL_WINDOWS} | "
        f"train={TRAIN_SIZE} | val={VAL_SIZE} | eval={EVAL_SIZE}"
    )

    consumer    = build_consumer()
    window      = deque(maxlen=WINDOW_SIZE)
    windows     = []

    for message in consumer:
        parsed_log = message.value
        features = extract_features(parsed_log)
        window.append(features)

        if len(window) == WINDOW_SIZE:
            windows.append(list(window))

            if len(windows) % 200 == 0:
                logger.info(f"Collected {len(windows)}/{TOTAL_WINDOWS} windows")

            if len(windows) >= TOTAL_WINDOWS:
                break

    data = np.array(windows, dtype=np.float32)
    
    train_data = data[:TRAIN_SIZE]
    val_data   = data[TRAIN_SIZE:TRAIN_SIZE+VAL_SIZE]
    eval_data  = data[TRAIN_SIZE+VAL_SIZE:]

    np.save(TRAIN_OUTPUT, train_data)
    np.save(VAL_OUTPUT, val_data)
    np.save(EVAL_OUTPUT, eval_data)

    logger.info(f"Saved train: {train_data.shape} -> {TRAIN_OUTPUT}")
    logger.info(f"Saved val: {val_data.shape} -> {VAL_OUTPUT}")
    logger.info(f"Saved eval: {eval_data.shape} -> {EVAL_OUTPUT}")
    
    consumer.close()

if __name__ == "__main__":
    main()