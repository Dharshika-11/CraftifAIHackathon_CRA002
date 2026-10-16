"""
CraftifAI PipeGen — Gesture Classifier
========================================
Classifies arm gestures from pose landmarks using configurable thresholds.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Optional

from pipeline.pose_estimator import PoseResult

logger = logging.getLogger(__name__)


# ======================================================================
# Gesture enum
# ======================================================================

class Gesture(enum.Enum):
    """Recognised gesture types.

    Each variant carries the exact command string sent to the ESP32-S3.
    ``NONE`` means no actionable gesture was detected.
    """

    NONE = ""
    RIGHT_ARM_RAISED = "LIGHT_ON"
    LEFT_ARM_RAISED = "LIGHT_OFF"
    BOTH_ARMS_RAISED = "SERVO_OPEN"


# ======================================================================
# Classification result
# ======================================================================

@dataclass
class GestureResult:
    """Result of a single-frame gesture classification.

    Attributes
    ----------
    gesture : Gesture
        The detected gesture (may be ``NONE``).
    confidence : float
        An indicative confidence score in [0, 1].
    right_raised : bool
        Whether the right arm was classified as raised.
    left_raised : bool
        Whether the left arm was classified as raised.
    detail : str
        Human-readable explanation of the classification decision.
    """

    gesture: Gesture = Gesture.NONE
    confidence: float = 0.0
    right_raised: bool = False
    left_raised: bool = False
    detail: str = ""


# ======================================================================
# Classifier
# ======================================================================

class GestureClassifier:
    """Classifies arm-raise gestures from pose keypoints.

    In MediaPipe's normalised coordinate system **Y increases downward**,
    so a raised wrist has a *smaller* Y than the shoulder.

    A wrist is considered "raised" when::

        wrist.y_norm < shoulder.y_norm - raise_threshold

    Parameters
    ----------
    raise_threshold : float
        Minimum normalised Y difference (shoulder − wrist) to count as
        "raised".  Default ``0.10``.
    confidence_threshold : float
        Minimum landmark visibility to trust a keypoint.  Default ``0.5``.
    """

    def __init__(
        self,
        raise_threshold: float = 0.10,
        confidence_threshold: float = 0.5,
    ) -> None:
        self._raise_threshold = raise_threshold
        self._confidence_threshold = confidence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, pose: PoseResult) -> GestureResult:
        """Classify the gesture visible in *pose*.

        Parameters
        ----------
        pose : PoseResult
            Output of a :class:`BasePoseEstimator`.

        Returns
        -------
        GestureResult
        """
        if not pose.detected:
            return GestureResult(detail="No person detected.")

        # --- Extract required landmarks ----------------------------------
        lm = pose.landmarks
        right_shoulder = lm.get("RIGHT_SHOULDER")
        right_wrist = lm.get("RIGHT_WRIST")
        left_shoulder = lm.get("LEFT_SHOULDER")
        left_wrist = lm.get("LEFT_WRIST")

        # --- Check visibility --------------------------------------------
        right_ok = self._is_visible(right_shoulder) and self._is_visible(right_wrist)
        left_ok = self._is_visible(left_shoulder) and self._is_visible(left_wrist)

        if not right_ok and not left_ok:
            return GestureResult(detail="Key landmarks not visible.")

        # --- Determine arm-raised state ----------------------------------
        right_raised = False
        left_raised = False
        right_diff = 0.0
        left_diff = 0.0

        if right_ok:
            assert right_shoulder is not None and right_wrist is not None
            right_diff = right_shoulder.y_norm - right_wrist.y_norm
            right_raised = right_diff > self._raise_threshold

        if left_ok:
            assert left_shoulder is not None and left_wrist is not None
            left_diff = left_shoulder.y_norm - left_wrist.y_norm
            left_raised = left_diff > self._raise_threshold

        # --- Map to gesture ----------------------------------------------
        if right_raised and left_raised:
            gesture = Gesture.BOTH_ARMS_RAISED
            confidence = min(right_diff, left_diff) / (self._raise_threshold + 0.2)
        elif right_raised:
            gesture = Gesture.RIGHT_ARM_RAISED
            confidence = right_diff / (self._raise_threshold + 0.2)
        elif left_raised:
            gesture = Gesture.LEFT_ARM_RAISED
            confidence = left_diff / (self._raise_threshold + 0.2)
        else:
            gesture = Gesture.NONE
            confidence = 0.0

        confidence = min(confidence, 1.0)

        detail = (
            f"R_diff={right_diff:+.3f} L_diff={left_diff:+.3f}  "
            f"R_raised={right_raised} L_raised={left_raised}"
        )
        logger.debug("Gesture classified: %s  %s", gesture.name, detail)

        return GestureResult(
            gesture=gesture,
            confidence=confidence,
            right_raised=right_raised,
            left_raised=left_raised,
            detail=detail,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_visible(self, lm: Optional[object]) -> bool:
        """Return ``True`` if *lm* exists and has sufficient visibility."""
        if lm is None:
            return False
        return getattr(lm, "visibility", 0.0) >= self._confidence_threshold
