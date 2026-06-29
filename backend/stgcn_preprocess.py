"""
stgcn_preprocess.py — Preprocessing pipeline for the ST-GCN exercise classifier.

Ported verbatim from Pose/Final_Classifer/classify.py to ensure feature-level
compatibility with the trained model.  The critical invariant is:

    1.  Extract 25-joint frames at the video's NATIVE frame rate.
    2.  Compute features (pos/vel/acc/bone_ratio) on the FULL sequence.
    3.  Subsample to T_MAX=150 AFTER features are computed.

NOTE: Uses raw landmark indices instead of mp.solutions.pose.PoseLandmark
because the installed mediapipe version (0.10.35) only ships the Task API.
"""

from __future__ import annotations

from typing import List

import numpy as np
import torch
import torch.nn.functional as F

from stgcn_model import EDGES, N_JOINTS, T_MAX


# ── MediaPipe landmark indices (stable across all versions) ────────────────
# These match the values of mp.solutions.pose.PoseLandmark exactly.
_NOSE = 0
_LEFT_SHOULDER = 11
_RIGHT_SHOULDER = 12
_LEFT_ELBOW = 13
_RIGHT_ELBOW = 14
_LEFT_WRIST = 15
_RIGHT_WRIST = 16
_LEFT_HIP = 23
_RIGHT_HIP = 24
_LEFT_KNEE = 25
_RIGHT_KNEE = 26
_LEFT_ANKLE = 27
_RIGHT_ANKLE = 28
_LEFT_FOOT_INDEX = 31
_RIGHT_FOOT_INDEX = 32


# ── Joint extraction (SAME mapping as training) ────────────────────────────
def extract_frame(lms) -> np.ndarray:
    """Map 33 MediaPipe landmarks to the 25-joint layout used by training.

    Parameters
    ----------
    lms : list-like
        Either MediaPipe NormalizedLandmark objects (with .x/.y/.z attributes)
        or plain (x, y, z) sequences / np.arrays.
    """
    def lm(i):
        p = lms[i]
        # Handle both attribute-based (MediaPipe) and index-based access
        if hasattr(p, 'x'):
            return np.array([p.x, p.y, p.z])
        return np.asarray(p[:3], dtype=np.float32)

    joints = np.zeros((25, 3), dtype=np.float32)

    joints[0]  = (lm(_LEFT_HIP) + lm(_RIGHT_HIP)) / 2
    joints[1]  = lm(_RIGHT_HIP)
    joints[2]  = lm(_RIGHT_KNEE)
    joints[3]  = lm(_RIGHT_ANKLE)
    joints[4]  = lm(_LEFT_HIP)
    joints[5]  = lm(_LEFT_KNEE)
    joints[6]  = lm(_LEFT_ANKLE)
    joints[7]  = joints[0]                                  # spine == hips
    joints[8]  = lm(_RIGHT_SHOULDER) * 0.5 + lm(_LEFT_SHOULDER) * 0.5
    joints[9]  = joints[8]                                  # neck == joint 8
    joints[10] = lm(_NOSE)
    joints[11] = lm(_LEFT_SHOULDER)
    joints[12] = lm(_LEFT_ELBOW)
    joints[13] = lm(_LEFT_WRIST)
    joints[14] = lm(_RIGHT_SHOULDER)
    joints[15] = lm(_RIGHT_ELBOW)
    joints[16] = lm(_RIGHT_WRIST)
    joints[17] = lm(_LEFT_FOOT_INDEX)
    joints[18] = joints[17]                                 # toe == foot
    joints[19] = lm(_RIGHT_FOOT_INDEX)
    joints[20] = joints[19]                                 # toe == foot
    joints[21] = joints[13]                                 # fingertip == wrist
    joints[22] = joints[13]
    joints[23] = joints[13]
    joints[24] = joints[13]
    return joints


# ── Feature extraction (IDENTICAL to preprocessing_gcn.py) ─────────────────
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
    """Uniform stride subsampling AFTER features are computed (never before)."""
    T = feat.shape[0]
    if T <= t_max:
        return feat
    idx = np.linspace(0, T - 1, t_max).astype(int)
    return feat[idx]


# ── End-to-end prediction from a joint buffer ──────────────────────────────
def predict_from_buffer(
    joints_list: List[np.ndarray],
    model,
    adj: torch.Tensor,
    label_encoder,
    device: torch.device,
) -> dict:
    """
    Run ST-GCN inference on a list of 25×3 joint arrays.

    Parameters
    ----------
    joints_list : list of np.ndarray, each (25, 3)
        The accumulated joints from ``extract_frame()`` calls.

    Returns
    -------
    dict with keys:
        predicted_class, confidence, top5_classes, top5_probs
    """
    if len(joints_list) < 10:
        return {
            "predicted_class": "unknown",
            "confidence": 0.0,
            "top5_classes": [],
            "top5_probs": [],
        }

    joints_seq = np.array(joints_list, dtype=np.float32)  # (T, 25, 3)

    # Feature extraction on FULL sequence
    feat = extract_node_features(joints_seq)               # (T, 25, 10)

    # Subsample AFTER feature computation
    feat = subsample_features(feat, T_MAX)                 # (<=150, 25, 10)

    x = torch.tensor(feat).unsqueeze(0).to(device)         # (1, T, 25, 10)
    mask = torch.ones(1, x.shape[1], dtype=torch.bool).to(device)

    model.eval()
    with torch.no_grad():
        logits = model(x, adj, mask)
        probs = F.softmax(logits, dim=1)
        top5p, top5i = torch.topk(probs, min(5, probs.shape[1]), dim=1)

    top5p = top5p.cpu().numpy()[0]
    top5i = top5i.cpu().numpy()[0]
    top5_classes = [label_encoder.classes_[i] for i in top5i]

    return {
        "predicted_class": top5_classes[0],
        "confidence": float(top5p[0]),
        "top5_classes": top5_classes,
        "top5_probs": top5p.tolist(),
    }
