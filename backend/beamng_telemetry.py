"""Decoder for the local EV Sound Lab BeamNG UDP protocol."""

import math
import struct

_PACKET = struct.Struct("<4s12f")
_FIELDS = (
    "speed_m_s", "throttle", "brake", "rpm", "motor_rpm", "motor_torque",
    "motor_power", "regen", "regen_torque", "regen_power", "motor_load", "watts",
)
_UNAVAILABLE = -999999.0


def decode_ev_sound_packet(packet: bytes) -> dict:
    if len(packet) != _PACKET.size:
        raise ValueError(f"unexpected EV Sound packet size: {len(packet)} bytes")
    marker, *values = _PACKET.unpack(packet)
    if marker != b"EVS1":
        raise ValueError("invalid EV Sound packet marker")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("non-finite EV telemetry value")
    fields = {key: (None if value == _UNAVAILABLE else value)
              for key, value in zip(_FIELDS, values)}
    for key in ("throttle", "brake", "regen"):
        value = fields[key]
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid normalized {key}")
    load = fields["motor_load"]
    if load is not None and not -1.0 <= load <= 1.0:
        raise ValueError("invalid normalized motor_load")
    if fields["speed_m_s"] is None or fields["speed_m_s"] < 0:
        raise ValueError("invalid vehicle speed")
    return fields
