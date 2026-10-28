"""Run with: .venv/bin/python -m unittest discover -s tests -v"""
import math
import random
import unittest

from simulation.vehicle_model import VehicleModel


class VehiclePhysicsTests(unittest.TestCase):
    def cars(self):
        return [VehicleModel.from_name(name) for name in VehicleModel.available_names()]

    def advance(self, car, throttle, brake, seconds, dt=0.01):
        for _ in range(round(seconds / dt)):
            car.update(throttle, brake, dt)

    def assert_energy(self, car, initial_battery, initial_speed=0):
        kinetic_change = 0.5 * car.effective_mass_kg * ((car.speed / 3.6)**2 - (initial_speed / 3.6)**2)
        losses = (car.road_loss_energy_j + car.friction_loss_energy_j
                  + car.powertrain_loss_energy_j + car.auxiliary_energy_j)
        self.assertAlmostEqual(initial_battery - car.battery_energy_j,
                               kinetic_change + losses, delta=0.001)
        self.assertAlmostEqual(initial_battery - car.battery_energy_j,
                               car.battery_discharge_energy_j + car.auxiliary_energy_j
                               - car.battery_recovered_energy_j, delta=0.001)

    def test_vehicle_specific_propulsion_maps(self):
        for car in self.cars():
            for rpm in range(0, int(car.max_rpm) + 1, 100):
                torque = car.propulsion_torque_limit(rpm)
                self.assertTrue(0 <= torque <= car.max_torque_nm)
                self.assertLessEqual(torque * rpm * 2 * math.pi / 60,
                                     car.max_power_w + 1e-6)
                if not car.power_taper:
                    expected = min(car.max_torque_nm,
                                   car.max_power_w / max(rpm * 2 * math.pi / 60, 1e-9))
                    self.assertEqual(torque, expected)
            if car.power_taper:
                for rpm, gain in car.power_taper[1:]:
                    self.assertAlmostEqual(car.propulsion_torque_limit(rpm) * rpm
                                           * 2 * math.pi / 60, car.max_power_w * gain)
                car.speed = 210
                initial_energy = car.battery_energy_j
                self.advance(car, 1, 0, 2)
                self.assertLessEqual(car.motor_torque_nm,
                                     car.propulsion_torque_limit(car.rpm) + 1e-6)
                self.assert_energy(car, initial_energy, initial_speed=210)
        for curve in (((0, 1), (12000, float('nan'))),
                      ((0, .8), (12000, 1)), ((0, 1), (0, .5)),
                      ((0, 1), (12000, 1.1))):
            with self.assertRaises(ValueError):
                VehicleModel(power_taper=curve)

    def test_real_two_speed_shift_and_energy_balance(self):
        car = VehicleModel.from_name('Porsche Taycan RWD (2023)')
        initial = car.battery_energy_j
        shifted = False
        previous_gear, previous_speed, previous_rpm = 1, 0, 0
        for _ in range(1500):
            car.update(1, 0, .005)
            if car.current_gear != previous_gear:
                self.assertEqual(car.current_gear, 2)
                self.assertLess(abs(car.speed - previous_speed), .2)
                self.assertAlmostEqual(car.rpm / previous_rpm,
                                       car.speed / previous_speed * 8 / 15)
                shifted = True
            self.assertLessEqual(car.motor_torque_nm, car.max_torque_nm + 1e-6)
            previous_gear, previous_speed, previous_rpm = car.current_gear, car.speed, car.rpm
        self.assertTrue(shifted)
        self.assert_energy(car, initial)
        for _ in range(1500):
            car.update(0, 1, .005)
        self.assertEqual(car.current_gear, 1)
        self.assertEqual(car.speed, 0)
        self.assert_energy(car, initial)
        for changes in ({'gear_ratios': (8, 15)}, {'gear_ratios': (15,)},
                        {'gear_ratios': (15, 8), 'shift_duration_s': 0},
                        {'gear_ratios': (15, 8), 'upshift_speed_kmh': 140}):
            with self.assertRaises(ValueError):
                VehicleModel(**changes)

    def test_acceleration_and_timestep_convergence(self):
        for name in VehicleModel.available_names():
            times = []
            speeds = []
            for dt in (0.005, 0.01, 0.02, 0.05):
                car = VehicleModel.from_name(name)
                elapsed = 0.0
                while car.speed < 100 and elapsed < 20:
                    car.update(1, 0, dt)
                    elapsed += dt
                self.assertLess(elapsed, 20)
                times.append(elapsed)
                speeds.append(car.speed)
            self.assertLess(max(times) - min(times), 0.08)
            if name == 'Honda e':
                # Published ~9 s; this is a plausibility band, not OEM calibration.
                self.assertTrue(8 <= times[1] <= 10, times)
            elif name.startswith('Tesla'):
                self.assertTrue(3 <= times[1] <= 4, times)
            else:
                self.assertTrue(6 <= times[1] <= 9, times)

    def test_rpm_tracks_gearing_in_drive_coast_and_regen(self):
        for car in self.cars():
            for throttle, brake in ((1, 0), (0, 0), (0, 1), (0.2, 0)):
                car.speed = 80
                car.update(throttle, brake, 0.02)
                expected = car.speed / 3.6 * car.gear_ratio / car.wheel_radius_m * 60 / (2 * math.pi)
                self.assertAlmostEqual(car.rpm, expected, places=9)
            car.max_speed *= 0.8
            car.update(0, 0, 0.01)
            expected = car.speed / 3.6 * car.gear_ratio / car.wheel_radius_m * 60 / (2 * math.pi)
            self.assertAlmostEqual(car.rpm, expected, places=9)

    def test_partial_throttle_scales_available_torque(self):
        for name in VehicleModel.available_names():
            powers = []
            for pedal in (0.25, 0.5, 1):
                car = VehicleModel.from_name(name)
                # Hold road speed for an isolated motor/pedal steady-state check.
                for _ in range(200):
                    car.speed = 100
                    car.update(pedal, 0, 0.01)
                powers.append(car.drive_power)
            self.assertAlmostEqual(powers[0] / powers[2], 0.25, delta=0.001)
            self.assertAlmostEqual(powers[1] / powers[2], 0.5, delta=0.001)

    def test_top_speed_uses_only_road_load_power(self):
        for car in self.cars():
            self.advance(car, 1, 0, 60, dt=0.02)
            self.assertAlmostEqual(car.speed, car.max_speed, delta=0.001)
            self.assertLessEqual(car.rpm, car.max_rpm)
            required = car.road_load_n * car.speed / 3.6 / car.drivetrain_efficiency
            self.assertAlmostEqual(car.drive_power * car.max_power_w, required, delta=0.01)
            self.assertLess(car.drive_power, 0.6)
        car = VehicleModel(max_rpm=6000)
        self.advance(car, 1, 0, 40)
        self.assertAlmostEqual(car.rpm, 6000, delta=0.001)
        self.assertLess(car.speed, car.max_speed)

    def test_traction_limits_drive_and_regen(self):
        for grip in (0, 0.15, 0.8):
            for car in self.cars():
                car.tire_grip = grip
                car.brake_tire_grip = grip
                self.advance(car, 1, 0, 1)
                rear_load = car.loaded_mass_kg * max(0, 9.81 * car.rear_weight_fraction
                                            + car.acceleration_m_s2 * car.cg_height_m / car.wheelbase_m)
                axle_load = car.loaded_mass_kg * 9.81 if car.drive_layout == "AWD" else rear_load
                self.assertLessEqual(car.drive_force_n, grip * axle_load + 1e-6)
                car.speed = 100
                self.advance(car, 0, 1, 0.5)
                rear_load = car.loaded_mass_kg * max(0, 9.81 * car.rear_weight_fraction
                                            + car.acceleration_m_s2 * car.cg_height_m / car.wheelbase_m)
                axle_load = car.loaded_mass_kg * 9.81 if car.drive_layout == "AWD" else rear_load
                self.assertLessEqual(car.regen_force_n, grip * axle_load + 1e-6)
                self.assertLessEqual(car.regen_force_n + car.friction_force_n,
                                     grip * car.loaded_mass_kg * 9.81 + 1e-6)

    def test_power_torque_and_battery_limits(self):
        for car in self.cars():
            for throttle, brake, seconds in ((1, 0, 30), (0, 1, 10)):
                for _ in range(round(seconds / 0.01)):
                    discharge_limit = car.discharge_power_limit_w
                    charge_limit = car.charge_power_limit_w
                    car.update(throttle, brake, 0.01)
                    self.assertLessEqual(car.drive_power, 1)
                    self.assertLessEqual(abs(car.motor_torque_nm), car.max_torque_nm)
                    self.assertLessEqual(car.battery_power_w, discharge_limit + 1e-6)
                    self.assertGreaterEqual(car.battery_power_w, -charge_limit - 1e-6)
                    self.assertTrue(0 <= car.soc <= 1)
                    self.assertGreaterEqual(car.regen, 0)
                    self.assertLessEqual(car.regen, car.max_regen_fraction + 1e-6)

    def test_torque_ramp_and_immediate_regen_mode(self):
        for car in self.cars():
            car.speed = 60
            car.update(1, 0, 0.01)
            self.assertTrue(0 < car.motor_torque_nm < car.max_torque_nm)
            first = car.drive_power
            self.advance(car, 1, 0, 0.2)
            self.assertGreater(car.drive_power, first)
            before = car.motor_torque_nm
            car.update(0, 0, 0.01)
            self.assertGreater(car.motor_torque_nm, 0)
            self.assertLess(car.motor_torque_nm, before)
            self.advance(car, 0, 0, 1)
            if car.lift_off_deceleration_g:
                self.assertGreater(car.regen, 0)
            car.update(1, 1, 0.01)
            self.assertEqual(car.drive_power, 0)
            self.assertLess(car.motor_torque_nm, 0)

    def test_calibrated_stopping_distances_and_traction(self):
        targets = (("Honda e", 100, 32.9),
                   ("Mazda EZ-6 600 (China)", 100, 38.0),
                   ("Tesla Model 3 Performance (2024 US)", 60 * 1.609344, 109 * .3048))
        for name, speed, target in targets:
            for dt in (.005, .01, .02, .05):
                car = VehicleModel.from_name(name)
                car.speed = speed
                initial_battery = car.battery_energy_j
                elapsed = 0
                while car.speed > .000001 and elapsed < 10:
                    car.update(0, 1, dt)
                    elapsed += dt
                    self.assertLessEqual(car.regen_force_n + car.friction_force_n,
                                         car.brake_tire_grip * car.loaded_mass_kg * 9.81 + 1e-6)
                self.assertLess(elapsed, 10)
                self.assertAlmostEqual(car.distance_m, target, delta=.15)
                self.assert_energy(car, initial_battery, speed)
            # A full battery changes energy recovery, not maximum service stopping.
            car = VehicleModel.from_name(name)
            car.speed, car.soc = speed, 1
            self.advance(car, 0, 1, 5)
            self.assertEqual(car.regen, 0)
            self.assertAlmostEqual(car.distance_m, target, delta=.15)

    def test_brake_strength_and_blending(self):
        for name in VehicleModel.available_names():
            decels = []
            for pedal in (0.01, 0.25, 0.5, 1):
                car = VehicleModel.from_name(name)
                car.speed = 100
                self.advance(car, 0, pedal, 0.5)
                decels.append(-car.acceleration_m_s2)
            self.assertEqual(decels, sorted(decels))
            self.assertGreater(decels[-1], decels[0] * (2.5 if name.startswith("Tesla") else 3))
            car = VehicleModel.from_name(name)
            car.speed = 100
            self.advance(car, 0, 1, 0.5)
            self.assertGreater(car.regen_force_n, 0)
            self.assertGreater(car.friction_force_n, 0)
            car.update(1, 0, 0.01)
            self.assertEqual(car.friction_force_n, 0)

    def test_full_cold_hot_batteries_still_allow_service_braking(self):
        for car in self.cars():
            car.soc = 1
            car.auxiliary_power_w = 0
            car.speed = 100
            self.advance(car, 0, 1, 1)
            self.assertEqual(car.regen, 0)
            self.assertGreater(car.friction_force_n, 0)
            self.assertLess(car.speed, 90)
            self.assertEqual(car.soc, 1)
        for temperature in (-20, 55):
            car = VehicleModel(battery_temperature_c=temperature, speed=80)
            self.advance(car, 0, 1, 1)
            self.assertEqual(car.regen, 0)
            self.assertGreater(car.friction_force_n, 0)

    def test_soc_and_temperature_charge_taper(self):
        car = VehicleModel()
        normal = car.charge_power_limit_w
        car.soc = 0.95
        self.assertAlmostEqual(car.charge_power_limit_w, normal * 0.5)
        car.soc = 0.99
        self.assertAlmostEqual(car.charge_power_limit_w, normal * 0.1)
        car.soc = 0.8
        car.battery_temperature_c = 0
        self.assertAlmostEqual(car.charge_power_limit_w, normal * 0.4)

    def test_coasting_and_low_speed_stop(self):
        coast = VehicleModel(speed=80, lift_off_deceleration_g=0)
        regen = VehicleModel(speed=80)
        self.advance(coast, 0, 0, 2)
        self.advance(regen, 0, 0, 2)
        self.assertTrue(0 < regen.speed < coast.speed < 80)
        self.assertEqual(coast.regen, 0)
        self.assertEqual(coast.friction_force_n, 0)
        low_speed = VehicleModel(speed=3)
        self.advance(low_speed, 0, 0, 0.2)
        self.assertLess(-low_speed.acceleration_m_s2, 9.81 * low_speed.lift_off_deceleration_g)
        for brake in (0, 1):
            car = VehicleModel(speed=5)
            initial = car.battery_energy_j
            self.advance(car, 0, brake, 15)
            self.assertEqual(car.speed, 0)
            self.assertEqual(car.rpm, 0)
            self.assertEqual(car.regen, 0)
            self.assertEqual(car.drive_power, 0)
            self.assert_energy(car, initial, 5)

    def test_regenerated_energy_cannot_exceed_initial_kinetic_energy(self):
        for car in self.cars():
            car.speed = 100
            initial_battery = car.battery_energy_j
            kinetic = 0.5 * car.effective_mass_kg * (100 / 3.6)**2
            self.advance(car, 0, 1, 15)
            self.assertEqual(car.speed, 0)
            self.assertTrue(0 < car.battery_recovered_energy_j < kinetic)
            self.assertGreater(car.soc, 0.8)
            self.assert_energy(car, initial_battery, 100)

    def test_empty_battery_and_stationary_auxiliaries(self):
        car = VehicleModel(soc=0)
        self.advance(car, 1, 0, 2)
        self.assertEqual(car.speed, 0)
        self.assertEqual(car.battery_power_w, 0)
        car = VehicleModel(speed=80, soc=0)
        self.advance(car, 0, 1, 1)
        self.assertGreater(car.soc, 0)
        car = VehicleModel()
        initial = car.battery_energy_j
        self.advance(car, 0, 0, 2)
        self.assertEqual(car.speed, 0)
        self.assertAlmostEqual(initial - car.battery_energy_j, 1000, delta=1e-5)

    def test_energy_balance_acceleration_braking_and_limits(self):
        for car in self.cars():
            initial = car.battery_energy_j
            for throttle, brake, seconds in ((1, 0, 40), (0, 0, 5), (0, 0.3, 3),
                                             (1, 0, 5), (0, 1, 15)):
                self.advance(car, throttle, brake, seconds, dt=0.02)
            self.assert_energy(car, initial)
            self.assertGreater(car.battery_recovered_energy_j, 0)
            self.assertGreater(car.powertrain_loss_energy_j, 0)

    def test_random_pedals_preserve_energy_and_bounds(self):
        randomizer = random.Random(42)
        for car in self.cars():
            initial = car.battery_energy_j
            for _ in range(3000):
                car.update(randomizer.uniform(-0.2, 1.2), randomizer.choice((0, 0, 0.3, 1)),
                           randomizer.choice((0.005, 0.01, 0.02, 0.05)))
                self.assertTrue(0 <= car.speed <= car.max_speed + 1e-9)
                self.assertTrue(0 <= car.rpm <= car.max_rpm + 1e-9)
                self.assertTrue(0 <= car.soc <= 1)
                self.assertTrue(math.isfinite(car.battery_power_w))
            self.assert_energy(car, initial)

    def test_public_presets_gentle_progressive_regen(self):
        from simulation.vehicle_model import SIMULATOR_PRESETS
        for name in SIMULATOR_PRESETS:
            torques = []
            for pedal in (0, .04, .10, .20, 1):
                car = VehicleModel.from_name(name)
                initial = car.battery_energy_j
                car.speed = 60
                self.advance(car, pedal, 0, 1)
                torques.append(car.motor_torque_nm)
                self.assert_energy(car, initial, 60)
                if pedal == 0:
                    self.assertAlmostEqual(car.regen_force_n / car.effective_mass_kg, .03 * 9.81, delta=.001)
                    self.assertEqual(car.friction_force_n, 0)
            self.assertEqual(torques, sorted(torques))
            self.assertLess(torques[0], torques[1])
            self.assertEqual(torques[2], 0)
            car = VehicleModel.from_name(name)
            self.advance(car, .03, 0, .5)
            self.assertGreater(car.speed, 0)
            car.speed, car.soc = 60, 1
            car.auxiliary_power_w = 0
            car.motor_torque_nm = 0
            self.advance(car, 0, 0, 1)
            self.assertEqual(car.regen, 0)
            self.assertEqual(car.friction_force_n, 0)

    def test_input_validation_and_noop_timestep(self):
        car = VehicleModel()
        initial = vars(car).copy()
        car.update(1, 0, 0)
        car.update(1, 0, -1)
        self.assertEqual(vars(car), initial)
        for arguments in ((math.nan, 0, 0.01), (0, math.inf, 0.01), (0, 0, math.nan)):
            with self.assertRaises(ValueError):
                car.update(*arguments)
        for arguments in ({'mass_kg': 0}, {'wheel_radius_m': -1}, {'soc': 1.1},
                          {'motor_efficiency': 1.1}, {'battery_temperature_c': math.nan}):
            with self.assertRaises(ValueError):
                VehicleModel(**arguments)


if __name__ == '__main__':
    unittest.main()
