"""
ST-GCN Exercise Classification — core model + preprocessing
=============================================================
Extracted from the original inference script, unchanged in logic.
This module is imported by main.py (the FastAPI app) and loaded once
at server startup so weights aren't reloaded per-request.
"""

import os
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import cv2
import mediapipe as mp
import warnings
warnings.filterwarnings("ignore")

# ── Constants (must match training exactly) ──────────────────────────────────
N_JOINTS = 25
C_IN     = 10
T_MAX    = 150   # same as training Config.T_MAX

EDGES = [
    (0,7),(7,8),(8,9),(9,10),
    (0,1),(1,2),(2,3),(3,17),(17,18),
    (0,4),(4,5),(5,6),(6,19),(19,20),
    (8,14),(14,15),(15,16),(16,23),(23,24),
    (8,11),(11,12),(12,13),(13,21),(21,22),
    (11,14),(1,4),
]


# ── Adjacency (identical to training) ────────────────────────────────────────
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


# ── Joint extraction — SAME mapping used to build the training set ──────────
def extract_frame(lms) -> np.ndarray:
    def lm(i):
        p = lms[i]
        return np.array([p.x, p.y, p.z])

    PL = mp.solutions.pose.PoseLandmark
    joints = np.zeros((25, 3), dtype=np.float32)

    joints[0]  = (lm(PL.LEFT_HIP.value) + lm(PL.RIGHT_HIP.value)) / 2
    joints[1]  = lm(PL.RIGHT_HIP.value)
    joints[2]  = lm(PL.RIGHT_KNEE.value)
    joints[3]  = lm(PL.RIGHT_ANKLE.value)
    joints[4]  = lm(PL.LEFT_HIP.value)
    joints[5]  = lm(PL.LEFT_KNEE.value)
    joints[6]  = lm(PL.LEFT_ANKLE.value)
    joints[7]  = joints[0]                       # spine == hips (confirmed in real data)
    joints[8]  = lm(PL.RIGHT_SHOULDER.value) * 0.5 + lm(PL.LEFT_SHOULDER.value) * 0.5
    joints[9]  = joints[8]                       # neck == joint 8 (confirmed)
    joints[10] = lm(PL.NOSE.value)
    joints[11] = lm(PL.LEFT_SHOULDER.value)
    joints[12] = lm(PL.LEFT_ELBOW.value)
    joints[13] = lm(PL.LEFT_WRIST.value)
    joints[14] = lm(PL.RIGHT_SHOULDER.value)
    joints[15] = lm(PL.RIGHT_ELBOW.value)
    joints[16] = lm(PL.RIGHT_WRIST.value)
    joints[17] = lm(PL.LEFT_FOOT_INDEX.value)
    joints[18] = joints[17]                      # toe == foot (confirmed)
    joints[19] = lm(PL.RIGHT_FOOT_INDEX.value)
    joints[20] = joints[19]                      # toe == foot (confirmed)
    joints[21] = joints[13]                      # fingertip placeholders == wrist (confirmed)
    joints[22] = joints[13]
    joints[23] = joints[13]
    joints[24] = joints[13]
    return joints


def video_to_joints(video_path: str) -> np.ndarray:
    """
    Extract joints at the video's NATIVE frame rate — no subsampling here.
    Subsampling (if needed) happens later, on the computed FEATURE tensor,
    exactly mirroring pad_collate() in the training script.
    """
    mp_pose = mp.solutions.pose
    cap = cv2.VideoCapture(video_path)
    frames = []
    dropped = 0

    with mp_pose.Pose(static_image_mode=False, model_complexity=2,
                       min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = pose.process(rgb)
            if res.pose_landmarks is None:
                dropped += 1
                continue
            joints = extract_frame(res.pose_landmarks.landmark)
            frames.append(joints)

    cap.release()
    print(f"  Extracted {len(frames)} frames ({dropped} dropped, no pose detected)")
    if len(frames) < 10:
        raise RuntimeError("Too few frames with detected pose — check video/lighting/framing.")
    return np.array(frames, dtype=np.float32)   # (T, 25, 3)


# ── Feature extraction — IDENTICAL to preprocessing_gcn.py ──────────────────
def torso_normalise_seq(joints_seq: np.ndarray) -> np.ndarray:
    hips = joints_seq[:, 0, :]
    neck = joints_seq[:, 9, :]
    translated = joints_seq - hips[:, None, :]
    torso_len = np.linalg.norm(neck - hips, axis=1).mean()
    if torso_len < 1e-6:
        torso_len = 1.0
    return translated / torso_len


def bone_length_ratios(joints_seq: np.ndarray) -> np.ndarray:
    hips = joints_seq[:, 0, :]
    neck = joints_seq[:, 9, :]
    torso = np.linalg.norm(neck - hips, axis=1).mean() + 1e-8
    parent = {0: 0}
    for (i, j) in EDGES:
        if j not in parent:
            parent[j] = i
        if i not in parent:
            parent[i] = j
    ratios = np.zeros(N_JOINTS, dtype=np.float32)
    for jdx in range(N_JOINTS):
        p = parent.get(jdx, jdx)
        bone_len = np.linalg.norm(joints_seq[:, jdx, :] - joints_seq[:, p, :], axis=1).mean()
        ratios[jdx] = bone_len / torso
    return ratios


def extract_node_features(joints_seq: np.ndarray) -> np.ndarray:
    """joints_seq: (T,25,3) raw, FULL native-framerate sequence -> (T,25,10)"""
    T = joints_seq.shape[0]
    pos = torso_normalise_seq(joints_seq)

    vel = np.zeros_like(pos)
    vel[1:] = pos[1:] - pos[:-1]
    vel[0] = vel[1]

    acc = np.zeros_like(vel)
    acc[1:] = vel[1:] - vel[:-1]
    acc[0] = acc[1]
    if T > 2:
        acc[1] = acc[2]

    br = bone_length_ratios(joints_seq)
    br_expanded = np.tile(br[None, :, None], (T, 1, 1))

    feat = np.concatenate([pos, vel, acc, br_expanded], axis=-1)
    return feat.astype(np.float32)


def subsample_features(feat: np.ndarray, t_max: int = T_MAX) -> np.ndarray:
    """Mirrors pad_collate's subsample(): uniform stride AFTER features
    are already computed, never before."""
    T = feat.shape[0]
    if T <= t_max:
        return feat
    idx = np.linspace(0, T - 1, t_max).astype(int)
    return feat[idx]


# ── Model (identical architecture) ───────────────────────────────────────────
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


# ── Loadable bundle used by the API layer ────────────────────────────────────
class STGCNPredictor:
    """
    Loads model + label encoder + adjacency ONCE and exposes a single
    predict(video_path) method. Instantiate this once at FastAPI startup.
    """

    def __init__(self, model_path: str, encoder_path: str, device: str = None):
        self.device = torch.device(
            device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        )

        with open(encoder_path, "rb") as f:
            self.label_encoder = pickle.load(f)
        self.num_classes = len(self.label_encoder.classes_)

        self.adj = build_adj().to(self.device)

        self.model = STGCN(c_in=C_IN, num_classes=self.num_classes).to(self.device)
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

        print(f"[STGCNPredictor] Loaded model with {self.num_classes} classes "
              f"on device={self.device}")

    def predict(self, video_path: str, top_k: int = 5) -> dict:
        joints_seq = video_to_joints(video_path)              # (T_raw, 25, 3) native fps
        feat       = extract_node_features(joints_seq)        # (T_raw, 25, 10) full-res features
        feat       = subsample_features(feat, T_MAX)          # (<=150, 25, 10) post-hoc subsample

        x    = torch.tensor(feat).unsqueeze(0).to(self.device)      # (1, T, 25, 10)
        mask = torch.ones(1, x.shape[1], dtype=torch.bool).to(self.device)

        with torch.no_grad():
            logits = self.model(x, self.adj, mask)
            probs  = F.softmax(logits, dim=1)
            k = min(top_k, probs.shape[1])
            topkp, topki = torch.topk(probs, k, dim=1)

        topkp = topkp.cpu().numpy()[0]
        topki = topki.cpu().numpy()[0]
        topk_classes = [self.label_encoder.classes_[i] for i in topki]

        return {
            "predicted_class": topk_classes[0],
            "confidence": float(topkp[0]),
            "top_k_classes": topk_classes,
            "top_k_probs": [float(p) for p in topkp],
            "num_frames_used": int(feat.shape[0]),
            "num_frames_raw": int(joints_seq.shape[0]),
        }
