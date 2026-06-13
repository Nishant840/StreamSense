import torch
import numpy as np
import onnxruntime as ort
import time
from model import LogAutoencoder

CHECKPOINT_DIR  = "checkpoints"
SERVICES        = ["service-a", "service-b", "service-c"]

WINDOW_SIZE = 50
INPUT_DIM   = 8

DEVICE = torch.device("cpu")

def export_to_onnx(model: LogAutoencoder, onnx_path: str) -> None:
    model.eval()

    dummy = torch.randn(1, WINDOW_SIZE, INPUT_DIM)

    torch.onnx.export(
        model,
        dummy,
        onnx_path,
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
    print(f"Model exported to {onnx_path}")

def verify_onnx(
        model: LogAutoencoder,
        onnx_path: str
) -> None:
    print("\nVerifying ONNX model...")

    dummy = torch.randn(1, WINDOW_SIZE, INPUT_DIM)

    with torch.no_grad():
        pytorch_output = model(dummy).numpy()

    session = ort.InferenceSession(onnx_path)
    onnx_output = session.run(
        ["reconstruction"],
        {"log_window": dummy.numpy()},
    )[0]

    max_diff = np.max(np.abs(pytorch_output - onnx_output))
    print(f"Max difference PyTorch vs ONNX: {max_diff:.8f}")

    if max_diff < 1e-4:
        print("ONNX model matches PyTorch output")
    else:
        print("Output differ - check export settings")

def benchmark(
        model: LogAutoencoder,
        onnx_path: str,
        runs: int=100
) -> None:

    dummy = torch.randn(1, WINDOW_SIZE, INPUT_DIM)
    session     = ort.InferenceSession(onnx_path)
    onnx_input  = dummy.numpy()

    for _ in range(10):
        with torch.no_grad():
            model(dummy)
        session.run(["reconstruction"], {"log_window": onnx_input})

    # pytorch benchmark
    start = time.perf_counter()
    for _ in range(runs):
        with torch.no_grad():
            model(dummy)
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
    for service in SERVICES:
        print(f"\n{'='*50}")
        print(f"Exporting: {service}")
        print(f"{'='*50}")

        svc_dir    = f"{CHECKPOINT_DIR}/{service}"
        model_path = f"{svc_dir}/best_model.pt"
        onnx_path  = f"{svc_dir}/model.onnx"

        model = LogAutoencoder().to(DEVICE)
        model.load_state_dict(
            torch.load(
                model_path,
                weights_only=True,
                map_location=DEVICE,
            )
        )
        model.eval()

        export_to_onnx(model, onnx_path)
        print(f"  Exported → {onnx_path}")
        verify_onnx(model, onnx_path)
        benchmark(model, onnx_path)
    
    print(f"\n All models exported!")

if __name__ == "__main__":
    main()