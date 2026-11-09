import unittest
import numpy as np
from tools.render_evolving_source import phrase_envelope, phrase_frequency


class EvolvingEnvelopeTest(unittest.TestCase):
    def test_phrase_keeps_low_start_but_reaches_higher_register(self):
        time=np.linspace(0,4.5,1000)
        frequency=phrase_frequency(time)
        self.assertAlmostEqual(frequency[0],160)
        self.assertGreater(frequency[-1],268)
        self.assertLess(frequency[-1],271)
        self.assertTrue(np.all(np.diff(frequency)>0))
        self.assertGreater(phrase_frequency(np.array([4.0]))[0]-phrase_frequency(np.array([3.0]))[0],15)

    def test_overlap_keeps_both_voices_present_during_handover(self):
        incoming=phrase_envelope(np.array([.9]))[0]
        outgoing=phrase_envelope(np.array([3.4]))[0]
        self.assertGreater(incoming**2,.55)
        self.assertGreater(outgoing**2,.2)
        self.assertLess(outgoing**2,.45)

    def test_overlapping_phrases_keep_constant_envelope_power(self):
        rate=48000
        local=np.arange(round(4.5*rate))/rate
        envelope=phrase_envelope(local)
        power=np.zeros(5*rate)
        for start in (0,round(2.5*rate)):
            np.add.at(power,(np.arange(len(envelope))+start)%len(power),envelope**2)
        np.testing.assert_allclose(power,1,atol=1e-10)
        self.assertEqual(envelope[0],0)
        self.assertLess(envelope[-1],1e-8)


if __name__=='__main__': unittest.main()
