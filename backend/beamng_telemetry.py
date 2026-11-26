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


# Regen power that reads as full regen on the gauge and in the sound: the motor's regen torque cap at REGEN_FULL_KMH
# (= the sound's top speed), or its regen power cap if lower. eSBR300: 100 Nm x 924 rad/s = 92 kW, so lift-off reads
# 71% at 100 km/h and 36% at 50 km/h, fading to 0 at a stop like a real EV power gauge. Was deceleration / 0.5 g (2026-11-20).
REGEN_FULL_KMH = 140.0


def regen_full_w(car):
    return min(car.max_regen_torque_nm * REGEN_FULL_KMH / 3.6 * car.motor_rad_s_per_m_s, car.max_regen_power_kw * 1000)


def regen_level(power_w, full_w):
    """Regen power (W, either sign) -> 0..1."""
    return min(1.0, abs(power_w) / full_w)


class TorqueScaler:
    """Signed motor torque (Nm) -> -1..+1 on fixed scales (no learned peaks).

    Drive: torque / the car's peak torque. Regen (negative torque): regen power (torque x motor speed, sent by the mod)
    over regen_full_w, not torque alone: in one-pedal drive the eSBR300 motor sits at its 100 Nm regen cap from lift-off,
    so torque alone would read 100% at any speed. Braking past the cap adds friction brakes only, as in a real EV.
    Small torques (noise around zero) and standstill read as exactly 0, and the output is lightly smoothed,
    so the gauges and the regen sound do not flicker.
    """

    def __init__(self, deadband_nm=4.0, still_speed_m_s=0.3, smooth_s=0.15):
        self.deadband_nm = deadband_nm
        self.still_speed = still_speed_m_s
        self.smooth_s = smooth_s
        self.value = 0.0
        self.started = False

    def update(self, torque, dt, speed=None, regen_power=None, drive_nm=500.0, full_w=92_400.0):
        dt = max(0.0, min(dt, 1.0))
        still = speed is not None and speed < self.still_speed
        if still or abs(torque) < self.deadband_nm:
            raw = 0.0
        elif torque > 0:
            raw = min(1.0, torque / drive_nm)
        else:
            raw = -regen_level(regen_power or 0.0, full_w)
        if not self.started or self.smooth_s <= 0 or dt <= 0:
            self.value, self.started = raw, True
        else:
            self.value += (raw - self.value) * (1.0 - math.exp(-dt / self.smooth_s))
        return self.value
