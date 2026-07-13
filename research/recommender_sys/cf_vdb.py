"""
cf_vdb.py — User-Profile Vector Database for Collaborative Filtering
====================================================================

Provides two public utilities:

1.  build_profile_vector(user: UserProfile) → np.ndarray
        Encodes a UserProfile into a fixed-length float32 vector using
        one-hot encoding for categorical fields and ordinal encoding for
        ordered fields.  The vector dimension is constant regardless of
        the user's values, making it suitable for cosine similarity search.

2.  UserProfileIndex
        A lightweight vector database backed by pure numpy (cosine similarity
        over a stored matrix).  Its API mirrors FAISS IndexFlatIP so the
        implementation can be swapped for faiss-cpu trivially once a
        Python 3.13 wheel is available:

            # Drop-in FAISS swap (future):
            # import faiss
            # index = faiss.IndexFlatIP(dim)
            # index.add(vectors)
            # D, I = index.search(query, top_k)

        For now numpy gives identical results with no native compilation.

EMBEDDING SCHEMA
----------------
The profile vector has the following layout (total dim = 30):

  [0:4]   goal_type         (one-hot over 4 goals)
  [4:7]   fitness_level     (one-hot over 3 levels)
  [7:8]   activity_level    (ordinal 0-4, normalised to 0-1)
  [8:20]  equipment flags   (multi-hot over 12 equipment types)
  [20:25] diet_type         (one-hot over 5 diet labels)
  [25:28] protein_focus     (one-hot over 3 levels)
  [28:30] cardio_strength   (one-hot over 3 biases → 2 dims after drop)

ACADEMIC CONTEXT
----------------
Profile-based (demographic) CF is documented in:
  Pazzani, M.J. (1999). A framework for collaborative, content-based and
  demographic filtering. Artificial Intelligence Review, 13(5-6), 393-408.

It is the standard approach for cold-start settings where interaction
data is sparse or absent — exactly the Revfit scenario.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

# ── import guard — works even when run outside the package ──────────────────
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from user_profile import UserProfile


# ================================================================== #
#  Vocabulary constants (must stay in sync with constants.py)         #
# ================================================================== #

_GOAL_TYPES    = ["fat_loss", "muscle_gain", "maintenance", "endurance"]       # dim 4
_FITNESS_LEVELS = ["beginner", "intermediate", "expert"]                        # dim 3
_ACTIVITY_ORDER = {                                                             # dim 1 (ordinal)
    "sedentary": 0, "light": 1, "moderate": 2, "active": 3, "very_active": 4,
}
_EQUIPMENT     = [                                                              # dim 12 (multi-hot)
    "Barbell", "Kettlebells", "Dumbbell", "Other", "Cable",
    "Machine", "Body Only", "Medicine Ball", "Exercise Ball",
    "Foam Roll", "E-Z Curl Bar", "Bands",
]
_DIET_TYPES    = ["omnivore", "vegetarian", "vegan", "ketogenic", "paleo"]     # dim 5
_PROTEIN_FOCUS = ["low", "medium", "high"]                                     # dim 3
_CARDIO_BIAS   = ["cardio", "balanced", "strength"]                            # dim 2 (drop last)

# Total vector dimension
PROFILE_DIM = 4 + 3 + 1 + 12 + 5 + 3 + 2   # = 30


# ================================================================== #
#  Profile → vector                                                   #
# ================================================================== #

def build_profile_vector(user: UserProfile) -> np.ndarray:
    """
    Encode a UserProfile into a float32 vector of length PROFILE_DIM (30).

    Categorical fields are one-hot encoded; equipment is multi-hot
    (multiple pieces of equipment can be active simultaneously); the
    activity level is ordinal-scaled to [0, 1].

    Unknown values default to a zero slice (safe fallback).

    Returns
    -------
    np.ndarray, shape (PROFILE_DIM,), dtype float32
    """
    vec = np.zeros(PROFILE_DIM, dtype=np.float32)
    offset = 0

    # ── goal_type (4 dims) ───────────────────────────────────────────
    if user.goal_type in _GOAL_TYPES:
        vec[offset + _GOAL_TYPES.index(user.goal_type)] = 1.0
    offset += 4

    # ── fitness_level (3 dims) ───────────────────────────────────────
    fl = user.fitness_level.lower()
    if fl in _FITNESS_LEVELS:
        vec[offset + _FITNESS_LEVELS.index(fl)] = 1.0
    offset += 3

    # ── activity_level (1 dim, ordinal 0-1) ─────────────────────────
    act_idx = _ACTIVITY_ORDER.get(user.activity_level.lower(), 2)
    vec[offset] = act_idx / (len(_ACTIVITY_ORDER) - 1)   # normalise to [0, 1]
    offset += 1

    # ── equipment (12 dims, multi-hot) ──────────────────────────────
    for eq in user.available_equipment:
        if eq in _EQUIPMENT:
            vec[offset + _EQUIPMENT.index(eq)] = 1.0
    offset += 12

    # ── diet_type (5 dims) ──────────────────────────────────────────
    dt = user.diet_type.lower()
    if dt in _DIET_TYPES:
        vec[offset + _DIET_TYPES.index(dt)] = 1.0
    offset += 5

    # ── protein_focus (3 dims) ───────────────────────────────────────
    pf = user.protein_focus.lower()
    if pf in _PROTEIN_FOCUS:
        vec[offset + _PROTEIN_FOCUS.index(pf)] = 1.0
    offset += 3

    # ── cardio_strength_bias (2 dims — drop last category) ──────────
    cb = user.cardio_strength_bias.lower()
    if cb in _CARDIO_BIAS[:-1]:   # "balanced" and "strength" only; "strength" is [1]
        vec[offset + _CARDIO_BIAS[:-1].index(cb)] = 1.0
    elif cb == _CARDIO_BIAS[-1]:   # "strength" maps to [1]
        vec[offset + 1] = 1.0
    # offset += 2  (last segment, no need to advance)

    return vec


# ================================================================== #
#  UserProfileIndex — numpy cosine similarity VDB                     #
# ================================================================== #

class UserProfileIndex:
    """
    Lightweight vector database for user profile similarity search.

    Stores L2-normalised profile vectors in a numpy matrix and answers
    nearest-neighbour queries using inner product (= cosine similarity
    after normalisation).

    This is functionally equivalent to FAISS IndexFlatIP and can be
    swapped out once faiss-cpu ships a Python 3.13 wheel.

    Example
    -------
    >>> index = UserProfileIndex()
    >>> index.fit(user_profiles, user_ids)
    >>> neighbours = index.query(target_user, top_k=3)
    >>> # [("Ahmed", 0.92), ("Layla", 0.87), ("Khalid", 0.81)]
    """

    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None   # shape (n_users, PROFILE_DIM)
        self._ids: List[str] = []

    # ── Building the index ────────────────────────────────────────────

    def fit(self, users: List[UserProfile], user_ids: List[str]) -> None:
        """
        Embed and store a population of user profiles.

        Parameters
        ----------
        users    : list of UserProfile objects to index
        user_ids : parallel list of string identifiers (e.g. persona names)
        """
        if not users:
            self._matrix = None
            self._ids = []
            return

        vecs = np.stack([build_profile_vector(u) for u in users])  # (n, 30)
        self._matrix = _l2_normalise_rows(vecs)
        self._ids = list(user_ids)

    # ── Querying ─────────────────────────────────────────────────────

    def query(
        self,
        user: UserProfile,
        top_k: int = 5,
        exclude_ids: List[str] | None = None,
    ) -> List[Tuple[str, float]]:
        """
        Return the `top_k` most similar profiles to `user`.

        Parameters
        ----------
        user       : target UserProfile to find neighbours for
        top_k      : maximum number of results
        exclude_ids: list of user_ids to skip (e.g. the target persona itself)

        Returns
        -------
        List of (user_id, cosine_similarity) tuples, descending by similarity.
        Similarity is in [-1, 1]; higher = more similar.
        """
        if self._matrix is None or len(self._ids) == 0:
            return []

        query_vec = build_profile_vector(user).reshape(1, -1)         # (1, 30)
        query_norm = _l2_normalise_rows(query_vec)                     # (1, 30)

        # Inner product with all stored vectors → cosine similarities
        scores = (self._matrix @ query_norm.T).flatten()               # (n,)

        # Build ranked list, excluding requested ids
        exclude = set(exclude_ids or [])
        ranked: List[Tuple[str, float]] = []
        for idx in np.argsort(scores)[::-1]:
            uid = self._ids[idx]
            if uid in exclude:
                continue
            ranked.append((uid, float(scores[idx])))
            if len(ranked) >= top_k:
                break

        return ranked

    # ── Diagnostics ───────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._ids)

    def __repr__(self) -> str:
        return f"<UserProfileIndex n={len(self._ids)} dim={PROFILE_DIM}>"


# ================================================================== #
#  Internal helpers                                                   #
# ================================================================== #

def _l2_normalise_rows(matrix: np.ndarray) -> np.ndarray:
    """
    L2-normalise each row of a 2-D matrix in-place (returns view).
    Rows with zero norm are left as zeros (safe for empty profiles).
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)   # avoid divide-by-zero
    return matrix / norms
