"""CLI configuration file helpers."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def _require_type(value: Any, expected_type: type[Any], field_name: str) -> Any:
    """Validate a config field type."""
    if not isinstance(value, expected_type):
        raise ValueError(f"Config field {field_name!r} must be a {expected_type.__name__}")
    return value


def _require_number(value: Any, field_name: str) -> float:
    """Validate a numeric config field."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Config field {field_name!r} must be a number")
    return float(value)


def _require_positive_int(value: Any, field_name: str) -> int:
    """Validate a positive integer config field."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Config field {field_name!r} must be an integer")
    if value <= 0:
        raise ValueError(f"Config field {field_name!r} must be greater than zero")
    return value


def _device_from_config(data: dict[str, Any]) -> str | None:
    """Resolve the configured device identifier from known aliases."""
    for key in ("device", "device_id", "mac", "uuid"):
        value = data.get(key)
        if value is not None:
            return _require_type(value, str, key)
    return None


def load_cli_config(path: str) -> dict[str, str | int | float | bool | None]:
    """Load CLI options from a TOML configuration file.

    Supported top-level keys:
    - ``device`` / ``device_id`` / ``mac`` / ``uuid``
    - ``interval``

    Supported ``[mqtt]`` keys:
    - ``enabled``
    - ``host``
    - ``port``
    - ``username``
    - ``password``
    - ``name``
    - ``prefix``
    - ``retain``
    """
    config_path = Path(path)
    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"Config file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not parse config file {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Config file {config_path} must contain a TOML table")

    resolved: dict[str, str | int | float | bool | None] = {}

    device_id = _device_from_config(raw)
    if device_id is not None:
        resolved["mac"] = device_id

    if "interval" in raw:
        resolved["interval"] = _require_number(raw["interval"], "interval")

    mqtt_config = raw.get("mqtt", {})
    if mqtt_config is None:
        mqtt_config = {}
    if not isinstance(mqtt_config, dict):
        raise ValueError(f"Config field 'mqtt' must be a table in {config_path}")

    mqtt_seen = False
    if "enabled" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt"] = _require_type(mqtt_config["enabled"], bool, "mqtt.enabled")
    if "host" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_host"] = _require_type(mqtt_config["host"], str, "mqtt.host")
    if "port" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_port"] = _require_positive_int(mqtt_config["port"], "mqtt.port")
    if "username" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_username"] = _require_type(
            mqtt_config["username"], str, "mqtt.username"
        )
    if "password" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_password"] = _require_type(
            mqtt_config["password"], str, "mqtt.password"
        )
    if "name" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_name"] = _require_type(mqtt_config["name"], str, "mqtt.name")
    if "prefix" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_prefix"] = _require_type(
            mqtt_config["prefix"], str, "mqtt.prefix"
        )
    if "retain" in mqtt_config:
        mqtt_seen = True
        resolved["mqtt_retain"] = _require_type(
            mqtt_config["retain"], bool, "mqtt.retain"
        )

    if mqtt_seen and "mqtt" not in resolved:
        resolved["mqtt"] = True

    return resolved