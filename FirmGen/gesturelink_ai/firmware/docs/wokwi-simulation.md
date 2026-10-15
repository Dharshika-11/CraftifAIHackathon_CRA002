# Wokwi Simulation Setup and Verification Record

## Project-to-simulator mapping

- This is an ESP-IDF project targeting `esp32s3`; `sdkconfig.defaults` sets `CONFIG_IDF_TARGET="esp32s3"`. Wokwi's documented ESP32 simulator includes the ESP32-S3 and lists `board-esp32-s3-devkitc-1` as an ESP32-S3 model.
- The Wokwi diagram uses part type `board-esp32-s3-devkitc-1`, an ESP32-S3 board. It is a simulator model, not an exact emulation of the GestureLink N16R8 carrier/board.
- `firmware/configs/app_config.h` assigns `APP_LED_GPIO` to 38. `firmware/bsp/board.h` maps `BOARD_LED_GPIO` to it and sets `BOARD_LED_ACTIVE_LEVEL` to 1. The adapter's `board_led_level(false)` is low and `board_led_level(true)` is high. It configures GPIO output and writes OFF before the command loop.
- The diagram wires GPIO 38 -> 220 ohm resistor -> green LED anode; the cathode returns to GND. This models an active-high LED.
- The console uses TX GPIO 43, RX GPIO 44 and 115200 baud according to sdkconfig defaults and app configuration.

## Correct ESP-IDF firmware input

The project build produced:

- `build/gesturelink_ai.elf` (ELF with symbols; referenced by the `elf` field).
- `build/gesturelink_ai.bin` (application-only image).
- `build/flasher_args.json` (ESP-IDF flash manifest that identifies application image, bootloader, partition table and offsets).

For an ESP-IDF project Wokwi recommends `build/flasher_args.json` as the `firmware` path so it loads a complete image. `wokwi.toml` now references that manifest and the ELF. Do not select the application-only `.bin` as a complete image.

The current root-level `wokwi.toml` and `diagram.json` describe this project's own simulation configuration. To avoid replacing or modifying an existing Wokwi project, open a separate Wokwi workspace/configuration for this directory, or duplicate the directory to a new location and select that copy's `wokwi.toml`. Do not run `wokwi-cli init`, because it can generate/replace project configuration files.

## Manual simulation steps

1. Build this directory with ESP-IDF v5.5.5 using the IDE's build action or `idf.py build`.
2. In VS Code, use **Wokwi: Select Config File** to select this project's `wokwi.toml` if the current workspace is your existing Wokwi project. Alternatively, open a separate copy of this project in a new window. The Wokwi extension does not compile the firmware; build first.
3. Start the Wokwi simulator. Choose `build/flasher_args.json` as the ESP-IDF full firmware image if the extension prompts for a firmware file. The ELF path provides symbols.
4. Open the serial monitor at 115200 baud. Record the startup log and verify the external GPIO 38 LED is OFF.
5. Send `LIGHT_ON` followed by Enter. Record the `Command accepted: LIGHT_ON` log and observe the LED turn ON.
6. Send `LIGHT_OFF` followed by Enter. Record the `Command accepted: LIGHT_OFF` log and observe the LED turn OFF.
7. Send `UNSUPPORTED` followed by Enter. Record `Command rejected: UNSUPPORTED` and confirm the LED remains OFF.
8. Capture the serial output and a screenshot showing the simulator/LED state after each command. These observations must come from a running Wokwi instance; static source/build inspection is not simulation evidence.

## Current execution status

Build artifacts and configuration have been inspected. `wokwi-cli` is not installed/available in this environment and no `WOKWI_CLI_TOKEN` is configured, so an automated cloud simulation could not be started here. No Wokwi run or LED behavior has been observed in this session. Physical hardware was not flashed.
