"""
stgcn_model.py — ST-GCN architecture and lazy model loader.

The three model classes (SpatialGraphConv, STGCNBlock, STGCN) are ported
verbatim from Pose/Final_Classifer/classify.py to ensure weight compatibility.

Call ``load_stgcn_model()`` to get the ready-to-use tuple:
    (model, adj_tensor, label_encoder, device)
"""

from __future__ import annotations

import os
import pickle
import logging
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# ── Constants (must match training exactly) ──────────────────────────────────
N_JOINTS = 25
C_IN = 10
T_MAX = 150

EDGES = [
    (0, 7), (7, 8), (8, 9), (9, 10),
    (0, 1), (1, 2), (2, 3), (3, 17), (17, 18),
    (0, 4), (4, 5), (5, 6), (6, 19), (19, 20),
    (8, 14), (14, 15), (15, 16), (16, 23), (23, 24),
    (8, 11), (11, 12), (12, 13), (13, 21), (21, 22),
    (11, 14), (1, 4),
]

# ── Paths (relative to this file) ───────────────────────────────────────────
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(_MODELS_DIR, "best_stgcn_v2.pt")
ENCODER_PATH = os.path.join(_MODELS_DIR, "label_encoder.pkl")


# ── Adjacency builder (identical to training) ───────────────────────────────
def build_adj(add_self_loops: bool = True) -> torch.Tensor:
    A = np.zeros((N_JOINTS, N_JOINTS), dtype=np.float32)
    for i, j in EDGES:
        A[i, j] = 1.0
        A[j, i] = 1.0
    if add_self_loops:
        A += np.eye(N_JOINTS, dtype=np.float32)
    D = A.sum(axis=1)
    D_inv_sqrt = np.where(D > 0, 1.0 / np.sqrt(D), 0.0)
    A_norm = D_inv_sqrt[:, None] * A * D_inv_sqrt[None, :]
    return torch.tensor(A_norm, dtype=torch.float32)


# ── Model classes (identical architecture to training) ───────────────────────
class SpatialGraphConv(nn.Module):
    def __init__(self, c_in, c_out, k=3):
        super().__init__()
        self.k, self.c_out = k, c_out
        self.W = nn.Conv2d(c_in, c_out * k, kernel_size=1, bias=False)
        self.M = nn.Parameter(torch.ones(k, N_JOINTS, N_JOINTS) / (k * N_JOINTS))
        self.bn = nn.BatchNorm2d(c_out)

    def forward(self, x, A):
        B, C, T, N = x.shape
        y = self.W(x)
        A_hat = A.unsqueeze(0) * self.M
        out = torch.zeros(B, self.c_out, T, N, device=x.device, dtype=x.dtype)
        for ki in range(self.k):
            xk = y[:, ki * self.c_out:(ki + 1) * self.c_out, :, :]
            xk_r = xk.permute(0, 2, 1, 3).reshape(B * T, self.c_out, N)
            out_k = torch.bmm(xk_r, A_hat[ki].t().unsqueeze(0).expand(B * T, -1, -1))
            out += out_k.reshape(B, T, self.c_out, N).permute(0, 2, 1, 3)
        return F.relu(self.bn(out))


class STGCNBlock(nn.Module):
    def __init__(self, c_in, c_out, temporal_stride=1, dropout=0.3):
        super().__init__()
        self.gcn = SpatialGraphConv(c_in, c_out)
        self.tcn = nn.Sequential(
            nn.Conv2d(c_out, c_out, kernel_size=(9, 1), stride=(temporal_stride, 1), padding=(4, 0)),
            nn.BatchNorm2d(c_out),
        )
        self.dropout = nn.Dropout(dropout)
        if c_in != c_out or temporal_stride != 1:
            self.residual = nn.Sequential(
                nn.Conv2d(c_in, c_out, kernel_size=1, stride=(temporal_stride, 1)),
                nn.BatchNorm2d(c_out),
            )
        else:
            self.residual = nn.Identity()
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x, A):
        res = self.residual(x)
        x = self.gcn(x, A)
        x = self.tcn(x)
        x = self.dropout(x)
        return self.relu(x + res)


class STGCN(nn.Module):
    def __init__(self, c_in, num_classes, dropout=0.3):
        super().__init__()
        self.bn_in = nn.BatchNorm1d(c_in * N_JOINTS)
        self.blocks = nn.ModuleList([
            STGCNBlock(c_in, 64, 1, dropout), STGCNBlock(64, 64, 2, dropout),
            STGCNBlock(64, 128, 1, dropout),  STGCNBlock(128, 128, 2, dropout),
            STGCNBlock(128, 256, 1, dropout), STGCNBlock(256, 256, 1, dropout),
        ])
        self.dropout_head = nn.Dropout(dropout)
        self.fc = nn.Linear(256, num_classes)

    def forward(self, x, A, mask=None):
        B, T, N, C = x.shape
        x = x.view(B * T, N * C)
        x = self.bn_in(x)
        x = x.view(B, T, N, C).permute(0, 3, 1, 2)
        for block in self.blocks:
            x = block(x, A)
        if mask is not None:
            T_prime = x.shape[2]
            m = mask.float().unsqueeze(1)
            m = F.adaptive_avg_pool1d(m, T_prime).squeeze(1)
            m = m.unsqueeze(1).unsqueeze(-1)
            x = (x * m).sum(dim=(2, 3)) / (m.sum(dim=(2, 3)) + 1e-8)
        else:
            x = x.mean(dim=(2, 3))
        x = self.dropout_head(x)
        return self.fc(x)


import warnings

# ── Lazy singleton loader ───────────────────────────────────────────────────
_model: STGCN | None = None
_adj: torch.Tensor | None = None
_label_encoder = None
_device: torch.device | None = None


def load_stgcn_model() -> Tuple:
    """
    Lazy-load and cache the ST-GCN model, adjacency matrix, and label encoder.

    Returns
    -------
    (model, adj, label_encoder, device)
    """
    global _model, _adj, _label_encoder, _device

    if _model is not None:
        return _model, _adj, _label_encoder, _device

    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(
            f"ST-GCN model weights not found at {MODEL_PATH}. "
            "Copy best_stgcn_v2.pt into backend/models/."
        )
    if not os.path.isfile(ENCODER_PATH):
        raise FileNotFoundError(
            f"Label encoder not found at {ENCODER_PATH}. "
            "Copy label_encoder.pkl into backend/models/."
        )

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("ST-GCN using device: %s", _device)

    # Load label encoder
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        # Suppress scikit-learn InconsistentVersionWarning
        try:
            from sklearn.exceptions import InconsistentVersionWarning
            warnings.simplefilter("ignore", category=InconsistentVersionWarning)
        except ImportError:
            pass
            
        with open(ENCODER_PATH, "rb") as f:
            _label_encoder = pickle.load(f)
            
    num_classes = len(_label_encoder.classes_)
    logger.info("Loaded label encoder: %d classes", num_classes)

    # Build adjacency
    _adj = build_adj().to(_device)

    # Build & load model
    _model = STGCN(c_in=C_IN, num_classes=num_classes).to(_device)
    _model.load_state_dict(torch.load(MODEL_PATH, map_location=_device))
    _model.eval()
    logger.info("ST-GCN model loaded from %s", MODEL_PATH)

    return _model, _adj, _label_encoder, _device
