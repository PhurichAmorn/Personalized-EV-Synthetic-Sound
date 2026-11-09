import unittest
import numpy as np
from audio.signal_checks import check_signal


class SignalChecksTest(unittest.TestCase):
    rate=48000

    def tone(self,seconds=1):
        time=np.arange(round(seconds*self.rate))/self.rate
        return .1*np.sin(2*np.pi*180*time)

    def codes(self,report):return {item['code'] for item in report['findings']}

    def test_clean_periodic_stereo_passes(self):
        x=self.tone()
        report=check_signal(np.column_stack([x,-x]),self.rate,loop=True)
        self.assertEqual(report['decision'],'pass')

    def test_nonfinite_and_overload_reject(self):
        x=self.tone();x[100]=np.nan
        self.assertEqual(check_signal(x,self.rate)['decision'],'reject')
        x=self.tone();x[100]=1.2
        self.assertIn('sample_overload',self.codes(check_signal(x,self.rate)))

    def test_click_and_short_dropout_are_reported(self):
        x=self.tone();x[20000:20004]+=[.4,-.3,.2,-.1]
        self.assertIn('impulse_transients',self.codes(check_signal(x,self.rate)))
        x=self.tone();x[20000:21680]=0
        self.assertIn('short_dropout',self.codes(check_signal(x,self.rate)))
        activity=np.ones(len(x),dtype=bool);activity[19000:22500]=False
        self.assertNotIn('short_dropout',self.codes(check_signal(x,self.rate,expected_active=activity)))

    def test_idle_is_not_a_dropout(self):
        x=np.r_[np.zeros(self.rate),self.tone(),np.zeros(self.rate)]
        self.assertNotIn('short_dropout',self.codes(check_signal(x,self.rate)))
        report=check_signal(np.zeros(self.rate),self.rate)
        self.assertEqual(report['decision'],'pass')
        self.assertEqual(check_signal(np.zeros(self.rate),self.rate,loop=True)['decision'],'reject')
        report=check_signal(np.zeros(self.rate),self.rate,expected_active=np.ones(self.rate,dtype=bool))
        self.assertIn('missing_expected_audio',self.codes(report))

    def test_broken_loop_only_checked_when_requested(self):
        x=self.tone();x[-1000:]+=.15
        self.assertIn('loop_discontinuity',self.codes(check_signal(x,self.rate,loop=True)))
        self.assertNotIn('loop_discontinuity',self.codes(check_signal(x,self.rate)))

    def test_loop_slope_reversal_is_detected_even_without_a_large_step(self):
        time=np.arange(self.rate)/self.rate
        x=.1*np.sin(2*np.pi*180.5*time)
        self.assertIn('loop_discontinuity',self.codes(check_signal(x,self.rate,loop=True)))

    def test_high_tone_is_review_not_rejection(self):
        time=np.arange(self.rate)/self.rate
        x=self.tone()+.08*np.sin(2*np.pi*10000*time)
        report=check_signal(x,self.rate)
        self.assertIn('high_frequency_energy',self.codes(report))
        self.assertEqual(report['decision'],'review')
        stereo=check_signal(np.column_stack([x,-x]),self.rate)
        self.assertIn('high_frequency_energy',self.codes(stereo))

    def test_flat_tops_are_not_assumed_full_scale_clipping(self):
        x=np.clip(self.tone()*4,-.07,.07)
        report=check_signal(x,self.rate)
        self.assertIn('flat_topped_signal',self.codes(report))
        self.assertNotEqual(report['decision'],'reject')
        clipped=np.clip(self.tone()*40,-1,1)
        self.assertIn('full_scale_flat_tops',self.codes(check_signal(clipped,self.rate)))

    def test_invalid_shapes_and_intent_are_rejected(self):
        with self.assertRaises(ValueError):check_signal(np.zeros((100,3)),self.rate)
        with self.assertRaises(ValueError):check_signal(np.zeros(0),self.rate)
        with self.assertRaises(ValueError):check_signal(self.tone(),0)
        with self.assertRaises(ValueError):check_signal(self.tone(),self.rate,expected_active=np.ones(10,dtype=bool))

    def test_envelope_wobble_is_measured_but_never_blocks(self):
        rate=48000;t=np.arange(rate*8)/rate;carrier=.3*np.sin(2*np.pi*220*t)
        steady=check_signal(carrier,rate);wobble=check_signal(carrier*(1+.5*np.sin(2*np.pi*4*t)),rate)
        self.assertEqual(wobble['decision'],'pass')
        self.assertGreater(wobble['metrics']['modulation']['fluct_0.5-20'],5*steady['metrics']['modulation']['fluct_0.5-20'])
        self.assertNotIn('modulation',check_signal(carrier[:rate*3],rate)['metrics'])  # too short to measure
