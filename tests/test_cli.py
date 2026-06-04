"""CLI parsing tests."""

from wattcycle_ble.cli import build_parser


APPLE_DEVICE_UUID = "6F1D8D3F-0E7E-4A30-9D29-6D49C9A7D6D8"


class TestBuildParser:
    def test_read_accepts_apple_device_uuid(self):
        args = build_parser().parse_args(["read", APPLE_DEVICE_UUID])

        assert args.command == "read"
        assert args.device == APPLE_DEVICE_UUID

    def test_loop_accepts_apple_device_uuid(self):
        args = build_parser().parse_args(["loop", APPLE_DEVICE_UUID])

        assert args.command == "loop"
        assert args.device == APPLE_DEVICE_UUID