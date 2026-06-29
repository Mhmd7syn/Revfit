"""
exercise_classifier.py — Phase 1 Automated Exercise Classifier (ST-GCN).

Uses ST-GCN model running on MediaPipe extracted features to classify
a short RGB video clip into one of the exercise taxonomy classes.
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
import cv2
import mediapipe as mp
from enum import IntEnum
import warnings
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(_MODELS_DIR, "best_stgcn_v2.pt")
ENCODER_PATH = os.path.join(_MODELS_DIR, "label_encoder.pkl")
MP_TASK_PATH = os.path.join(_MODELS_DIR, "pose_landmarker_heavy.task")

# ── Globals for caching ──────────────────────────────────────────
_model: torch.nn.Module | None = None
_label_encoder = None
_device: torch.device | None = None
_adj: torch.Tensor | None = None

EXERCISE_CLASSES: list[str] = []

if os.path.exists(ENCODER_PATH):
    with open(ENCODER_PATH, "rb") as f:
        _label_encoder = pickle.load(f)
    EXERCISE_CLASSES = [str(c) for c in _label_encoder.classes_]

NUM_CLASSES = len(EXERCISE_CLASSES)

class PoseLandmark(IntEnum):
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32

N_JOINTS = 25
C_IN = 10
T_MAX = 150

EDGES = [
    (0,7),(7,8),(8,9),(9,10),
    (0,1),(1,2),(2,3),(3,17),(17,18),
    (0,4),(4,5),(5,6),(6,19),(19,20),
    (8,14),(14,15),(15,16),(16,23),(23,24),
    (8,11),(11,12),(12,13),(13,21),(21,22),
    (11,14),(1,4),
]

def _get_device() -> torch.device:
    global _device
    if _device is None:
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Exercise classifier using device: %s", _device)
    return _device

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

def extract_frame(lms) -> np.ndarray:
    def lm(i):
        p = lms[i]
        return np.array([p.x, p.y, p.z])
    PL = PoseLandmark
    joints = np.zeros((25, 3), dtype=np.float32)
    joints[0]  = (lm(PL.LEFT_HIP.value) + lm(PL.RIGHT_HIP.value)) / 2
    joints[1]  = lm(PL.RIGHT_HIP.value)
    joints[2]  = lm(PL.RIGHT_KNEE.value)
    joints[3]  = lm(PL.RIGHT_ANKLE.value)
    joints[4]  = lm(PL.LEFT_HIP.value)
    joints[5]  = lm(PL.LEFT_KNEE.value)
    joints[6]  = lm(PL.LEFT_ANKLE.value)
    joints[7]  = joints[0]
    joints[8]  = lm(PL.RIGHT_SHOULDER.value) * 0.5 + lm(PL.LEFT_SHOULDER.value) * 0.5
    joints[9]  = joints[8]
    joints[10] = lm(PL.NOSE.value)
    joints[11] = lm(PL.LEFT_SHOULDER.value)
    joints[12] = lm(PL.LEFT_ELBOW.value)
    joints[13] = lm(PL.LEFT_WRIST.value)
    joints[14] = lm(PL.RIGHT_SHOULDER.value)
    joints[15] = lm(PL.RIGHT_ELBOW.value)
    joints[16] = lm(PL.RIGHT_WRIST.value)
    joints[17] = lm(PL.LEFT_FOOT_INDEX.value)
    joints[18] = joints[17]
    joints[19] = lm(PL.RIGHT_FOOT_INDEX.value)
    joints[20] = joints[19]
    joints[21] = joints[13]
    joints[22] = joints[13]
    joints[23] = joints[13]
    joints[24] = joints[13]
    return joints

def video_to_joints(video_path: str) -> np.ndarray:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    
    if not os.path.exists(MP_TASK_PATH):
        raise FileNotFoundError(f"MediaPipe task model not found at {MP_TASK_PATH}")

    base_options = python.BaseOptions(model_asset_path=MP_TASK_PATH)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Could not open video file.")
        
    frames = []
    last_ts = -1
    dropped = 0
    
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
            
            if timestamp_ms <= last_ts:
                timestamp_ms = last_ts + 1
            last_ts = timestamp_ms

            res = landmarker.detect_for_video(mp_image, timestamp_ms)
            
            if not res.pose_landmarks:
                dropped += 1
                continue
            
            joints = extract_frame(res.pose_landmarks[0])
            frames.append(joints)

    cap.release()
    if len(frames) < 10:
        raise RuntimeError("Too few frames with detected pose.")
    return np.array(frames, dtype=np.float32)

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
    T = feat.shape[0]
    if T <= t_max:
        return feat
    idx = np.linspace(0, T - 1, t_max).astype(int)
    return feat[idx]

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

def _load_model() -> torch.nn.Module:
    global _model, _adj
    if _model is not None:
        return _model

    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(f"Model checkpoint not found at {MODEL_PATH}")

    device = _get_device()
    logger.info("Loading ST-GCN checkpoint from %s ...", MODEL_PATH)
    
    model = STGCN(c_in=C_IN, num_classes=NUM_CLASSES).to(device)
    model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
    model.eval()
    
    _model = model
    _adj = build_adj().to(device)
    return _model

def classify_exercise(video_path: str) -> Tuple[str, float]:
    if not os.path.isfile(MODEL_PATH):
        logger.warning("Model checkpoints not found! Returning mock classification ('squat', 0.95) for GUI testing.")
        return "squat", 0.95

    try:
        model = _load_model()
        device = _get_device()

        joints_seq = video_to_joints(video_path)
        feat = extract_node_features(joints_seq)
        feat = subsample_features(feat, T_MAX)

        x = torch.tensor(feat).unsqueeze(0).to(device)
        mask = torch.ones(1, x.shape[1], dtype=torch.bool).to(device)

        with torch.no_grad():
            logits = model(x, _adj, mask)
            probs = F.softmax(logits, dim=1)
            top1p, top1i = torch.max(probs, dim=1)

        predicted_class = EXERCISE_CLASSES[top1i.item()]
        confidence = round(top1p.item(), 4)
        
        logger.info(
            "Classification result: %s (%.2f%% confidence)",
            predicted_class,
            confidence * 100,
        )
        return predicted_class, confidence
    except Exception as e:
        logger.error(f"Error classifying exercise: {e}"); 
        raise RuntimeError(f"Error classifying exercise: {e}")
