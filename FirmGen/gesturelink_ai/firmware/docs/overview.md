# GestureLink AI ESP32-S3 Firmware

## Purpose

A UART command-driven LED controller for the GestureLink ESP32-S3 N16R8 board. The firmware configures the active-high LED on GPIO 38 OFF before processing command lines. It accepts exact, case-sensitive `LIGHT_ON` and `LIGHT_OFF` commands and reports accepted or rejected commands over the UART console.

## Hardware and console map

| Signal | ESP32-S3 GPIO | Configuration |
|---|---:|---|
| Status LED | 38 | Active-high; OFF is low |
| UART console TX | 43 | 115200 baud |
| UART console RX | 44 | 115200 baud |

Commands are line-oriented. The maximum supported command payload is 32 bytes. CR, LF, and CRLF line endings are accepted; overlong input is drained and rejected.

## Modules

- `firmware/app/app.c` starts the application and command service.
- `firmware/services/gesture_service.c` performs hardware-independent exact command matching and runs the line-processing loop.
- `firmware/interfaces/gesture_io.h` defines the portable LED/input/reporting callback contract.
- `firmware/platforms/esp32/gesture_platform.c` implements GPIO and console access with ESP-IDF APIs.
- `firmware/bsp/board.h` identifies GPIO 38 and the active-high LED polarity.

## Build and simulation

Build with ESP-IDF v5.5.5 for ESP32-S3 using the repository's normal `idf.py build` workflow or the IDE's **Build project** action. Application pin and command settings are in `firmware/configs/app_config.h`; UART console pin selection is also reflected in `sdkconfig.defaults`.

Wokwi project configuration is provided by `wokwi.toml` and `diagram.json`. The Wokwi firmware path uses ESP-IDF's `build/flasher_args.json` manifest (full image: bootloader, partition table, application); `build/gesturelink_ai.elf` supplies symbols. Open the simulator serial monitor at 115200 baud and send one command per line. The simulated GPIO 38 LED is connected active-high through a 220-ohm resistor. See `firmware/docs/wokwi-simulation.md` for non-destructive setup instructions and the manual verification checklist; no Wokwi runtime result is claimed until a simulation has actually run.

Run host acceptance tests with the instructions in `firmware/tests/unit/README.md`. Physical hardware flashing has not been performed.
