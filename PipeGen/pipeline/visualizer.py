"""
CraftifAI PipeGen — Debug Visualizer
======================================
Draws skeleton overlays, gesture state, confidence bars, and command history
on the camera frame using OpenCV.
"""

from __future__ import annotations

import time
import logging
from collections import deque
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

from pipeline.gesture_classifier import Gesture, GestureResult
from pipeline.pose_estimator import PoseResult
from pipeline.reliability import ReliabilityFilter

logger = logging.getLogger(__name__)

# Colour palette (BGR)
_GREEN = (0, 255, 0)
_RED = (0, 0, 255)
_YELLOW = (0, 255, 255)
_CYAN = (255, 255, 0)
_WHITE = (255, 255, 255)
_GREY = (160, 160, 160)
_BG = (30, 30, 30)

# Skeleton connections (MediaPipe indices of the key arm landmarks)
_SKELETON_CONNECTIONS: List[Tuple[str, str]] = [
    ("LEFT_SHOULDER", "LEFT_ELBOW"),
    ("LEFT_ELBOW", "LEFT_WRIST"),
    ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
    ("RIGHT_ELBOW", "RIGHT_WRIST"),
    ("LEFT_SHOULDER", "RIGHT_SHOULDER"),
]


class Visualizer:
    """Renders debug information on top of the camera frame.

    Parameters
    ----------
    show_skeleton : bool
        Draw pose skeleton lines and keypoint circles.
    show_gesture : bool
        Display the current gesture label.
    show_confidence : bool
        Show confidence score.
    show_command_history : bool
        Show a scrolling list of recently sent commands.
    max_history : int
        Maximum number of command-history entries to display.
    """

    def __init__(
        self,
        show_skeleton: bool = True,
        show_gesture: bool = True,
        show_confidence: bool = True,
        show_command_history: bool = True,
        max_history: int = 5,
    ) -> None:
        self._show_skeleton = show_skeleton
        self._show_gesture = show_gesture
        self._show_confidence = show_confidence
        self._show_history = show_command_history

        self._history: Deque[Tuple[float, str]] = deque(maxlen=max_history)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_command(self, command: str) -> None:
        """Append *command* to the visual history log."""
        self._history.append((time.time(), command))

    def draw(
        self,
        frame: np.ndarray,
        pose: PoseResult,
        gesture: GestureResult,
        reliability: ReliabilityFilter,
    ) -> np.ndarray:
        """Draw all overlays and return the annotated frame (mutated in-place).

        Parameters
        ----------
        frame : np.ndarray
            BGR camera frame.
        pose : PoseResult
            Current pose estimation result.
        gesture : GestureResult
            Current gesture classification.
        reliability : ReliabilityFilter
            The reliability filter (for cooldown info).

        Returns
        -------
        np.ndarray
            The same frame with overlays drawn.
        """
        if self._show_skeleton:
            self._draw_skeleton(frame, pose)

        if self._show_gesture:
            self._draw_gesture_label(frame, gesture)

        if self._show_confidence:
            self._draw_confidence(frame, gesture, reliability)

        if self._show_history:
            self._draw_command_history(frame)

        return frame

    def show(self, frame: np.ndarray) -> bool:
        """Display *frame* in an OpenCV window.

        Returns
        -------
        bool
            ``False`` if the user pressed **q** (quit signal).
        """
        cv2.imshow("PipeGen — GestureLink AI", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            return False
        return True

    def close(self) -> None:
        """Destroy all OpenCV windows."""
        cv2.destroyAllWindows()
        logger.info("Visualizer windows closed.")

    # ------------------------------------------------------------------
    # Skeleton
    # ------------------------------------------------------------------

    def _draw_skeleton(self, frame: np.ndarray, pose: PoseResult) -> None:
        if not pose.detected:
            return

        lm = pose.landmarks

        # Draw connections
        for a_name, b_name in _SKELETON_CONNECTIONS:
            a = lm.get(a_name)
            b = lm.get(b_name)
            if a is not None and b is not None:
                cv2.line(frame, (a.x_px, a.y_px), (b.x_px, b.y_px), _CYAN, 2)

        # Draw keypoints
        for name in ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW",
                      "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST"):
            pt = lm.get(name)
            if pt is not None:
                colour = _GREEN if pt.visibility >= 0.5 else _RED
                cv2.circle(frame, (pt.x_px, pt.y_px), 6, colour, -1)
                cv2.putText(
                    frame,
                    f"{pt.visibility:.0%}",
                    (pt.x_px + 8, pt.y_px - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    _WHITE,
                    1,
                )

    # ------------------------------------------------------------------
    # Gesture label
    # ------------------------------------------------------------------

    def _draw_gesture_label(
        self, frame: np.ndarray, gesture: GestureResult
    ) -> None:
        label = gesture.gesture.name.replace("_", " ")
        colour = _GREEN if gesture.gesture != Gesture.NONE else _GREY

        # Background rectangle
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        cv2.rectangle(frame, (10, 10), (20 + tw, 20 + th + 10), _BG, -1)
        cv2.putText(
            frame, label, (15, 15 + th), cv2.FONT_HERSHEY_SIMPLEX, 1.0, colour, 2
        )

    # ------------------------------------------------------------------
    # Confidence & cooldown
    # ------------------------------------------------------------------

    def _draw_confidence(
        self,
        frame: np.ndarray,
        gesture: GestureResult,
        reliability: ReliabilityFilter,
    ) -> None:
        h = frame.shape[0]
        y = h - 60

        # Confidence bar
        bar_w = int(200 * gesture.confidence)
        cv2.rectangle(frame, (10, y), (210, y + 18), _GREY, 1)
        cv2.rectangle(frame, (10, y), (10 + bar_w, y + 18), _GREEN, -1)
        cv2.putText(
            frame,
            f"Conf: {gesture.confidence:.0%}",
            (215, y + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            _WHITE,
            1,
        )

        # Streak info
        streak_text = (
            f"Streak: {reliability.streak_count}  "
            f"({reliability.streak_gesture.name})"
        )
        cv2.putText(
            frame,
            streak_text,
            (10, y + 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            _YELLOW,
            1,
        )

        # Cooldown for current gesture command
        if gesture.gesture != Gesture.NONE:
            cd = reliability.cooldown_remaining(gesture.gesture.value)
            if cd > 0:
                cd_text = f"Cooldown: {cd:.1f}s"
                cv2.putText(
                    frame,
                    cd_text,
                    (10, y + 55),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.40,
                    _RED,
                    1,
                )

    # ------------------------------------------------------------------
    # Command history
    # ------------------------------------------------------------------

    def _draw_command_history(self, frame: np.ndarray) -> None:
        w = frame.shape[1]
        x = w - 220
        y_start = 15

        cv2.putText(
            frame,
            "CMD History",
            (x, y_start),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            _YELLOW,
            1,
        )
        for i, (ts, cmd) in enumerate(reversed(list(self._history))):
            age = time.time() - ts
            line = f"{cmd}  ({age:.0f}s ago)"
            cv2.putText(
                frame,
                line,
                (x, y_start + 20 + i * 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                _WHITE,
                1,
            )
