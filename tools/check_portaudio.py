"""Windows/Mac diagnostic: show which PortAudio library the app would load and whether it opens."""
import ctypes, os, sys
import audio  # sets the bundled library path
try:
    import _sounddevice_data as d
    print('sounddevice data:', list(d.__path__))
    folder = os.path.join(list(d.__path__)[0], 'portaudio-binaries')
    print('binaries:', os.listdir(folder) if os.path.isdir(folder) else 'MISSING ' + folder)
except ImportError:
    print('_sounddevice_data missing: reinstall with pip install --force-reinstall sounddevice')
import sounddevice as sd
print('sounddevice loaded PortAudio:', sd._libname)
print('output devices:', [(i, x['name']) for i, x in enumerate(sd.query_devices()) if x['max_output_channels'] > 0])
try:
    ctypes.CDLL(sd._libname)
    print('direct load: ok')
except OSError as exc:
    print('direct load failed:', exc)
