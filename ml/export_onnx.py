import torch
import numpy as np
import onnxruntime as ort
from model import LogAutoencoder

CHECKPOINT_PATH = "checkpoints/best_model.pt"
ONNX_PATH       = "checkpoints/model.onnx"

WINDOW_SIZE = 50
INPUT_DIM   = 8
BATCH_SIZE  = 1

DEVICE = torch.device("cpu")

def export_to_onnx(model: LogAutoencoder) -> None:
    model.eval()

    dummy_input = torch.randn(BATCH_SIZE, WINDOW_SIZE, INPUT_DIM)

    torch.onnx.export(
        model,
        dummy_input,
        ONNX_PATH,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["log_window"],
        output_names=["reconstruction"],
        dynamic_axes={
            "log_window":   {0: "batch_size"},
            "reconstruction": {0, "batch_size"},
        },
    )
    print(f"Model exported to {ONNX_PATH}")

def verify_onnx(model: LogAutoencoder) -> None:
    print("\nVerifying ONNX model...")

    dummy_input = torch.randn(BATCH_SIZE, WINDOW_SIZE, INPUT_DIM)

    with torch.no_grad():
        pytorch_output = model(dummy_input).numpy()

    session = ort.InferenceSession(ONNX_PATH)
    onnx_output = session.run(
        ["reconstruction"],
        {"log_window": dummy_input.numpy()},
    )[0]

    max_diff = np.max(np.abs(pytorch_output - onnx_output))
    print(f"Max difference PyTorch vs ONNX: {max_diff:.8f}")

    if max_diff < 1e-5:
        print("ONNX model matches PyTorch output")
    else:
        print("Output differ - check export settings")

def benchmark(model: LogAutoencoder, runs: int=100) -> None:
    import time

    dummy_input = torch.randn(BATCH_SIZE, WINDOW_SIZE, INPUT_DIM)
    session     = ort.InferenceSession(ONNX_PATH)
    onnx_input  = dummy_input.numpy()

    for _ in range(10):
        with torch.no_grad():
            model(dummy_input)
        session.run(["reconstruction"], {"log_window": onnx_input})

    # pytorch benchmark
    start = time.perf_counter()
    for _ in range(runs):
        with torch.no_grad():
            model(dummy_input)
    pytorch_ms = (time.perf_counter() - start) / runs * 1000

    # onnx benchmark
    start = time.perf_counter()
    for _ in range(runs):
        session.run(["reconstruction"], {"log_window": onnx_input})
    onnx_ms = (time.perf_counter() - start) / runs * 1000

    print(f"\nBenchmark ({runs} runs):")
    print(f"  PyTorch:  {pytorch_ms:.3f}ms per inference")
    print(f"  ONNX:     {onnx_ms:.3f}ms per inference")
    print(f"  Speedup:  {pytorch_ms/onnx_ms:.2f}x")

def main():
    print("Loading PyTorch model...")
    model = LogAutoencoder().to(DEVICE)
    model.load_state_dict(
        torch.load(CHECKPOINT_PATH, weights_only=True, map_location=DEVICE)
    )
    model.eval()

    export_to_onnx(model)
    verify_onnx(model)
    benchmark(model)

    print(f"\nDone! ONNX model saved to {ONNX_PATH}")

if __name__ == "__main__":
    main()