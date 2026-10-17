"""
Unit tests for Vision geometry, EAR computation, and ROI validation.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

import pytest

from app.modules.vision.geometry import (
    NormalizedROI,
    Point2D,
    calculate_eye_aspect_ratio,
    compute_landmarks_bbox,
    compute_landmarks_center,
    euclidean_distance_2d,
    evaluate_landmark_quality,
    extract_ear_from_landmarks,
)


def test_point2d_in_bounds() -> None:
    p_valid = Point2D(0.5, 0.5)
    assert p_valid.in_bounds() is True

    p_out_x = Point2D(1.1, 0.5)
    assert p_out_x.in_bounds() is False

    p_out_neg = Point2D(-0.1, 0.5)
    assert p_out_neg.in_bounds() is False


def test_normalized_roi_bounds_validation() -> None:
    # Valid ROI
    roi = NormalizedROI(0.0, 0.0, 0.5, 1.0)
    assert roi.width == 0.5
    assert roi.height == 1.0
    assert roi.area == 0.5

    # Invalid bounds (x_min >= x_max)
    with pytest.raises(ValueError, match="Invalid ROI horizontal bounds"):
        NormalizedROI(0.6, 0.0, 0.5, 1.0)

    # Invalid bounds (negative or > 1.0)
    with pytest.raises(ValueError, match="Invalid ROI horizontal bounds"):
        NormalizedROI(-0.1, 0.0, 0.5, 1.0)

    with pytest.raises(ValueError, match="Invalid ROI vertical bounds"):
        NormalizedROI(0.0, 0.0, 0.5, 1.2)


def test_normalized_roi_point_containment() -> None:
    roi = NormalizedROI(0.1, 0.2, 0.6, 0.8)
    assert roi.contains_point(Point2D(0.3, 0.5)) is True
    assert roi.contains_point(Point2D(0.05, 0.5)) is False
    assert roi.contains_point(Point2D(0.3, 0.9)) is False


def test_normalized_roi_overlap_detection() -> None:
    roi_left = NormalizedROI(0.0, 0.0, 0.5, 1.0)
    roi_right = NormalizedROI(0.5, 0.0, 1.0, 1.0)
    # Touching boundary is not overlapping
    assert roi_left.overlaps(roi_right) is False

    roi_overlap = NormalizedROI(0.4, 0.0, 0.9, 1.0)
    assert roi_left.overlaps(roi_overlap) is True
    assert roi_overlap.overlaps(roi_left) is True


def test_euclidean_distance_2d() -> None:
    p1 = Point2D(0.0, 0.0)
    p2 = Point2D(3.0, 4.0)
    assert euclidean_distance_2d(p1, p2) == pytest.approx(5.0)


def test_calculate_eye_aspect_ratio_open_and_closed() -> None:
    # Standard open eye: horizontal=0.2, vertical1=0.06, vertical2=0.06
    # EAR = (0.06 + 0.06) / (2 * 0.2) = 0.30
    p1 = Point2D(0.1, 0.5)
    p2 = Point2D(0.15, 0.47)
    p3 = Point2D(0.25, 0.47)
    p4 = Point2D(0.3, 0.5)
    p5 = Point2D(0.25, 0.53)
    p6 = Point2D(0.15, 0.53)

    ear_open = calculate_eye_aspect_ratio((p1, p2, p3, p4, p5, p6))
    assert ear_open == pytest.approx(0.30, rel=1e-2)

    # Closed eye: vertical distances near 0.01
    p2_closed = Point2D(0.15, 0.495)
    p3_closed = Point2D(0.25, 0.495)
    p5_closed = Point2D(0.25, 0.505)
    p6_closed = Point2D(0.15, 0.505)
    ear_closed = calculate_eye_aspect_ratio((p1, p2_closed, p3_closed, p4, p5_closed, p6_closed))
    assert ear_closed < 0.10


def test_calculate_eye_aspect_ratio_zero_denominator_guard() -> None:
    # Coincident horizontal points (denominator near 0)
    p1 = Point2D(0.2, 0.5)
    p4 = Point2D(0.2, 0.5)
    p2 = Point2D(0.2, 0.45)
    p3 = Point2D(0.2, 0.45)
    p5 = Point2D(0.2, 0.55)
    p6 = Point2D(0.2, 0.55)

    ear = calculate_eye_aspect_ratio((p1, p2, p3, p4, p5, p6))
    assert ear == 0.0


def test_extract_ear_from_landmarks_missing_or_incomplete() -> None:
    # Empty list
    left, right, avg = extract_ear_from_landmarks([])
    assert (left, right, avg) == (0.0, 0.0, 0.0)

    # Incomplete dictionary
    left, right, avg = extract_ear_from_landmarks({33: Point2D(0.1, 0.1)})
    assert (left, right, avg) == (0.0, 0.0, 0.0)


def test_evaluate_landmark_quality() -> None:
    # Empty landmarks
    usable, score = evaluate_landmark_quality([])
    assert usable is False
    assert score == 0.0

    # High quality centered face landmarks
    valid_face = [Point2D(0.3 + 0.01 * (i % 20), 0.3 + 0.01 * (i // 20)) for i in range(100)]
    usable, score = evaluate_landmark_quality(valid_face)
    assert usable is True
    assert 0.8 <= score <= 1.0

    # Face with out of bounds landmarks
    out_of_bounds = [Point2D(1.5, 1.5) for _ in range(50)] + [Point2D(0.5, 0.5) for _ in range(50)]
    usable, score = evaluate_landmark_quality(out_of_bounds)
    assert usable is False
    assert score < 0.3

    # Degenerate tiny bbox
    tiny = [Point2D(0.5001, 0.5001) for _ in range(20)]
    usable, score = evaluate_landmark_quality(tiny)
    assert usable is False
