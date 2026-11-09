import unittest
import numpy as np
from tools.source_voice import bowed_tone, organic_motion


class StringSourceTest(unittest.TestCase):
    def test_organic_motion_is_subtle_repeatable_and_loop_continuous(self):
        time=np.linspace(0,5,240001)
        phase,pressure=organic_motion(time,175,42)
        same_phase,same_pressure=organic_motion(time,175,42)
        np.testing.assert_array_equal(phase,same_phase)
        np.testing.assert_array_equal(pressure,same_pressure)
        self.assertAlmostEqual(phase[0],phase[-1],places=10)
        self.assertAlmostEqual(pressure[0],pressure[-1],places=10)
        cents=1200*np.log2(1+np.gradient(phase,time)/(2*np.pi*175))
        self.assertLess(np.max(abs(cents)),7)
        self.assertGreater(np.std(cents),.5)
        self.assertLess(np.max(abs(pressure-1)),.025)
        other_phase,_=organic_motion(time,175,43)
        self.assertGreater(np.max(abs(phase-other_phase)),.01)

    def test_warm_voice_keeps_harmonics_without_excess_upper_weight(self):
        rate=48000
        time=np.arange(rate)/rate
        signal=bowed_tone(2*np.pi*175*time,175)
        power=np.abs(np.fft.rfft(signal))**2
        frequencies=np.fft.rfftfreq(len(signal),1/rate)
        centroid=np.sum(frequencies*power)/power.sum()
        self.assertGreater(centroid,180)
        self.assertLess(centroid,215)

    def test_low_string_voice_is_periodic_tonal_and_has_restrained_upper_band(self):
        rate=48000
        time=np.arange(rate)/rate
        signal=bowed_tone(2*np.pi*140*time,140)
        power=np.abs(np.fft.rfft(signal))**2
        frequencies=np.fft.rfftfreq(len(signal),1/rate)
        self.assertTrue(np.isfinite(signal).all())
        self.assertEqual(frequencies[np.argmax(power)],140)
        self.assertGreater(power[280],power[140]*.04)
        self.assertLess(power[frequencies>2500].sum()/power.sum(),.01)
        self.assertLess(abs(signal[-1]-signal[0]),np.max(abs(np.diff(signal)))*1.01)

class SourceDimensionTest(unittest.TestCase):
    def test_early_reflections_are_stereo_periodic_and_keep_dry_core(self):
        from tools.source_voice import source_dimension
        rate=48000
        signal=np.sin(2*np.pi*175*np.arange(5*rate)/rate)*.1
        stereo=source_dimension(signal,rate)
        self.assertEqual(stereo.shape,(len(signal),2))
        self.assertGreater(np.sqrt(np.mean((stereo[:,0]-stereo[:,1])**2)),.002)
        self.assertLess(np.max(abs(stereo)),.15)
        self.assertLess(np.max(abs(stereo[0]-stereo[-1])),np.max(abs(np.diff(stereo,axis=0)))*1.01)
        impulse=np.zeros(rate);impulse[0]=1
        reflected=source_dimension(impulse,rate)
        np.testing.assert_allclose(reflected[0],.88,atol=1e-6)
        self.assertGreater(np.sum(reflected[round(.02*rate):round(.16*rate)]**2),.001)


if __name__=='__main__': unittest.main()
