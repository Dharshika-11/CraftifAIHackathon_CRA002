"""
Unit tests for ``pipeline.gesture_classifier``
================================================
Run with::

    cd PipeGen
    python -m pytest tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.gesture_classifier import Gesture, GestureClassifier, GestureResult
from pipeline.pose_estimator import Landmark, PoseResult


# ======================================================================
# Helpers
# ======================================================================

def _make_landmark(name: str, y_norm: float, visibility: float = 0.9) -> Landmark:
    """Create a :class:`Landmark` with only the fields the classifier uses."""
    return Landmark(
        name=name,
        x_norm=0.5,
        y_norm=y_norm,
        z_norm=0.0,
        visibility=visibility,
        x_px=320,
        y_px=int(y_norm * 480),
    )


def _make_pose(
    rs_y: float = 0.5,
    rw_y: float = 0.5,
    ls_y: float = 0.5,
    lw_y: float = 0.5,
    visibility: float = 0.9,
) -> PoseResult:
    """Build a minimal ``PoseResult`` with the four key landmarks."""
    lms = {
        "RIGHT_SHOULDER": _make_landmark("RIGHT_SHOULDER", rs_y, visibility),
        "RIGHT_WRIST": _make_landmark("RIGHT_WRIST", rw_y, visibility),
        "LEFT_SHOULDER": _make_landmark("LEFT_SHOULDER", ls_y, visibility),
        "LEFT_WRIST": _make_landmark("LEFT_WRIST", lw_y, visibility),
    }
    return PoseResult(landmarks=lms, all_landmarks=list(lms.values()), detected=True)


# ======================================================================
# Test class
# ======================================================================

class TestGestureClassifier:
    """Tests for :class:`GestureClassifier`."""

    def setup_method(self) -> None:
        self.clf = GestureClassifier(raise_threshold=0.10, confidence_threshold=0.5)

    # ---- Basic gesture recognition -------------------------------------

    def test_no_person_detected(self) -> None:
        """NONE when no person in frame."""
        pose = PoseResult(detected=False)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.NONE

    def test_right_arm_raised(self) -> None:
        """RIGHT_ARM_RAISED when right wrist well above right shoulder."""
        pose = _make_pose(rs_y=0.5, rw_y=0.2, ls_y=0.5, lw_y=0.6)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.RIGHT_ARM_RAISED
        assert result.right_raised is True
        assert result.left_raised is False
        assert result.confidence > 0

    def test_left_arm_raised(self) -> None:
        """LEFT_ARM_RAISED when left wrist well above left shoulder."""
        pose = _make_pose(rs_y=0.5, rw_y=0.6, ls_y=0.5, lw_y=0.2)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.LEFT_ARM_RAISED
        assert result.left_raised is True
        assert result.right_raised is False

    def test_both_arms_raised(self) -> None:
        """BOTH_ARMS_RAISED when both wrists above both shoulders."""
        pose = _make_pose(rs_y=0.5, rw_y=0.2, ls_y=0.5, lw_y=0.2)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.BOTH_ARMS_RAISED
        assert result.right_raised is True
        assert result.left_raised is True

    def test_no_gesture_arms_down(self) -> None:
        """NONE when both arms are at or below shoulder height."""
        pose = _make_pose(rs_y=0.5, rw_y=0.55, ls_y=0.5, lw_y=0.55)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.NONE

    # ---- Edge cases ----------------------------------------------------

    def test_just_below_threshold(self) -> None:
        """NONE when wrist is above shoulder but not by enough."""
        # shoulder at 0.5, wrist at 0.45 → diff = 0.05 < threshold 0.10
        pose = _make_pose(rs_y=0.5, rw_y=0.45, ls_y=0.5, lw_y=0.55)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.NONE

    def test_just_above_threshold(self) -> None:
        """RIGHT_ARM_RAISED when wrist just barely exceeds the threshold."""
        # shoulder at 0.5, wrist at 0.39 → diff = 0.11 > threshold 0.10
        pose = _make_pose(rs_y=0.5, rw_y=0.39, ls_y=0.5, lw_y=0.55)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.RIGHT_ARM_RAISED

    def test_low_confidence_landmarks_rejected(self) -> None:
        """NONE when landmark visibility is below the confidence threshold."""
        pose = _make_pose(rs_y=0.5, rw_y=0.2, ls_y=0.5, lw_y=0.2, visibility=0.3)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.NONE

    def test_partial_visibility_right_only(self) -> None:
        """Only the visible side is considered when the other has low vis."""
        lms = {
            "RIGHT_SHOULDER": _make_landmark("RIGHT_SHOULDER", 0.5, 0.9),
            "RIGHT_WRIST": _make_landmark("RIGHT_WRIST", 0.2, 0.9),
            "LEFT_SHOULDER": _make_landmark("LEFT_SHOULDER", 0.5, 0.3),  # low vis
            "LEFT_WRIST": _make_landmark("LEFT_WRIST", 0.2, 0.3),       # low vis
        }
        pose = PoseResult(landmarks=lms, all_landmarks=list(lms.values()), detected=True)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.RIGHT_ARM_RAISED

    def test_missing_landmarks(self) -> None:
        """NONE when required landmarks are entirely missing."""
        pose = PoseResult(landmarks={}, all_landmarks=[], detected=True)
        result = self.clf.classify(pose)
        assert result.gesture == Gesture.NONE

    # ---- Command string mapping ----------------------------------------

    def test_gesture_command_strings(self) -> None:
        """Verify that each Gesture variant maps to the correct firmware command."""
        assert Gesture.RIGHT_ARM_RAISED.value == "LIGHT_ON"
        assert Gesture.LEFT_ARM_RAISED.value == "LIGHT_OFF"
        assert Gesture.BOTH_ARMS_RAISED.value == "SERVO_OPEN"
        assert Gesture.NONE.value == ""

    # ---- Confidence score -----------------------------------------------

    def test_confidence_bounded_0_1(self) -> None:
        """Confidence score should be clamped to [0, 1]."""
        pose = _make_pose(rs_y=0.8, rw_y=0.0, ls_y=0.8, lw_y=0.0)
        result = self.clf.classify(pose)
        assert 0.0 <= result.confidence <= 1.0
