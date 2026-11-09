"""Python bindings for the native C++ audio engine."""
from dataclasses import asdict, field, make_dataclass
from importlib.util import find_spec
import os
import struct
import sys
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
    # sounddevice ships PortAudio for every platform; pick the one for this OS.
    _library_name = (f'libportaudio{struct.calcsize("P") * 8}bit.dll' if sys.platform == 'win32'
                     else 'libportaudio.dylib' if sys.platform == 'darwin' else '')
    _libraries = [path for path in [_library_dir / _library_name] if _library_name and path.exists()]
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

# Audition variants share the three experiment modes; saved search profiles remain independent.
SOUND_RECIPES = {
    'Comfort': {
        'Clean Electric': SOUND_THEMES['Comfort'],
        'Warm Motor': {**SOUND_THEMES['Comfort'], 'electric_pitch_scale': 0.25,
                       'electric_pitch_offset': 78.0, 'electric_depth': 0.12,
                       'electric_cutoff': 430.0, 'richness': 0.12,
                       'electric_growl': 0.24, 'drive_cruise_gain': 0.32},
    },
    'Sport': {
        'Electric Sport': SOUND_THEMES['Sport'],
        'ICE Inspired': {**SOUND_THEMES['Sport'], 'order_synthesis': 1.0,
                         'order_rpm_scale': 1.35, 'order_throttle_rpm_boost': 3200.0},
    },
    'Deep': {
        'Traction Glide': SOUND_THEMES['Deep'],
        'Orchestral Rise': {**SOUND_THEMES['Deep'], 'electric_pitch_scale': 0.78,
                           'electric_pitch_offset': 42.0, 'electric_cutoff': 760.0,
                           'electric_depth': 0.15, 'traction_mix': 0.08,
                           'orchestral_mix': 0.88, 'drive_cruise_gain': 0.48,
                           'drive_attack_s': 0.35, 'drive_release_s': 0.55,
                           'electric_pitch_smoothing_s': 0.28},
    },
}
