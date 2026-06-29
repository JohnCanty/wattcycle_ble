"""Tests for Linux-specific BLE connection behavior."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from wattcycle_ble.client import WattcycleClient


class TestWattcycleClientConnect(IsolatedAsyncioTestCase):
    async def test_connect_resolves_linux_string_address_before_connect(self):
        battery = WattcycleClient("C0:D6:3C:58:2C:90")
        fake_device = object()
        mock_client = AsyncMock()

        with patch("wattcycle_ble.client.sys.platform", "linux"), patch(
            "wattcycle_ble.client.BleakScanner.find_device_by_address",
            new=AsyncMock(return_value=fake_device),
        ) as find_device, patch(
            "wattcycle_ble.client.BleakClient", return_value=mock_client
        ) as bleak_client:
            await battery.connect()

        find_device.assert_awaited_once_with("C0:D6:3C:58:2C:90", timeout=10.0)
        bleak_client.assert_called_once_with(fake_device)
        mock_client.connect.assert_awaited_once()

    async def test_connect_reports_missing_linux_device_cleanly(self):
        battery = WattcycleClient("C0:D6:3C:58:2C:90")

        with patch("wattcycle_ble.client.sys.platform", "linux"), patch(
            "wattcycle_ble.client.BleakScanner.find_device_by_address",
            new=AsyncMock(return_value=None),
        ) as find_device, patch("wattcycle_ble.client.BleakClient") as bleak_client:
            with self.assertRaisesRegex(RuntimeError, "was not found during scan"):
                await battery.connect()

        find_device.assert_awaited_once_with("C0:D6:3C:58:2C:90", timeout=10.0)
        bleak_client.assert_not_called()

    async def test_connect_falls_back_to_single_discovered_wattcycle_device(self):
        battery = WattcycleClient("C0:D6:3C:58:2C:90")
        fallback_device = SimpleNamespace(name="WT12V100AH100MINIBT", address="DA:7A:11:22:33:44")
        mock_client = AsyncMock()

        with patch("wattcycle_ble.client.sys.platform", "linux"), patch(
            "wattcycle_ble.client.BleakScanner.find_device_by_address",
            new=AsyncMock(return_value=None),
        ) as find_device, patch.object(
            WattcycleClient, "scan", new=AsyncMock(return_value=[fallback_device])
        ) as scan_devices, patch(
            "wattcycle_ble.client.BleakClient", return_value=mock_client
        ) as bleak_client:
            await battery.connect()

        find_device.assert_awaited_once_with("C0:D6:3C:58:2C:90", timeout=10.0)
        scan_devices.assert_awaited_once_with(timeout=10.0)
        bleak_client.assert_called_once_with(fallback_device)
        mock_client.connect.assert_awaited_once()

    async def test_connect_requires_explicit_choice_when_multiple_devices_match(self):
        battery = WattcycleClient("C0:D6:3C:58:2C:90")
        devices = [
            SimpleNamespace(name="WT12V100AH100MINIBT", address="DA:7A:11:22:33:44"),
            SimpleNamespace(name="XDZN_001_EF2F", address="DA:7A:11:22:33:55"),
        ]

        with patch("wattcycle_ble.client.sys.platform", "linux"), patch(
            "wattcycle_ble.client.BleakScanner.find_device_by_address",
            new=AsyncMock(return_value=None),
        ) as find_device, patch.object(
            WattcycleClient, "scan", new=AsyncMock(return_value=devices)
        ) as scan_devices, patch("wattcycle_ble.client.BleakClient") as bleak_client:
            with self.assertRaisesRegex(RuntimeError, "Multiple Wattcycle devices are advertising"):
                await battery.connect()

        find_device.assert_awaited_once_with("C0:D6:3C:58:2C:90", timeout=10.0)
        scan_devices.assert_awaited_once_with(timeout=10.0)
        bleak_client.assert_not_called()