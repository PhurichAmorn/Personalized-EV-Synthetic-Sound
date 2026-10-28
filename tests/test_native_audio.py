"""Native DSP integration checks."""
import unittest
from dataclasses import replace

import numpy as np

from audio import OrderSynth, SoundEngine


class NativeAudioTests(unittest.TestCase):
    def render(self, engine, frames):
        output = np.empty((frames, 2), dtype=np.float32)
        engine._callback(output, frames, None, None)
        return output.copy()

    def test_order_configuration_preserves_running_state(self):
        synth = OrderSynth()
        synth.set_parameters(4000, 75)
        synth.render(4096)
        phase, rpm = synth.phases.copy(), synth.rpm
        synth.config = replace(synth.config, master_gain=.4)
        np.testing.assert_array_equal(synth.phases, phase)
        self.assertEqual(synth.rpm, rpm)

    def test_order_resume_updates_native_state(self):
        engine = SoundEngine(16000)
        engine.order_synth.set_parameters(5000, 80)
        engine.order_active = True
        engine._order_sleeping = True
        self.render(engine, 1)
        self.assertAlmostEqual(engine.order_synth.rpm, 5000)

    def test_native_rejects_mismatched_audio_buffers(self):
        with self.assertRaises(ValueError):
            SoundEngine(8000)._render_traction_cycle(
                np.zeros(16), np.zeros(1), np.zeros(16), np.zeros(16))

if __name__ == "__main__":
    unittest.main()
