"""Command-line interface for wattcycle-ble."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .client import WattcycleClient
from .config import load_cli_config
from .models import AnalogQuantity, ProductInfo, WarningInfo
from .mqtt import (
    MqttConfig,
    MqttPublisher,
    build_analog_quantity_fields,
    build_product_info_fields,
    build_topic_root,
    build_warning_info_fields,
    default_battery_name,
)


def print_battery_data(aq: AnalogQuantity) -> None:
    """Pretty-print battery data to stdout."""
    print()
    print("=" * 60)
    print("  BATTERY STATUS")
    print("=" * 60)

    print(f"\n  SOC:                {aq.soc}%")
    print(f"  Current:            {aq.current:.1f} A")
    print(f"  Module Voltage:     {aq.module_voltage:.2f} V")
    print(f"  Remaining Capacity: {aq.remaining_capacity:.1f} Ah")
    print(f"  Total Capacity:     {aq.total_capacity:.1f} Ah")
    print(f"  Design Capacity:    {aq.design_capacity:.1f} Ah")
    print(f"  Cycle Count:        {aq.cycle_number}")

    print(f"\n  Cell Voltages ({aq.cell_count} cells):")
    for i, v in enumerate(aq.cell_voltages):
        print(f"    Cell {i + 1:2d}: {v:.3f} V")
    if aq.cell_voltages:
        vmin = min(aq.cell_voltages)
        vmax = max(aq.cell_voltages)
        print(f"    Delta:  {(vmax - vmin) * 1000:.1f} mV  (min={vmin:.3f}, max={vmax:.3f})")

    print(f"\n  Temperatures ({aq.temperature_count} sensors):")
    print(f"    MOS:    {aq.mos_temperature:.1f} C")
    print(f"    PCB:    {aq.pcb_temperature:.1f} C")
    for i, t in enumerate(aq.cell_temperatures):
        print(f"    Cell {i + 1}: {t:.1f} C")

    if aq.soh is not None:
        print(f"\n  SOH:                {aq.soh}%")
    if aq.cumulative_capacity is not None:
        print(f"  Cumulative Cap:     {aq.cumulative_capacity:.1f} Ah")
    if aq.remaining_time_min is not None:
        hours = aq.remaining_time_min // 60
        mins = aq.remaining_time_min % 60
        print(f"  Remaining Time:     {hours}h {mins}m")
    if aq.balance_current is not None:
        print(f"  Balance Current:    {aq.balance_current:.1f} A")

    print()


async def cmd_scan(args: argparse.Namespace) -> None:
    """Scan for Wattcycle devices."""
    devices = await WattcycleClient.scan(timeout=args.timeout)
    if not devices:
        print("No Wattcycle/XDZN devices found.")
        return
    print(f"\nFound {len(devices)} device(s):")
    for d in devices:
        print(f"  {d.name}  ({d.address})")


def print_product_info(pi: ProductInfo) -> None:
    """Pretty-print product information to stdout."""
    print(f"\n  Firmware:     {pi.firmware_version}")
    print(f"  Manufacturer: {pi.manufacturer_name}")
    print(f"  Serial:       {pi.serial_number}")


def print_warning_info(wi: WarningInfo) -> None:
    """Pretty-print warning information to stdout."""
    if wi.protections:
        print(f"  Protections:  {', '.join(wi.protections)}")
    if wi.faults:
        print(f"  Faults:       {', '.join(wi.faults)}")
    if wi.warnings:
        print(f"  Warnings:     {', '.join(wi.warnings)}")
    if not (wi.protections or wi.faults or wi.warnings):
        print("  No active warnings or faults.")


def add_config_arg(parser: argparse.ArgumentParser) -> None:
    """Add a TOML config file option to a subcommand parser."""
    parser.add_argument(
        "-c",
        "--config",
        help="path to a TOML file containing device and MQTT settings",
    )


def add_mqtt_args(parser: argparse.ArgumentParser) -> None:
    """Add MQTT publishing options to a subcommand parser."""
    parser.add_argument(
        "-mqtt",
        "--mqtt",
        action="store_true",
        default=argparse.SUPPRESS,
        help="publish battery fields to MQTT instead of printing them",
    )
    parser.add_argument(
        "--mqtt-host",
        default=argparse.SUPPRESS,
        help="MQTT broker host (default: localhost)",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=argparse.SUPPRESS,
        help="MQTT broker port (default: 1883)",
    )
    parser.add_argument(
        "--mqtt-username",
        default=argparse.SUPPRESS,
        help="MQTT username",
    )
    parser.add_argument(
        "--mqtt-password",
        default=argparse.SUPPRESS,
        help="MQTT password",
    )
    parser.add_argument(
        "--mqtt-name",
        default=argparse.SUPPRESS,
        help="battery name used as the MQTT topic root (defaults to serial or device id)",
    )
    parser.add_argument(
        "--mqtt-prefix",
        default=argparse.SUPPRESS,
        help="optional MQTT topic prefix added before the battery name",
    )
    parser.add_argument(
        "--mqtt-retain",
        action="store_true",
        default=argparse.SUPPRESS,
        help="set the retain flag on MQTT publishes",
    )


def resolve_configured_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> argparse.Namespace:
    """Merge a TOML config file into parsed CLI args.

    Explicit CLI options take precedence over file values.
    """
    if args.command not in {"read", "loop"}:
        return args

    defaults: dict[str, object] = {
        "mqtt": False,
        "mqtt_host": "localhost",
        "mqtt_port": 1883,
        "mqtt_username": None,
        "mqtt_password": None,
        "mqtt_name": None,
        "mqtt_prefix": "",
        "mqtt_retain": False,
    }
    if args.command == "loop":
        defaults["interval"] = 5.0

    config_values: dict[str, object] = {}
    config_path = getattr(args, "config", None)
    if config_path:
        try:
            config_values = load_cli_config(config_path)
        except ValueError as exc:
            parser.error(str(exc))

    missing = object()
    for key, default in defaults.items():
        value = getattr(args, key, missing)
        if value is missing:
            setattr(args, key, config_values.get(key, default))

    mac_value = getattr(args, "mac", missing)
    if mac_value is missing:
        config_mac = config_values.get("mac")
        if config_mac:
            args.mac = str(config_mac)
        else:
            parser.error(
                f"{args.command} requires a device identifier or --config with device = \"...\""
            )

    return args


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="wattcycle-ble",
        description="BLE client for XDZN/Wattcycle battery monitors",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="enable debug logging",
    )

    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="scan for Wattcycle devices")
    scan_p.add_argument(
        "-t", "--timeout", type=float, default=10.0,
        help="scan timeout in seconds (default: 10)",
    )

    read_p = sub.add_parser("read", help="read battery data (default)")
    read_p.add_argument(
        "mac",
        nargs="?",
        default=argparse.SUPPRESS,
        help="device identifier (MAC address or Apple/CoreBluetooth UUID)",
    )
    add_config_arg(read_p)
    add_mqtt_args(read_p)

    loop_p = sub.add_parser("loop", help="continuously poll battery data")
    loop_p.add_argument(
        "mac",
        nargs="?",
        default=argparse.SUPPRESS,
        help="device identifier (MAC address or Apple/CoreBluetooth UUID)",
    )
    loop_p.add_argument(
        "-i", "--interval", type=float, default=argparse.SUPPRESS,
        help="poll interval in seconds (default: 5)",
    )
    add_config_arg(loop_p)
    add_mqtt_args(loop_p)

    return parser


def _build_mqtt_publisher(args: argparse.Namespace) -> MqttPublisher | None:
    """Create an MQTT publisher when MQTT mode is enabled."""
    if not args.mqtt:
        return None

    return MqttPublisher(
        MqttConfig(
            host=args.mqtt_host,
            port=args.mqtt_port,
            username=args.mqtt_username,
            password=args.mqtt_password,
            topic_prefix=args.mqtt_prefix,
            retain=args.mqtt_retain,
        )
    )


def _mqtt_topic_root(args: argparse.Namespace, pi: ProductInfo | None) -> str:
    """Resolve the MQTT topic root for the current battery."""
    battery_name = default_battery_name(args.mac, pi, args.mqtt_name)
    return build_topic_root(battery_name, args.mqtt_prefix)


async def cmd_read(args: argparse.Namespace) -> None:
    """Connect and read battery data."""
    publisher = _build_mqtt_publisher(args)
    try:
        if publisher is not None:
            publisher.connect()

        async with WattcycleClient(args.mac) as client:
            if not await client.detect_frame_head():
                print("Could not communicate with device.", file=sys.stderr)
                sys.exit(1)

            pi = await client.read_product_info()
            topic_root = _mqtt_topic_root(args, pi)
            if pi:
                if publisher is not None:
                    publisher.publish_fields(topic_root, build_product_info_fields(pi))
                else:
                    print_product_info(pi)

            aq = await client.read_analog_quantity()
            if aq:
                if publisher is not None:
                    publisher.publish_fields(topic_root, build_analog_quantity_fields(aq))
                else:
                    print_battery_data(aq)

            wi = await client.read_warning_info()
            if wi:
                if publisher is not None:
                    publisher.publish_fields(topic_root, build_warning_info_fields(wi))
                else:
                    print_warning_info(wi)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        if publisher is not None:
            publisher.disconnect()


async def cmd_loop(args: argparse.Namespace) -> None:
    """Continuously poll battery data."""
    publisher = _build_mqtt_publisher(args)
    try:
        if publisher is not None:
            publisher.connect()

        while True:
            try:
                async with WattcycleClient(args.mac) as client:
                    if not await client.detect_frame_head():
                        raise RuntimeError("Could not communicate with device.")

                    pi = await client.read_product_info()
                    topic_root = _mqtt_topic_root(args, pi)
                    if pi:
                        if publisher is not None:
                            publisher.publish_fields(topic_root, build_product_info_fields(pi))
                        else:
                            print_product_info(pi)

                    while True:
                        aq = await client.read_analog_quantity()
                        if aq:
                            if publisher is not None:
                                publisher.publish_fields(topic_root, build_analog_quantity_fields(aq))
                            else:
                                print_battery_data(aq)

                        wi = await client.read_warning_info()
                        if wi:
                            if publisher is not None:
                                publisher.publish_fields(topic_root, build_warning_info_fields(wi))
                            else:
                                print_warning_info(wi)

                        await asyncio.sleep(args.interval)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                await asyncio.sleep(args.interval)
    except KeyboardInterrupt:
        if not args.mqtt:
            print("\nStopped.")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        if publisher is not None:
            publisher.disconnect()


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = resolve_configured_args(parser, parser.parse_args())

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "scan":
        asyncio.run(cmd_scan(args))
    elif args.command == "loop":
        asyncio.run(cmd_loop(args))
    elif args.command == "read":
        asyncio.run(cmd_read(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
