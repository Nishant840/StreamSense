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
SERVICES        = ["service-a", "service-b", "service-c"]

WINDOWS_PER_SERVICE = {
    "service-a": 1000,
    "service-b": 1000,
    "service-c": 1000,
}

TRAIN_RATIO = 0.667
VAL_RATIO   = 0.167
EVAL_RATIO  = 0.166

OUTPUT_DIR  = "../ml"

def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        "parsed-logs",
        bootstrap_servers="localhost:29092",
        group_id="training-data-collector-v3",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8"))
    )

def main():
    total_needed = sum(WINDOWS_PER_SERVICE.values())
    logger.info(
        f"Starting balanced collection | "
        f"per service={WINDOWS_PER_SERVICE} | "
        f"total={total_needed}"
    )

    consumer    = build_consumer()

    windows: dict[str,list] = {s: [] for s in SERVICES}
    buffers: dict[str, deque] = {
        s: deque(maxlen=WINDOW_SIZE) for s in SERVICES
    }

    for message in consumer:
        parsed_log = message.value
        service    = parsed_log.get("service", "")

        if service not in SERVICES:
            continue

        if len(windows[service]) >= WINDOWS_PER_SERVICE[service]:
            if all(
                len(windows[s]) >= WINDOWS_PER_SERVICE[s]
                for s in SERVICES
            ):
                break
            continue


        features = extract_features(parsed_log)
        buffers[service].append(features)

        if len(buffers[service]) == WINDOW_SIZE:
            windows[service].append(list(buffers[service]))

            collected = {s: len(windows[s]) for s in SERVICES}
            if sum(collected.values()) % 100 == 0:
                logger.info(f"Progress: {collected}")

    consumer.close()

    for service in SERVICES:
        data        = np.array(windows[service], dtype=np.float32)
        train_end   = int(len(data) * TRAIN_RATIO)
        val_end     = int(len(data) * (TRAIN_RATIO + VAL_RATIO))

        train_data  = data[:train_end]
        val_data    = data[train_end:val_end]
        eval_data   = data[val_end:]

        svc = service.replace("-", "_")
        np.save(f"{OUTPUT_DIR}/train_data_{svc}.npy", train_data)
        np.save(f"{OUTPUT_DIR}/val_data_{svc}.npy", val_data)
        np.save(f"{OUTPUT_DIR}/eval_data_{svc}.npy", eval_data)

        logger.info(
            f"{service} -> "
            f"train={train_data.shape} | "
            f"val={val_data.shape} | "
            f"eval={eval_data.shape}"
        )

    logger.info("Collection complete!")

if __name__ == "__main__":
    main()