"""
Shared retrieval score handling.

Both ChromaDB and Qdrant return raw cosine-like similarity scores. The
validation pipeline expects a calibrated ``score`` that can satisfy the
evidence sufficiency floor while preserving the raw value as
``relevance_score``.
"""

from __future__ import annotations

# Discard chunks below this raw cosine similarity.
MIN_COSINE_THRESHOLD: float = 0.40

# Must stay aligned with validation.MIN_AVG_SCORE_FOR_SUFFICIENCY.
SCORE_FLOOR: float = 0.65


def distance_to_raw_score(distance: float) -> float:
    """
    Convert a cosine distance to raw cosine similarity in [0, 1].

    ChromaDB cosine distance = 1 - cosine_similarity for normalised vectors.
    """
    return round(max(0.0, min(1.0, 1.0 - distance)), 6)


def raw_similarity_score(score: float) -> float:
    """Clamp a vector-store similarity score to [0, 1]."""
    return round(max(0.0, min(1.0, score)), 6)


def calibrate_score(raw_score: float) -> float:
    """
    Linear calibration from [MIN_COSINE_THRESHOLD, 1.0] to [SCORE_FLOOR, 1.0].
    """
    span = 1.0 - MIN_COSINE_THRESHOLD
    if span <= 0:
        return SCORE_FLOOR
    calibrated = SCORE_FLOOR + (
        (raw_score - MIN_COSINE_THRESHOLD) / span * (1.0 - SCORE_FLOOR)
    )
    return round(min(1.0, max(SCORE_FLOOR, calibrated)), 4)
