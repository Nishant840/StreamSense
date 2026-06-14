import numpy as np
import torch
import torch.nn as nn
from model import LogAutoencoder

CHECKPOINT_DIR  = "checkpoints"
SERVICES        = ["service-a", "service-b", "service-c"]
THRESHOLD_PATH  = "checkpoints/threshold.npy"
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

def load_model(service: str) -> tuple[LogAutoencoder, float]:
    svc_dir = f"{CHECKPOINT_DIR}/{service}"
    model = LogAutoencoder().to(DEVICE)
    model.load_state_dict(
        torch.load(f"{svc_dir}/best_model.pt", weights_only=True, map_location=DEVICE)
    )
    model.eval()
    threshold = float(np.load(f"{svc_dir}/threshold.npy"))
    return model, threshold

def inject_error_spike(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # level feature → ERROR (0.75), is_error → 1.0
    for i in range(20, 50):
        window[i][0] = 0.75     # level = ERROR
        window[i][4] = 1.0      # is_error = 1.0
        window[i][3] = 0.001    # very low latency (connection refused)
    return window

def inject_slowdown(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # response_time feature → 10x normal (clamped to 1.0)
    for i in range(window.shape[0]):
        window[i][3] = min(window[i][3] * 10, 1.0)
    return window

def inject_unknown_template(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # template_id feature → very high value never seen in training
    for i in range(10, 40):
        window[i][2] = 0.99   # template_id = 99 (unknown)
        window[i][0] = 0.75   # ERROR level
        window[i][4] = 1.0    # is_eror
    return window

def inject_memory_leak(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # gradually increasing response times simulating memory pressure
    for i in range(window.shape[0]):
        leak_factor     = 1.0 + (i / window.shape[0]) * 9.0
        window[i][3]    = min(window[i][3] * leak_factor, 1.0)
        window[i][5]    = min(window[i][5] * leak_factor, 1.0)
    return window

def score_window(
        model: LogAutoencoder,
        window: np.ndarray,
) -> float:
    tensor = torch.tensor(window, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        recon = model(tensor)
        loss  = torch.mean((recon[0, -1] - tensor[0, -1]) ** 2)
    return loss.item()


def compute_metrics(
        scores:     list[float],
        labels:     list[int],
        threshold:  float
) -> dict:
    tp = fp = tn = fn = 0

    for score, label in zip(scores, labels):
        predicted = 1 if score > threshold else 0

        if predicted == 1 and label == 1:
            tp += 1
        elif predicted == 1 and label == 0:
            fp += 1
        elif predicted == 0 and label == 0:
            tn += 1
        elif predicted == 0 and label == 1:
            fn += 1
    
    precision = tp / (tp+fp) if (tp+fp) > 0 else 0.0
    recall    = tp / (tp+fn) if (tp+fn) > 0 else 0.0
    f1        = (
        2*precision*recall / (precision+recall)
        if (precision+recall) > 0 else 0.0
    )
    accuracy = (tp+tn) / (tp+fp+tn+fn)

    return {
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "accuracy":  round(accuracy,  4),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }

def evaluate_service(
    service:    str,
    model:      LogAutoencoder,
    threshold:  float,
    eval_data:  np.ndarray,
) -> None:
    injectors = [
        ("error_spike",         inject_error_spike),
        ("slowdown",            inject_slowdown),
        ("unknown_template",    inject_unknown_template),
        ("memory_leak",         inject_memory_leak),
    ]

    all_scores = []
    all_labels = []

    normal_scores       = []
    anomaly_by_type     = {name: [] for name, _ in injectors}
    
    for window in eval_data:
        score = score_window(model, window)
        normal_scores.append(score)
        all_scores.append(score)
        all_labels.append(0)

        for name, fn in injectors:
            a_score = score_window(model, fn(window))
            anomaly_by_type[name].append(a_score)
            all_scores.append(a_score)
            all_labels.append(1)

    print(f"\n{'='*55}")
    print(f"  {service.upper()}")
    print(f"{'='*55}")
    print(f"  Threshold: {threshold:.6f}")
    print(f"  [NORMAL] avg={np.mean(normal_scores):.6f} | "
          f"correct={sum(s <= threshold for s in normal_scores)/len(normal_scores)*100:.1f}%")
    
    for name, scores in anomaly_by_type.items():
        detected = sum(s > threshold for s in scores) / len(scores) * 100
        print(f"  [{name.upper()}] avg={np.mean(scores):.6f} | "
              f"detection={detected:.1f}%")
        
    metrics = compute_metrics(all_scores, all_labels, threshold)
    print(f"\n  Precision={metrics['precision']} | "
          f"Recall={metrics['recall']} | "
          f"F1={metrics['f1']}")
    print(f"  TP={metrics['tp']} FP={metrics['fp']} "
          f"TN={metrics['tn']} FN={metrics['fn']}")

    target = "✅ F1 > 0.80" if metrics["f1"] > 0.80 else "❌ Below target"
    print(f"  {target}")


def main():
    print("Loading model...")
    overall_scores = []
    overall_labels = []

    for service in SERVICES:
        model, threshold = load_model(service)
        svc             = service.replace("-", "_")
        eval_data       = np.load(f"eval_data_{svc}.npy")

        evaluate_service(service, model, threshold, eval_data)

    print(f"\n{'='*55}")
    print("    Done!")

if __name__ == "__main__":
    main()