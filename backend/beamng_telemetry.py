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


# Deceleration that reads as full regen on the gauge and in the sound. ponytail: one global value, tuned by ear in
# BeamNG; make it per car if cars differ a lot.
REGEN_FULL_G = 0.5


def regen_from_decel(acceleration_m_s2):
    """How hard the car slows, 0..1 (REGEN_FULL_G = 1)."""
    return min(1.0, max(0.0, -acceleration_m_s2 / (REGEN_FULL_G * 9.81)))


class TorqueScaler:
    """Signed motor torque (Nm) -> -1..+1 on fixed scales (no learned peaks).

    Drive: torque / the car's peak torque. Regen (negative torque): how hard the car slows (regen_from_decel), not the
    motor torque: in one-pedal drive the eSBR300 motor is already at its 100 Nm regen limit on lift-off, and braking only
    adds friction brakes the torque cannot show, so torque alone would read 100% for both.
    Small torques (noise around zero) and standstill read as exactly 0, and the output is lightly smoothed,
    so the gauges and the regen sound do not flicker.
    """

    def __init__(self, deadband_nm=4.0, still_speed_m_s=0.3, smooth_s=0.15):
        self.deadband_nm = deadband_nm
        self.still_speed = still_speed_m_s
        self.smooth_s = smooth_s
        self.value = 0.0
        self.started = False

    def update(self, torque, dt, speed=None, acceleration=0.0, drive_nm=500.0):
        dt = max(0.0, min(dt, 1.0))
        still = speed is not None and speed < self.still_speed
        if still or abs(torque) < self.deadband_nm:
            raw = 0.0
        elif torque > 0:
            raw = min(1.0, torque / drive_nm)
        else:
            raw = -regen_from_decel(acceleration)
        if not self.started or self.smooth_s <= 0 or dt <= 0:
            self.value, self.started = raw, True
        else:
            self.value += (raw - self.value) * (1.0 - math.exp(-dt / self.smooth_s))
        return self.value
