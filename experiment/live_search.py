"""Versioned, local interactive preference search; never changes vehicle state."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import hashlib
from itertools import combinations
import math
import logging
import os
import shutil
from pathlib import Path
import random
import secrets
import time
import uuid

from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer
from audio import AUDIO_SOURCE_FILES, SOUND_THEMES
from audio import OrderSoundConfig
from experiment.preference_gp import select_query

DATA_ROOT = Path(__file__).resolve().parents[1] / 'experiment_data' / 'interactive'
# Normalized exploratory controls; physical mappings are frozen in each session.
CONTROLS = ('register', 'motion', 'richness', 'depth', 'brightness', 'texture', 'effort', 'regen')
GP_CONTROLS = ('harmonic_mix', 'pitch_trajectory', 'amplitude_trajectory', 'spectral_balance')
COMFORT_CONTROLS = ('register', 'timbre', 'ensemble', 'response')
COMFORT_OPENING = (
    (0., 0., 0., 0.), (1., 1., 0., 1.),
    (.5, .5, 0., .5), (.25, .65, 1., .65),
    (.85, .2, .85, .15), (.15, .85, .2, .9),
)
# Shared physical mapping for new sessions. Mode only selects the opening seed.
CHARACTER_CONTROLS = ('register', 'motion', 'tone', 'whirl', 'pulse', 'shimmer',
                      'ensemble', 'phrase', 'response', 'regen')
CHARACTER_SEEDS = {
    'Comfort': (.50, .06, .05, 0., 0., 0., 0., 0., .12, .12),
    'Sport': (.18, .93, .85, .35, .50, .10, 0., .12, .88, .42),
    'Deep': (0., .25, .30, .05, .05, 0., .25, .05, .35, .25),
}
CHARACTER_OPENING = (
    (.18, .20, .25, .95, .05, .05, .05, .15, .45, .30),  # moving whirr
    (.55, .75, .82, .05, .95, .15, .05, .10, .85, .40),  # rhythmic motor
    (.85, .35, .25, .10, .05, .95, .05, .05, .55, .25),  # light high tone
    (.32, .24, .40, .05, .05, .05, .95, .18, .38, .30),  # chordal body
    (.35, .60, .50, .25, .10, .10, .18, .95, .60, .45),  # changing phrase
)
DEEP_MOTOR_OPENING = (.45, .58, .55, .15, .20, .08, 0., 0., .62, .35)
FEATURE_GROUPS = (('register',), ('motion',), ('tone', 'whirl'),
                  ('pulse', 'shimmer'), ('ensemble', 'phrase'), ('response', 'regen'))
FEATURE_MIXES = ((0, 1), (2, 3, 4), tuple(range(6)))
VERSION = 3


def now():
    return datetime.now(timezone.utc).isoformat()


def profile_for(base, controls):
    keys = set(controls)
    if keys not in (set(CONTROLS), set(GP_CONTROLS), set(COMFORT_CONTROLS), set(CHARACTER_CONTROLS)) or any(
            not math.isfinite(v) or not 0 <= v <= 1 for v in controls.values()):
        raise ValueError('Invalid sound controls.')
    p = dict(base)
    if keys == set(CHARACTER_CONTROLS):
        register, motion, tone, whirl, pulse, shimmer, ensemble, phrase, response, regen = (
            controls[key] for key in CHARACTER_CONTROLS)
        start, scale = 70 + 110 * register, .08 + 1.15 * motion
        p.update(base_hz=70., gain=.32, electric_mix=1., order_synthesis=False,
                 electric_start_hz=start, electric_pitch_scale=scale,
                 electric_pitch_offset=max(0., start - 70 * scale),
                 richness=.02 + .54 * tone, electric_depth=min(.30, .04 + .19 * ensemble + .09 * tone),
                 electric_cutoff=430 + 600 * tone + 600 * shimmer,
                 electric_detune=.002 + .012 * whirl, electric_growl=.8 * tone,
                 electric_effort=.25 + 1.3 * response,
                 electric_whirl=whirl, electric_pulse=pulse, electric_shimmer=shimmer,
                 orchestral_mix=.65 * ensemble, traction_mix=.70 * phrase,
                 traction_cycle_s=2.5, traction_cycle_mix=phrase,
                 traction_crossfade_s=.75, traction_sweep_hz=90.,
                 traction_morph_mix=.25, traction_stage_colour=.55,
                 drive_cruise_gain=.12 + .70 * response,
                 acceleration_richness=.01 + .17 * response,
                 drive_attack_s=.25 - .19 * response,
                 drive_release_s=.42 - .28 * response,
                 electric_pitch_smoothing_s=.23 - .14 * response,
                 electric_regen_gain=.15 + .50 * regen,
                 electric_regen_richness=.5 * regen,
                 regen_attack_s=.30 - .16 * response,
                 regen_release_s=.45 - .20 * response)
    elif keys == set(COMFORT_CONTROLS):
        def span(low, middle, high, value):
            return low + (middle - low) * 2 * value if value <= .5 else middle + (high - middle) * (2 * value - 1)

        register, timbre, ensemble, response = (controls[key] for key in COMFORT_CONTROLS)
        start = span(90., 125., 170., register)
        p.update(electric_start_hz=start,
                 electric_pitch_offset=start - base['electric_pitch_scale'] * base['base_hz'],
                 richness=span(.01, base['richness'], .30, timbre),
                 electric_cutoff=span(390., base['electric_cutoff'], 1000., timbre),
                 electric_depth=span(.02, base['electric_depth'], .14, timbre),
                 orchestral_mix=.55 * ensemble,
                 drive_cruise_gain=span(.08, base['drive_cruise_gain'], .45, response),
                 acceleration_richness=span(0., base['acceleration_richness'], .16, response),
                 electric_effort=span(.18, base['electric_effort'], 1.1, response),
                 drive_attack_s=span(.22, base['drive_attack_s'], .08, response),
                 drive_release_s=span(.45, base['drive_release_s'], .20, response))
    elif keys == set(GP_CONTROLS):
        pitch_factor = .5 + controls['pitch_trajectory']
        scale = base['electric_pitch_scale'] * pitch_factor
        start = (base.get('electric_start_hz') or
                 base['electric_pitch_offset'] + base['electric_pitch_scale'] * base['base_hz']) * pitch_factor
        mix = .5 + controls['harmonic_mix']
        p.update(electric_start_hz=start, electric_pitch_scale=scale,
                 electric_pitch_offset=max(0, start - scale * base['base_hz']),
                 richness=min(.9, base['richness'] * mix),
                 electric_effort=min(2., base.get('electric_effort', 1.) * mix),
                 electric_load_exponent=.7 + .6 * controls['amplitude_trajectory'],
                 electric_depth=min(.3, max(0., base.get('electric_depth', .14)
                                              + .16 * (controls['spectral_balance'] - .5))),
                 electric_cutoff=min(2000., max(200., base.get('electric_cutoff', 900.)
                                                + 900 * (controls['spectral_balance'] - .5))))
    else:
        start = base['electric_pitch_offset'] + base['electric_pitch_scale'] * base['base_hz']
        scale = base['electric_pitch_scale'] * (.4 + 1.2 * controls['motion'])
        p.update(electric_start_hz=start * (.6 + .8 * controls['register']),
                 electric_pitch_scale=scale,
                 electric_pitch_offset=max(0, start * (.6 + .8 * controls['register']) - scale * base['base_hz']),
                 richness=controls['richness'] * .9,
                 electric_depth=.04 + .20 * controls['depth'],
                 electric_cutoff=450 + 950 * controls['brightness'],
                 electric_detune=.015 * controls['texture'],
                 electric_effort=.3 + 1.2 * controls['effort'],
                 electric_regen_gain=.15 + .5 * controls['regen'])
    return p


class LiveSearch(QObject):
    changed = Signal()

    def __init__(self, controller, parent=None, root=DATA_ROOT):
        super().__init__(parent)
        self.controller, self.root = controller, Path(root)
        self.data = None
        self.path = None
        self.trace_preview = None
        self.message = ''
        self._sample_time = time.monotonic()
        self._stats = self._empty_stats()
        self.monitor = QTimer(self)
        self.monitor.setInterval(200)
        self.monitor.timeout.connect(self._sample)

    @staticmethod
    def _empty_stats():
        return dict(seconds=0., samples=0, speed_sum=0., min_speed=None, max_speed=0.,
                    load_sum=0., pedal_sum=0., acceleration_sum=0.)

    active = Property(bool, lambda s: bool(s.data and s.data['status'] == 'active'), notify=changed)
    participant = Property(str, lambda s: s.data['participant'] if s.data else '', notify=changed)
    mode = Property(str, lambda s: s.data['mode'] if s.data else '', notify=changed)
    learningMethod = Property(str, lambda s: s.data.get('learning_method', 'evolutionary') if s.data else '', notify=changed)
    pairNumber = Property(int, lambda s: s.data['completed'] + (0 if s.data.get('checkpoint') else 1) if s.data else 1, notify=changed)
    selected = Property(str, lambda s: s.data['selected'] if s.data else '', notify=changed)
    triedA = Property(bool, lambda s: bool(s.data and s.data['tried']['A']), notify=changed)
    triedB = Property(bool, lambda s: bool(s.data and s.data['tried']['B']), notify=changed)
    ratingA = Property(int, lambda s: s.data['ratings']['A'] if s.data else 0, notify=changed)
    ratingB = Property(int, lambda s: s.data['ratings']['B'] if s.data else 0, notify=changed)
    ratingSources = Property('QVariantMap', lambda s: s.data.get('rating_sources', {}) if s.data else {}, notify=changed)
    preference = Property(str, lambda s: s.data.get('preference', '') if s.data else '', notify=changed)
    preferenceReady = Property(bool, lambda s: bool(s.data and s.data.get('preference') in ('A', 'equal', 'B')
                                                       and all(s.data['tried'].values())), notify=changed)
    feedbackReady = Property(bool, lambda s: bool(s.data and
        (all(s.data['ratings'].values()) or (s.data.get('preference') in ('A', 'equal', 'B')
                                             and all(s.data['tried'].values())))), notify=changed)
    error = Property(str, lambda s: s.message, notify=changed)
    checkpoint = Property(str, lambda s: s.data.get('checkpoint', '') if s.data else '', notify=changed)
    debug = Property('QVariantMap', lambda s: s._debug(), notify=changed)

    @property
    def profile(self):
        if self.trace_preview:
            return self.trace_preview['profile']
        if not self.data:
            return None
        ident = self.data.get('playing')
        return self.data['candidates'][ident]['profile'] if ident else None

    def _commit(self, data, path=None):
        path = path or self.path
        temporary = path.with_suffix('.tmp')
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError) as exc:
            self.message = f'Could not save: {exc}'
            logging.getLogger('Search').error(self.message)
            self.changed.emit()
            return False
        self.data, self.path, self.message = data, path, ''
        self.changed.emit()
        return True

    def _candidate(self, d, controls, parents=(), kind='initial'):
        ident = f"c{len(d['candidates']) + 1:04}"
        d['candidates'][ident] = dict(id=ident, controls=controls, profile=profile_for(d['base'], controls),
                                     parents=list(parents), kind=kind, created=now())
        return ident

    def _pair(self, d, ids, rng):
        ids = list(ids)
        rng.shuffle(ids)
        d['pair'] = dict(zip(('A', 'B'), ids))
        d['ratings'] = dict(A=0, B=0)
        d['rating_sources'] = dict(A=0, B=0)
        if d.get('learning_method') == 'evolutionary':
            for slot, ident in d['pair'].items():
                for number in range(len(d['history']), 0, -1):
                    previous = d['history'][number - 1]
                    previous_slot = next((key for key, candidate in previous['pair'].items()
                                          if candidate == ident), None)
                    score = previous.get('ratings', {}).get(previous_slot, 0)
                    if score:
                        d['ratings'][slot] = score
                        d['rating_sources'][slot] = number
                        break
        d['preference'] = ''
        d['tried'] = dict(A=False, B=False)
        d['selected'] = ''

    @Slot(str, str)
    @Slot(str, str, str)
    def start(self, participant, mode, learning_method='evolutionary'):
        participant = participant.strip()
        if (not participant or len(participant) > 80 or mode not in SOUND_THEMES
                or learning_method not in ('evolutionary', 'gp_preference') or self.active):
            self.message = 'Enter a name or alias (up to 80 characters).'
            self.changed.emit()
            return
        seed = secrets.randbits(53)
        rng = random.Random(seed)
        base = dict(SOUND_THEMES[mode])
        control_keys = CHARACTER_CONTROLS
        d = dict(schema=VERSION,
                 algorithm='gp-feature-v2' if learning_method == 'gp_preference' else 'three-lineage-character-v1',
                 learning_method=learning_method, id=uuid.uuid4().hex,
                 participant=participant, participant_id=uuid.uuid5(uuid.NAMESPACE_URL, participant.casefold()).hex,
                 mode=mode, vehicle=self.controller.selectedVehicle, vehicle_snapshot=asdict(self.controller.car),
                 created=now(), seed=seed,
                 sound_config=asdict(self.controller.audio.order_synth.config),
                 dsp_hashes={name: hashlib.sha256((Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                             for name in AUDIO_SOURCE_FILES},
                 base=base, control_keys=control_keys,
                 bounds={k: [0., 1.] for k in control_keys}, completed=0, block_end=20,
                 status='active', checkpoint='', candidates={}, history=[], auditions=[], survivors=[],
                 playing=None, favorite=None)
        controls = dict(zip(control_keys, CHARACTER_SEEDS[mode]))
        d['baseline_controls'] = deepcopy(controls)
        if learning_method == 'gp_preference':
            initial = []
            d['feature_winners'] = {}
            for group in FEATURE_GROUPS:
                for high in (False, True):
                    variant = dict(controls)
                    for key in group:
                        variant[key] = (.55 if key in ('whirl', 'pulse', 'shimmer', 'ensemble', 'phrase')
                                        else .8) if high else .05
                    initial.append(self._candidate(d, variant, kind='feature-contrast'))
        else:
            initial = [self._candidate(d, controls, kind='mode-seed')]
            opening = (DEEP_MOTOR_OPENING, *CHARACTER_OPENING[1:]) if mode == 'Deep' else CHARACTER_OPENING
            initial.extend(self._candidate(d, dict(zip(control_keys, values))) for values in opening)
        d['initial'] = initial
        self._pair(d, initial[:2], rng)
        if self._commit(d, self.root / d['id'] / 'session.json'):
            self.trace_preview = None
            self._stats = self._empty_stats()
            self._sample_time = time.monotonic()
            self.monitor.start()
            self.controller._update_audio()
            label = 'GP preference + expected improvement' if learning_method == 'gp_preference' else 'evolutionary mutation'
            logging.getLogger('Search').info('Session started: %s · %s.', mode, label)

    @Slot(str, result='QVariantList')
    def sessions(self, participant):
        rows = []
        for path in self.root.glob('*/session.json'):
            try:
                d = json.loads(path.read_text())
                if d['participant'].casefold() == participant.strip().casefold() and d['schema'] == VERSION:
                    method = 'GP' if d.get('learning_method') == 'gp_preference' else 'Evolutionary'
                    rows.append(dict(id=d['id'], text=f"{d['created'][:16]} · {d['mode']} · {method} · {d['completed']} pairs · {d['status']}",
                                     favorite=bool(d.get('favorite'))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(rows, key=lambda x: x['text'], reverse=True)

    @Slot(result='QVariantList')
    def traceSessions(self):
        rows = []
        for path in self.root.glob('*/session.json'):
            try:
                d = json.loads(path.read_text(encoding='utf-8'))
                if d.get('schema') != VERSION:
                    continue
                rows.append(dict(id=d['id'], participant=d['participant'], mode=d['mode'],
                                 learning_method=d.get('learning_method', 'evolutionary'),
                                 created=d['created'], completed=d.get('completed', 0),
                                 status=d.get('status', 'unknown'), favorite=bool(d.get('favorite'))))
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(rows, key=lambda row: row['created'], reverse=True)

    @Slot(str, result='QVariantMap')
    def traceSession(self, ident):
        if len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
            return {}
        try:
            d = json.loads((self.root / ident / 'session.json').read_text(encoding='utf-8'))
            if d.get('schema') != VERSION:
                return {}
            candidates = d['candidates']
            favorite_slot = next((ending.get('favorite_slot', '') for ending in reversed(d.get('endings', []))
                                  if ending.get('reason') == 'satisfied'), '')
            comparisons = []
            for index, row in enumerate(d.get('history', []), 1):
                pair = {slot: candidates[candidate_id] for slot, candidate_id in row['pair'].items()}
                auditions = {a.get('slot'): a.get('stats', {}) for a in d.get('auditions', [])
                             if a.get('pair') == index}
                comparisons.append(dict(number=index, time=row.get('time', ''), pair=pair,
                                        preference=row.get('preference', ''), winner=row.get('winner'),
                                        ratings=row.get('ratings', {}), rating_sources=row.get('rating_sources', {}),
                                        auditions=auditions))
            if d.get('pair') and not d.get('checkpoint') and d.get('completed', 0) < d.get('block_end', 20):
                comparisons.append(dict(number=d.get('completed', 0) + 1, time='',
                                        pair={slot: candidates[candidate_id] for slot, candidate_id in d['pair'].items()},
                                        preference=d.get('preference', ''), ratings=d.get('ratings', {}),
                                        rating_sources=d.get('rating_sources', {}), winner=None, auditions={}, current=True,
                                        final_choice=favorite_slot if d.get('status') == 'satisfied' else ''))
            return dict(id=d['id'], participant=d['participant'], mode=d['mode'],
                        learning_method=d.get('learning_method', 'evolutionary'), created=d['created'],
                        status=d.get('status', 'unknown'), completed=d.get('completed', 0),
                        comparisons=comparisons, skipped_pairs=d.get('skipped_pairs', []), candidates=candidates,
                        favorite=d.get('favorite'), favorite_slot=favorite_slot, base=d.get('base', {}),
                        bounds=d.get('bounds', {}), sound_config=d.get('sound_config', {}))
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    @Slot(str, str, result=bool)
    def previewTraceCandidate(self, session_id, candidate_id):
        if self.active:
            self.message = 'Finish or pause personalization before replaying a saved candidate.'
            self.changed.emit()
            return False
        if len(session_id) != 32 or any(c not in '0123456789abcdef' for c in session_id):
            return False
        try:
            d = json.loads((self.root / session_id / 'session.json').read_text(encoding='utf-8'))
            candidate = d['candidates'][candidate_id]
            profile = candidate['profile']
            profile_for(d['base'], candidate['controls'])
            if not isinstance(profile, dict):
                return False
            self.controller._search.clearPlayback()
            self.trace_preview = dict(profile=profile, mode=d['mode'], candidate=candidate_id, session=session_id)
            self.controller.sound_theme = d['mode']
            self.controller.soundThemeChanged.emit()
            self.controller._update_audio()
            if not self.controller.running:
                self.controller.toggle()
            self.changed.emit()
            logging.getLogger('Search').info('Replaying saved sound %s from %s.', candidate_id, d['created'][:16])
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    @Slot(str, result=bool)
    def deleteSession(self, ident):
        if len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
            return False
        if self.active and self.data and self.data.get('id') == ident:
            self.message = 'Pause or finish the active session before deleting it.'
            self.changed.emit()
            return False
        path = self.root / ident
        if not (path / 'session.json').is_file():
            return False
        trash = self.root / f'.deleting-{ident}-{uuid.uuid4().hex}'
        try:
            path.rename(trash)
            shutil.rmtree(trash)
        except OSError as exc:
            if trash.exists() and not path.exists():
                try:
                    trash.rename(path)
                except OSError:
                    pass
            self.message = f'Could not delete session: {exc}'
            self.changed.emit()
            return False
        if self.data and self.data.get('id') == ident:
            self.monitor.stop()
            self.data = self.path = self.trace_preview = None
            self.controller._update_audio()
        elif self.trace_preview and self.trace_preview.get('session') == ident:
            self.trace_preview = None
            self.controller._update_audio()
        self.message = ''
        self.changed.emit()
        logging.getLogger('Search').info('Saved session deleted: %s.', ident[:8])
        return True

    @Slot(str, bool)
    def restore(self, ident, favorite_only=False):
        if self.active or len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
            return
        path = self.root / ident / 'session.json'
        try:
            d = json.loads(path.read_text())
            if d['schema'] != VERSION or d.get('algorithm') not in (
                    'three-lineage-mutation-v1', 'gp-preference-active-v1', 'gp-preference-ei-v2',
                    'three-lineage-comfort-v1', 'gp-preference-comfort-v1',
                    'three-lineage-character-v1', 'gp-character-v1', 'gp-feature-v2'):
                raise ValueError('Unsupported session version.')
            for candidate in d['candidates'].values():
                profile_for(d['base'], candidate['controls'])
            if favorite_only:
                if not d['favorite']:
                    raise ValueError('This session has no saved sound.')
                d['playing'] = d['favorite']
                d['status'] = 'loaded'
            else:
                d['status'] = 'active'
                d['resumed'] = now()
            config = OrderSoundConfig(**d['sound_config'])
            self.controller.selectSoundTheme(d['mode'])
            self.controller.selectVehicle(d['vehicle'])
            if self._commit(d, path):
                self.controller.audio.order_synth.config = config
                self._stats = self._empty_stats()
                if not favorite_only:
                    self._sample_time = time.monotonic()
                    self.monitor.start()
                self.controller._update_audio()
                logging.getLogger('Search').info('Saved sound loaded.' if favorite_only else 'Previous search resumed.')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.message = f'Could not restore session: {exc}'
            self.changed.emit()

    def _sample(self):
        current = time.monotonic()
        dt = min(.5, max(0., current - self._sample_time))
        self._sample_time = current
        if not self.active or not self.selected:
            return
        c, s = self.controller, self._stats
        if not c.running or c.sound_starting:
            return
        s['samples'] += 1
        s['speed_sum'] += c.car.speed
        s['min_speed'] = c.car.speed if s['min_speed'] is None else min(s['min_speed'], c.car.speed)
        s['max_speed'] = max(s['max_speed'], c.car.speed)
        s['load_sum'] += c.car.motor_torque_nm / (c.car.max_torque_nm if c.car.motor_torque_nm >= 0 else c.car.max_regen_torque_nm)
        s['pedal_sum'] += c.throttle
        s['acceleration_sum'] += c.car.acceleration_m_s2
        s['seconds'] += dt

    def _flush_audition(self, d):
        if self.selected:
            d['auditions'].append(dict(candidate=self.data['pair'][self.selected], slot=self.selected,
                                       pair=self.pairNumber, ended=now(),
                                       stats=deepcopy(self._stats)))

    @Slot(str)
    def choose(self, slot):
        if not self.active or slot not in ('A', 'B'):
            return
        d = deepcopy(self.data)
        self._flush_audition(d)
        d['selected'] = slot
        d['tried'][slot] = True
        d['playing'] = d['pair'][slot]
        if self._commit(d):
            self._stats = self._empty_stats()
            self.controller._update_audio()
            logging.getLogger('Search').info('Listening to %s (%s); vehicle state unchanged.', slot, d['pair'][slot])

    @Slot(str, int)
    def rate(self, slot, value):
        if (not self.active or slot not in ('A', 'B') or not 1 <= value <= 7
                or not (self.data['tried'][slot] or self.data.get('rating_sources', {}).get(slot, 0))):
            return
        d = deepcopy(self.data)
        d['ratings'][slot] = value
        d.setdefault('rating_sources', {})[slot] = 0
        if self._commit(d):
            logging.getLogger('Search').info('Sound %s rated %s/7.', slot, value)

    @Slot(str)
    def ratePreference(self, value):
        if (not self.active or value not in ('A', 'equal', 'B')
                or not all(self.data['tried'].values())):
            return
        d = deepcopy(self.data)
        d['preference'] = value
        if self._commit(d):
            logging.getLogger('Search').info('A/B preference: %s.', value)

    @Slot()
    def retrySimilar(self):
        if not self.active or self.checkpoint:
            return
        d = deepcopy(self.data)
        self._flush_audition(d)
        pair = dict(d['pair'])
        ids = set(pair.values())
        opening = d.get('initial', [])
        first_opening = 2 * d['completed']
        anchor = next((ident for ident in (d.get('incumbent'), d.get('parent'),
                                          opening[first_opening] if first_opening < len(opening) else None)
                       if ident in ids), pair['A'])
        keys = tuple(d.get('control_keys', CHARACTER_CONTROLS))
        motor_keys = tuple(key for key in ('register', 'motion', 'tone', 'response', 'regen',
                                          'richness', 'brightness', 'effort') if key in keys)
        varied = motor_keys if len(motor_keys) >= 2 else keys
        rng = random.Random(d['seed'] + d['completed'] + 9973 * (len(d.get('skipped_pairs', [])) + 1))
        existing = [candidate['controls'] for candidate in d['candidates'].values()]
        for _ in range(100):
            controls = dict(d['candidates'][anchor]['controls'])
            for key in rng.sample(varied, min(len(varied), 3)):
                controls[key] = min(1., max(0., controls[key] + rng.choice((-1, 1)) * rng.uniform(.2, .45)))
            if (sum((controls[key] - d['candidates'][anchor]['controls'][key]) ** 2 for key in keys) >= .22 ** 2
                    and all(sum((controls[key] - old[key]) ** 2 for key in keys) >= .08 ** 2
                            for old in existing)):
                break
        else:
            self.message = 'Could not find a distinct replacement sound.'
            self.changed.emit()
            return
        child = self._candidate(d, controls, [anchor], 'similarity-retry')
        d.setdefault('skipped_pairs', []).append(dict(number=d['completed'] + 1, pair=pair,
                                                       reason='too_similar', replacement=child, time=now()))
        previous_slot = next(slot for slot, ident in pair.items() if ident == anchor)
        anchor_tried = d['tried'][previous_slot]
        anchor_score = d['ratings'][previous_slot]
        anchor_score_source = d.get('rating_sources', {}).get(previous_slot, 0)
        self._pair(d, [anchor, child], rng)
        anchor_slot = next(slot for slot, ident in d['pair'].items() if ident == anchor)
        child_slot = 'B' if anchor_slot == 'A' else 'A'
        d['tried'][anchor_slot] = anchor_tried
        if anchor_score:
            d['ratings'][anchor_slot] = anchor_score
            d['rating_sources'][anchor_slot] = anchor_score_source
        d['selected'] = child_slot
        d['tried'][child_slot] = True
        d['playing'] = child
        if self._commit(d):
            self._stats = self._empty_stats()
            self.controller._update_audio()

    @Slot()
    def rejectBoth(self):
        if (not self.active or self.checkpoint or self.learningMethod != 'gp_preference'
                or not all(self.data['tried'].values())):
            return
        d = deepcopy(self.data)
        self._flush_audition(d)
        pair = dict(d['pair'])
        keys = tuple(d.get('control_keys', CHARACTER_CONTROLS))
        rng = random.Random(d['seed'] + d['completed'] + 17431 * (len(d.get('skipped_pairs', [])) + 1))
        existing = [candidate['controls'] for candidate in d['candidates'].values()]
        replacements = []
        for _ in range(2):
            for _ in range(100):
                controls = {key: rng.random() for key in keys}
                if all(sum((controls[key] - old[key]) ** 2 for key in keys) >= .25 ** 2 for old in existing):
                    break
            else:
                self.message = 'Could not find two distinct replacement sounds.'
                self.changed.emit()
                return
            replacements.append(controls)
            existing.append(controls)
        ids = [self._candidate(d, controls, kind='neither-replacement') for controls in replacements]
        d.setdefault('rejected', []).extend(pair.values())
        d.setdefault('skipped_pairs', []).append(dict(number=d['completed'] + 1, pair=pair,
                                                       reason='neither', replacements=ids, time=now()))
        if d.get('favorite') in pair.values():
            d['favorite'] = None
        if d.get('algorithm') in ('gp-preference-ei-v2', 'gp-preference-comfort-v1', 'gp-character-v1', 'gp-feature-v2'):
            d['incumbent'] = ids[0]
        self._pair(d, ids, rng)
        d['selected'] = 'A'
        d['tried']['A'] = True
        d['playing'] = d['pair']['A']
        if self._commit(d):
            self._stats = self._empty_stats()
            self.controller._update_audio()

    @Slot()
    def next(self):
        d = self.data
        pairwise = bool(d and d.get('preference') in ('A', 'equal', 'B') and all(d['tried'].values()))
        individual = bool(d and all(d['ratings'].values()))
        if not self.active or self.checkpoint or not (pairwise or individual):
            return
        d = deepcopy(d)
        self._flush_audition(d)
        rng = random.Random(d['seed'] + d['completed'] + 1)
        a, b = d['pair']['A'], d['pair']['B']
        use_pairwise = pairwise and (d.get('learning_method') != 'evolutionary' or not individual)
        if use_pairwise:
            preference = d['preference']
            winner = a if preference == 'A' else b if preference == 'B' else None
        else:
            ra, rb = d['ratings']['A'], d['ratings']['B']
            winner = d.get('parent') if ra == rb and d['completed'] >= 3 else (
                rng.choice([a, b]) if ra == rb else (a if ra > rb else b))
            d['preference'] = ''
        d['history'].append(dict(pair=dict(d['pair']), ratings=dict(d['ratings']),
                                 rating_sources=dict(d.get('rating_sources', {})),
                                 preference=d.get('preference', ''), winner=winner, time=now()))
        method = d.get('learning_method', 'evolutionary')
        if method == 'evolutionary':
            winner = winner or d.get('parent') or rng.choice([a, b])
            d['history'][-1]['winner'] = winner
            if d['completed'] < 3:
                d['survivors'].append(winner)
            else:
                d['survivors'][d['lineage']] = winner
        if d.get('algorithm') == 'gp-feature-v2' and d['completed'] < len(FEATURE_GROUPS):
            expected = set(d['initial'][2*d['completed']:2*d['completed']+2])
            if winner and set(d['pair'].values()) == expected:
                d['feature_winners'][str(d['completed'])] = winner
        if d.get('algorithm') in ('gp-preference-ei-v2', 'gp-preference-comfort-v1', 'gp-character-v1', 'gp-feature-v2'):
            d['incumbent'] = winner or d.get('incumbent') or a
        d['completed'] += 1
        if d['completed'] % 20 == 10:
            d['checkpoint'] = 'break'
        if d['completed'] >= d['block_end']:
            d['checkpoint'] = 'cap'
        if not d['checkpoint']:
            if method == 'gp_preference':
                self._prepare_gp_pair(d, rng)
            else:
                self._prepare_next(d, rng)
        if self._commit(d):
            self._stats = self._empty_stats()
            if method == 'gp_preference':
                detail = 'GP pair selected.' if not d['checkpoint'] else 'Waiting for continuation.'
            else:
                detail = f"{len(d['survivors'])} sounds retained."
                if d['checkpoint']:
                    detail += ' Waiting for continuation.'
            logging.getLogger('Search').info('Comparison %s saved. %s', d['completed'], detail)

    def _prepare_next(self, d, rng):
        if d['completed'] < 3:
            self._pair(d, d['initial'][2*d['completed']:2*d['completed']+2], rng)
            return
        control_keys = tuple(d.get('control_keys', CONTROLS))
        d['lineage'] = (d['completed'] - 3) % 3
        parent = d['survivors'][d['lineage']]
        d['parent'] = parent
        broad = (d['completed'] - 3) % 5 == 4
        exploratory = d.get('algorithm') in ('three-lineage-comfort-v1', 'three-lineage-character-v1')
        sigma = (.30 if d['completed'] < 8 else .18 if d['completed'] < 14 else .10) if exploratory else .15
        minimum_distance = (.25 if d['completed'] < 8 else .14 if d['completed'] < 14 else .08) if exploratory else .05
        existing = [x['controls'] for x in d['candidates'].values()]
        for _ in range(100):
            controls = dict(d['candidates'][parent]['controls'])
            for k in rng.sample(list(control_keys), len(control_keys) if broad else rng.randint(1, 2)):
                controls[k] = rng.random() if broad else min(1., max(0., controls[k] + rng.gauss(0, sigma)))
            if all(sum((controls[k]-other[k])**2 for k in control_keys) > minimum_distance**2 for other in existing):
                break
        else:
            raise ValueError('Could not generate a distinct candidate.')
        child = self._candidate(d, controls, [parent], 'exploration' if broad else 'mutation')
        self._pair(d, [parent, child], rng)

    def _prepare_gp_pair(self, d, rng):
        feature = d.get('algorithm') == 'gp-feature-v2'
        if feature and d['completed'] < len(FEATURE_GROUPS):
            self._pair(d, d['initial'][2*d['completed']:2*d['completed']+2], rng)
            return
        if feature and 17 <= d['completed'] < 20 and self._prepare_feature_mix(d, rng):
            return
        exploratory = d.get('algorithm') in ('gp-preference-comfort-v1', 'gp-character-v1', 'gp-feature-v2')
        character = d.get('algorithm') in ('gp-character-v1', 'gp-feature-v2')
        improvement_search = d.get('algorithm') in ('gp-preference-ei-v2', 'gp-preference-comfort-v1', 'gp-character-v1', 'gp-feature-v2')
        control_keys = tuple(d.get('control_keys', GP_CONTROLS))
        sigma = (.30 if d['completed'] < 8 else .18 if d['completed'] < 14 else .10) if exploratory else .16
        minimum_distance = (.25 if d['completed'] < 8 else .14 if d['completed'] < 14 else .08) if exploratory else .01
        if d['completed'] < (5 if character else 3):
            ids = ([d['incumbent'], d['initial'][d['completed'] + 1]] if improvement_search
                   else d['initial'][2*d['completed']:2*d['completed']+2])
            self._pair(d, ids, rng)
            return

        pool, pool_ids = [], []
        for ident, candidate in d['candidates'].items():
            if ident in d.get('rejected', ()):
                continue
            pool.append(candidate['controls'])
            pool_ids.append(ident)
        preferred = []
        for row in d['history']:
            score = row.get('preference', '')
            if score not in ('A', 'B') or row['pair'][score] in d.get('rejected', ()):
                continue
            slot = score
            preferred.append(d['candidates'][row['pair'][slot]]['controls'])
        for _ in range(24):
            center = None
            if preferred and rng.random() < (.55 if character and d['completed'] < 10 else .7):
                center = (rng.choice(preferred) if feature
                          else d['candidates'][d['incumbent']]['controls'] if improvement_search
                          else rng.choice(preferred))
            controls = ({key: min(1., max(0., center[key] + rng.gauss(0, sigma)))
                         for key in control_keys} if center is not None
                        else {key: rng.random() for key in control_keys})
            if all(sum((controls[key] - old[key]) ** 2 for key in control_keys) > (.0001 if improvement_search else .01)
                   for old in pool):
                pool.append(controls)
                pool_ids.append(None)

        observations = [row for row in d['history'] if row.get('preference') in ('A', 'equal', 'B')]
        xa = [d['candidates'][row['pair']['A']]['controls'] for row in observations]
        xb = [d['candidates'][row['pair']['B']]['controls'] for row in observations]
        outcomes = [row['preference'] for row in observations]
        seen = []
        id_to_index = {ident: i for i, ident in enumerate(pool_ids) if ident is not None}
        for row in observations:
            aid, bid = row['pair']['A'], row['pair']['B']
            if aid in id_to_index and bid in id_to_index:
                seen.append((id_to_index[aid], id_to_index[bid]))
        for row in d.get('skipped_pairs', []):
            aid, bid = row['pair']['A'], row['pair']['B']
            if aid in id_to_index and bid in id_to_index:
                seen.append((id_to_index[aid], id_to_index[bid]))
        def vector(controls):
            return [controls[key] for key in control_keys]

        indices = select_query([vector(controls) for controls in pool],
                               [vector(controls) for controls in xa],
                               [vector(controls) for controls in xb], outcomes,
                               vector(d['baseline_controls']), seen,
                               incumbent=id_to_index[d['incumbent']] if improvement_search else None,
                               min_distance=minimum_distance,
                               kernel_length=.65 if character else .35,
                               kernel_groups=tuple(tuple(control_keys.index(key) for key in group)
                                                   for group in FEATURE_GROUPS) if feature else None)
        if indices is None:
            if improvement_search:
                raise ValueError('Could not generate a distinct challenger.')
            indices = rng.sample(range(len(pool)), 2)
        ids = []
        for index in indices:
            ident = pool_ids[index]
            if ident is None:
                ident = self._candidate(d, pool[index], kind='gp-proposal')
                pool_ids[index] = ident
            ids.append(ident)
        self._pair(d, ids, rng)

    def _prepare_feature_mix(self, d, rng):
        planned = FEATURE_MIXES[d['completed'] - 17]
        incumbent = d['incumbent']
        original = d['candidates'][incumbent]['controls']
        available = [index for index in range(len(FEATURE_GROUPS))
                     if d['feature_winners'].get(str(index))
                     and d['feature_winners'][str(index)] not in d.get('rejected', ())]
        if len(available) < 2:
            return False
        existing = [candidate['controls'] for candidate in d['candidates'].values()]
        choices = ([planned] if set(planned) <= set(available) else [])
        for size in range(min(len(planned), len(available)), 1, -1):
            for group in combinations(available, size):
                if group not in choices:
                    choices.append(group)
        for groups in choices:
            sources = [(FEATURE_GROUPS[index], d['feature_winners'][str(index)]) for index in groups]
            for fraction in (1., .75, .5):
                controls = dict(original)
                for group, ident in sources:
                    preferred = d['candidates'][ident]['controls']
                    for key in group:
                        controls[key] = original[key] + fraction * (preferred[key] - original[key])
                if all(sum((controls[key] - other[key]) ** 2 for key in CHARACTER_CONTROLS) > .08 ** 2
                       for other in existing):
                    parents = list(dict.fromkeys([incumbent, *(ident for _, ident in sources)]))
                    child = self._candidate(d, controls, parents, 'feature-mix')
                    self._pair(d, [incumbent, child], rng)
                    return True
        return False

    @Slot()
    def continueBlock(self):
        if not self.active or not self.checkpoint:
            return
        d = deepcopy(self.data)
        if d['checkpoint'] == 'cap':
            d['block_end'] += 20
        self._flush_audition(d)
        d['checkpoint'] = ''
        rng = random.Random(d['seed'] + d['completed'])
        if d.get('learning_method', 'evolutionary') == 'gp_preference':
            self._prepare_gp_pair(d, rng)
        else:
            self._prepare_next(d, rng)
        if self._commit(d):
            self._stats = self._empty_stats()

    @Slot(bool)
    @Slot(bool, str)
    def finish(self, satisfied=False, favorite_slot=''):
        if not self.active:
            return
        if satisfied and (favorite_slot not in ('A', 'B') or not all(self.data['tried'].values())):
            self.message = 'Listen to both sounds, then choose A or B to save.'
            self.changed.emit()
            return
        d = deepcopy(self.data)
        self._flush_audition(d)
        if satisfied:
            d['favorite'] = d['pair'][favorite_slot]
            d['selected'] = favorite_slot
            d['playing'] = d['favorite']
        d['status'] = 'satisfied' if satisfied else 'paused'
        d['endings'] = d.get('endings', []) + [dict(reason=d['status'], time=now(), candidate=d['playing'],
                                                  favorite_slot=favorite_slot if satisfied else '')]
        if self._commit(d):
            self._stats = self._empty_stats()
            self.monitor.stop()
            if satisfied:
                self.controller._update_audio()
            logging.getLogger('Search').info('Selected sound saved as favorite.' if satisfied else 'Search paused; progress saved.')

    def clearPlayback(self):
        self.trace_preview = None
        if self.data and not self.active:
            self.data = None
            self.changed.emit()

    @Slot(result=bool)
    def discard(self):
        if not self.active or self.path != self.root / self.data['id'] / 'session.json':
            return False
        try:
            self.path.with_suffix('.tmp').unlink(missing_ok=True)
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            self.message = f'Could not discard session: {exc}'
            self.changed.emit()
            return False
        try:
            self.path.parent.rmdir()
        except OSError:
            pass
        self.monitor.stop()
        self.data = self.path = None
        self.message = ''
        self.changed.emit()
        logging.getLogger('Search').info('Current session discarded.')
        return True

    def _debug(self):
        if not self.data:
            return dict(rows=[], history=[], survivors=[])
        d = self.data
        keys = d.get('control_keys', CONTROLS)
        return dict(rows=[dict(name=k, a=d['candidates'][d['pair']['A']]['controls'][k],
                               b=d['candidates'][d['pair']['B']]['controls'][k]) for k in keys],
                    pair=d['pair'], history=d['history'], survivors=d['survivors'],
                    learning_method=d.get('learning_method', 'evolutionary'),
                    preference=d.get('preference', ''),
                    candidates=d['candidates'], selected=d['playing'], completed=d['completed'])

    @Slot()
    def close(self):
        if self.active:
            self.finish(False)
