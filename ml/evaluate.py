import numpy as np
import torch
import torch.nn as nn
from model import LogAutoencoder

EVAL_PATH       = "eval_data.npy"
CHECKPOINT_PATH = "checkpoints/best_model.pt"
THRESHOLD_PATH  = "checkpoints/threshold.npy"

WINDOW_SIZE = 50
INPUT_DIM   = 8

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

def load_model() -> tuple[LogAutoencoder, float]:
    model = LogAutoencoder().to(DEVICE)
    model.load_state_dict(
        torch.load(CHECKPOINT_PATH, weights_only=True, map_location=DEVICE)
    )
    model.eval()
    threshold = float(np.load(THRESHOLD_PATH))
    return model, threshold

def inject_error_spike(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # level feature → ERROR (0.75), is_error → 1.0
    for i in range(20, 50):
        window[i][0] = 0.75     # level = ERROR
        window[i][6] = 1.0      # is_error = 1.0
        window[i][5] = 0.001    # very low latency (connection refused)
    return window

def inject_slowdown(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # response_time feature → 10x normal (clamped to 1.0)
    for i in range(window.shape[0]):
        window[i][5] = min(window[i][5] * 10, 1.0)
    return window

def inject_unknown_template(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # template_id feature → very high value never seen in training
    for i in range(10, 40):
        window[i][4] = 0.99   # template_id = 99 (unknown)
        window[i][0] = 0.75   # ERROR level
        window[i][6] = 1.0    # is_eror
    return window

def inject_memory_leak(window: np.ndarray) -> np.ndarray:
    window = window.copy()
    # gradually increasing response times simulating memory pressure
    for i in range(window.shape[0]):
        leak_factor     = 1.0 + (i / window.shape[0]) * 9.0
        window[i][5]    = min(window[i][5] * leak_factor, 1.0)
        window[i][7]    = min(window[i][7] * leak_factor, 1.0)
    return window

def score_window(
        model: LogAutoencoder,
        window: np.ndarray,
) -> float:
    tensor = torch.tensor(window, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        recon = model(tensor)
        loss  = nn.MSELoss()(recon, tensor)
    return loss.item()

def evaluate(
    model: LogAutoencoder,
    threshold: float,
    eval_data: np.ndarray,
) -> dict:
    
    results = {
        "normal":           {"scores": [], "labels": []},
        "error_spike":      {"scores": [], "labels": []},
        "slowdown":         {"scores": [], "labels": []},
        "unknown_template": {"scores": [], "labels": []},
        "memory_leak":      {"scores": [], "labels": []}
    }

    for window in eval_data:
        # normal window -> label 0
        score = score_window(model, window)
        results["normal"]["scores"].append(score)
        results["normal"]["labels"].append(0)

        # anomaly windows -> label 1
        for anomaly_type, inject_fn in [
            ("error_spike",     inject_error_spike),
            ("slowdown",        inject_slowdown),
            ("unknown_template",inject_unknown_template),
            ("memory_leak",     inject_memory_leak),
        ]:
            anomaly_window  = inject_fn(window)
            score           = score_window(model, anomaly_window)
            results[anomaly_type]["scores"].append(score)
            results[anomaly_type]["labels"].append(1)

    return results

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

def print_results(
    results:   dict,
    threshold: float,
) -> None:

    print(f"\n{'='*60}")
    print(f"  StreamSense Anomaly Detection — Evaluation Report")
    print(f"{'='*60}")
    print(f"  Threshold: {threshold:.6f}")
    print(f"{'='*60}\n")

    all_scores = []
    all_labels = []

    for anomaly_type, data in results.items():
        is_anomaly = anomaly_type != "normal"
        scores     = data["scores"]
        labels     = data["labels"]

        all_scores.extend(scores)
        all_labels.extend(labels)

        avg_score = np.mean(scores)
        detection = (
            sum(1 for s in scores if s > threshold) / len(scores)
            if is_anomaly
            else sum(1 for s in scores if s <= threshold) / len(scores)
        )

        print(f"  [{anomaly_type.upper()}]")
        print(f"    Avg score:   {avg_score:.6f}")
        print(f"    {'Detection' if is_anomaly else 'Correct normal'} rate: {detection*100:.1f}%")
        print()

    print(f"{'='*60}")
    print(f"  Overall Metrics (all anomaly types combined)")
    print(f"{'='*60}")

    metrics = compute_metrics(all_scores, all_labels, threshold)

    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall:    {metrics['recall']:.4f}")
    print(f"  F1 Score:  {metrics['f1']:.4f}")
    print(f"  Accuracy:  {metrics['accuracy']:.4f}")
    print()
    print(f"  TP: {metrics['tp']} | FP: {metrics['fp']} | "
          f"TN: {metrics['tn']} | FN: {metrics['fn']}")
    print(f"{'='*60}\n")

    target = "✅ TARGET MET (F1 > 0.80)" if metrics["f1"] > 0.80 else "❌ Below target"
    print(f"  {target}")
    print()

def main():
    print("Loading model and threshold...")
    model, threshold = load_model()

    print("Loading evaluation data...")
    eval_data = np.load(EVAL_PATH)
    print(f"Eval windows: {eval_data.shape}")

    print("Running evaluation...")
    results = evaluate(model, threshold, eval_data)

    print_results(results, threshold)

if __name__ == "__main__":
    main()