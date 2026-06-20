"""
exercise_classifier.py — Phase 1 Automated Exercise Classifier.

Uses a 50/50 weighted hybrid ensemble of VideoMAE (ViT) and X3D-M (3D CNN)
to classify a short RGB video clip into one of the exercise taxonomy classes.

This module is entirely independent of the Pose Estimator / Form Evaluation
pipeline (Phase 2+).  It does NOT import from Pose/Code/*.

Public API
----------
classify_exercise(video_path) → (predicted_class, confidence)
    Run the full ensemble inference pipeline on a video file.

EXERCISE_CLASSES : list[str]
    Canonical ordered list of class labels matching model output indices.
"""

from __future__ import annotations

import os
import logging
from typing import Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 20-class taxonomy (sorted — must match the label order used during training)
# ---------------------------------------------------------------------------
EXERCISE_CLASSES: list[str] = [
    "barbell biceps curl",
    "bench press",
    "chest fly machine",
    "deadlift",
    "hammer curl",
    "hip thrust",
    "lat pulldown",
    "lateral raise",
    "leg extension",
    "leg raises",
    "lunge",
    "plank",
    "pull up",
    "push-up",
    "romanian deadlift",
    "russian twist",
    "shoulder press",
    "squat",
    "t bar row",
    "tricep dips",
]

NUM_CLASSES = len(EXERCISE_CLASSES)

# ---------------------------------------------------------------------------
# Model checkpoint paths (relative to repository root)
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_MODELS_DIR = os.path.join(_REPO_ROOT, "Pose", "Models")

VIDEOMAE_CHECKPOINT = os.path.join(_MODELS_DIR, "videomae_classifier.pt")
X3D_M_CHECKPOINT = os.path.join(_MODELS_DIR, "x3d_m_classifier.pt")

# Ensemble weight (0.5 each = equal weighting)
VIDEOMAE_WEIGHT = 0.5
X3D_WEIGHT = 0.5

# ---------------------------------------------------------------------------
# Lazy-loaded model singletons
# ---------------------------------------------------------------------------
_videomae_model: torch.nn.Module | None = None
_x3d_model: torch.nn.Module | None = None
_device: torch.device | None = None


def _get_device() -> torch.device:
    """Select CUDA if available, else CPU."""
    global _device
    if _device is None:
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Exercise classifier using device: %s", _device)
    return _device


def _load_videomae() -> torch.nn.Module:
    """Lazy-load the VideoMAE classifier checkpoint."""
    global _videomae_model
    if _videomae_model is not None:
        return _videomae_model

    if not os.path.isfile(VIDEOMAE_CHECKPOINT):
        raise FileNotFoundError(
            f"VideoMAE checkpoint not found at {VIDEOMAE_CHECKPOINT}. "
            "Please place the trained weights there."
        )

    device = _get_device()
    logger.info("Loading VideoMAE checkpoint from %s …", VIDEOMAE_CHECKPOINT)
    _videomae_model = torch.load(
        VIDEOMAE_CHECKPOINT, map_location=device, weights_only=False
    )
    if isinstance(_videomae_model, dict):
        # If saved as state_dict, the caller must wrap in the architecture.
        # For now, assume full-model save.
        raise RuntimeError(
            "VideoMAE checkpoint appears to be a state_dict, not a full model. "
            "Wrap it in the model architecture before saving, or update "
            "_load_videomae() to construct the model first."
        )
    _videomae_model.to(device)
    _videomae_model.eval()
    return _videomae_model


def _load_x3d() -> torch.nn.Module:
    """Lazy-load the X3D-M classifier checkpoint."""
    global _x3d_model
    if _x3d_model is not None:
        return _x3d_model

    if not os.path.isfile(X3D_M_CHECKPOINT):
        raise FileNotFoundError(
            f"X3D-M checkpoint not found at {X3D_M_CHECKPOINT}. "
            "Please place the trained weights there."
        )

    device = _get_device()
    logger.info("Loading X3D-M checkpoint from %s …", X3D_M_CHECKPOINT)
    _x3d_model = torch.load(
        X3D_M_CHECKPOINT, map_location=device, weights_only=False
    )
    if isinstance(_x3d_model, dict):
        raise RuntimeError(
            "X3D-M checkpoint appears to be a state_dict, not a full model. "
            "Wrap it in the model architecture before saving, or update "
            "_load_x3d() to construct the model first."
        )
    _x3d_model.to(device)
    _x3d_model.eval()
    return _x3d_model


# ---------------------------------------------------------------------------
# Frame sampling
# ---------------------------------------------------------------------------

def _sample_frames(video_path: str, num_frames: int = 16) -> np.ndarray:
    """
    Uniformly sample *num_frames* RGB frames from a video file.

    Returns
    -------
    np.ndarray of shape (T, H, W, 3), dtype uint8
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        raise RuntimeError(f"Video has no frames: {video_path}")

    # Uniform temporal indices
    indices = np.linspace(0, total - 1, num=num_frames, dtype=int)

    frames: list[np.ndarray] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if not ret:
            # Duplicate last successful frame on read failure
            if frames:
                frames.append(frames[-1].copy())
            continue
        # BGR → RGB
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    cap.release()

    if len(frames) < num_frames:
        # Pad with last frame if video was too short
        while len(frames) < num_frames:
            frames.append(frames[-1].copy() if frames else np.zeros((224, 224, 3), dtype=np.uint8))

    return np.stack(frames[:num_frames])  # (T, H, W, 3)


# ---------------------------------------------------------------------------
# Preprocessing helpers
# ---------------------------------------------------------------------------

# ImageNet normalisation stats
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _preprocess_for_videomae(
    frames: np.ndarray,
    size: int = 224,
) -> torch.Tensor:
    """
    Preprocess sampled frames for VideoMAE.

    Parameters
    ----------
    frames : (T, H, W, 3) uint8 array

    Returns
    -------
    torch.Tensor of shape (1, 3, T, H, W)  — batch of 1
    """
    processed = []
    for f in frames:
        f_resized = cv2.resize(f, (size, size)).astype(np.float32) / 255.0
        f_norm = (f_resized - _MEAN) / _STD
        processed.append(f_norm)

    arr = np.stack(processed)            # (T, H, W, 3)
    arr = arr.transpose(3, 0, 1, 2)     # (3, T, H, W)
    return torch.from_numpy(arr).unsqueeze(0).float()  # (1, 3, T, H, W)


def _preprocess_for_x3d(
    frames: np.ndarray,
    size: int = 182,
) -> torch.Tensor:
    """
    Preprocess sampled frames for X3D-M (requires 182×182 input).

    Parameters
    ----------
    frames : (T, H, W, 3) uint8 array

    Returns
    -------
    torch.Tensor of shape (1, 3, T, H, W)  — batch of 1
    """
    processed = []
    for f in frames:
        f_resized = cv2.resize(f, (size, size)).astype(np.float32) / 255.0
        f_norm = (f_resized - _MEAN) / _STD
        processed.append(f_norm)

    arr = np.stack(processed)            # (T, H, W, 3)
    arr = arr.transpose(3, 0, 1, 2)     # (3, T, H, W)
    return torch.from_numpy(arr).unsqueeze(0).float()  # (1, 3, T, H, W)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_exercise(video_path: str) -> Tuple[str, float]:
    """
    Classify the exercise shown in *video_path* using the VideoMAE + X3D-M
    ensemble.

    Returns
    -------
    (predicted_class, confidence)
        predicted_class : str — one of ``EXERCISE_CLASSES``
        confidence      : float — ensemble probability in [0, 1]

    Raises
    ------
    FileNotFoundError
        If model checkpoints are missing.
    RuntimeError
        If the video cannot be read or has no frames.
    """
    device = _get_device()

    # 1. Sample 16 frames uniformly
    frames = _sample_frames(video_path, num_frames=16)

    # 2. Preprocess
    videomae_input = _preprocess_for_videomae(frames).to(device)
    x3d_input = _preprocess_for_x3d(frames).to(device)

    # 3. Load models (lazy, cached)
    videomae = _load_videomae()
    x3d = _load_x3d()

    # 4. Forward pass
    with torch.no_grad():
        videomae_logits = videomae(videomae_input)  # (1, NUM_CLASSES)
        x3d_logits = x3d(x3d_input)                # (1, NUM_CLASSES)

    # 5. Softmax → weighted average
    videomae_probs = F.softmax(videomae_logits, dim=-1)
    x3d_probs = F.softmax(x3d_logits, dim=-1)

    ensemble_probs = (
        VIDEOMAE_WEIGHT * videomae_probs + X3D_WEIGHT * x3d_probs
    )  # (1, NUM_CLASSES)

    # 6. Argmax
    confidence, pred_idx = ensemble_probs.max(dim=-1)
    predicted_class = EXERCISE_CLASSES[pred_idx.item()]
    confidence_value = round(confidence.item(), 4)

    logger.info(
        "Classification result: %s (%.2f%% confidence)",
        predicted_class,
        confidence_value * 100,
    )

    return predicted_class, confidence_value
