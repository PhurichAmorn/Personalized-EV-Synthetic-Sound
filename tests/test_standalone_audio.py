"""Build and exercise the core without Python headers, NumPy, or audio hardware."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StandaloneAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = shutil.which('clang++') or shutil.which('g++')
        if not cls.compiler or os.name == 'nt':
            raise unittest.SkipTest('Standalone compiler checks require clang++/g++ on this platform')
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.build = Path(cls.temporary.name)
        common = [cls.compiler, '-std=c++17', '-O1', '-pthread']
        link = ['-ldl'] if sys.platform != 'darwin' else []
        sources = [ROOT / 'audio' / name for name in (
            'config.cpp', 'dsp.cpp', 'engine.cpp', 'order.cpp', 'random.cpp', 'output.cpp')]
        subprocess.run(common + [str(ROOT / 'tests/native_engine_test.cpp')]
                       + list(map(str, sources)) + link + ['-o', str(cls.build / 'engine')],
                       check=True, capture_output=True, text=True)
        shared = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
        cls.library = cls.build / ('fake.dylib' if sys.platform == 'darwin' else 'fake.so')
        subprocess.run(common + shared + [str(ROOT / 'tests/fake_portaudio.cpp'),
                                          '-o', str(cls.library)], check=True, capture_output=True, text=True)
        subprocess.run(common + [str(ROOT / 'tests/native_output_test.cpp'),
                                 str(ROOT / 'audio/output.cpp')]
                       + link + ['-o', str(cls.build / 'output')], check=True, capture_output=True, text=True)

    def test_standalone_engine_and_allocation_free_callback(self):
        subprocess.run([str(self.build / 'engine'), str(self.library)], check=True, capture_output=True, text=True)

    def test_native_device_lifecycle(self):
        subprocess.run([str(self.build / 'output'), str(self.library)],
                       check=True, capture_output=True, text=True)

    def test_desktop_bridge_needs_no_python_audio_runtime(self):
        subprocess.run([sys.executable, '-c', """
import sys
from audio import SoundEngine, SOUND_THEMES
import numpy as np
engine = SoundEngine(8000)
engine.set_driving_parameters(50, 70, .7, 2, 'ready', SOUND_THEMES['Comfort'])
out = np.empty((512, 2), dtype=np.float32)
engine._callback(out, 512, None, None)
assert np.isfinite(out).all() and np.max(np.abs(out)) > 0
assert 'sounddevice' not in sys.modules
assert 'scipy' not in sys.modules
"""], cwd=ROOT, check=True, capture_output=True, text=True)

    def test_native_playback_bridge_and_failure_recovery(self):
        subprocess.run([sys.executable, '-c', """
import os
import numpy as np
from audio import SoundEngine
engine = SoundEngine(16000)
engine.start()
assert engine.sample_rate == 48000 and engine.stream.active
try:
    engine._callback(np.empty((16, 2), dtype=np.float32), 16, None, None)
except RuntimeError:
    pass
else:
    raise AssertionError('Offline rendering must not advance a live stream')
engine.stop()
assert engine.stream is None
os.environ['FAKE_START_FAIL'] = '1'
try:
    engine.start()
except RuntimeError:
    pass
else:
    raise AssertionError('Device start failure must propagate')
assert engine.stream is None
os.environ.pop('FAKE_START_FAIL')
engine.refresh_devices()
engine.start()
assert engine.stream.active
engine.stop()
"""], cwd=ROOT, env=dict(os.environ, EV_SOUND_PORTAUDIO_LIBRARY=str(self.library)),
                       check=True, capture_output=True, text=True)
