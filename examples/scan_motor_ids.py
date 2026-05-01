#!/usr/bin/env python3
"""Scan a Feetech serial bus and print responding servo IDs.

The defaults target a Raspberry Pi Zero 2 W running Raspberry Pi OS Lite with
the primary UART exposed at /dev/serial0. The scan uses PING only; it does not
change servo state.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import scservo_sdk as scs  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "serial":
        raise
    scs = None
    SCS_IMPORT_ERROR = exc
else:
    SCS_IMPORT_ERROR = None


DEFAULT_PORT = "/dev/serial0"
DEFAULT_BAUDRATE = 1000000
MIN_SERVO_ID = 0
MAX_SERVO_ID = 253

ScanResult = Tuple[int, int, int]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan a Feetech STS/HLS serial bus and print every servo ID that "
            "responds to PING."
        )
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Serial port to scan. Default: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=DEFAULT_BAUDRATE,
        help=f"Serial baudrate. Default: {DEFAULT_BAUDRATE}",
    )
    parser.add_argument(
        "--servo-type",
        choices=("sts", "hls"),
        default="sts",
        help="Packet handler to use. Default: sts",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=MIN_SERVO_ID,
        help=f"First servo ID to ping. Default: {MIN_SERVO_ID}",
    )
    parser.add_argument(
        "--end-id",
        type=int,
        default=MAX_SERVO_ID,
        help=f"Last servo ID to ping, inclusive. Default: {MAX_SERVO_ID}",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="PING attempts per ID. Increase on noisy wiring. Default: 1",
    )
    args = parser.parse_args(argv)
    validate_args(args)
    return args


def validate_args(args: argparse.Namespace) -> None:
    if not MIN_SERVO_ID <= args.start_id <= MAX_SERVO_ID:
        raise SystemExit(
            f"--start-id must be between {MIN_SERVO_ID} and {MAX_SERVO_ID}"
        )
    if not MIN_SERVO_ID <= args.end_id <= MAX_SERVO_ID:
        raise SystemExit(f"--end-id must be between {MIN_SERVO_ID} and {MAX_SERVO_ID}")
    if args.start_id > args.end_id:
        raise SystemExit("--start-id must be less than or equal to --end-id")
    if args.retries < 1:
        raise SystemExit("--retries must be at least 1")


def require_scservo_sdk() -> Any:
    if SCS_IMPORT_ERROR is None:
        return scs

    print(
        "Missing Python dependency: pyserial.\n\n"
        "Install it on Raspberry Pi OS with one of:\n"
        "  python3 -m pip install pyserial\n"
        "  sudo apt install python3-serial\n\n"
        "If you are working from this repo, installing the package also works:\n"
        "  python3 -m pip install -e .",
        file=sys.stderr,
    )
    raise SystemExit(1)


def build_packet_handler(servo_type: str, port_handler: Any):
    sdk = require_scservo_sdk()
    if servo_type == "sts":
        return sdk.sms_sts(port_handler)
    if servo_type == "hls":
        return sdk.hls(port_handler)
    raise ValueError(f"Unsupported servo type: {servo_type}")


def scan_ids(packet_handler, ids: Iterable[int], retries: int) -> List[ScanResult]:
    sdk = require_scservo_sdk()
    found: List[ScanResult] = []

    for servo_id in ids:
        for _ in range(retries):
            model_number, comm_result, error = packet_handler.ping(servo_id)
            if comm_result == sdk.COMM_SUCCESS:
                found.append((servo_id, model_number, error))
                break

    return found


def print_results(packet_handler, results: Sequence[ScanResult]) -> None:
    if not results:
        print("No servos responded.")
        return

    print("\nResponding servo IDs:")
    for servo_id, model_number, error in results:
        line = f"  ID {servo_id:03d}"
        if model_number:
            line += f"  model={model_number}"
        if error:
            line += f"  error={packet_handler.getRxPacketError(error)}"
        print(line)

    ids = " ".join(str(servo_id) for servo_id, _, _ in results)
    print(f"\nFound {len(results)} servo(s): {ids}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    sdk = require_scservo_sdk()

    port_handler = sdk.PortHandler(args.port)
    packet_handler = build_packet_handler(args.servo_type, port_handler)

    try:
        if not port_handler.openPort():
            print(f"Failed to open port {args.port}", file=sys.stderr)
            return 1

        if not port_handler.setBaudRate(args.baudrate):
            print(f"Failed to set baudrate to {args.baudrate}", file=sys.stderr)
            return 1

        print(
            f"Scanning {args.servo_type.upper()} servos on {args.port} at "
            f"{args.baudrate} baud, IDs {args.start_id}-{args.end_id}..."
        )
        results = scan_ids(
            packet_handler,
            range(args.start_id, args.end_id + 1),
            args.retries,
        )
        print_results(packet_handler, results)
        return 0
    except OSError as exc:
        print(f"Serial error on {args.port}: {exc}", file=sys.stderr)
        return 1
    finally:
        if getattr(port_handler, "is_open", False):
            port_handler.closePort()


if __name__ == "__main__":
    raise SystemExit(main())
