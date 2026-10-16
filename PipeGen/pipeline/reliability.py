"""
CraftifAI PipeGen — Reliability Safeguards
============================================
Confidence filtering, temporal smoothing, cooldown, and hysteresis logic to
ensure only validated commands reach the ESP32-S3.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from pipeline.gesture_classifier import Gesture, GestureResult

logger = logging.getLogger(__name__)


class ReliabilityFilter:
    """Multi-layer filter that gates gesture detections before dispatch.

    Layers (applied in order):
    1. **Confidence filter** — reject results whose confidence is below a
       threshold.
    2. **Temporal smoothing** — the *same* gesture must appear for
       ``stable_frames`` consecutive frames.
    3. **Hysteresis** — after a gesture fires, it must drop to ``NONE``
       before it can re-trigger.
    4. **Cooldown** — after sending a command, the same command cannot be
       sent again for ``cooldown_seconds``.

    Parameters
    ----------
    confidence_threshold : float
        Minimum ``GestureResult.confidence`` to accept.
    stable_frames : int
        Number of consecutive identical-gesture frames required.
    cooldown_seconds : float
        Minimum elapsed time before re-sending the same command.
    hysteresis : bool
        If ``True``, gesture must drop before same gesture re-triggers.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        stable_frames: int = 5,
        cooldown_seconds: float = 3.0,
        hysteresis: bool = True,
    ) -> None:
        self._conf_thresh = confidence_threshold
        self._stable_frames = stable_frames
        self._cooldown_sec = cooldown_seconds
        self._hysteresis = hysteresis

        # Internal state
        self._streak_gesture: Gesture = Gesture.NONE
        self._streak_count: int = 0
        self._last_fired: Gesture = Gesture.NONE
        self._last_send_time: dict[str, float] = {}  # command → timestamp
        self._gesture_dropped: bool = True  # hysteresis flag

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, result: GestureResult) -> Optional[str]:
        """Feed a new frame's classification and return a command (or None).

        Parameters
        ----------
        result : GestureResult
            Output of :meth:`GestureClassifier.classify`.

        Returns
        -------
        str or None
            The command string to send (e.g. ``"LIGHT_ON"``), or ``None``
            if the gesture was filtered out.
        """
        gesture = result.gesture
        confidence = result.confidence

        # Layer 1: confidence filter
        if gesture != Gesture.NONE and confidence < self._conf_thresh:
            logger.debug(
                "Reliability: rejected %s (confidence=%.2f < %.2f)",
                gesture.name,
                confidence,
                self._conf_thresh,
            )
            gesture = Gesture.NONE

        # Layer 2: temporal smoothing
        if gesture == self._streak_gesture:
            self._streak_count += 1
        else:
            self._streak_gesture = gesture
            self._streak_count = 1

        if self._streak_count < self._stable_frames:
            # Not stable yet — no command
            return None

        # If gesture dropped to NONE, record for hysteresis
        if gesture == Gesture.NONE:
            if self._last_fired != Gesture.NONE:
                self._gesture_dropped = True
                logger.debug("Reliability: gesture dropped — hysteresis reset.")
            return None

        # Layer 3: hysteresis
        if self._hysteresis:
            if gesture == self._last_fired and not self._gesture_dropped:
                return None

        # Layer 4: cooldown
        cmd = gesture.value
        now = time.monotonic()
        last_t = self._last_send_time.get(cmd, 0.0)
        if (now - last_t) < self._cooldown_sec:
            remaining = self._cooldown_sec - (now - last_t)
            logger.debug(
                "Reliability: cooldown active for %s (%.1fs remaining)",
                cmd,
                remaining,
            )
            return None

        # --- All layers passed — authorise command -----------------------
        self._last_send_time[cmd] = now
        self._last_fired = gesture
        self._gesture_dropped = False
        logger.info(
            "Reliability: APPROVED %s (confidence=%.2f, streak=%d)",
            cmd,
            confidence,
            self._streak_count,
        )
        return cmd

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def streak_count(self) -> int:
        """Current consecutive-frame streak count."""
        return self._streak_count

    @property
    def streak_gesture(self) -> Gesture:
        """Gesture in the current streak."""
        return self._streak_gesture

    def cooldown_remaining(self, command: str) -> float:
        """Seconds of cooldown remaining for *command* (0.0 if none)."""
        last_t = self._last_send_time.get(command, 0.0)
        remaining = self._cooldown_sec - (time.monotonic() - last_t)
        return max(remaining, 0.0)

    def reset(self) -> None:
        """Reset all internal state."""
        self._streak_gesture = Gesture.NONE
        self._streak_count = 0
        self._last_fired = Gesture.NONE
        self._last_send_time.clear()
        self._gesture_dropped = True
        logger.info("Reliability filter reset.")
