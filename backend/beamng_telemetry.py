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
    Small torques (noise around zero) and standstill read as exactly 0, and the output is lightly smoothed,
    so the gauges and the regen sound do not flicker.
    """

    def __init__(self, drive_floor=100.0, regen_floor=40.0, forget_s=90.0,
                 deadband_nm=3.0, deadband_fraction=0.04, still_speed_m_s=0.3, smooth_s=0.12):
        self.floors = (drive_floor, regen_floor)
        self.peaks = [drive_floor, regen_floor]
        self.forget_s = forget_s
        self.deadband_nm = deadband_nm
        self.deadband_fraction = deadband_fraction
        self.still_speed = still_speed_m_s
        self.smooth_s = smooth_s
        self.value = 0.0
        self.started = False

    def update(self, torque, dt, speed=None):
        dt = max(0.0, min(dt, 1.0))
        keep = math.exp(-dt / self.forget_s)
        self.peaks = [floor + (peak - floor) * keep for floor, peak in zip(self.floors, self.peaks)]
        side = 0 if torque >= 0 else 1
        still = speed is not None and speed < self.still_speed
        if still or abs(torque) < max(self.deadband_nm, self.deadband_fraction * self.peaks[side]):
            raw = 0.0
        else:
            self.peaks[side] = max(self.peaks[side], abs(torque))
            raw = max(-1.0, min(1.0, torque / self.peaks[side]))
        if not self.started or self.smooth_s <= 0 or dt <= 0:
            self.value, self.started = raw, True
        else:
            self.value += (raw - self.value) * (1.0 - math.exp(-dt / self.smooth_s))
        return self.value
