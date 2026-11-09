"""Typed desktop commands over the existing Qt-backed application state."""

import math
from audio import SOUND_RECIPES
from experiment.source_search import SourceDiscovery


class DesktopBridge:
    def __init__(self, controller):
        self.controller = controller
        self.source_discovery = SourceDiscovery()

    def snapshot(self):
        c = self.controller
        s = c.search
        return {
            'sourceDiscovery': self.source_discovery.snapshot(),
            'sourceMode': c.sourceMode, 'beamngConnected': c.beamngConnected,
            'beamngError': c.beamngError, 'beamngThrottle': c.telemetryThrottle,
            'beamngBrake': c.telemetryBrake, 'beamngRegen': c.telemetryRegen,
            'running': c.running, 'starting': c.sound_starting,
            'speed': c.speed, 'rpm': c.rpm, 'gear': c.gear, 'hasGears': c.hasGears,
            'maxRpm': c.maxRpm, 'speedGaugeMaximum': c.speedGaugeMaximum,
            'power': c.power, 'charge': c.charge, 'regenActive': c.regenActive,
            'acceleration': c.beamng_acceleration if c.sourceMode == 'BeamNG' else c.car.acceleration_m_s2,
            'motorLoad': c._signed_motor_load(), 'sourceAudition': c.source_audition,
            'vehicle': c.selectedVehicle, 'vehicleNames': c.vehicleNames,
            'specs': c.specs,
            'soundTheme': c.selectedSoundTheme, 'soundThemes': c.soundThemes,
            'soundRecipes': {mode: list(recipes) for mode, recipes in SOUND_RECIPES.items()},
            'soundRecipeSelection': c.sound_recipe.copy(),
            'parameters': c.parameters, 'soundSweepActive': c.soundSweepActive,
            'audioError': c.error, 'throttleInput': c.throttleInput, 'controllerThrottle': c.controller_pedals()[0], 'controllerBrake': c.controller_pedals()[1],
            'brakeInput': c.brakeInput, 'controllerName': c.controllerName,
            'controllerBattery': c.controllerBattery, 'controllerError': c.controllerError,
            'availableControllers': c.availableControllers,
            'controllerEnabled': c.controllerEnabled,
            'search': {
                'active': s.active, 'participant': s.participant, 'mode': s.mode,
                'learningMethod': s.learningMethod, 'algorithm': s.data.get('algorithm', '') if s.data else '',
                'pairNumber': s.pairNumber,
                'selected': s.selected, 'triedA': s.triedA, 'triedB': s.triedB,
                'preference': s.preference, 'preferenceReady': s.preferenceReady,
                'ratingA': s.ratingA, 'ratingB': s.ratingB,
                'ratingSources': s.ratingSources, 'feedbackReady': s.feedbackReady,
                'checkpoint': s.checkpoint, 'error': s.error,
                'stage': ('Explore recipes' if s.pairNumber <= 4 else 'Tune linked traits' if s.pairNumber <= 14
                          else 'Combine preferred traits' if s.pairNumber <= 18 else 'Refine')
                         if s.data and s.data.get('algorithm') == 'recipe-pairwise-v1' else
                         # v2 phases follow LiveSearch._prepare_probe_pair: probes, tune, combine, branch challenge, refine.
                         ('Explore recipes' if s.pairNumber <= 4 else 'Tune linked traits' if s.pairNumber <= 14
                          else 'Combine preferred traits' if s.pairNumber <= 17 else 'Challenge current best'
                          if s.pairNumber == 18 else 'Refine')
                         if s.data and s.data.get('algorithm') == 'recipe-pairwise-v2' else '',
                'pairRecipes': {slot: s.data['candidates'][ident].get('recipe_name', '')
                                for slot, ident in s.data.get('pair', {}).items()} if s.data else {},
            },
            'experiment': {'state': c.experiment.state, 'error': c.experiment.error},
        }

    @staticmethod
    def _number(payload, key):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f'Invalid {key} pedal value')
        return float(value)

    @staticmethod
    def _text(payload, key):
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f'Invalid {key}')
        return value

    @staticmethod
    def _bool(payload, key):
        value = payload.get(key)
        if not isinstance(value, bool):
            raise ValueError(f'Invalid {key}')
        return value

    def command(self, name, payload):
        if not isinstance(payload, dict):
            raise ValueError('Invalid payload')
        c, s = self.controller, self.controller.search
        if name.startswith('sourceDiscovery'):
            discovery = self.source_discovery
            if name == 'sourceDiscoveryStart':
                if s.active or c.soundSweepActive:raise ValueError('Stop the native experiment or debug sweep first')
                if discovery.active:raise ValueError('Finish the current source trial before starting another')
                discovery.start()
            elif name == 'sourceDiscoveryHeard':discovery.heard(self._text(payload,'id'),payload.get('context',{}))
            elif name == 'sourceDiscoveryFeedback':discovery.feedback(payload.get('ratings'),payload.get('context',{}))
            elif name == 'sourceDiscoveryPlayoff':discovery.playoff_feedback(payload.get('choice'),payload.get('context',{}))
            elif name == 'sourceDiscoveryBookmark':discovery.bookmark(self._text(payload,'id'),self._bool(payload,'enabled'),payload.get('note'))
            elif name == 'sourceDiscoveryFinish':discovery.finish(payload.get('id'))
            elif name == 'sourceDiscoveryExport':return discovery.export()
            elif name == 'sourceDiscoveryRetry':
                if discovery.busy or not discovery.active:raise ValueError('No failed active trial to retry')
                with discovery.lock:discovery._prepare()
            else:raise ValueError('Unknown source discovery command')
            return self.snapshot()
        if self.source_discovery.active and name in ('searchStart','searchRestore','tracePreview','sweep'):
            raise ValueError('Finish the source-discovery trial before native search or audio debugging')
        if name == 'vehicleStart':
            if not c.running:c.toggle()
        elif name == 'sourceMode':
            c.selectSource(self._text(payload, 'value'))
        elif name == 'toggle':
            c.toggle()
        elif name == 'sourceAudition':
            enabled = self._bool(payload, 'value')
            if enabled and (s.active or c.soundSweepActive):
                raise ValueError('Stop the active experiment or audio debug sweep before source audition')
            c.source_audition = enabled
            c._update_audio()
        elif name == 'vehicle':
            value = self._text(payload, 'name')
            if value not in c.vehicleNames:
                raise ValueError('Unknown vehicle')
            c.selectVehicle(value)
        elif name == 'theme':
            value = self._text(payload, 'name')
            if value not in c.soundThemes:
                raise ValueError('Unknown sound theme')
            c.selectSoundTheme(value)
        elif name == 'recipeCycle':
            value = self._text(payload, 'name')
            if value not in SOUND_RECIPES:
                raise ValueError('Unknown sound theme')
            c.cycleSoundRecipe(value)
        elif name == 'starting':
            c.setSoundStarting(self._bool(payload, 'value'))
            c._pedals_changed()
        elif name == 'pedals':
            throttle = self._number(payload, 'throttle')
            brake = self._number(payload, 'brake')
            c.external_throttle, c.external_brake = throttle, brake
            c._pedals_changed()
        elif name == 'powertrain':
            return c.powertrain
        elif name == 'focus':
            c.input_focused = self._bool(payload, 'value')
            if not c.input_focused:
                c.external_throttle = c.external_brake = 0.0
                c.gamepad_armed = False
            c._pedals_changed()
        elif name == 'controller':
            value = payload.get('id')
            if type(value) is not int:
                raise ValueError('Invalid controller id')
            c.selectController(value)
        elif name == 'controllerEnabled':
            c.setControllerEnabled(self._bool(payload, 'value'))
        elif name == 'sweep':
            c.toggleSoundSweep()
        elif name == 'debugVisible':
            c.enableSoundDebug(self._bool(payload, 'value'))
        elif name == 'soundDebug':
            return c.soundDebug()
        elif name == 'searchStart':
            if self.source_discovery.active:raise ValueError('Finish the source-discovery trial first')
            s.start(self._text(payload, 'participant'), self._text(payload, 'mode'),
                    self._text(payload, 'method'))
        elif name == 'searchSessions':
            return s.sessions(self._text(payload, 'participant'))
        elif name == 'searchRestore':
            s.restore(self._text(payload, 'id'), self._bool(payload, 'favoriteOnly'))
        elif name == 'searchChoose':
            slot = self._text(payload, 'slot')
            if slot not in ('A', 'B'):
                raise ValueError('Invalid sound slot')
            s.choose(slot)
        elif name == 'searchPreference':
            value = payload.get('value')
            if value not in ('A', 'equal', 'B'):
                raise ValueError('Invalid preference')
            s.ratePreference(value)
        elif name == 'searchRate':
            slot = self._text(payload, 'slot')
            value = payload.get('value')
            if slot not in ('A', 'B') or type(value) is not int or not 1 <= value <= 7:
                raise ValueError('Invalid sound rating')
            s.rate(slot, value)
        elif name == 'searchSimilar':
            s.retrySimilar()
        elif name == 'searchNeither':
            s.rejectBoth()
        elif name == 'searchNext':
            s.next()
        elif name == 'searchContinue':
            s.continueBlock()
        elif name == 'searchFinish':
            satisfied = self._bool(payload, 'satisfied')
            favorite_slot = payload.get('favoriteSlot', '')
            if favorite_slot not in ('', 'A', 'B') or (satisfied and favorite_slot not in ('A', 'B')):
                raise ValueError('Choose sound A or B to save')
            s.finish(satisfied, favorite_slot)
        elif name == 'searchDiscard':
            return s.discard()
        elif name == 'traceSessions':
            return s.traceSessions()
        elif name == 'traceSession':
            return s.traceSession(self._text(payload, 'id'))
        elif name == 'traceDelete':
            return s.deleteSession(self._text(payload, 'id'))
        elif name == 'tracePreview':
            return s.previewTraceCandidate(self._text(payload, 'sessionId'), self._text(payload, 'candidateId'))
        else:
            raise ValueError(f'Unknown command: {name}')
        return self.snapshot()
