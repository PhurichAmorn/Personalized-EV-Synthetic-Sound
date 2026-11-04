"""Print BeamNG OutGauge or EV Sound Lab custom UDP telemetry."""

import argparse
import math
import socket
import struct
from datetime import datetime


OUTGAUGE = struct.Struct("<I4sHBB7f2I3f16s16si")
EVSOUND = struct.Struct("<4s12f")


def decode(packet: bytes) -> dict:
    if packet.startswith(b"EVS1"):
        if len(packet) != EVSOUND.size:
            raise ValueError(f"unexpected EV Sound packet size: {len(packet)} bytes")
        marker, speed, throttle, brake, rpm, motor_rpm, motor_torque, motor_power, regen, regen_torque, regen_power, motor_load, watts = EVSOUND.unpack(packet)
        fields = {"speed_m_s": speed, "throttle": throttle, "brake": brake, "rpm": rpm,
                  "motor_rpm": motor_rpm, "motor_torque": motor_torque, "motor_power": motor_power,
                  "regen": regen, "regen_torque": regen_torque, "regen_power": regen_power,
                  "motor_load": motor_load, "watts": watts}
        if not all(math.isfinite(value) for value in fields.values()):
            raise ValueError("non-finite EV telemetry value")
        return {key: (None if value == -999999 else value) for key, value in fields.items()}
    if packet.startswith(b"EVSL1 "):
        return dict(field.split("=", 1) for field in packet.decode("ascii").split()[1:])
    if len(packet) != OUTGAUGE.size:
        raise ValueError(f"unexpected packet size: {len(packet)} bytes")
    values = OUTGAUGE.unpack(packet)
    speed, rpm = values[5:7]
    throttle, brake, clutch = values[14:17]
    if not all(math.isfinite(value) for value in (speed, rpm, throttle, brake, clutch)):
        raise ValueError("non-finite telemetry value")
    return {"speed_m_s": speed, "rpm": rpm, "throttle": throttle, "brake": brake, "clutch": clutch}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="local interface to bind")
    parser.add_argument("--port", type=int, default=4444, help="BeamNG UDP port (custom Lua protocol defaults to 4445)")
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
                print(
                    f"{datetime.now().astimezone().isoformat(timespec='milliseconds')} "
                    f"{source} ignored: {error}; bytes={len(packet)} hex={packet.hex()}"
                )


if __name__ == "__main__":
    main()
