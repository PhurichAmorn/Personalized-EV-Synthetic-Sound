import unittest
import numpy as np
from tools.prepare_gs_baseline import integrated_loudness,match_loudness,periodic_loop,hall_reflections


class BaselineTest(unittest.TestCase):
    def test_hall_wet_path_removes_direct_arrival_and_preserves_late_field(self):
        hall=np.zeros((48000,2))
        hall[1440]=1
        hall[7200]=.3
        result=hall_reflections(hall)
        self.assertEqual(result[1440,0],0)
        self.assertGreater(abs(result[7200,0]),.1)
        self.assertTrue(np.isfinite(result).all())

    def test_known_mono_reference_tone_and_gain_invariance(self):
        time=np.arange(48000*3)/48000
        tone=.1*np.sin(2*np.pi*1000*time)
        self.assertAlmostEqual(integrated_loudness(tone),-23,delta=.2)
        self.assertAlmostEqual(integrated_loudness(match_loudness(tone,-24)),-24,delta=.03)

    def test_loop_preserves_length_and_joins_without_impulse(self):
        time=np.arange(round(5.5*48000))/48000
        signal=.1*np.sin(2*np.pi*173.7*time)
        loop=periodic_loop(signal,48000)
        self.assertEqual(len(loop),5*48000)
        self.assertLess(abs(loop[0]-loop[-1]),.005)
        self.assertTrue(np.isfinite(loop).all())

    def test_generated_comparison_set_is_complete_and_level_matched(self):
        from pathlib import Path
        import json
        from scipy.io.wavfile import read
        root=Path('desktop/public/audio/baseline-v1')
        if not (root/'manifest.json').exists():self.skipTest('Generate comparison assets first')
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual(len(manifest['clips']),16)
        self.assertEqual(len({clip['id'] for clip in manifest['clips']}),16)
        for clip in manifest['clips']:
            rate,data=read(root/Path(clip['url']).name)
            audio=data.astype(float)/32768
            self.assertEqual(rate,48000)
            self.assertEqual(audio.shape[1],2)
            self.assertTrue(np.isfinite(audio).all())
            self.assertLess(np.max(abs(audio)),.7)
            self.assertAlmostEqual(integrated_loudness(audio),manifest['target_lufs'],delta=.05)
            self.assertAlmostEqual(len(audio)/rate,clip['seconds'])

    def test_stereo_loop_keeps_paired_channels(self):
        time=np.arange(round(5.5*48000))/48000
        signal=.1*np.sin(2*np.pi*173.7*time)
        loop=periodic_loop(np.column_stack([signal,-signal*.5]))
        self.assertEqual(loop.shape,(5*48000,2))
        np.testing.assert_allclose(loop[:,1],-.5*loop[:,0])

    def test_silence_is_rejected_for_normalization(self):
        with self.assertRaises(ValueError):match_loudness(np.zeros(48000),-24)


if __name__=='__main__':unittest.main()
