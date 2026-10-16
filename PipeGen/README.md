# CraftifAI PipeGen — GestureLink AI Vision Pipeline

> Real-time human pose estimation → gesture classification → ESP32-S3 command dispatch.

---

## Overview

**PipeGen** is the computer-vision component of the *GestureLink AI* project.
It captures webcam video, runs MediaPipe Pose estimation, classifies arm-raise
gestures, and sends validated commands to an ESP32-S3 micro-controller over
serial UART.

### Gesture → Command Mapping

| Gesture           | Command String | Trigger                                    |
|-------------------|----------------|--------------------------------------------|
| Right arm raised  | `LIGHT_ON`     | Right wrist significantly above shoulder   |
| Left arm raised   | `LIGHT_OFF`    | Left wrist significantly above shoulder    |
| Both arms raised  | `SERVO_OPEN`   | Both wrists significantly above shoulders  |
| None / ambiguous  | *(nothing)*    | No command sent                            |

---

## Project Structure

```
PipeGen/
├── README.md                       # This file
├── requirements.txt                # Python dependencies
├── config.yaml                     # All tunable parameters
├── run_pipeline.py                 # Main entry point
├── pipeline/
│   ├── __init__.py
│   ├── camera.py                   # OpenCV camera wrapper
│   ├── pose_estimator.py           # MediaPipe / TensorRT backends
│   ├── gesture_classifier.py       # Keypoint → gesture classification
│   ├── command_sender.py           # Serial / MQTT / dry-run transport
│   ├── reliability.py              # Confidence, smoothing, cooldown, hysteresis
│   ├── visualizer.py               # Debug overlay (skeleton, state, history)
│   └── logger.py                   # Structured logging (text / JSON)
└── tests/
    ├── __init__.py
    └── test_gesture_classifier.py  # Unit tests
```

---

## Quick Start

### 1. Install dependencies

```bash
cd PipeGen
pip install -r requirements.txt
```

### 2. Edit `config.yaml`

Set `serial.port` to the COM port your ESP32-S3 is connected to (e.g. `COM3`
on Windows, `/dev/ttyUSB0` on Linux).

### 3. Run the pipeline

```bash
# Default — webcam + serial + visualisation
python run_pipeline.py

# Dry-run (no serial, just log)
python run_pipeline.py --dry-run

# Override serial port
python run_pipeline.py --port COM5

# Headless (no OpenCV window)
python run_pipeline.py --no-viz

# Custom config
python run_pipeline.py --config my_config.yaml

# Debug logging
python run_pipeline.py --log-level DEBUG
```

Press **q** in the visualisation window or **Ctrl+C** in the terminal to stop.

---

## Configuration Reference (`config.yaml`)

| Section            | Key                        | Default       | Description                                    |
|--------------------|----------------------------|---------------|------------------------------------------------|
| `camera`           | `index`                    | `0`           | Camera device index                            |
|                    | `width` / `height`         | `640` / `480` | Capture resolution                             |
|                    | `fps`                      | `30`          | Target frame rate                              |
| `pose`             | `backend`                  | `mediapipe`   | `"mediapipe"` or `"tensorrt"` (future)         |
|                    | `model_complexity`         | `1`           | 0 = lite, 1 = full, 2 = heavy                 |
|                    | `min_detection_confidence` | `0.5`         | Person-detection confidence                    |
|                    | `min_tracking_confidence`  | `0.5`         | Landmark-tracking confidence                   |
| `gesture`          | `raise_threshold`          | `0.10`        | Norm-Y diff for "arm raised"                   |
| `reliability`      | `confidence_threshold`     | `0.5`         | Min landmark visibility                        |
|                    | `stable_frames`            | `5`           | Consecutive frames before firing               |
|                    | `cooldown_seconds`         | `3.0`         | Re-send cooldown per command                   |
|                    | `hysteresis`               | `true`        | Gesture must drop before re-trigger            |
| `serial`           | `port`                     | `COM3`        | Serial port                                    |
|                    | `baudrate`                 | `115200`      | Baud rate                                      |
|                    | `timeout`                  | `1.0`         | Read timeout (seconds)                         |
|                    | `dry_run`                  | `false`       | Log-only mode                                  |
| `mqtt`             | `enabled`                  | `false`       | Enable MQTT transport                          |
| `visualization`    | `enabled`                  | `true`        | Show debug window                              |
| `logging`          | `level`                    | `INFO`        | Log level                                      |
|                    | `json_output`              | `false`       | Structured JSON log lines                      |
|                    | `log_file`                 | `null`        | Optional file path                             |

---

## Reliability Layers

Commands pass through four sequential filters before dispatch:

1. **Confidence filter** — landmarks below `confidence_threshold` are ignored.
2. **Temporal smoothing** — the same gesture must persist for `stable_frames`
   consecutive frames.
3. **Hysteresis** — once a gesture fires, it must return to `NONE` before the
   same gesture can fire again.
4. **Cooldown** — the same command cannot be re-sent within `cooldown_seconds`.

---

## Running Tests

```bash
cd PipeGen
python -m pytest tests/ -v
```

---

## ESP32-S3 Firmware Protocol

The firmware reads ASCII lines from UART at 115200 baud:

```
LIGHT_ON\n
LIGHT_OFF\n
SERVO_OPEN\n
```

It responds with a JSON ACK:

```json
{"status": "ok", "cmd": "LIGHT_ON"}
```

---

## License

Internal — CraftifAI / GestureLink AI project.
