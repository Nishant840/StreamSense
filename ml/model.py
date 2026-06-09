import torch
import torch.nn as nn

class LogAutoencoder(nn.Module):

    def __init__(
            self,
            input_dim:      int = 8,
            window_size:    int = 50,
            latent_dim:     int = 16,
    ):
        super().__init__()
        
        self.input_dim      = input_dim
        self.window_size    = window_size
        self.latent_dim     = latent_dim
        self.flat_dim       = input_dim * window_size #400

        self.encoder = nn.Sequential(
            nn.Linear(self.flat_dim, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Dropout(0.1),

            nn.Linear(128, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(0.1),

            nn.Linear(64, latent_dim),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),

            nn.Linear(64, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),

            nn.Linear(128, self.flat_dim),
            nn.Sigmoid(),
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size      = x.shape[0]
        x_flat          = x.view(batch_size, -1)
        latent          = self.encoder(x_flat)
        recon_flat      = self.decoder(latent)
        return recon_flat.view(batch_size, self.window_size, self.input_dim)
    
    def reconstruction_loss(self, x: torch.Tensor, recon: torch.Tensor) -> torch.Tensor:
        return nn.MSELoss()(recon, x)
    
    def anomaly_score(self, x: torch.Tensor) -> float:
        was_training = self.training
        self.eval()
        with torch.no_grad():
            # BatchNorm needs batch size > 1
            if x.shape[0] == 1:
                x = x.repeat(2,1,1)[:1]
            recon = self.forward(x)
            loss = self.reconstruction_loss(x, recon)

        if was_training:
            self.train()
        return loss.item()
    