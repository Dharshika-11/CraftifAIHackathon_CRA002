# GestureLink AI Requirement Traceability

| ID | Requirement | Implementation | Acceptance coverage | Status |
|---|---|---|---|---|
| GL-REQ-01 | Control LED on GPIO 38 | `firmware/configs/app_config.h`, `firmware/bsp/board.h`, `firmware/platforms/esp32/gesture_platform.c` | `test_board_led_configuration`, `test_startup_initializes_led_off`, `test_light_on_turns_led_on`, `test_light_off_turns_led_off` | Host tests passed; physical output not observed |
| GL-REQ-02 | Accept LIGHT_ON and LIGHT_OFF via configurable input | `firmware/configs/app_config.h`, `firmware/services/gesture_service.c`, `firmware/platforms/esp32/gesture_platform.c` | `test_light_on_turns_led_on`, `test_light_off_turns_led_off`, `test_crlf_is_accepted`, `test_fragmented_line_assembly` | Host tests passed |
| GL-REQ-03 | Initialize LED OFF | `gesture_service_run()` initializes output before reading commands; adapter configures GPIO output then sets logical OFF | `test_startup_initializes_led_off`, `test_service_processes_commands_and_reports_results` | Host tests passed; hardware startup not observed |
| GL-REQ-04 | Reject invalid commands and log results via UART | Exact matching rejects malformed input; adapter logs with `ESP_LOGI("Command accepted: %s")` / `ESP_LOGW("Command rejected: %s")` | `test_invalid_commands_never_turn_led_on`, `test_service_processes_commands_and_reports_results`, `test_service_reports_overlong_line_as_invalid` | Host tests passed; UART hardware output not observed |
| GL-REQ-05 | Acceptance tests for commands, invalid input, startup behavior | `firmware/tests/unit/gesture_service_acceptance.c`, host CMake project | 10 named acceptance tests | Executed: all 10 passed |
| GL-REQ-06 | Requirement-linked tests and traceability report | This report plus named test runner in `firmware/tests/unit/gesture_service_acceptance.c` | Requirement IDs map to implementation/test rows above | Host tests passed |
| GL-REQ-07 | Suitable for later Wokwi simulation | `wokwi.toml`, `diagram.json`, `firmware/docs/overview.md`, `firmware/docs/wokwi-simulation.md` | UART/GPIO scenario and safe setup instructions documented | ESP32-S3 configuration and artifacts inspected; Wokwi runtime not verified |

## Verification evidence

- ESP-IDF target configuration: ESP32-S3; the latest ESP-IDF build completed successfully during this Wokwi preparation.
- ESP-IDF 5.5.5 toolchain headers were located at `C:/esp/v5.5.5/esp-idf`.
- Host command: `cmake -G Ninja -S firmware/tests/unit -B build-host-ninja`; `cmake --build build-host-ninja`; `ctest --test-dir build-host-ninja --output-on-failure`.
- Result: 1/1 CTest test passed; the executable reported all 10 named acceptance tests passed.
- No firmware source changed during this correction; no ESP-IDF rebuild was required.
- Wokwi tool status: `wokwi-cli` not found and no `WOKWI_CLI_TOKEN` is set. Wokwi simulation was not executed; runtime LED and serial observations remain unverified.
- `wokwi.toml` now uses `build/flasher_args.json`, the ESP-IDF full-image manifest, and `build/gesturelink_ai.elf`; see `firmware/docs/wokwi-simulation.md`.
- No physical hardware was flashed.
