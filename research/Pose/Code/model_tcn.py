import torch
import torch.nn as nn

class TemporalConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, dilation, dropout=0.25):
        super().__init__()
        padding = (kernel_size - 1) * dilation // 2
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, dilation=dilation, padding=padding)
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        return self.dropout(self.relu(self.bn(self.conv(x))))

class ResidualBlock1D(nn.Module):
    def __init__(self, channels, kernel_size, dilation, dropout=0.25):
        super().__init__()
        self.conv1 = TemporalConv(channels, channels, kernel_size, dilation, dropout)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, dilation=dilation, padding=(kernel_size - 1) * dilation // 2)
        self.bn = nn.BatchNorm1d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        res = self.conv1(x)
        res = self.dropout(self.bn(self.conv2(res)))
        return self.relu(x + res)

class Temporal3DRefinementNet(nn.Module):
    """
    A 1D Dilated Convolutional Network that maps 81 frames of 33x3 pose to 81 frames of 25x3 pose.
    Receptive field: 1 + 2 * (3^0 + 3^1 + 3^2 + 3^3) = 81 frames with kernel size 3 and dilations [1, 3, 9, 27].
    Outputs the full aligned window (B, T, 25, 3) for temporal consistency losses.
    """
    def __init__(self, num_joints_in=33, in_features=3, num_joints_out=25, out_features=3, channels=256, dropout=0.25):
        super().__init__()
        self.in_dim = num_joints_in * in_features
        self.out_dim = num_joints_out * out_features
        
        self.expand = TemporalConv(self.in_dim, channels, kernel_size=1, dilation=1, dropout=0.0)
        
        dilations = [1, 3, 9, 27]
        self.res_blocks = nn.ModuleList([
            ResidualBlock1D(channels, kernel_size=3, dilation=d, dropout=dropout) for d in dilations
        ])
        
        self.shrink = nn.Conv1d(channels, self.out_dim, kernel_size=1)
        
    def forward(self, x):
        # x shape: (B, T, V_in, C_in)
        B, T, V_in, C_in = x.shape
        x = x.view(B, T, -1).permute(0, 2, 1) # Shape: (B, V_in*C_in, T)
        
        x = self.expand(x)
        for block in self.res_blocks:
            x = block(x)
            
        x = self.shrink(x) # Shape: (B, V_out*C_out, T)
        
        x = x.view(B, self.out_dim // 3, 3, T).permute(0, 3, 1, 2) # (B, T, 25, 3)
        return x
