"""
CraftifAI PipeGen — Pose Estimator
====================================
Abstracts pose-estimation backends behind a common interface.

* **MediaPipePoseEstimator** — production-ready, CPU / GPU via MediaPipe.
* **TensorRTPoseEstimator**  — stub for future TensorRT-accelerated path.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ======================================================================
# Data classes
# ======================================================================

@dataclass
class Landmark:
    """A single pose landmark in both normalized and pixel coordinates.

    Attributes
    ----------
    name : str
        Human-readable name (e.g. ``"RIGHT_WRIST"``).
    x_norm : float
        Normalised X coordinate [0, 1].
    y_norm : float
        Normalised Y coordinate [0, 1] — *increases downward*.
    z_norm : float
        Normalised depth (relative to hips).
    visibility : float
        MediaPipe visibility / confidence score [0, 1].
    x_px : int
        Pixel X coordinate in the source frame.
    y_px : int
        Pixel Y coordinate in the source frame.
    """

    name: str
    x_norm: float
    y_norm: float
    z_norm: float
    visibility: float
    x_px: int
    y_px: int


@dataclass
class PoseResult:
    """Container for a single-frame pose estimation result.

    Attributes
    ----------
    landmarks : dict[str, Landmark]
        Mapping from landmark name → :class:`Landmark`.
    all_landmarks : list[Landmark]
        Full ordered list of landmarks (MediaPipe returns 33).
    detected : bool
        ``True`` if at least one person was detected.
    """

    landmarks: Dict[str, Landmark] = field(default_factory=dict)
    all_landmarks: List[Landmark] = field(default_factory=list)
    detected: bool = False


# ======================================================================
# Landmark names we care about (subset of MediaPipe's 33)
# ======================================================================

# fmt: off
KEY_LANDMARKS = [
    "LEFT_SHOULDER",  "RIGHT_SHOULDER",
    "LEFT_ELBOW",     "RIGHT_ELBOW",
    "LEFT_WRIST",     "RIGHT_WRIST",
]
# fmt: on


# ======================================================================
# Abstract base class
# ======================================================================

class BasePoseEstimator(abc.ABC):
    """Interface that every pose-estimation backend must implement."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Allocate resources (model load, device warm-up)."""

    @abc.abstractmethod
    def estimate(self, frame: np.ndarray) -> PoseResult:
        """Run inference on a BGR frame and return a :class:`PoseResult`."""

    @abc.abstractmethod
    def release(self) -> None:
        """Free resources."""


# ======================================================================
# MediaPipe backend
# ======================================================================

class MediaPipePoseEstimator(BasePoseEstimator):
    """Pose estimator backed by *mediapipe.solutions.pose*.

    Parameters
    ----------
    model_complexity : int
        ``0`` (lite), ``1`` (full), or ``2`` (heavy).
    min_detection_confidence : float
        Minimum confidence for the person-detection stage.
    min_tracking_confidence : float
        Minimum confidence for the landmark-tracking stage.
    """

    # MediaPipe landmark index → name (only the ones we need).
    _INDEX_TO_NAME: Dict[int, str] = {
        11: "LEFT_SHOULDER",
        12: "RIGHT_SHOULDER",
        13: "LEFT_ELBOW",
        14: "RIGHT_ELBOW",
        15: "LEFT_WRIST",
        16: "RIGHT_WRIST",
    }

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._model_complexity = model_complexity
        self._min_det = min_detection_confidence
        self._min_trk = min_tracking_confidence
        self._pose = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        import mediapipe as mp  # lazy import

        self._mp_pose = mp.solutions.pose
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=self._model_complexity,
            min_detection_confidence=self._min_det,
            min_tracking_confidence=self._min_trk,
        )
        logger.info(
            "MediaPipe Pose initialised (complexity=%d, det=%.2f, trk=%.2f)",
            self._model_complexity,
            self._min_det,
            self._min_trk,
        )

    def release(self) -> None:
        if self._pose is not None:
            self._pose.close()
            self._pose = None
            logger.info("MediaPipe Pose released.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def estimate(self, frame: np.ndarray) -> PoseResult:
        """Run MediaPipe Pose on *frame* (BGR) and return a PoseResult."""
        if self._pose is None:
            raise RuntimeError("Pose estimator not initialised — call initialize() first.")

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        pose_result = PoseResult()

        if results.pose_landmarks is None:
            return pose_result

        pose_result.detected = True

        for idx, lm in enumerate(results.pose_landmarks.landmark):
            name = self._INDEX_TO_NAME.get(idx)
            landmark = Landmark(
                name=name or f"LANDMARK_{idx}",
                x_norm=lm.x,
                y_norm=lm.y,
                z_norm=lm.z,
                visibility=lm.visibility,
                x_px=int(lm.x * w),
                y_px=int(lm.y * h),
            )
            pose_result.all_landmarks.append(landmark)
            if name is not None:
                pose_result.landmarks[name] = landmark

        return pose_result


# ======================================================================
# TensorRT backend (stub)
# ======================================================================

class TensorRTPoseEstimator(BasePoseEstimator):
    """Placeholder for a future TensorRT-accelerated pose estimator.

    Raises :class:`NotImplementedError` on every call.
    """

    def initialize(self) -> None:
        raise NotImplementedError(
            "TensorRT pose estimator is not yet implemented. "
            "Use 'mediapipe' backend for now."
        )

    def estimate(self, frame: np.ndarray) -> PoseResult:
        raise NotImplementedError

    def release(self) -> None:
        pass


# ======================================================================
# Factory
# ======================================================================

def create_pose_estimator(cfg: dict) -> BasePoseEstimator:
    """Instantiate a pose estimator from the *pose* section of config.yaml.

    Parameters
    ----------
    cfg : dict
        The ``pose`` section of the loaded YAML config.

    Returns
    -------
    BasePoseEstimator
    """
    backend = cfg.get("backend", "mediapipe").lower()
    if backend == "mediapipe":
        return MediaPipePoseEstimator(
            model_complexity=cfg.get("model_complexity", 1),
            min_detection_confidence=cfg.get("min_detection_confidence", 0.5),
            min_tracking_confidence=cfg.get("min_tracking_confidence", 0.5),
        )
    elif backend == "tensorrt":
        return TensorRTPoseEstimator()
    else:
        raise ValueError(f"Unknown pose backend: {backend!r}")
