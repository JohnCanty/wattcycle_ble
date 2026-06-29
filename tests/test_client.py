"""Tests for Linux-specific BLE connection behavior."""

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