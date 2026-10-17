"""retrieval_scoring: raw similarity handling and score calibration."""
import pytest

import retrieval_scoring as rs


def test_distance_to_raw_score_is_one_minus_distance():
    assert rs.distance_to_raw_score(0.0) == 1.0
    assert rs.distance_to_raw_score(0.25) == 0.75


@pytest.mark.parametrize("distance,expected", [(-0.5, 1.0), (1.5, 0.0), (2.0, 0.0)])
def test_distance_to_raw_score_clamps_to_unit_interval(distance, expected):
    assert rs.distance_to_raw_score(distance) == expected


@pytest.mark.parametrize("score,expected", [(-1.0, 0.0), (0.4, 0.4), (3.0, 1.0)])
def test_raw_similarity_score_clamps(score, expected):
    assert rs.raw_similarity_score(score) == expected


def test_calibration_anchors():
    # MIN_COSINE_THRESHOLD maps to SCORE_FLOOR, and 1.0 maps to 1.0.
    assert rs.calibrate_score(rs.MIN_COSINE_THRESHOLD) == pytest.approx(rs.SCORE_FLOOR, abs=1e-4)
    assert rs.calibrate_score(1.0) == 1.0


def test_calibration_is_monotonic_and_not_floored_below_anchor():
    # Low-relevance chunks must stay distinguishable from borderline ones.
    xs = [0.0, 0.1, 0.2, 0.35, 0.5, 0.8, 1.0]
    ys = [rs.calibrate_score(x) for x in xs]
    assert ys == sorted(ys)
    assert len(set(ys)) == len(ys)
    assert rs.calibrate_score(0.1) < rs.SCORE_FLOOR


def test_calibration_never_exceeds_one():
    assert rs.calibrate_score(5.0) == 1.0
