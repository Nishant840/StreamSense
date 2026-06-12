import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from model import LogAutoencoder
import os

DATA_PATH       = "train_data.npy"
VAL_PATH        = "val_data.npy"
CHECKPOINT_DIR  = "checkpoints"
CHECKPOINT_PATH = f"{CHECKPOINT_DIR}/best_model.pt"
THRESHOLD_PATH  = f"{CHECKPOINT_DIR}/threshold.npy"

BATCH_SIZE      = 32
EPOCHS          = 40
LEARNING_RATE   = 1e-3
TRAIN_SPLIT     = 0.8
THRESHOLD_PCT   = 97

DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

def load_data() -> tuple[DataLoader, DataLoader]:
    train_raw = np.load(DATA_PATH)
    val_raw   = np.load(VAL_PATH)

    train_data = torch.tensor(train_raw, dtype=torch.float32)
    val_data   = torch.tensor(val_raw, dtype=torch.float32)
    
    train_ds     = TensorDataset(train_data)
    val_ds       = TensorDataset(val_data)


    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    print(f"Train size: {len(train_ds)} | Val size: {len(val_ds)}")
    return train_loader, val_loader

def train(
        model:          LogAutoencoder,
        train_loader:   DataLoader,
        val_loader:     DataLoader,
) -> list[dict]:
    
    optimizer   = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler   = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=3, factor=0.5
    )
    criterion   = nn.MSELoss()

    best_val_loss   = float("inf")
    history         = []

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
            torch.save(model.state_dict(), CHECKPOINT_PATH)
            saved = "saved"
        else:
            saved = ""

        history.append({
            "epoch":        epoch,
            "train_loss":   train_loss,
            "val_loss":     val_loss   
        })

        print(
            f"Epoch {epoch:02d}/{EPOCHS} | "
            f"train={train_loss:.6f} | "
            f"val={val_loss:.6f} | "
            f"saved"
        )

    return history

def calculate_threshold(
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

            for i in range(batch.shape[0]):
                loss = nn.MSELoss()(recon[i], batch[i])
                all_losses.append(loss.item())

    threshold = float(np.percentile(all_losses, THRESHOLD_PCT))
    np.save(THRESHOLD_PATH, np.array(threshold))

    print(f"Threshold ({THRESHOLD_PCT}th percentile): {threshold:.6f}")
    print(f"Min loss: {min(all_losses):.6f}")
    print(f"Max loss: {max(all_losses):.6f}")
    print(f"Mean loss: {np.mean(all_losses):.6f}")

    return threshold

def main():
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    print(f"Using device: {DEVICE}")

    model = LogAutoencoder().to(DEVICE)
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")

    train_loader, val_loader = load_data()
    history = train(model, train_loader, val_loader)

    print("\nLoading best model for threshold calculation...")
    model.load_state_dict(torch.load(CHECKPOINT_PATH, weights_only=True))
    threshold = calculate_threshold(model, val_loader)

    print(f"\nTraining complete!")
    print(f"Best val loss: {min(h['val_loss'] for h in history):.6f}")
    print(f"Anomaly threshold: {threshold:.6f}")

if __name__ == "__main__":
    main()