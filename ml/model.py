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

        self.encoder = nn.LSTM(
            input_size=input_dim, 
            hidden_size=latent_dim, 
            num_layers=1, 
            batch_first=True
        )
        self.decoder = nn.LSTM(
            input_size=latent_dim, 
            hidden_size=latent_dim, 
            num_layers=1, 
            batch_first=True
        )
        self.output_layer = nn.Linear(latent_dim, input_dim)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size = x.shape[0]
        
        # x shape: (batch_size, window_size, input_dim)
        _, (hidden, _) = self.encoder(x)
        
        # hidden shape: (1, batch_size, latent_dim)
        # We need to feed this hidden state as input to the decoder for `window_size` steps
        hidden = hidden.transpose(0, 1) # (batch_size, 1, latent_dim)
        decoder_input = hidden.repeat(1, self.window_size, 1) # (batch_size, window_size, latent_dim)
        
        decoder_out, _ = self.decoder(decoder_input) # (batch_size, window_size, latent_dim)
        out = self.output_layer(decoder_out) # (batch_size, window_size, input_dim)
        
        return self.sigmoid(out)
    
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
    