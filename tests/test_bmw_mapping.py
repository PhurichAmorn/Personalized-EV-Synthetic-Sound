"""Regression for harmonic-fit jumps becoming fast audible pitch wobble."""
import unittest
import numpy as np
from tools.render_bmw_mapping import smooth_pitch


class SmoothPitchTest(unittest.TestCase):
    def test_harmonic_jump_has_bounded_speed_and_continuous_velocity(self):
        time=np.arange(0,4,2048/48000)
        estimate=np.where(time<2,0.,12.)+.25*np.sin(2*np.pi*7*time)
        curve=smooth_pitch(time,estimate)
        dense=np.linspace(time[0],time[-1],10000)
        self.assertLess(np.max(np.abs(curve(dense,1))),12)
        self.assertLess(np.max(np.abs(np.diff(curve(dense,1)))),.03)
        self.assertLess(abs(curve(time[0])),.5)
        self.assertLess(abs(curve(time[-1])-12),.5)


if __name__=='__main__': unittest.main()
