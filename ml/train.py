import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from model import LogAutoencoder
import os


CHECKPOINT_DIR  = "checkpoints"
BATCH_SIZE      = 32
EPOCHS          = 40
LEARNING_RATE   = 1e-3
TRAIN_SPLIT     = 0.8
THRESHOLD_PCT   = 99

SERVICES = ["service-a", "service-b", "service-c"]

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

def load_data(service: str) -> tuple[DataLoader, DataLoader]:
    svc        = service.replace("-", "_")
    train_data = np.load(f"train_data_{svc}.npy")
    val_data   = np.load(f"val_data_{svc}.npy")

    train_data = torch.tensor(train_data, dtype=torch.float32)
    val_data   = torch.tensor(val_data,   dtype=torch.float32)
    
    train_ds     = TensorDataset(train_data)
    val_ds       = TensorDataset(val_data)


    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    print(f"   Train size: {len(train_data)} | Val size: {len(val_data)}")
    return train_loader, val_loader

def train_model(
        service:        str,
        train_loader:   DataLoader,
        val_loader:     DataLoader,
) -> LogAutoencoder:
    
    model       = LogAutoencoder().to(DEVICE)
    optimizer   = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler   = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=3, factor=0.5
    )
    criterion   = nn.MSELoss()

    svc_dir     = f"{CHECKPOINT_DIR}/{service}"
    os.makedirs(svc_dir, exist_ok=True)
    best_path   = f"{svc_dir}/best_model.pt"

    best_val_loss   = float("inf")

    for epoch in range(1, EPOCHS+1):
        model.train()
        train_losses = []

        for (batch,) in train_loader:
            batch   = batch.to(DEVICE)
            recon   = model(batch)
            loss    = criterion(recon, batch)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_losses.append(loss.item())

        model.eval()
        val_losses = []

        with torch.no_grad():
            for (batch,) in val_loader:
                batch = batch.to(DEVICE)
                recon = model(batch)
                loss  = criterion(recon, batch)
                val_losses.append(loss.item())

        train_loss  = np.mean(train_losses)
        val_loss    = np.mean(val_losses)

        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss   = val_loss
            torch.save(model.state_dict(), best_path)
            saved = "saved"
        else:
            saved = ""


        print(
            f"  Epoch {epoch:02d}/{EPOCHS} | "
            f"train={train_loss:.6f} | "
            f"val={val_loss:.6f} | "
            f"saved"
        )

    model.load_state_dict(
        torch.load(best_path, weights_only=True, map_location=DEVICE)
    )

    return model

def calculate_threshold(
        service:    str,
        model:      LogAutoencoder,
        val_loader: DataLoader
) -> float:
    
    print("\nCalculating anomaly threhold...")
    model.eval()
    all_losses = []

    with torch.no_grad():
        for (batch,) in val_loader:
            batch = batch.to(DEVICE)
            recon = model(batch)

            mse_per_log = torch.mean((recon - batch)**2, dim=2)
            last_log_mse = mse_per_log[:, -1]
            all_losses.extend(last_log_mse.cpu().tolist())

    threshold = float(np.percentile(all_losses, THRESHOLD_PCT))
    svc_dir   = f"{CHECKPOINT_DIR}/{service}"
    np.save(f"{svc_dir}/threshold.npy", np.array(threshold))

    print(f"    Threshold ({THRESHOLD_PCT}th percentile): {threshold:.6f}")
    print(f"Min loss: {min(all_losses):.6f}")
    print(f"Max loss: {max(all_losses):.6f}")
    print(f"Mean loss: {np.mean(all_losses):.6f}")

    return threshold

def main():
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    print(f"Using device: {DEVICE}")

    for service in SERVICES:
        print(f"{'='*50}")
        print(f"Training: {service}")
        print(f"{'='*50}")

        train_loader, val_loader = load_data(service)
        model     = train_model(service, train_loader, val_loader)
        threshold = calculate_threshold(service, model, val_loader)

        print(f"    {service} done | threshold={threshold:.6f}\n")

if __name__ == "__main__":
    main()