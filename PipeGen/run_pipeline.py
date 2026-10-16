#!/usr/bin/env python3
"""
CraftifAI PipeGen — Main Pipeline Entry Point
===============================================
Orchestrates: capture → pose estimate → classify → reliability filter →
command send → visualize → log.

Usage
-----
    python run_pipeline.py                          # defaults from config.yaml
    python run_pipeline.py --dry-run                # no serial, just log
    python run_pipeline.py --port COM5 --no-viz     # override port, hide GUI
    python run_pipeline.py --config my_config.yaml  # custom config file

Press **q** in the visualisation window (or Ctrl+C in the terminal) to quit.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ``pipeline`` package resolves
# even when invoked directly (``python run_pipeline.py``).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.camera import Camera
from pipeline.command_sender import BaseCommandSender, create_command_sender
from pipeline.gesture_classifier import GestureClassifier, GestureResult
from pipeline.logger import setup_logging
from pipeline.pose_estimator import BasePoseEstimator, create_pose_estimator
from pipeline.reliability import ReliabilityFilter
from pipeline.visualizer import Visualizer

logger = logging.getLogger("pipegen")

# ======================================================================
# Configuration helpers
# ======================================================================

def load_config(path: str) -> Dict[str, Any]:
    """Load and return the YAML config file as a dict."""
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg or {}


def apply_cli_overrides(cfg: Dict[str, Any], args: argparse.Namespace) -> None:
    """Mutate *cfg* with any CLI-supplied overrides."""
    if args.port is not None:
        cfg.setdefault("serial", {})["port"] = args.port
    if args.dry_run:
        cfg.setdefault("serial", {})["dry_run"] = True
    if args.no_viz:
        cfg.setdefault("visualization", {})["enabled"] = False
    if args.camera is not None:
        cfg.setdefault("camera", {})["index"] = args.camera
    if args.log_level is not None:
        cfg.setdefault("logging", {})["level"] = args.log_level


# ======================================================================
# CLI
# ======================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CraftifAI PipeGen — GestureLink AI vision pipeline",
    )
    p.add_argument(
        "--config",
        default=str(_PROJECT_ROOT / "config.yaml"),
        help="Path to YAML config file (default: config.yaml)",
    )
    p.add_argument("--port", help="Serial port override (e.g. COM3)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Log commands instead of sending over serial",
    )
    p.add_argument(
        "--no-viz",
        action="store_true",
        help="Disable the OpenCV visualisation window",
    )
    p.add_argument(
        "--camera",
        type=int,
        help="Camera device index override",
    )
    p.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level override",
    )
    return p


# ======================================================================
# Pipeline
# ======================================================================

class Pipeline:
    """Top-level pipeline orchestrator.

    Owns the lifecycle of every sub-module and runs the main loop.
    """

    def __init__(self, cfg: Dict[str, Any]) -> None:
        self._cfg = cfg
        self._running = False

        # Modules (initialised in .start())
        self._camera: Camera = None  # type: ignore[assignment]
        self._estimator: BasePoseEstimator = None  # type: ignore[assignment]
        self._classifier: GestureClassifier = None  # type: ignore[assignment]
        self._reliability: ReliabilityFilter = None  # type: ignore[assignment]
        self._sender: BaseCommandSender = None  # type: ignore[assignment]
        self._visualizer: Visualizer | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise every module and open resources."""
        cam_cfg = self._cfg.get("camera", {})
        self._camera = Camera(
            index=cam_cfg.get("index", 0),
            width=cam_cfg.get("width", 640),
            height=cam_cfg.get("height", 480),
            fps=cam_cfg.get("fps", 30),
        )
        if not self._camera.open():
            raise RuntimeError("Cannot open camera — aborting.")

        self._estimator = create_pose_estimator(self._cfg.get("pose", {}))
        self._estimator.initialize()

        gest_cfg = self._cfg.get("gesture", {})
        rel_cfg = self._cfg.get("reliability", {})
        self._classifier = GestureClassifier(
            raise_threshold=gest_cfg.get("raise_threshold", 0.10),
            confidence_threshold=rel_cfg.get("confidence_threshold", 0.5),
        )

        self._reliability = ReliabilityFilter(
            confidence_threshold=rel_cfg.get("confidence_threshold", 0.5),
            stable_frames=rel_cfg.get("stable_frames", 5),
            cooldown_seconds=rel_cfg.get("cooldown_seconds", 3.0),
            hysteresis=rel_cfg.get("hysteresis", True),
        )

        self._sender = create_command_sender(self._cfg)
        if not self._sender.open():
            logger.warning("Command sender failed to open — commands will not be sent.")

        viz_cfg = self._cfg.get("visualization", {})
        if viz_cfg.get("enabled", True):
            self._visualizer = Visualizer(
                show_skeleton=viz_cfg.get("show_skeleton", True),
                show_gesture=viz_cfg.get("show_gesture", True),
                show_confidence=viz_cfg.get("show_confidence", True),
                show_command_history=viz_cfg.get("show_command_history", True),
                max_history=viz_cfg.get("max_history", 5),
            )

        logger.info("Pipeline initialised — all modules ready.")

    def stop(self) -> None:
        """Release every module in reverse order."""
        logger.info("Shutting down pipeline…")
        if self._visualizer is not None:
            self._visualizer.close()
        if self._sender is not None:
            self._sender.close()
        if self._estimator is not None:
            self._estimator.release()
        if self._camera is not None:
            self._camera.close()
        logger.info("Pipeline shut down cleanly.")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Execute the main capture → process → send loop."""
        self._running = True
        frame_count = 0
        t_start = time.monotonic()

        logger.info("Pipeline running.  Press 'q' in the window or Ctrl+C to stop.")

        try:
            while self._running:
                # 1. Capture
                ok, frame = self._camera.read()
                if not ok or frame is None:
                    logger.warning("Frame grab failed — skipping.")
                    continue

                frame_count += 1

                # 2. Pose estimation
                pose = self._estimator.estimate(frame)

                # 3. Gesture classification
                gesture = self._classifier.classify(pose)

                # 4. Reliability filter
                command = self._reliability.update(gesture)

                # 5. Send command (if approved)
                if command is not None:
                    ack = self._sender.send(command)
                    logger.info(
                        "Command sent: %s  ACK=%s",
                        command,
                        "OK" if ack else "FAIL",
                    )
                    if self._visualizer is not None:
                        self._visualizer.record_command(command)

                # 6. Visualize
                if self._visualizer is not None:
                    self._visualizer.draw(frame, pose, gesture, self._reliability)
                    if not self._visualizer.show(frame):
                        logger.info("Quit signal received from visualiser.")
                        break

                # Periodic FPS log
                if frame_count % 300 == 0:
                    elapsed = time.monotonic() - t_start
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    logger.info("Processed %d frames  (%.1f FPS)", frame_count, fps)

        except KeyboardInterrupt:
            logger.info("Ctrl+C received.")
        finally:
            self._running = False

    def request_stop(self) -> None:
        """Signal the run-loop to exit."""
        self._running = False


# ======================================================================
# Entry point
# ======================================================================

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load config
    cfg = load_config(args.config)
    apply_cli_overrides(cfg, args)

    # Logging
    log_cfg = cfg.get("logging", {})
    setup_logging(
        level=log_cfg.get("level", "INFO"),
        json_output=log_cfg.get("json_output", False),
        log_file=log_cfg.get("log_file"),
    )

    # Build & run pipeline
    pipeline = Pipeline(cfg)

    # Graceful shutdown on SIGINT / SIGTERM
    def _handle_signal(signum, frame):  # type: ignore[no-untyped-def]
        logger.info("Signal %d received — stopping.", signum)
        pipeline.request_stop()

    signal.signal(signal.SIGINT, _handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle_signal)

    try:
        pipeline.start()
        pipeline.run()
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
