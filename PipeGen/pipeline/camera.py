"""
CraftifAI PipeGen — Camera Capture Module
==========================================
OpenCV VideoCapture wrapper with configurable resolution, FPS, and graceful
error handling.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Camera:
    """Thread-safe OpenCV camera wrapper.

    Parameters
    ----------
    index : int
        Camera device index (0 = default webcam).
    width : int
        Desired capture width in pixels.
    height : int
        Desired capture height in pixels.
    fps : int
        Target frames per second.
    """

    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> None:
        self._index = index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """Open the camera device.

        Returns
        -------
        bool
            ``True`` if the camera was opened successfully.
        """
        logger.info(
            "Opening camera index=%d  res=%dx%d  fps=%d",
            self._index,
            self._width,
            self._height,
            self._fps,
        )
        self._cap = cv2.VideoCapture(self._index)
        if not self._cap.isOpened():
            logger.error("Failed to open camera index %d", self._index)
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
        logger.info(
            "Camera opened — actual res=%dx%d  fps=%.1f",
            actual_w,
            actual_h,
            actual_fps,
        )
        return True

    def close(self) -> None:
        """Release the camera device."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released.")

    # ------------------------------------------------------------------
    # Frame acquisition
    # ------------------------------------------------------------------

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read a single frame from the camera.

        Returns
        -------
        tuple[bool, np.ndarray | None]
            ``(success, frame)`` where *frame* is a BGR ``np.ndarray`` or
            ``None`` on failure.
        """
        if self._cap is None or not self._cap.isOpened():
            logger.warning("read() called but camera is not open.")
            return False, None

        ret, frame = self._cap.read()
        if not ret:
            logger.warning("Failed to grab frame from camera.")
            return False, None
        return True, frame

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """Return whether the camera is currently open."""
        return self._cap is not None and self._cap.isOpened()

    @property
    def resolution(self) -> Tuple[int, int]:
        """Return ``(width, height)`` of the capture."""
        return self._width, self._height

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.close()
