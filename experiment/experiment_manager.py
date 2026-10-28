"""Local pilot records and deterministic sound auditions; no optimizer or vehicle updates."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import uuid

import numpy as np
from scipy.io.wavfile import write
from PySide6.QtCore import QObject, Property, QRunnable, QThreadPool, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from audio import AUDIO_SOURCE_FILES, OrderSoundConfig
from audio import SOUND_THEMES
from audio import SoundEngine

DATA_ROOT = Path(__file__).resolve().parents[1] / 'experiment_data'
# Audio-domain test inputs, not a physical acceleration/braking calibration.
STIMULUS = ((0, 0, 0, 0, 0), (1, 0, 0, 0, 0), (2, 10, 60, .6, 2),
            (6, 60, 60, .6, 2), (7, 70, 20, .15, 0), (11, 70, 20, .15, 0),
            (12, 65, 0, -.35, -1), (15, 35, 0, -.35, -1), (16, 35, 0, 0, 0))
# Provisional pilot bounds, not global/theme/personalization decisions.
CONTROL_BOUNDS = {'pitch_scale': (.5, 1.5), 'pitch_offset': (0, 60),
                  'speed_curve': (.5, 3), 'regen_presence': (.2, .7)}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ExperimentStore:
    def __init__(self, root=DATA_ROOT):
        self.root = Path(root)
        self.path = None

    def start(self, metadata):
        session = self.root / f'{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:10]}'
        session.mkdir(parents=True)
        record = dict(schema_version=1, session_id=session.name, created_utc=utc_now(), **metadata)
        with (session / 'session.json').open('x', encoding='utf-8') as handle:
            json.dump(record, handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        self.path = session

    def append(self, kind, **data):
        if self.path is None:
            raise RuntimeError('No experiment session is open.')
        line = json.dumps(dict(kind=kind, utc=utc_now(), **data), allow_nan=False) + '\n'
        with (self.path / 'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())


def candidate_snapshot(profile_name, controls, config):
    if set(controls) != set(CONTROL_BOUNDS):
        raise ValueError('Unknown or missing pilot controls.')
    for key, (low, high) in CONTROL_BOUNDS.items():
        if not low <= controls[key] <= high:
            raise ValueError(f'{key} is outside its pilot range.')
    profile = dict(SOUND_THEMES[profile_name], electric_pitch_scale=controls['pitch_scale'],
                   electric_pitch_offset=controls['pitch_offset'])
    config = replace(config, speed_pitch_saturation=controls['speed_curve'],
                     regen_gain=controls['regen_presence'])
    return dict(candidate_id=uuid.uuid4().hex, origin=profile_name, controls=dict(controls),
                profile=profile, order_config=asdict(config))


class RenderSignals(QObject):
    done = Signal(str, object, str)


class RenderPair(QRunnable):
    def __init__(self, token, path, candidates, signals):
        super().__init__()
        self.token, self.path, self.candidates, self.signals = token, path, candidates, signals

    def run(self):
        try:
            results = {}
            rate, frames = 48000, 480
            times = np.array([row[0] for row in STIMULUS])
            values = np.array(STIMULUS)[:, 1:]
            for label, candidate in self.candidates.items():
                config = OrderSoundConfig(**candidate['order_config'])
                engine = SoundEngine(rate, config)
                chunks = []
                for block in range(1600):
                    t = block / 100
                    speed, pedal, load, accel = [float(np.interp(t, times, values[:, i])) for i in range(4)]
                    engine.set_driving_parameters(speed, pedal, load, accel, 'ready', candidate['profile'])
                    out = np.empty((frames, 1), dtype=np.float32)
                    engine._callback(out, frames, None, None)
                    chunks.append(out[:, 0].copy())
                samples = np.concatenate(chunks)
                fade = np.linspace(0, 1, rate // 10)
                samples[:len(fade)] *= fade
                samples[-len(fade):] *= fade[::-1]
                if not np.isfinite(samples).all() or np.max(np.abs(samples)) >= 1:
                    raise ValueError('Audition render is invalid or clipped.')
                target = self.path / f'{candidate["candidate_id"]}.wav'
                write(target, rate, samples)
                results[label] = dict(path=str(target), sample_rate=rate, duration_s=16,
                                      peak=float(np.max(np.abs(samples))), rms=float(np.sqrt(np.mean(samples**2))),
                                      sha256=hashlib.sha256(target.read_bytes()).hexdigest())
            self.signals.done.emit(self.token, results, '')
        except Exception as exc:
            self.signals.done.emit(self.token, {}, str(exc))


class ExperimentManager(QObject):
    changed = Signal()

    def __init__(self, simulator, parent=None, data_root=DATA_ROOT):
        super().__init__(parent)
        self.simulator = simulator
        self.store = ExperimentStore(data_root)
        self.stage = 'setup'
        self.error = ''
        self.profile = 'Deep'
        self.trial = 0
        self.saved = 0
        self.pair = {}
        self.renders = {}
        self.heard = set()
        self.playing = ''
        self.session_open = False
        self.practice = False
        self.token = ''
        self.controls = {'A': dict(pitch_scale=1., pitch_offset=20., speed_curve=2., regen_presence=.45),
                         'B': dict(pitch_scale=.8, pitch_offset=15., speed_curve=1.5, regen_presence=.35)}
        self.rng = random.Random()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.signals = RenderSignals(self)
        self.signals.done.connect(self._rendered)
        self.output = QAudioOutput(self)
        self.output.setVolume(1.)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.player.errorOccurred.connect(self._playback_error)
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self._device_changed)

    state = Property(str, lambda self: self.stage, notify=changed)
    message = Property(str, lambda self: self.error, notify=changed)
    profiles = Property('QStringList', lambda self: list(SOUND_THEMES), constant=True)
    savedCount = Property(int, lambda self: self.saved, notify=changed)
    trialNumber = Property(int, lambda self: self.trial, notify=changed)
    playingSound = Property(str, lambda self: self.playing, notify=changed)
    heardA = Property(bool, lambda self: 'A' in self.heard, notify=changed)
    heardB = Property(bool, lambda self: 'B' in self.heard, notify=changed)
    sessionPath = Property(str, lambda self: str(self.store.path or DATA_ROOT), notify=changed)
    candidateControls = Property('QVariantMap', lambda self: self.controls, notify=changed)
    busy = Property(bool, lambda self: self.stage == 'rendering' or bool(self.playing), notify=changed)

    def _log(self, kind, **data):
        try:
            self.store.append(kind, **data)
            return True
        except Exception as exc:
            self.error = f'Unable to save experiment data: {exc}'
            self.changed.emit()
            return False

    @Slot(str, bool)
    def start(self, profile, practice):
        if self.session_open or self.stage == 'rendering':
            return
        if profile not in SOUND_THEMES:
            return
        try:
            source = Path(__file__).resolve().parents[1]
            hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                      for name in AUDIO_SOURCE_FILES}
            self.store.start(dict(mode='manual_pilot', initial_profile=profile, practice_selected=practice,
                                  vehicle=asdict(self.simulator.car), engine_hashes=hashes,
                                  stimulus=list(STIMULUS), stimulus_columns=['time_s', 'speed_kmh', 'accelerator_percent',
                                                                            'signed_motor_load', 'acceleration_m_s2'],
                                  pilot_bounds=CONTROL_BOUNDS, rating_scale=dict(min=1, max=7),
                                  loudness_matching=False, output_volume=1.0))
        except Exception as exc:
            self.error = f'Unable to create experiment session: {exc}'
            self.changed.emit()
            return
        self.session_open = True
        self.profile, self.practice = profile, practice
        self.saved, self.trial, self.error = 0, 0, ''
        if practice:
            self.simulator.selectSoundTheme(profile)
            self.stage = 'practice'
        else:
            self.beginComparison()
        self.changed.emit()

    @Slot()
    def beginComparison(self):
        if not self.session_open or self.stage not in ('practice', 'setup'):
            return
        self.simulator.shutdown()
        self.stage = 'edit'
        self._log('practice_finished', practiced=self.practice)
        self.changed.emit()

    @Slot(str, str, float)
    def setControl(self, candidate, key, value):
        if self.stage != 'edit' or candidate not in ('A', 'B') or key not in CONTROL_BOUNDS:
            return
        low, high = CONTROL_BOUNDS[key]
        if not low <= value <= high:
            return
        self.controls[candidate][key] = round(value, 4)
        self.changed.emit()

    @Slot()
    def varyB(self):
        if self.stage != 'edit':
            return
        for key, (low, high) in CONTROL_BOUNDS.items():
            self.controls['B'][key] = round(self.rng.uniform(low, high), 3)
        self.changed.emit()

    @Slot()
    def prepare(self):
        if self.stage != 'edit' or not self.session_open:
            return
        try:
            pair = {label: candidate_snapshot(self.profile, values, self.simulator.audio.order_synth.config)
                    for label, values in self.controls.items()}
        except Exception as exc:
            self.error = str(exc)
            self.changed.emit()
            return
        token = uuid.uuid4().hex
        if not self._log('pair_created', trial=self.trial + 1, pair_id=token, candidates=pair):
            return
        self.token, self.pair = token, pair
        self.trial += 1
        self.error = ''
        self.stage = 'rendering'
        self.heard.clear()
        self.renders = {}
        self.changed.emit()
        self.pool.start(RenderPair(token, self.store.path, pair, self.signals))

    @Slot(str, object, str)
    def _rendered(self, token, renders, error):
        if token != self.token or not self.session_open:
            return
        if error:
            self.error = f'Unable to render audition: {error}'
            self.stage = 'edit'
        elif self._log('pair_rendered', trial=self.trial, pair_id=token, audio=renders):
            self.renders = renders
            self.stage = 'compare'
        else:
            self.stage = 'edit'
        self.changed.emit()

    @Slot(str)
    def play(self, label):
        if self.stage != 'compare' or label not in self.renders or self.playing:
            return
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self.error = 'No system audio output is available.'
            self.changed.emit()
            return
        if not self._log('audition_started', trial=self.trial, pair_id=self.token, label=label,
                         candidate_id=self.pair[label]['candidate_id'], output_device=device.description()):
            return
        self.error = ''
        self.output.setDevice(device)
        self.playing = label
        self.player.setSource(QUrl.fromLocalFile(self.renders[label]['path']))
        self.player.play()
        self.changed.emit()

    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.playing:
            label = self.playing
            if self._log('audition_completed', trial=self.trial, pair_id=self.token, label=label):
                self.heard.add(label)
            self.playing = ''
            self.changed.emit()

    def _playback_error(self, error, message):
        if error != QMediaPlayer.Error.NoError:
            self.error = f'Audio playback failed: {message}. Replay the sound before rating.'
            self.playing = ''
            self.changed.emit()

    def _device_changed(self):
        if self.playing:
            self.stopPlayback()
            self.error = 'Audio output changed. Replay the sound on the new output before rating.'
            self.changed.emit()
        self.output.setDevice(QMediaDevices.defaultAudioOutput())

    @Slot()
    def stopPlayback(self):
        if self.playing:
            label = self.playing
            self.player.stop()
            self.playing = ''
            self._log('audition_stopped', trial=self.trial, pair_id=self.token, label=label)
            self.changed.emit()

    @Slot(str, int, int, str)
    def saveRating(self, preferred, rating_a, rating_b, notes):
        if self.stage != 'compare' or self.playing or self.heard != {'A', 'B'}:
            return
        if preferred not in ('A', 'B', 'tie', 'neither') or not (1 <= rating_a <= 7 and 1 <= rating_b <= 7):
            self.error = 'Select a preference and rate both sounds from 1 to 7.'
            self.changed.emit()
            return
        if len(notes) > 4000:
            self.error = 'Please limit notes to 4,000 characters.'
            self.changed.emit()
            return
        if not self._log('comparison', trial=self.trial, pair_id=self.token, preferred=preferred,
                         ratings={'A': rating_a, 'B': rating_b}, notes=notes):
            return
        self.saved += 1
        self.error = ''
        self.stage = 'saved'
        self.changed.emit()

    @Slot()
    def nextPair(self):
        if self.stage == 'saved':
            self.stage = 'edit'
            self.heard.clear()
            self.changed.emit()

    @Slot()
    def finish(self):
        if self.stage == 'rendering':
            return
        self.stopPlayback()
        if self.session_open and not self._log('session_finished', saved_comparisons=self.saved):
            return
        self.session_open = False
        self.stage = 'setup'
        self.error = ''
        self.changed.emit()

    @Slot()
    def close(self):
        self.stopPlayback()
        if self.session_open:
            self._log('session_closed', saved_comparisons=self.saved, pending_pair=self.token)
        self.session_open = False
        self.token = ''
        self.pool.waitForDone()
