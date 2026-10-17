# AeroGuard Vision Subsystem

> **SIMULATION ONLY — NOT FOR OPERATIONAL AVIATION USE**  
> This software is a simulation demonstration developed for the IBM Z Datathon 2026. It is not designed, certified, or intended for operational flight monitoring, avionics integration, medical diagnosis, or pilot alertness assessment.

## Overview

The Vision subsystem provides pilot observation evidence to the AeroGuard orchestrator through the frozen `VisionAdapter` protocol:

```python
class VisionAdapter(Protocol):
    def configure_scenario(self, scenario_id: str) -> None: ...
    def observe(self, pilot_id: PilotId, observed_at: datetime) -> PilotObservation: ...
```

## Key Invariants & Safety Policy

1. **Conservative Uncertainty (`UNKNOWN`)**:
   - Absence of camera, camera closure, severe blur, extreme lighting, obstructed lens, or missing facial landmarks immediately map to `UNKNOWN` with `observation_quality=0.0`.
   - Vision estimates only visual availability, eye openness cues, and quality. It never claims clinical responsiveness or medical consciousness.
2. **Strict Pilot Separation**:
   - `PILOT_1` and `PILOT_2` maintain separate evidence histories and channel configurations.
   - Observations are never copied or duplicated across pilots.
   - If a source or ROI is unassigned or disabled, that pilot emits `UNKNOWN`.
3. **Temporal Evidence Windowing**:
   - Single-frame blinks or closed-eye readings do not trigger `POSSIBLY_UNRESPONSIVE`.
   - Concerning visual cues must persist across a configured window (`min_closed_window_ms`, default 3,000 ms) with high-quality continuous evidence.
   - Positive responsiveness requires sustained clear cues (`min_open_window_ms`, default 1,000 ms).
   - Any gap or invalid frame resets the accumulated duration.
4. **Single-Webcam Limitation**:
   - A single laptop camera monitors a single pilot. Dual-pilot demonstration with a single camera requires explicit disjoint non-overlapping ROIs (`VisionConfig.split_frame()`), or synthetic scenario replay.

## Adapters

- **`MockVisionAdapter`**: P0 default mock returning deterministic scenario outcomes for the 5 benchmark scenarios.
- **`RealVisionAdapter`**: Uncertainty-aware real adapter using pure-Python geometry, bounded evidence windows, and configurable frame sources.
- **`ReplayLandmarkSource`**: Deterministic replay provider with zero external dependencies.
- **`OpenCVCaptureSource`**: Optional hardware camera / video file capture provider (requires optional `opencv-python`).

## Composition Root Integration (for Abhinav)

To wire `RealVisionAdapter` into `backend/app/main.py`:

```python
from app.modules.vision import RealVisionAdapter, VisionConfig

# Standard dual-pilot split frame replay:
vision_adapter = RealVisionAdapter(config=VisionConfig.split_frame())

# Or single-pilot monitoring on PILOT_1:
vision_adapter = RealVisionAdapter(config=VisionConfig.single_pilot(PilotId.PILOT_1))
```
