"""
CraftifAI PipeGen — Command Sender
====================================
Transports validated commands to the ESP32-S3 over Serial UART, with an
optional MQTT stub and a dry-run mode for development.
"""

from __future__ import annotations

import abc
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ======================================================================
# Abstract transport
# ======================================================================

class BaseCommandSender(abc.ABC):
    """Interface for all command transport backends."""

    @abc.abstractmethod
    def open(self) -> bool:
        """Open the transport channel. Return ``True`` on success."""

    @abc.abstractmethod
    def send(self, command: str) -> bool:
        """Send *command* and return ``True`` if an ACK was received."""

    @abc.abstractmethod
    def close(self) -> None:
        """Close the transport channel."""


# ======================================================================
# Serial UART sender
# ======================================================================

class SerialCommandSender(BaseCommandSender):
    """Send plain-text commands over a serial UART link using *pyserial*.

    The firmware is expected to:
    * Read one line per command (terminated by ``\\n``).
    * Respond with a JSON ACK: ``{"status": "ok", "cmd": "..."}``

    Parameters
    ----------
    port : str
        Serial port name (e.g. ``"COM3"`` or ``"/dev/ttyUSB0"``).
    baudrate : int
        Baud rate (default ``115200``).
    timeout : float
        Read timeout in seconds (default ``1.0``).
    """

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial = None  # type: ignore[assignment]

    def open(self) -> bool:
        try:
            import serial  # type: ignore[import-untyped]

            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baudrate,
                timeout=self._timeout,
            )
            # Give the ESP32-S3 a moment to reset after opening serial
            time.sleep(0.5)
            logger.info(
                "Serial port %s opened at %d baud.", self._port, self._baudrate
            )
            return True
        except Exception as exc:
            logger.error("Failed to open serial port %s: %s", self._port, exc)
            return False

    def send(self, command: str) -> bool:
        """Send *command* followed by ``\\n`` and wait for a JSON ACK."""
        if self._serial is None or not self._serial.is_open:
            logger.error("Serial port is not open — cannot send %r.", command)
            return False

        payload = (command + "\n").encode("ascii")
        try:
            self._serial.write(payload)
            self._serial.flush()
            logger.info("TX → %r", command)
        except Exception as exc:
            logger.error("Serial write error: %s", exc)
            return False

        # --- Wait for ACK ------------------------------------------------
        return self._read_ack(command)

    def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("Serial port %s closed.", self._port)

    # ------------------------------------------------------------------

    def _read_ack(self, expected_cmd: str) -> bool:
        """Read one line from serial and validate as JSON ACK."""
        try:
            raw = self._serial.readline()
            if not raw:
                logger.warning("No ACK received (timeout).")
                return False

            line = raw.decode("ascii", errors="replace").strip()
            logger.debug("RX ← %s", line)

            ack = json.loads(line)
            if ack.get("status") == "ok" and ack.get("cmd") == expected_cmd:
                logger.info("ACK received for %r ✓", expected_cmd)
                return True
            else:
                logger.warning("Unexpected ACK payload: %s", ack)
                return False
        except json.JSONDecodeError:
            logger.warning("ACK was not valid JSON: %r", raw)
            return False
        except Exception as exc:
            logger.error("Error reading ACK: %s", exc)
            return False


# ======================================================================
# Dry-run sender (for development / testing)
# ======================================================================

class DryRunCommandSender(BaseCommandSender):
    """Logs commands without actually sending them.

    Useful for testing the pipeline without a connected ESP32.
    """

    def open(self) -> bool:
        logger.info("[DRY-RUN] Command sender ready (no serial connection).")
        return True

    def send(self, command: str) -> bool:
        logger.info("[DRY-RUN] Would send → %r", command)
        return True

    def close(self) -> None:
        logger.info("[DRY-RUN] Command sender closed.")


# ======================================================================
# MQTT sender (stub)
# ======================================================================

class MQTTCommandSender(BaseCommandSender):
    """Publish commands to an MQTT topic.

    This is a minimal stub — expand as needed.

    Parameters
    ----------
    broker : str
        MQTT broker hostname.
    port : int
        MQTT broker port (default ``1883``).
    topic : str
        Topic to publish commands on.
    """

    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "gesturelink/commands",
    ) -> None:
        self._broker = broker
        self._port = port
        self._topic = topic
        self._client = None  # type: ignore[assignment]

    def open(self) -> bool:
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-untyped]

            self._client = mqtt.Client()
            self._client.connect(self._broker, self._port)
            self._client.loop_start()
            logger.info("MQTT connected to %s:%d", self._broker, self._port)
            return True
        except Exception as exc:
            logger.error("MQTT connection failed: %s", exc)
            return False

    def send(self, command: str) -> bool:
        if self._client is None:
            logger.error("MQTT client not connected.")
            return False
        try:
            info = self._client.publish(self._topic, command)
            info.wait_for_publish()
            logger.info("MQTT published %r to %s", command, self._topic)
            return True
        except Exception as exc:
            logger.error("MQTT publish error: %s", exc)
            return False

    def close(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("MQTT client disconnected.")


# ======================================================================
# Factory
# ======================================================================

def create_command_sender(cfg: dict) -> BaseCommandSender:
    """Build a command sender from the loaded config.

    Parameters
    ----------
    cfg : dict
        The full YAML config dict (not just a sub-section).

    Returns
    -------
    BaseCommandSender
    """
    serial_cfg = cfg.get("serial", {})

    if serial_cfg.get("dry_run", False):
        return DryRunCommandSender()

    mqtt_cfg = cfg.get("mqtt", {})
    if mqtt_cfg.get("enabled", False):
        return MQTTCommandSender(
            broker=mqtt_cfg.get("broker", "localhost"),
            port=mqtt_cfg.get("port", 1883),
            topic=mqtt_cfg.get("topic", "gesturelink/commands"),
        )

    return SerialCommandSender(
        port=serial_cfg.get("port", "COM3"),
        baudrate=serial_cfg.get("baudrate", 115200),
        timeout=serial_cfg.get("timeout", 1.0),
    )
