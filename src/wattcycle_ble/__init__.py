"""wattcycle-ble: BLE client for XDZN/Wattcycle battery management systems.

Example::

    import asyncio
    from wattcycle_ble import WattcycleClient

    async def main():
        device_id = "C0:D6:3C:57:EF:2F"  # or a macOS CoreBluetooth UUID

        async with WattcycleClient(device_id) as client:
            await client.detect_frame_head()
            data = await client.read_analog_quantity()
            print(f"SOC: {data.soc}%  Voltage: {data.module_voltage}V")

    asyncio.run(main())
"""

from .client import WattcycleClient
from .models import AnalogQuantity, ProductInfo, WarningInfo

__all__ = [
    "WattcycleClient",
    "AnalogQuantity",
    "ProductInfo",
    "WarningInfo",
]
