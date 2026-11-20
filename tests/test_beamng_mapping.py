import unittest
from backend.beamng_telemetry import TorqueScaler
from backend.controller import SimulatorController


def packet(**fields):
    base = dict(speed_m_s=20.0, throttle=0.0, brake=0.0, rpm=None, motor_rpm=3000.0, motor_torque=0.0, motor_power=None,
                regen=1.0, regen_torque=None, regen_power=None, motor_load=0.2, watts=None)
    return {**base, **fields}


class TorqueScalerTests(unittest.TestCase):
    def test_drive_is_torque_over_car_peak(self):
        scaler = TorqueScaler(smooth_s=0)
        self.assertAlmostEqual(scaler.update(250, .03, speed=20, drive_nm=500), .5)
        self.assertAlmostEqual(scaler.update(900, .03, speed=20, drive_nm=500), 1.0)

    def test_regen_follows_regen_power_not_torque(self):
        # Recorded eSBR300 one-pedal drive: lift-off sits at the -100 Nm cap at any speed; power (torque x motor speed) fades as it slows.
        scaler = TorqueScaler(smooth_s=0)
        fast = scaler.update(-100, .03, speed=27.8, regen_power=-66_000, full_w=92_400)
        slow = scaler.update(-100, .03, speed=5.6, regen_power=-13_000, full_w=92_400)
        self.assertAlmostEqual(fast, -.714, places=2)
        self.assertAlmostEqual(slow, -.141, places=2)
        self.assertEqual(scaler.update(-100, .03, speed=40, regen_power=-150_000, full_w=92_400), -1.0)
        self.assertEqual(scaler.update(-100, .03, speed=20, regen_power=None), 0.0)  # no power sent: no regen

    def test_esbr300_full_scale_is_its_regen_cap_at_140(self):
        from simulation.vehicle_model import VehicleModel
        from backend.beamng_telemetry import regen_full_w
        self.assertAlmostEqual(regen_full_w(VehicleModel.from_name('BeamNG eSBR300')) / 1000, 92.4, delta=.5)

    def test_noise_around_zero_and_standstill_read_as_zero(self):
        scaler = TorqueScaler(smooth_s=0)
        for torque in (-1.0, -2.5, 1.5, -0.5):                   # jitter at a standstill
            self.assertEqual(scaler.update(torque, .03, speed=0.0, regen_power=-20_000), 0.0)
        self.assertEqual(scaler.update(-2.0, .03, speed=15, regen_power=-20_000), 0.0)  # inside the deadband while moving too
        self.assertLess(scaler.update(-30.0, .03, speed=15, regen_power=-20_000), 0)   # a real regen torque still shows
        self.assertEqual(scaler.update(-30.0, .03, speed=0.1, regen_power=-20_000), 0.0)  # but not when stopped

    def test_output_is_smoothed(self):
        scaler = TorqueScaler(smooth_s=0.15)
        scaler.update(0, .03, speed=10)
        first = scaler.update(-60, .03, speed=10, regen_power=-200_000)
        self.assertTrue(-1.0 < first < 0.0)                      # moving toward -1, not jumping
        for _ in range(40):
            last = scaler.update(-60, .03, speed=10, regen_power=-200_000)
        self.assertLess(last, -.95)


class ControllerRegenTests(unittest.TestCase):
    def setUp(self):
        self.controller = SimulatorController()
        self.controller.selectSource('BeamNG')

    def test_coasting_with_regen_setting_on_is_not_full_regen(self):
        c = self.controller
        c.receive_beamng_telemetry(packet(motor_torque=200.0), received_at=1.0)       # driving
        c.receive_beamng_telemetry(packet(motor_torque=0.0, regen=1.0), received_at=1.1)  # coasting, setting still 100%
        self.assertEqual(c.telemetryRegen, 0.0)
        self.assertFalse(c.regenActive)

    def test_negative_torque_is_regen_for_gauge_and_sound(self):
        c = self.controller
        for step in range(30):  # held hard regen at speed settles past the smoothing
            c.receive_beamng_telemetry(packet(motor_torque=-100.0, motor_load=0.1, speed_m_s=40.0, regen_power=-100_000.0), received_at=1 + step / 10)
        self.assertGreater(c.telemetryRegen, .9)
        self.assertLess(c._signed_motor_load(), -.9)
        self.assertGreater(c.charge, .9)
        self.assertEqual(c.power, 0.0)

    def test_cars_without_motor_device_fall_back_to_the_packet_fields(self):
        c = self.controller
        c.receive_beamng_telemetry(packet(motor_torque=None, motor_load=0.4, regen=0.3), received_at=1.0)
        self.assertAlmostEqual(c._signed_motor_load(), .4)
        self.assertAlmostEqual(c.telemetryRegen, .3)


if __name__ == '__main__':
    unittest.main()
