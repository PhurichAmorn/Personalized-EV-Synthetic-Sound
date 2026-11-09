import unittest
import numpy as np
from tools.render_bmw_steady import clean_spectrum


class CleanSpectrumTest(unittest.TestCase):
    def test_noise_and_close_sidebands_do_not_become_extra_voices(self):
        frequencies=np.arange(24001.)
        magnitude=np.ones(len(frequencies))*.01
        for harmonic in range(1,20):
            magnitude+=np.exp(-.5*((frequencies-harmonic*50)/2)**2)/harmonic
        magnitude+=.3*np.exp(-.5*((frequencies-106)/2)**2)
        spectrum,root,count=clean_spectrum(magnitude,48000,12)
        bins=np.flatnonzero(abs(spectrum)>0)
        self.assertLess(abs(root-50),2)
        self.assertLessEqual(count,24)
        np.testing.assert_allclose(bins/(root*12),np.arange(1,count+1),atol=1e-10)


if __name__=='__main__': unittest.main()
