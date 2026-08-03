"""
Shared retrieval score handling.

Qdrant returns raw cosine-like similarity scores. The validation pipeline
expects a calibrated ``score`` that can satisfy the evidence sufficiency
floor while preserving the raw value as ``relevance_score``.
"""

from __future__ import annotations

# Calibration anchor: raw cosine similarity at/below this value maps to the
# low end of the calibrated range (see calibrate_score). No longer used to
# discard chunks at retrieval time — validation.py is the sole authority for
# relevance filtering; retrieval returns the full recall set.
MIN_COSINE_THRESHOLD: float = 0.35

# Must stay aligned with validation.MIN_AVG_SCORE_FOR_SUFFICIENCY.
# Lowered from 0.65 to 0.60 so the calibrated score floor has clear headroom
# below the sufficiency gate (0.55), preventing rounding-error abstentions.
SCORE_FLOOR: float = 0.60


def distance_to_raw_score(distance: float) -> float:
    """
    Convert a cosine distance to raw cosine similarity in [0, 1].

    Cosine distance = 1 - cosine_similarity for normalised vectors.
    """
    return round(max(0.0, min(1.0, 1.0 - distance)), 6)


def raw_similarity_score(score: float) -> float:
    """Clamp a vector-store similarity score to [0, 1]."""
    return round(max(0.0, min(1.0, score)), 6)


def calibrate_score(raw_score: float) -> float:
    """
    Linear calibration anchored so that MIN_COSINE_THRESHOLD maps to
    SCORE_FLOOR and 1.0 maps to 1.0.

    Scores below MIN_COSINE_THRESHOLD are NOT floored — they continue
    scaling down below SCORE_FLOOR so that low-relevance chunks remain
    distinguishable from borderline ones. This matters now that retrieval
    no longer discards low-similarity chunks: validation's sufficiency and
    ranking logic relies on `score` reflecting true relative quality across
    the full recall set, not just the previously-thresholded subset.
    """
    span = 1.0 - MIN_COSINE_THRESHOLD
    if span <= 0:
        return SCORE_FLOOR
    calibrated = SCORE_FLOOR + (
        (raw_score - MIN_COSINE_THRESHOLD) / span * (1.0 - SCORE_FLOOR)
    )
    return round(min(1.0, calibrated), 4)
