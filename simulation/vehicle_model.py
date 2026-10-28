from dataclasses import dataclass
import math


VEHICLE_CONFIGS = {
    "Honda e": {
        "max_power_kw": 100.0, "max_torque_nm": 315.0, "mass_kg": 1513.0,
        # 10,000 RPM is the published peak-power range endpoint, not a rev limit.
        "max_speed": 145.0, "max_rpm": 12000.0,  # estimated simulation ceiling
        "battery_kwh": 35.5, "battery_type": "Lithium-ion",
        "range_km": 222, "range_standard": "WLTP",
        # Honda Japan specifies 9.545:1; loaded radius estimated from rear 205/55R16.
        "gear_ratio": 9.545, "wheel_radius_m": 0.310,
        "wheelbase_m": 2.530, "cg_height_m": 0.500,
        # ADAC Advance/17-inch 32.9 m at 100 km/h: proxy for this base trim.
        "max_brake_deceleration_g": 1.27609388, "brake_tire_grip": 1.40,
        "brake_calibration": "32.9 m from 100 km/h (ADAC Advance/17-inch proxy)",
    },
    "Mazda EZ-6 600 (China)": {
        "max_power_kw": 190.0, "max_torque_nm": 320.0, "mass_kg": 1962.0,
        "max_speed": 170.0, "max_rpm": 18000.0,  # estimated simulation ceiling
        "battery_kwh": 68.8, "battery_type": "LFP",
        "range_km": 600, "range_standard": "CLTC",
        # Estimated reduction, not a verified EZ-6 ratio. Radius from rear 245/45R19.
        "gear_ratio": 13.561, "wheel_radius_m": 0.345,
        "wheelbase_m": 2.895, "cg_height_m": 0.520,
        # Provisional dry-road 38 m target; no verified 600 BEV stopping test.
        "max_brake_deceleration_g": 1.09517433, "brake_tire_grip": 1.30,
        "brake_calibration": "38 m from 100 km/h (provisional estimate, unverified)",
        "drag_area_m2": 0.62, "rolling_resistance": 0.010,
        "usable_battery_kwh": 64.0,
        "max_regen_torque_nm": 180.0, "max_regen_power_kw": 100.0,
        "max_charge_power_kw": 80.0, "max_discharge_power_kw": 225.0,
    },
    "Tesla Model 3 Performance (2024 US)": {
        "max_power_kw": 380.3, "max_torque_nm": 741.0, "mass_kg": 1851.0,
        # ponytail: exploratory taper, not digitized MPP/OEM measurements.
        # Replace these assumed knots when trim-specific numeric data is available.
        "power_taper": ((0.0, 1.0), (9000.0, 1.0), (12000.0, 0.95),
                        (16000.0, 0.82), (20000.0, 0.65)),
        "motor_map_description": "Estimated high-RPM taper; numerical points unverified",
        "drive_layout": "AWD", "max_speed": 262.0, "max_rpm": 20000.0,
        "battery_kwh": 82.0, "battery_type": "Lithium-ion (estimated capacity)",
        "range_km": 488, "range_standard": "EPA, 2024",
        "gear_ratio": 9.03, "wheel_radius_m": 0.330,
        "wheelbase_m": 2.875, "cg_height_m": 0.480,
        # ponytail: aggregate dual-motor envelope and ideal AWD torque allocation;
        # replace with separate axle motor maps when measured data is available.
        "tire_grip": 1.05, "drag_area_m2": 0.50, "rolling_resistance": 0.010,
        "usable_battery_kwh": 75.0,
        "max_regen_torque_nm": 250.0, "max_regen_power_kw": 90.0,
        "max_charge_power_kw": 75.0, "max_discharge_power_kw": 430.0,
        "lift_off_deceleration_g": 0.18,
        # Edmunds 2024 US Performance: 109 ft from 60 mph, not 100 km/h.
        "max_brake_deceleration_g": 1.17509739, "brake_tire_grip": 1.35,
        "brake_calibration": "109 ft from 60 mph (Edmunds 2024 Performance)",
    },
    "Porsche Taycan RWD (2023)": {
        # MY23 US standard battery, normal output; Launch Control is not simulated.
        "max_power_kw": 240.0, "max_torque_nm": 338.95, "mass_kg": 2071.13,
        "max_speed": 230.13, "max_rpm": 16000.0,
        "battery_kwh": 79.2, "usable_battery_kwh": 71.0,
        "battery_type": "Lithium-ion", "range_km": 335, "range_standard": "EPA, MY23",
        "gear_ratio": 15.0, "gear_ratios": (15.0, 8.0), "wheel_radius_m": .355,
        "wheelbase_m": 2.9007, "rear_weight_fraction": .51, "cg_height_m": .48,
        # ponytail: Sport-like shift strategy and timing are estimates, not OEM maps.
        "upshift_speed_kmh": 85.0, "downshift_speed_kmh": 55.0, "shift_duration_s": .20,
        "tire_grip": 1.0, "brake_tire_grip": 1.20,
        "max_brake_deceleration_g": 1.0,
        "brake_calibration": "Estimated 1.0 g dry braking; unverified",
        "drag_area_m2": .55, "rolling_resistance": .010,
        "max_regen_torque_nm": 200.0, "max_regen_power_kw": 140.0,
        "max_charge_power_kw": 120.0, "max_discharge_power_kw": 285.0,
        # Porsche defaults to coasting on lift-off; service brake blends regeneration.
        "lift_off_deceleration_g": 0.0,
        "motor_map_description": "Estimated motor envelope; real 2-speed layout, estimated shifting",
    },
}


# Public simulator presets; the manufacturer configurations remain internal references.
SIMULATOR_PRESETS = {
    "Compact EV": "Honda e",
    "Performance EV": "Tesla Model 3 Performance (2024 US)",
}


@dataclass
class VehicleModel:
    """Flat-road, forward-only EV; SI internally, existing dashboard units externally.

    Published peak specs do not supply an OEM torque/BMS map. Unverified road
    load, tire, response, and battery limits below are calibration estimates.
    """
    name: str = "Honda e"
    drive_layout: str = "RWD"
    brake_calibration: str = "Generic brake calibration, unverified"
    max_power_kw: float = 100.0
    max_torque_nm: float = 315.0
    power_taper: tuple[tuple[float, float], ...] = ()
    motor_map_description: str = "Estimated constant-torque / constant-power envelope"
    mass_kg: float = 1513.0
    max_speed: float = 145.0  # km/h; electronic speed limit, independent of gearing
    max_rpm: float = 12000.0  # simulation ceiling; mechanical maximum unverified
    battery_kwh: float = 35.5
    battery_type: str = "Lithium-ion"
    range_km: int = 222
    range_standard: str = "WLTP"
    speed: float = 0.0
    rpm: float = 0.0
    regen: float = 0.0  # recovered battery power / peak propulsion shaft power
    drive_power: float = 0.0  # positive motor shaft power / peak shaft power

    gear_ratio: float = 9.545
    gear_ratios: tuple[float, ...] = ()
    current_gear: int = 1
    upshift_speed_kmh: float = 85.0
    downshift_speed_kmh: float = 55.0
    shift_duration_s: float = .20
    shift_remaining_s: float = 0.0
    pending_gear: int = 1
    wheel_radius_m: float = 0.310
    wheelbase_m: float = 2.530
    cg_height_m: float = 0.500
    rear_weight_fraction: float = 0.50
    tire_grip: float = 0.80
    # Effective dry ABS braking grip, independent of the existing launch calibration.
    # None inherits tire_grip; not a measured tire slip curve or ABS simulation.
    brake_tire_grip: float | None = None
    payload_kg: float = 75.0  # driver; published mass_kg remains the curb mass
    rotational_mass_fraction: float = 0.04
    drivetrain_efficiency: float = 0.97  # reduction gear, not motor/inverter
    motor_efficiency: float = 0.92
    regen_efficiency: float = 0.90  # generator/inverter, after reduction gear
    copper_loss_at_peak_w: float = 2000.0
    rolling_resistance: float = 0.012
    drag_area_m2: float = 0.70
    progressive_pedal: bool = False
    lift_off_deceleration_g: float = 0.12
    max_brake_deceleration_g: float = 0.50
    regen_fade_speed_m_s: float = 2.0
    torque_response_s: float = 0.08
    brake_response_s: float = 0.08
    speed_limit_response_s: float = 0.40

    # ponytail: fixed battery temperature and estimated BMS maps; replace with
    # measured maps/thermal dynamics when vehicle calibration data is available.
    usable_battery_kwh: float = 28.5
    soc: float = 0.80
    battery_temperature_c: float = 25.0
    max_regen_torque_nm: float = 160.0
    max_regen_power_kw: float = 50.0  # generator shaft limit
    max_charge_power_kw: float = 40.0  # battery acceptance, independent of DC charger
    max_discharge_power_kw: float = 120.0
    auxiliary_power_w: float = 500.0

    motor_torque_nm: float = 0.0
    brake_force_n: float = 0.0
    drive_force_n: float = 0.0
    regen_force_n: float = 0.0
    friction_force_n: float = 0.0
    road_load_n: float = 0.0
    acceleration_m_s2: float = 0.0
    battery_power_w: float = 0.0  # positive discharge; negative net charging
    distance_m: float = 0.0
    battery_discharge_energy_j: float = 0.0
    battery_recovered_energy_j: float = 0.0
    road_loss_energy_j: float = 0.0
    friction_loss_energy_j: float = 0.0
    powertrain_loss_energy_j: float = 0.0
    auxiliary_energy_j: float = 0.0

    def __post_init__(self):
        if self.drive_layout not in ("RWD", "AWD"):
            raise ValueError("Drive layout must be RWD or AWD.")
        positive = (self.mass_kg, self.max_power_kw, self.max_torque_nm,
                    self.max_speed, self.max_rpm, self.gear_ratio, self.wheel_radius_m,
                    self.wheelbase_m, self.usable_battery_kwh, self.torque_response_s,
                    self.brake_response_s, self.speed_limit_response_s,
                    self.regen_fade_speed_m_s)
        if not all(math.isfinite(x) and x > 0 for x in positive):
            raise ValueError("Vehicle dimensions, ratings and response times must be positive.")
        if self.gear_ratios:
            if (len(self.gear_ratios) != 2
                    or not all(math.isfinite(r) and r > 0 for r in self.gear_ratios)
                    or self.gear_ratios[0] <= self.gear_ratios[1]
                    or self.current_gear not in (1, 2)
                    or not all(math.isfinite(v) and v > 0 for v in
                               (self.upshift_speed_kmh, self.downshift_speed_kmh, self.shift_duration_s))
                    or self.downshift_speed_kmh >= self.upshift_speed_kmh
                    or self.upshift_speed_kmh >= self.max_speed):
                raise ValueError("Two-speed gearbox requires descending ratios, valid gear and shift thresholds.")
            self.gear_ratio = self.gear_ratios[self.current_gear - 1]
            if self.upshift_speed_kmh / 3.6 * self.gear_ratios[0] / self.wheel_radius_m * 60 / (2 * math.pi) >= self.max_rpm:
                raise ValueError("Upshift must occur before the first-gear RPM ceiling.")
        if self.power_taper:
            if (len(self.power_taper) < 2 or self.power_taper[0][0] != 0
                    or self.power_taper[-1][0] != self.max_rpm
                    or any(not math.isfinite(r) or not math.isfinite(g) or r < 0 or not 0 <= g <= 1
                           for r, g in self.power_taper)
                    or any(b[0] <= a[0] or b[1] > a[1]
                           for a, b in zip(self.power_taper, self.power_taper[1:]))):
                raise ValueError("Power taper must span 0 to max RPM with decreasing gains in [0, 1].")
        efficiencies = (self.drivetrain_efficiency, self.motor_efficiency,
                        self.regen_efficiency)
        if not all(0 < x <= 1 for x in efficiencies):
            raise ValueError("Efficiencies must be in (0, 1].")
        nonnegative = (self.tire_grip, self.payload_kg, self.cg_height_m, self.rotational_mass_fraction,
                       self.rolling_resistance, self.drag_area_m2,
                       self.lift_off_deceleration_g, self.max_brake_deceleration_g,
                       self.max_regen_torque_nm, self.max_regen_power_kw,
                       self.max_charge_power_kw, self.max_discharge_power_kw,
                       self.auxiliary_power_w, self.copper_loss_at_peak_w)
        if not all(math.isfinite(x) and x >= 0 for x in nonnegative):
            raise ValueError("Losses and limits must be finite and nonnegative.")
        if not 0 <= self.soc <= 1 or not 0 <= self.rear_weight_fraction <= 1:
            raise ValueError("SOC and rear weight fraction must be in [0, 1].")
        if self.brake_tire_grip is not None and (not math.isfinite(self.brake_tire_grip) or self.brake_tire_grip < 0):
            raise ValueError("Braking tire grip must be finite and nonnegative.")
        if not math.isfinite(self.speed) or self.speed < 0:
            raise ValueError("Initial speed must be finite and nonnegative.")
        if not math.isfinite(self.battery_temperature_c):
            raise ValueError("Battery temperature must be finite.")
        self.rpm = self.speed / 3.6 * self.motor_rad_s_per_m_s * 60 / (2 * math.pi)

    @classmethod
    def from_name(cls, name: str) -> "VehicleModel":
        if name in SIMULATOR_PRESETS:
            config = dict(VEHICLE_CONFIGS[SIMULATOR_PRESETS[name]])
            config.update(lift_off_deceleration_g=0.03, progressive_pedal=True)
            config["brake_calibration"] = config["brake_calibration"].split(" (")[0] + " (reference target)"
            return cls(name=name, **config)
        return cls(name=name, **VEHICLE_CONFIGS[name])

    @classmethod
    def available_names(cls) -> tuple[str, ...]:
        return tuple(VEHICLE_CONFIGS)

    @property
    def motor_rad_s_per_m_s(self) -> float:
        return self.gear_ratio / self.wheel_radius_m

    @property
    def max_power_w(self) -> float:
        return self.max_power_kw * 1000

    def propulsion_torque_limit(self, rpm: float) -> float:
        """Shared shaft envelope before traction and electrical limits."""
        if not math.isfinite(rpm) or rpm < 0:
            raise ValueError("Motor RPM must be finite and nonnegative.")
        gain = 1.0
        if self.power_taper:
            gain = self.power_taper[-1][1]
            for (r0, g0), (r1, g1) in zip(self.power_taper, self.power_taper[1:]):
                if rpm <= r1:
                    u = max(0.0, (rpm - r0) / (r1 - r0))
                    gain = g0 + (g1 - g0) * u * u * (3 - 2 * u)
                    break
        omega = rpm * 2 * math.pi / 60
        return min(self.max_torque_nm, self.max_power_w * gain / max(omega, 1e-9))

    @property
    def loaded_mass_kg(self) -> float:
        return self.mass_kg + self.payload_kg

    @property
    def effective_mass_kg(self) -> float:
        return self.loaded_mass_kg * (1 + self.rotational_mass_fraction)

    @property
    def battery_energy_j(self) -> float:
        return self.soc * self.usable_battery_kwh * 3_600_000

    @property
    def max_regen_fraction(self) -> float:
        # Stable gauge scale; instantaneous SOC/temperature limits do not rescale it.
        return min(self.max_charge_power_kw,
                   self.max_regen_power_kw * self.regen_efficiency) / self.max_power_kw

    @property
    def charge_power_limit_w(self) -> float:
        # Estimated taper over the last 10% SOC and at cold/hot pack temperatures.
        temperature = max(0.0, min(1.0, (self.battery_temperature_c + 10) / 25,
                                   (55 - self.battery_temperature_c) / 15))
        return self.max_charge_power_kw * 1000 * temperature * min(1.0, (1 - self.soc) / 0.10)

    @property
    def discharge_power_limit_w(self) -> float:
        temperature = max(0.0, min(1.0, (self.battery_temperature_c + 20) / 25,
                                   (60 - self.battery_temperature_c) / 15))
        return self.max_discharge_power_kw * 1000 * temperature * min(1.0, self.soc / 0.05)

    def update(self, throttle: float, brake: float, dt: float) -> None:
        if not all(math.isfinite(x) for x in (throttle, brake, dt)):
            raise ValueError("Pedals and timestep must be finite.")
        if dt <= 0:
            return
        throttle = min(1.0, max(0.0, throttle))
        brake = min(1.0, max(0.0, brake))
        # A delayed GUI frame catches up through bounded physics steps.
        steps = math.ceil(dt / 0.01)
        for _ in range(steps):
            self._step(throttle, brake, dt / steps)

    def _update_transmission(self, throttle, brake, dt):
        if not self.gear_ratios:
            return
        if self.shift_remaining_s > 0:
            self.shift_remaining_s = max(0.0, self.shift_remaining_s - dt)
            if self.shift_remaining_s == 0:
                old_ratio = self.gear_ratio
                self.current_gear = self.pending_gear
                self.gear_ratio = self.gear_ratios[self.current_gear - 1]
                self.motor_torque_nm *= old_ratio / self.gear_ratio
            return
        next_gear = self.current_gear
        if self.current_gear == 1 and self.speed >= self.upshift_speed_kmh and throttle > 0 and brake == 0:
            next_gear = 2
        elif self.current_gear == 2 and self.speed <= self.downshift_speed_kmh:
            next_gear = 1
        if next_gear != self.current_gear:
            self.pending_gear = next_gear
            self.shift_remaining_s = self.shift_duration_s

    def _step(self, throttle: float, brake: float, dt: float) -> None:
        self._update_transmission(throttle, brake, dt)
        shifting = self.shift_remaining_s > 0
        v = self.speed / 3.6
        mass = self.effective_mass_kg
        k = self.motor_rad_s_per_m_s
        gear_eff = self.drivetrain_efficiency
        road = (self.loaded_mass_kg * 9.81 * self.rolling_resistance
                + 0.5 * 1.225 * self.drag_area_m2 * v * v) if v > 0 else 0.0
        # Upper speed bound makes torque/power limits valid across the whole step.
        omega_bound = (v + self.tire_grip * 9.81 * dt) * k
        available = self.propulsion_torque_limit(omega_bound * 60 / (2 * math.pi))
        battery_available = min(self.discharge_power_limit_w, self.battery_energy_j / dt)
        auxiliaries = min(self.auxiliary_power_w, battery_available)
        propulsion_budget = max(0.0, battery_available - auxiliaries)
        copper_k = self.copper_loss_at_peak_w / self.max_torque_nm**2
        b = omega_bound / self.motor_efficiency
        denominator = b + math.sqrt(b * b + 4 * copper_k * propulsion_budget)
        electrical_torque_cap = 2 * propulsion_budget / denominator if denominator else 0.0
        available = 0.0 if shifting else min(available, electrical_torque_cap)
        speed_limit = min(self.max_speed / 3.6, self.max_rpm * 2 * math.pi / 60 / k)

        # Neutral band shrinks to zero at standstill for a light-pedal launch.
        band = min(1.0, v / self.regen_fade_speed_m_s) if self.progressive_pedal else 0.0
        lower, upper = 0.08 * band, 0.12 * band
        drive_pedal = max(0.0, (throttle - upper) / (1 - upper))
        lift_fraction = max(0.0, 1 - throttle / lower) if lower else float(throttle == 0)
        lift_fraction = lift_fraction * lift_fraction * (3 - 2 * lift_fraction)
        if self.progressive_pedal:
            # Gentle motor braking is additional to passive road losses, not a total-decel target.
            lift_force = mass * 9.81 * self.lift_off_deceleration_g * lift_fraction
        else:
            lift_force = max(0.0, mass * 9.81 * self.lift_off_deceleration_g - road) if throttle == 0 else 0.0
        full_brake_force = max(0.0, mass * 9.81 * self.max_brake_deceleration_g - road)
        regen_request = (1 - brake) * lift_force + brake * full_brake_force
        requested_brake = regen_request if brake else 0.0
        fade = min(1.0, v / self.regen_fade_speed_m_s)
        fade = fade * fade * (3 - 2 * fade)
        charge_budget = min(self.charge_power_limit_w,
                            (self.usable_battery_kwh * 3_600_000 - self.battery_energy_j)
                            / dt + auxiliaries)
        regen_cap = min(self.max_regen_torque_nm,
                        self.max_regen_power_kw * 1000 / max(v * k, 1e-9),
                        charge_budget / max(v * k * self.regen_efficiency, 1e-9))
        if shifting:
            regen_cap = 0.0
        if drive_pedal > 0 and not brake:
            target = drive_pedal * available
            speed_force = road + mass * max(0.0, speed_limit - v) / self.speed_limit_response_s
            target = min(target, speed_force / (k * gear_eff))
        else:
            target = -min(regen_cap, regen_request * gear_eff / k) * fade

        # The service brake overrides propulsion immediately; ordinary lift-off crosses zero smoothly.
        if brake and self.motor_torque_nm > 0:
            self.motor_torque_nm = 0.0
        response = -math.expm1(-dt / self.torque_response_s)
        torque = self.motor_torque_nm + (target - self.motor_torque_nm) * response
        self.brake_force_n += (requested_brake - self.brake_force_n) * -math.expm1(-dt / self.brake_response_s)
        # Releasing the service brake must not leave residual friction during drive.
        if not brake:
            self.brake_force_n = 0.0

        drive = regen = friction = 0.0
        if torque > 0 and not brake:
            drive = min(torque, available) * k * gear_eff
            # RWD traction including longitudinal load transfer; ideal slip control.
            load_k = self.tire_grip * self.loaded_mass_kg * self.cg_height_m / (self.wheelbase_m * mass)
            grip = max(0.0, (self.tire_grip * self.loaded_mass_kg * 9.81 * self.rear_weight_fraction
                            - load_k * road) / max(1 - load_k, 1e-9))
            if self.drive_layout == "AWD":
                grip = self.tire_grip * self.loaded_mass_kg * 9.81
            drive = min(drive, grip, self.tire_grip * self.loaded_mass_kg * 9.81,
                        max(0.0, road + mass * (speed_limit - v) / dt))
        else:
            # Reverse energy flow: wheel braking includes gearbox losses.
            regen = min(max(0.0, -torque), regen_cap * fade) * k / gear_eff
            total_request = max(regen, self.brake_force_n)
            grip = self.brake_tire_grip if brake and self.brake_tire_grip is not None else self.tire_grip
            total_request = min(total_request, grip * self.loaded_mass_kg * 9.81)
            deceleration = (road + total_request) / mass
            rear_load = self.loaded_mass_kg * max(0.0, 9.81 * self.rear_weight_fraction
                                         - deceleration * self.cg_height_m / self.wheelbase_m)
            axle_load = self.loaded_mass_kg * 9.81 if self.drive_layout == "AWD" else rear_load
            regen = min(regen, total_request, self.tire_grip * axle_load)
            friction = max(0.0, total_request - regen) if brake else 0.0

        # Stop without reversing or discarding kinetic energy at a speed clamp.
        resisting = road + regen + friction
        stop_scale = min(1.0, (mass * v / dt + drive) / resisting) if resisting else 1.0
        road *= stop_scale
        regen *= stop_scale
        friction *= stop_scale
        acceleration = (drive - road - regen - friction) / mass
        next_v = max(0.0, v + acceleration * dt)
        mean_v = (v + next_v) / 2
        shaft_drive_w = drive * mean_v / gear_eff
        shaft_regen_w = regen * mean_v * gear_eff
        achieved_torque = drive / (k * gear_eff) if drive else -regen * gear_eff / k
        copper = copper_k * achieved_torque**2
        drive_electrical_w = shaft_drive_w / self.motor_efficiency + (copper if drive else 0.0)
        recovered_w = max(0.0, shaft_regen_w * self.regen_efficiency - (copper if regen else 0.0))

        self.battery_power_w = drive_electrical_w + auxiliaries - recovered_w
        self.soc = min(1.0, max(0.0, self.soc - self.battery_power_w * dt
                               / (self.usable_battery_kwh * 3_600_000)))
        self.battery_discharge_energy_j += drive_electrical_w * dt
        self.battery_recovered_energy_j += recovered_w * dt
        self.auxiliary_energy_j += auxiliaries * dt
        self.road_loss_energy_j += road * mean_v * dt
        self.friction_loss_energy_j += friction * mean_v * dt
        self.powertrain_loss_energy_j += (drive_electrical_w - drive * mean_v
                                         + regen * mean_v - recovered_w) * dt
        self.distance_m += mean_v * dt
        self.speed = next_v * 3.6
        self.rpm = next_v * k * 60 / (2 * math.pi)
        self.acceleration_m_s2 = acceleration
        self.drive_force_n, self.regen_force_n = drive, regen
        self.friction_force_n, self.road_load_n = friction, road
        self.motor_torque_nm = achieved_torque
        self.drive_power = shaft_drive_w / self.max_power_w if next_v > 0 else 0.0
        self.regen = recovered_w / self.max_power_w if next_v > 0 else 0.0
