"""MQTT publishing helpers for wattcycle-ble."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from .models import AnalogQuantity, ProductInfo, WarningInfo

_TOPIC_SEGMENT_RE = re.compile(r"[^A-Za-z0-9_-]+")


def sanitize_topic_segment(value: str) -> str:
    """Normalize a string so it is safe to use in an MQTT topic."""
    segment = _TOPIC_SEGMENT_RE.sub("_", value.strip())
    return segment.strip("_") or "battery"


def default_battery_name(
    device_id: str,
    product_info: ProductInfo | None,
    override: str | None = None,
) -> str:
    """Choose the MQTT battery name from override, serial, or device id."""
    candidate = override
    if not candidate and product_info is not None:
        candidate = product_info.serial_number
    if not candidate:
        candidate = device_id
    return sanitize_topic_segment(candidate)


def build_topic_root(battery_name: str, prefix: str = "") -> str:
    """Build the MQTT topic root for a battery."""
    parts = []
    normalized_prefix = prefix.strip("/")
    if normalized_prefix:
        parts.extend(
            sanitize_topic_segment(part)
            for part in normalized_prefix.split("/")
            if part
        )
    parts.append(sanitize_topic_segment(battery_name))
    return "/".join(parts)


def build_product_info_fields(product_info: ProductInfo) -> dict[str, str]:
    """Convert product information to MQTT field payloads."""
    fields: dict[str, str] = {}
    if product_info.firmware_version:
        fields["firmware"] = product_info.firmware_version
    if product_info.manufacturer_name:
        fields["manufacturer"] = product_info.manufacturer_name
    if product_info.serial_number:
        fields["serial"] = product_info.serial_number
    return fields


def build_analog_quantity_fields(aq: AnalogQuantity) -> dict[str, str]:
    """Convert analog battery data to MQTT field payloads."""
    fields = {
        "SOC": str(aq.soc),
        "Current": f"{aq.current:.1f}",
        "Voltage": f"{aq.module_voltage:.2f}",
        "Rcapacity": f"{aq.remaining_capacity:.1f}",
        "Tcapacity": f"{aq.total_capacity:.1f}",
        "Dcapacity": f"{aq.design_capacity:.1f}",
        "Cycles": str(aq.cycle_number),
        "MOS": f"{aq.mos_temperature:.1f}",
        "PCB": f"{aq.pcb_temperature:.1f}",
    }

    for index, voltage in enumerate(aq.cell_voltages, start=1):
        fields[f"Cell{index}V"] = f"{voltage:.3f}"

    if aq.cell_voltages:
        delta_mv = (max(aq.cell_voltages) - min(aq.cell_voltages)) * 1000.0
        fields["Delta"] = f"{delta_mv:.1f}"

    for index, temperature in enumerate(aq.cell_temperatures, start=1):
        fields[f"Cell{index}Temp"] = f"{temperature:.1f}"

    if aq.soh is not None:
        fields["SOH"] = str(aq.soh)
    if aq.cumulative_capacity is not None:
        fields["CumulativeCapacity"] = f"{aq.cumulative_capacity:.1f}"
    if aq.remaining_time_min is not None:
        fields["RemainingTimeMin"] = str(aq.remaining_time_min)
    if aq.balance_current is not None:
        fields["BalanceCurrent"] = f"{aq.balance_current:.1f}"

    return fields


def build_warning_info_fields(warning_info: WarningInfo) -> dict[str, str]:
    """Convert warning data to MQTT field payloads."""
    return {
        "protections": json.dumps(warning_info.protections),
        "faults": json.dumps(warning_info.faults),
        "warnings": json.dumps(warning_info.warnings),
    }


@dataclass(slots=True)
class MqttConfig:
    """MQTT connection options."""

    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = None
    topic_prefix: str = ""
    retain: bool = False
    connect_timeout: float = 5.0


class MqttPublisher:
    """Publish battery fields to an MQTT broker."""

    def __init__(self, config: MqttConfig):
        try:
            from paho.mqtt import client as mqtt_client
        except ImportError as exc:  # pragma: no cover - runtime dependency check
            raise RuntimeError(
                "MQTT support requires paho-mqtt. Reinstall the package or run "
                "`python -m pip install -e .`."
            ) from exc

        self._config = config
        self._mqtt_client = mqtt_client
        self._client: Any = mqtt_client.Client()
        if config.username:
            self._client.username_pw_set(config.username, config.password)
        self._loop_started = False

    def connect(self) -> None:
        """Connect to the MQTT broker."""
        try:
            self._client.connect(self._config.host, self._config.port, keepalive=60)
        except OSError as exc:
            raise RuntimeError(
                f"Could not connect to MQTT broker at {self._config.host}:{self._config.port}: {exc}"
            ) from exc

        self._client.loop_start()
        self._loop_started = True

        deadline = time.monotonic() + self._config.connect_timeout
        while not self._client.is_connected():
            if time.monotonic() >= deadline:
                self.disconnect()
                raise RuntimeError(
                    f"Timed out connecting to MQTT broker at {self._config.host}:{self._config.port}"
                )
            time.sleep(0.05)

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        try:
            if self._client.is_connected():
                self._client.disconnect()
        finally:
            if self._loop_started:
                self._client.loop_stop()
                self._loop_started = False

    def publish_fields(self, topic_root: str, fields: dict[str, str]) -> None:
        """Publish multiple field payloads below a topic root."""
        for field, payload in fields.items():
            info = self._client.publish(
                f"{topic_root}/{field}",
                payload,
                retain=self._config.retain,
            )
            info.wait_for_publish()
            if info.rc != 0:
                error_message = self._mqtt_client.error_string(info.rc)
                raise RuntimeError(f"Failed to publish {topic_root}/{field}: {error_message}")