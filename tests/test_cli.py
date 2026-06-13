"""CLI and MQTT helper tests."""

from wattcycle_ble.cli import build_parser, resolve_configured_args
from wattcycle_ble.models import AnalogQuantity, ProductInfo, WarningInfo
from wattcycle_ble.mqtt import (
    build_analog_quantity_fields,
    build_product_info_fields,
    build_topic_root,
    build_warning_info_fields,
    default_battery_name,
)


APPLE_DEVICE_UUID = "D422BCFF-4F6D-6407-5A60-98E50E72832A"


class TestBuildParser:
    def test_read_accepts_apple_device_uuid(self):
        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(["read", APPLE_DEVICE_UUID]),
        )

        assert args.command == "read"
        assert args.mac == APPLE_DEVICE_UUID

    def test_loop_accepts_apple_device_uuid(self):
        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(["loop", APPLE_DEVICE_UUID]),
        )

        assert args.command == "loop"
        assert args.mac == APPLE_DEVICE_UUID

    def test_read_accepts_mqtt_options(self):
        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(
                [
                    "read",
                    APPLE_DEVICE_UUID,
                    "-mqtt",
                    "--mqtt-host",
                    "mqtt.local",
                    "--mqtt-name",
                    "house battery",
                    "--mqtt-prefix",
                    "garage/batteries",
                    "--mqtt-retain",
                ]
            ),
        )

        assert args.command == "read"
        assert args.mac == APPLE_DEVICE_UUID
        assert args.mqtt is True
        assert args.mqtt_host == "mqtt.local"
        assert args.mqtt_name == "house battery"
        assert args.mqtt_prefix == "garage/batteries"
        assert args.mqtt_retain is True

    def test_loop_accepts_mqtt_options(self):
        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(["loop", APPLE_DEVICE_UUID, "-mqtt"]),
        )

        assert args.command == "loop"
        assert args.mac == APPLE_DEVICE_UUID
        assert args.mqtt is True

    def test_read_accepts_toml_config_without_positional_device(self, tmp_path):
        config_file = tmp_path / "battery.toml"
        config_file.write_text(
            "\n".join(
                [
                    'device = "D422BCFF-4F6D-6407-5A60-98E50E72832A"',
                    "",
                    "[mqtt]",
                    'host = "mqtt.local"',
                    "port = 1884",
                    'username = "battery"',
                    'password = "secret"',
                    'name = "house battery"',
                    'prefix = "garage/batteries"',
                    "retain = true",
                ]
            )
        )

        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(["read", "--config", str(config_file)]),
        )

        assert args.mac == APPLE_DEVICE_UUID
        assert args.mqtt is True
        assert args.mqtt_host == "mqtt.local"
        assert args.mqtt_port == 1884
        assert args.mqtt_username == "battery"
        assert args.mqtt_password == "secret"
        assert args.mqtt_name == "house battery"
        assert args.mqtt_prefix == "garage/batteries"
        assert args.mqtt_retain is True

    def test_loop_config_supplies_interval_and_cli_overrides(self, tmp_path):
        config_file = tmp_path / "battery.toml"
        config_file.write_text(
            "\n".join(
                [
                    'device = "D422BCFF-4F6D-6407-5A60-98E50E72832A"',
                    "interval = 12",
                    "",
                    "[mqtt]",
                    "enabled = true",
                    'host = "mqtt.local"',
                ]
            )
        )

        args = resolve_configured_args(
            build_parser(),
            build_parser().parse_args(
                [
                    "loop",
                    "--config",
                    str(config_file),
                    "--mqtt-host",
                    "override.local",
                    "--interval",
                    "3",
                ]
            ),
        )

        assert args.mac == APPLE_DEVICE_UUID
        assert args.interval == 3
        assert args.mqtt is True
        assert args.mqtt_host == "override.local"

    def test_read_requires_device_without_config(self):
        parser = build_parser()

        try:
            resolve_configured_args(parser, parser.parse_args(["read"]))
        except SystemExit as exc:
            assert exc.code == 2
        else:  # pragma: no cover - defensive
            raise AssertionError("expected parser error")


class TestMqttHelpers:
    def test_default_battery_name_prefers_serial_number(self):
        pi = ProductInfo(serial_number="WTaEaAA25343102")

        assert default_battery_name(APPLE_DEVICE_UUID, pi) == "WTaEaAA25343102"
        assert build_topic_root("WTaEaAA25343102", "garage/batteries") == "garage/batteries/WTaEaAA25343102"

    def test_build_product_info_fields(self):
        pi = ProductInfo(
            firmware_version="WT30_10004SW13_L_02",
            manufacturer_name="11112222333344445555",
            serial_number="WTaEaAA25343102",
        )

        fields = build_product_info_fields(pi)

        assert fields == {
            "firmware": "WT30_10004SW13_L_02",
            "manufacturer": "11112222333344445555",
            "serial": "WTaEaAA25343102",
        }

    def test_build_analog_quantity_fields(self):
        aq = AnalogQuantity(
            cell_count=4,
            cell_voltages=[3.340, 3.337, 3.343, 3.339],
            temperature_count=3,
            mos_temperature=23.0,
            pcb_temperature=26.9,
            cell_temperatures=[22.8],
            current=2.6,
            module_voltage=13.35,
            remaining_capacity=72.0,
            total_capacity=100.0,
            cycle_number=1,
            design_capacity=100.0,
            soc=72,
        )

        fields = build_analog_quantity_fields(aq)

        assert fields["SOC"] == "72"
        assert fields["Current"] == "2.6"
        assert fields["Voltage"] == "13.35"
        assert fields["Rcapacity"] == "72.0"
        assert fields["Cell1V"] == "3.340"
        assert fields["Cell4V"] == "3.339"
        assert fields["Delta"] == "6.0"
        assert fields["MOS"] == "23.0"
        assert fields["PCB"] == "26.9"
        assert fields["Cell1Temp"] == "22.8"

    def test_build_warning_info_fields(self):
        wi = WarningInfo(status_register_1=0x01, warning_register_1=0x20)

        fields = build_warning_info_fields(wi)

        assert fields["protections"] == '["cell_overcharge"]'
        assert fields["faults"] == "[]"
        assert fields["warnings"] == '["discharge_overcurrent"]'