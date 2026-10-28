"""Python bindings for the native C++ audio engine."""
from dataclasses import asdict, field, make_dataclass
from importlib.util import find_spec
import os
import struct
from pathlib import Path

try:
    from audio import _native_dsp
except ImportError as exc:
    raise ImportError('Native audio extension is required; run ./launch.sh to build it.') from exc

if not hasattr(_native_dsp, 'Engine'):
    raise ImportError('Native audio extension is outdated; run ./launch.sh to rebuild it.')

# Reuse sounddevice's bundled PortAudio without initializing a second client.
_package = find_spec('_sounddevice_data')
if _package and _package.submodule_search_locations:
    _library_dir = Path(next(iter(_package.submodule_search_locations))) / 'portaudio-binaries'
    _libraries = list(_library_dir.glob('libportaudio*.dylib')) + [
        path for path in [_library_dir / f'libportaudio{struct.calcsize("P") * 8}bit.dll']
        if path.exists()
    ]
    if _libraries and not os.environ.get('EV_SOUND_PORTAUDIO_LIBRARY'):
        _native_dsp.set_output_library(str(_libraries[0]))


def _validate_order_config(self):
    _native_dsp.validate_config(asdict(self))


AUDIO_SOURCE_FILES = (
    'audio/__init__.py', 'audio/engine.h', 'audio/engine.cpp',
    'audio/config.cpp', 'audio/order.cpp', 'audio/random.cpp',
    'audio/dsp.h', 'audio/dsp.cpp', 'audio/output.h',
    'audio/output.cpp', 'audio/bindings.cpp',
)
OrderSoundConfig = make_dataclass(
    'OrderSoundConfig',
    [(name, type(value), field(default=value)) for name, value in _native_dsp.order_defaults().items()],
    frozen=True, namespace={'__post_init__': _validate_order_config, '__module__': __name__},
)
OrderSynth = _native_dsp.OrderSynth
smooth_curve = _native_dsp.smooth_curve
PROFILES = _native_dsp.profiles()
DEBUG_THEMES = _native_dsp.debug_themes()
SOUND_THEMES = _native_dsp.sound_themes()
SoundEngine = _native_dsp.Engine
