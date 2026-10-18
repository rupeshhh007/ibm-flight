"""
Pure-Python geometric and landmark math for pilot eye aspect ratio and ROI validation.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
No external CV dependencies required.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Point2D:
    x: float
    y: float

    def in_bounds(self) -> bool:
        if math.isnan(self.x) or math.isnan(self.y) or math.isinf(self.x) or math.isinf(self.y):
            return False
        return 0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0


@dataclass(frozen=True, slots=True)
class NormalizedROI:
    """
    Normalized region of interest in [0.0, 1.0] coordinates.
    x_min, y_min is top-left; x_max, y_max is bottom-right.
    """
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        for val in (self.x_min, self.y_min, self.x_max, self.y_max):
            if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
                raise ValueError(f"ROI coordinates must be finite numbers (got {val})")

        if not (0.0 <= self.x_min < self.x_max <= 1.0):
            raise ValueError(f"Invalid ROI horizontal bounds: x_min={self.x_min}, x_max={self.x_max}")
        if not (0.0 <= self.y_min < self.y_max <= 1.0):
            raise ValueError(f"Invalid ROI vertical bounds: y_min={self.y_min}, y_max={self.y_max}")

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains_point(self, point: Point2D) -> bool:
        if not point.in_bounds():
            return False
        return self.x_min <= point.x <= self.x_max and self.y_min <= point.y <= self.y_max

    def overlaps(self, other: NormalizedROI) -> bool:
        """Return True if two ROIs overlap strictly with non-zero intersection area."""
        return not (
            self.x_max <= other.x_min
            or self.x_min >= other.x_max
            or self.y_max <= other.y_min
            or self.y_min >= other.y_max
        )


def euclidean_distance_2d(p1: Point2D, p2: Point2D) -> float:
    if not (p1.in_bounds() and p2.in_bounds()):
        # Handle un-normalized or NaN/Inf points safely
        if math.isnan(p1.x) or math.isnan(p1.y) or math.isnan(p2.x) or math.isnan(p2.y):
            return 0.0
        if math.isinf(p1.x) or math.isinf(p1.y) or math.isinf(p2.x) or math.isinf(p2.y):
            return 0.0
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def calculate_eye_aspect_ratio(
    eye_points: Sequence[Point2D],
) -> float | None:
    """
    Compute Eye Aspect Ratio (EAR) from 6 2D landmarks:
    p1: outer corner
    p2: top lid outer
    p3: top lid inner
    p4: inner corner
    p5: bottom lid inner
    p6: bottom lid outer

    EAR = (|p2 - p6| + |p3 - p5|) / (2.0 * |p1 - p4|)
    Safely guarded against zero, near-zero, NaN, and Inf denominators.
    Returns None if eye points are missing, out of bounds, degenerate, or zero-width.
    """
    try:
        p1, p2, p3, p4, p5, p6 = eye_points
        for p in (p1, p2, p3, p4, p5, p6):
            if not p.in_bounds():
                return None

        horizontal_dist = euclidean_distance_2d(p1, p4)
        # Eye width must be non-zero and physically plausible (at least 0.5% of normalized frame)
        if horizontal_dist < 0.005 or math.isnan(horizontal_dist) or math.isinf(horizontal_dist):
            return None

        v1 = euclidean_distance_2d(p2, p6)
        v2 = euclidean_distance_2d(p3, p5)
        if math.isnan(v1) or math.isnan(v2) or math.isinf(v1) or math.isinf(v2):
            return None

        ear = (v1 + v2) / (2.0 * horizontal_dist)
        if math.isnan(ear) or math.isinf(ear) or ear < 0.0 or ear > 1.0:
            return None
        return round(max(0.0, min(1.0, ear)), 4)
    except Exception:
        return None


# MediaPipe FaceMesh standard landmark indices for left and right eyes
# Left eye (subject perspective):
LEFT_EYE_INDICES = (33, 160, 158, 133, 153, 144)
# Right eye (subject perspective):
RIGHT_EYE_INDICES = (362, 385, 387, 263, 373, 380)


def extract_ear_from_landmarks(
    landmarks: Sequence[Point2D] | dict[int, Point2D],
) -> tuple[float | None, float | None, float | None]:
    """
    Extract (left_ear, right_ear, avg_ear) from landmark collection.
    If points are missing, invalid, or zero-width, returns (None, None, None).
    """
    try:
        if isinstance(landmarks, dict):
            left_points = tuple(landmarks[idx] for idx in LEFT_EYE_INDICES)
            right_points = tuple(landmarks[idx] for idx in RIGHT_EYE_INDICES)
        else:
            left_points = tuple(landmarks[idx] for idx in LEFT_EYE_INDICES)
            right_points = tuple(landmarks[idx] for idx in RIGHT_EYE_INDICES)
    except (IndexError, KeyError, TypeError):
        return None, None, None

    left_ear = calculate_eye_aspect_ratio(left_points)
    right_ear = calculate_eye_aspect_ratio(right_points)
    if left_ear is None or right_ear is None:
        return None, None, None

    avg_ear = (left_ear + right_ear) / 2.0
    if math.isnan(avg_ear) or math.isinf(avg_ear):
        return None, None, None
    return left_ear, right_ear, round(avg_ear, 4)


def compute_landmarks_bbox(landmarks: Sequence[Point2D]) -> tuple[float, float, float, float] | None:
    """Return (x_min, y_min, x_max, y_max) of landmarks, or None if empty or invalid."""
    if not landmarks:
        return None
    xs = [p.x for p in landmarks if not (math.isnan(p.x) or math.isinf(p.x))]
    ys = [p.y for p in landmarks if not (math.isnan(p.y) or math.isinf(p.y))]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def compute_landmarks_center(landmarks: Sequence[Point2D]) -> Point2D | None:
    if not landmarks:
        return None
    valid_points = [p for p in landmarks if not (math.isnan(p.x) or math.isnan(p.y) or math.isinf(p.x) or math.isinf(p.y))]
    if not valid_points:
        return None
    avg_x = sum(p.x for p in valid_points) / len(valid_points)
    avg_y = sum(p.y for p in valid_points) / len(valid_points)
    return Point2D(avg_x, avg_y)


def evaluate_landmark_quality(landmarks: Sequence[Point2D]) -> tuple[bool, float]:
    """
    Check if landmarks are usable and compute a quality score in [0.0, 1.0].
    Returns (is_usable, quality_score).
    """
    if not landmarks or len(landmarks) < 6:
        return False, 0.0

    # NaN / Inf guard
    for p in landmarks:
        if math.isnan(p.x) or math.isnan(p.y) or math.isinf(p.x) or math.isinf(p.y):
            return False, 0.0

    in_bounds_count = sum(1 for p in landmarks if p.in_bounds())
    ratio = in_bounds_count / len(landmarks)
    if ratio < 0.90:
        return False, round(max(0.0, ratio * 0.3), 3)

    bbox = compute_landmarks_bbox(landmarks)
    if bbox is None:
        return False, 0.0
    x_min, y_min, x_max, y_max = bbox
    width = x_max - x_min
    height = y_max - y_min
    area = width * height

    # Face bounding box must not be degenerate or unreasonably small/large
    if width < 0.02 or height < 0.02:
        return False, 0.1
    if area > 0.98:
        return False, 0.2

    # Check that eye landmarks exist and are not zero-width/degenerate
    try:
        if isinstance(landmarks, (list, tuple)) and len(landmarks) >= 388:
            left_w = euclidean_distance_2d(landmarks[33], landmarks[133])
            right_w = euclidean_distance_2d(landmarks[362], landmarks[263])
            if left_w < 0.005 or right_w < 0.005:
                return False, 0.0
    except Exception:
        return False, 0.0

    # Higher score for centered, well-sized faces with 100% in-bounds landmarks
    quality = min(1.0, 0.5 + 0.5 * ratio)
    if math.isnan(quality) or math.isinf(quality):
        return False, 0.0
    return True, round(max(0.0, min(1.0, quality)), 3)
