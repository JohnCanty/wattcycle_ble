# wattcycle-ble

A Python library and CLI for communicating with XDZN/Wattcycle BLE battery management systems.

Protocol reverse-engineered from the `com.gz.wattcycle` Android app. See [PROTOCOL.md](PROTOCOL.md) for the full protocol specification.

## Tested Devices

| Device | Firmware | Cells | Notes |
|--------|----------|-------|-------|
| XDZN_001_EF2F | WT12_20004SW10_L447 | 4S LiFePO4 | 314 Ah |
| WT12V100AH100MINIBT | WT30_10004SW13_L_02 | 4S LiFePO4 | 100 Ah |

If you have a different Wattcycle/XDZN device, please open an issue with your results.

## Installation

Install from GitHub:

```bash
python3 -m pip install git+https://github.com/qume/wattcycle_ble.git
```

Or clone and install locally in editable mode:

```bash
git clone https://github.com/qume/wattcycle_ble.git
cd wattcycle_ble
python3 -m pip install -e .
```

### macOS

macOS often ships with an older system Python that is too old for this project. `wattcycle-ble` requires Python 3.11+.

Install a supported Python with Homebrew, create a virtual environment, and install from the project root:

```bash
brew install python@3.12

cd /path/to/wattcycle_ble
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e .
```

Run the CLI from the virtual environment:

```bash
wattcycle-ble scan
wattcycle-ble read <device-id>
```

If the console script is not on your shell path, use the module form instead:

```bash
python -m wattcycle_ble.cli scan
python -m wattcycle_ble.cli read <device-id>
```

The first BLE operation may trigger a macOS Bluetooth permission prompt for your terminal app.

## CLI Usage

Scan for devices:

```bash
wattcycle-ble scan
```

Read battery data:

```bash
wattcycle-ble read <device-id>
```

Example on macOS:

```bash
wattcycle-ble read 6F1D8D3F-0E7E-4A30-9D29-6D49C9A7D6D8
```

Continuously poll (every 5 seconds):

```bash
wattcycle-ble loop <device-id> --interval 5
```

Add `-v` for debug logging:

```bash
wattcycle-ble -v read <device-id>
```

Publish battery data to MQTT instead of printing it:

```bash
wattcycle-ble read <device-id> -mqtt
wattcycle-ble loop <device-id> -mqtt --mqtt-host 192.168.1.10 --mqtt-name house-battery
```

Load the device identifier and MQTT settings from a TOML file:

```bash
wattcycle-ble read --config battery.toml
wattcycle-ble loop --config battery.toml
```

Example `battery.toml`:

```toml
device = "D422BCFF-4F6D-6407-5A60-98E50E72832A"
interval = 5

[mqtt]
enabled = true
host = "192.168.1.10"
port = 1883
username = "mqtt-user"
password = "mqtt-password"
name = "house-battery"
prefix = "garage/batteries"
retain = true
```

Values passed on the command line override the config file. For example:

```bash
wattcycle-ble loop --config battery.toml --interval 10 --mqtt-host test-broker.local
```

When `-mqtt` is enabled, normal battery output is suppressed and each field is published as a separate topic. By default the topic root is `/<serial-or-device-id>/`; use `--mqtt-name` to override the battery name and `--mqtt-prefix` to add a prefix such as `/garage/`.

Common MQTT topics:
- `/<battery-name>/firmware`
- `/<battery-name>/serial`
- `/<battery-name>/SOC`
- `/<battery-name>/Current`
- `/<battery-name>/Voltage`
- `/<battery-name>/Cell1V`
- `/<battery-name>/Delta`
- `/<battery-name>/MOS`
- `/<battery-name>/PCB`
- `/<battery-name>/protections`
- `/<battery-name>/warnings`

MQTT options:
- `--mqtt-host` broker host, default `localhost`
- `--mqtt-port` broker port, default `1883`
- `--mqtt-username` and `--mqtt-password` for broker authentication
- `--mqtt-name` to override the battery name used in topics
- `--mqtt-prefix` to prepend a path segment before the battery name
- `--mqtt-retain` to publish retained messages

`<device-id>` is the platform BLE identifier: a MAC address on Linux/Windows or the Apple/CoreBluetooth UUID on macOS.

Use `wattcycle-ble scan` first to discover the identifier to pass into `read` or `loop`.

## Library Usage

```python
import asyncio
from wattcycle_ble import WattcycleClient

async def main():
    device_id = "C0:D6:3C:57:EF:2F"  # or a macOS CoreBluetooth UUID

    async with WattcycleClient(device_id) as client:
        await client.detect_frame_head()

        info = await client.read_product_info()
        print(f"Firmware: {info.firmware_version}")
        print(f"Serial:   {info.serial_number}")

        data = await client.read_analog_quantity()
        print(f"SOC: {data.soc}%")
        print(f"Voltage: {data.module_voltage:.2f} V")
        print(f"Current: {data.current:.1f} A")
        print(f"Capacity: {data.remaining_capacity:.1f} / {data.total_capacity:.1f} Ah")

        for i, v in enumerate(data.cell_voltages):
            print(f"  Cell {i+1}: {v:.3f} V")

        warnings = await client.read_warning_info()
        if warnings.protections:
            print(f"Active protections: {warnings.protections}")

asyncio.run(main())
```

### Scanning for Devices

```python
devices = await WattcycleClient.scan(timeout=10.0)
for d in devices:
    print(f"{d.name} ({d.address})")
```

On macOS, `d.address` is the Apple/CoreBluetooth UUID you can pass back into `WattcycleClient(...)` or the CLI.

## Protocol

The full BLE protocol documentation is in [PROTOCOL.md](PROTOCOL.md).

Key points:
- BLE service `0xFFF0` with write (`FFF2`), notify (`FFF1`), and auth (`FFFA`) characteristics
- Authentication: write `HiLink` to `FFFA`
- Modbus-like framing with CRC16
- No pairing required

## Requirements

- Python 3.11+
- [bleak](https://github.com/hbldh/bleak) (BLE library)
- [paho-mqtt](https://github.com/eclipse-paho/paho.mqtt.python) (MQTT publishing)
- Linux, macOS, or Windows with Bluetooth support

## License

MIT
# wattcycle_ble
