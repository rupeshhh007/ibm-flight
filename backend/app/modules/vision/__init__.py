"""
AeroGuard Vision Subsystem.

SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE.
"""

from .adapter import RealVisionAdapter
from .config import PilotChannelConfig, VisionConfig
from .geometry import NormalizedROI, Point2D
from .mock import MockVisionAdapter
from .sources import FrameSource, ReplayLandmarkSource

__all__ = [
    "MockVisionAdapter",
    "RealVisionAdapter",
    "VisionConfig",
    "PilotChannelConfig",
    "NormalizedROI",
    "Point2D",
    "FrameSource",
    "ReplayLandmarkSource",
]
