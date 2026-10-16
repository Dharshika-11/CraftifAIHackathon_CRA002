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
# MediaPipe backend (Tasks API with legacy solutions fallback)
# ======================================================================

class MediaPipePoseEstimator(BasePoseEstimator):
    """Pose estimator backed by MediaPipe Tasks API (or legacy solutions.pose).

    Parameters
    ----------
    model_complexity : int
        ``0`` (lite), ``1`` (full), or ``2`` (heavy).
    min_detection_confidence : float
        Minimum confidence for the person-detection stage.
    min_tracking_confidence : float
        Minimum confidence for the landmark-tracking stage.
    model_path : Optional[str]
        Explicit path to the .task file (optional).
    """

    _INDEX_TO_NAME: Dict[int, str] = {
        11: "LEFT_SHOULDER",
        12: "RIGHT_SHOULDER",
        13: "LEFT_ELBOW",
        14: "RIGHT_ELBOW",
        15: "LEFT_WRIST",
        16: "RIGHT_WRIST",
    }

    _MODEL_FILES: Dict[int, str] = {
        0: "pose_landmarker_lite.task",
        1: "pose_landmarker_full.task",
        2: "pose_landmarker_heavy.task",
    }

    _MODEL_URLS: Dict[int, str] = {
        0: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
        1: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
        2: "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
    }

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: Optional[str] = None,
    ) -> None:
        self._model_complexity = int(model_complexity)
        if self._model_complexity not in (0, 1, 2):
            self._model_complexity = 1
        self._min_det = min_detection_confidence
        self._min_trk = min_tracking_confidence
        self._model_path = model_path
        self._mode = "uninitialized"  # "tasks" or "legacy"
        self._detector = None
        self._mp = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_task_model(self) -> str:
        import os
        import urllib.request
        from pathlib import Path

        if self._model_path and os.path.exists(self._model_path):
            return self._model_path

        base_dir = Path(__file__).resolve().parent.parent / "models"
        base_dir.mkdir(parents=True, exist_ok=True)
        filename = self._MODEL_FILES.get(self._model_complexity, "pose_landmarker_full.task")
        model_file = base_dir / filename

        if not model_file.exists():
            url = self._MODEL_URLS.get(self._model_complexity, self._MODEL_URLS[1])
            logger.info("Downloading pose landmarker model from %s...", url)
            urllib.request.urlretrieve(url, str(model_file))
            logger.info("Model saved to %s", model_file)

        return str(model_file)

    def initialize(self) -> None:
        import mediapipe as mp
        self._mp = mp

        # Try legacy solutions.pose first if available
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
            self._mode = "legacy"
            self._detector = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=self._model_complexity,
                min_detection_confidence=self._min_det,
                min_tracking_confidence=self._min_trk,
            )
            logger.info(
                "MediaPipe Pose (legacy solutions) initialised (complexity=%d)",
                self._model_complexity,
            )
            return

        # Otherwise use MediaPipe Tasks API
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            task_model_path = self._ensure_task_model()
            base_options = python.BaseOptions(model_asset_path=task_model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                min_pose_detection_confidence=self._min_det,
                min_tracking_confidence=self._min_trk,
                output_segmentation_masks=False,
            )
            self._detector = vision.PoseLandmarker.create_from_options(options)
            self._mode = "tasks"
            logger.info(
                "MediaPipe PoseLandmarker (Tasks API) initialised with model %s",
                task_model_path,
            )
        except Exception as exc:
            logger.error("Failed to initialise MediaPipe Tasks API: %s", exc)
            raise

    def release(self) -> None:
        if self._detector is not None:
            if hasattr(self._detector, "close"):
                self._detector.close()
            self._detector = None
            logger.info("MediaPipe Pose released.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def estimate(self, frame: np.ndarray) -> PoseResult:
        """Run pose estimation on *frame* (BGR) and return a PoseResult."""
        if self._detector is None:
            raise RuntimeError("Pose estimator not initialised — call initialize() first.")

        h, w = frame.shape[:2]
        pose_result = PoseResult()

        if self._mode == "tasks":
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
            detection_result = self._detector.detect(mp_image)

            if not detection_result.pose_landmarks:
                return pose_result

            pose_result.detected = True
            landmarks_list = detection_result.pose_landmarks[0]

            for idx, lm in enumerate(landmarks_list):
                name = self._INDEX_TO_NAME.get(idx)
                vis = getattr(lm, "visibility", 1.0)
                if vis is None:
                    vis = 1.0
                landmark = Landmark(
                    name=name or f"LANDMARK_{idx}",
                    x_norm=float(lm.x),
                    y_norm=float(lm.y),
                    z_norm=float(lm.z) if hasattr(lm, "z") else 0.0,
                    visibility=float(vis),
                    x_px=int(lm.x * w),
                    y_px=int(lm.y * h),
                )
                pose_result.all_landmarks.append(landmark)
                if name is not None:
                    pose_result.landmarks[name] = landmark

            return pose_result

        else:
            # Legacy solutions.pose
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self._detector.process(rgb)

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
