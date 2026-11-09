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


class TorqueScaler:
    """Signed motor torque (Nm) -> -1..+1, scaled by the largest drive and regen torque seen so far.

    BeamNG gives no torque limits, and its load field never goes negative, so regen would never sound.
    The remembered peaks decay slowly toward a floor, so a car or regen-setting change re-scales within minutes.
    """

    def __init__(self, drive_floor=100.0, regen_floor=40.0, forget_s=90.0):
        self.floors = (drive_floor, regen_floor)
        self.peaks = [drive_floor, regen_floor]
        self.forget_s = forget_s

    def update(self, torque, dt):
        keep = math.exp(-max(0.0, min(dt, 1.0)) / self.forget_s)
        self.peaks = [floor + (peak - floor) * keep for floor, peak in zip(self.floors, self.peaks)]
        side = 0 if torque >= 0 else 1
        self.peaks[side] = max(self.peaks[side], abs(torque))
        return max(-1.0, min(1.0, torque / self.peaks[side]))
