"""Print BeamNG OutGauge UDP packets for a local telemetry proof of concept."""

import argparse
import math
import socket
import struct
from datetime import datetime


OUTGAUGE = struct.Struct("<I4sHBB8f2I2f3f16s16si")


def decode(packet: bytes) -> dict:
    if len(packet) not in (OUTGAUGE.size, OUTGAUGE.size - 4):
        raise ValueError(f"unexpected packet size: {len(packet)} bytes")
    values = OUTGAUGE.unpack(packet.ljust(OUTGAUGE.size, b"\0"))
    speed, rpm = values[5:7]
    throttle, brake, clutch = values[14:17]
    if not all(math.isfinite(value) for value in (speed, rpm, throttle, brake, clutch)):
        raise ValueError("non-finite telemetry value")
    return {"speed_m_s": speed, "rpm": rpm, "throttle": throttle, "brake": brake, "clutch": clutch}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="local interface to bind")
    parser.add_argument("--port", type=int, default=4444, help="BeamNG OutGauge UDP port")
    args = parser.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.host, args.port))
        print(f"Listening for OutGauge on {args.host}:{args.port}; Ctrl+C to stop")
        while True:
            packet, source = sock.recvfrom(4096)
            try:
                state = decode(packet)
                print(f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} {source} {state}")
            except ValueError as error:
                print(f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} {source} ignored: {error}")


if __name__ == "__main__":
    main()
