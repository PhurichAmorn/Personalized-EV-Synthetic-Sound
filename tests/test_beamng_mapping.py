import unittest
from backend.beamng_telemetry import TorqueScaler
from backend.controller import SimulatorController


def packet(**fields):
    base = dict(speed_m_s=20.0, throttle=0.0, brake=0.0, rpm=None, motor_rpm=3000.0, motor_torque=0.0, motor_power=None,
                regen=1.0, regen_torque=None, regen_power=None, motor_load=0.2, watts=None)
    return {**base, **fields}


class TorqueScalerTests(unittest.TestCase):
    def test_drive_and_regen_scale_to_their_own_peaks(self):
        scaler = TorqueScaler(drive_floor=100, regen_floor=40)
        self.assertAlmostEqual(scaler.update(300, .03), 1.0)    # new peak
        self.assertAlmostEqual(scaler.update(150, .03), .5, places=2)
        self.assertAlmostEqual(scaler.update(-20, .03), -.5)     # half of the 40 Nm regen floor
        self.assertAlmostEqual(scaler.update(-80, .03), -1.0)    # new regen peak
        self.assertAlmostEqual(scaler.update(-40, .03), -.5, places=2)

    def test_peaks_are_forgotten_slowly(self):
        scaler = TorqueScaler(forget_s=10)
        scaler.update(1000, .03)
        for _ in range(100):
            scaler.update(0, 1.0)
        self.assertLess(scaler.peaks[0], 300)


class ControllerRegenTests(unittest.TestCase):
    def setUp(self):
        self.controller = SimulatorController()
        self.controller.selectSource('BeamNG')

    def test_coasting_with_regen_setting_on_is_not_full_regen(self):
        c = self.controller
        c.receive_beamng_telemetry(packet(motor_torque=200.0), received_at=1.0)       # driving sets the drive peak
        c.receive_beamng_telemetry(packet(motor_torque=0.0, regen=1.0), received_at=1.1)  # coasting, setting still 100%
        self.assertEqual(c.telemetryRegen, 0.0)
        self.assertFalse(c.regenActive)

    def test_negative_torque_is_regen_for_gauge_and_sound(self):
        c = self.controller
        c.receive_beamng_telemetry(packet(motor_torque=-60.0, motor_load=0.1), received_at=1.0)
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
