import torch
import torch.nn as nn

class LogAutoencoder(nn.Module):

    def __init__(
            self,
            input_dim:      int = 8,
            window_size:    int = 50,
            latent_dim:     int = 4,
    ):
        super().__init__()
        
        self.input_dim      = input_dim
        self.window_size    = window_size
        self.latent_dim     = latent_dim
        self.flat_dim       = input_dim * window_size #400

        self.network = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, latent_dim),
            nn.ReLU(),
            nn.Linear(latent_dim, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim),
            nn.Sigmoid()
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, window_size, input_dim)
        # nn.Linear automatically broadcasts over the window_size dimension
        return self.network(x)
    
    def reconstruction_loss(self, x: torch.Tensor, recon: torch.Tensor) -> torch.Tensor:
        return nn.MSELoss()(recon, x)
    
    def anomaly_score(self, x: torch.Tensor) -> float:
        was_training = self.training
        self.eval()
        with torch.no_grad():
            recon = self.forward(x)
            loss = self.reconstruction_loss(x, recon)

        if was_training:
            self.train()
        return loss.item()
    