# Host acceptance tests

Run the hardware-independent command-policy tests on Windows with the available GCC and Ninja host tools:

```powershell
cmake -G Ninja -S firmware/tests/unit -B build-host-ninja
cmake --build build-host-ninja
ctest --test-dir build-host-ninja --output-on-failure
```

The simulator UART console is configured for GPIO 43 TX and GPIO 44 RX at 115200 baud. Send one command per line (`LIGHT_ON` or `LIGHT_OFF`) in Wokwi's serial monitor. The onboard LED model is externalized in `diagram.json` on GPIO 38; it starts OFF and changes only after an exact accepted command.
