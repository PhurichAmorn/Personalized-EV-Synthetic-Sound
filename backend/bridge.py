"""Typed desktop commands over the existing Qt-backed application state."""

import math


class DesktopBridge:
    def __init__(self, controller):
        self.controller = controller

    def snapshot(self):
        c = self.controller
        s = c.search
        return {
            'running': c.running, 'starting': c.sound_starting,
            'speed': c.speed, 'rpm': c.rpm, 'gear': c.gear, 'hasGears': c.hasGears,
            'maxRpm': c.maxRpm, 'speedGaugeMaximum': c.speedGaugeMaximum,
            'power': c.power, 'charge': c.charge, 'regenActive': c.regenActive,
            'vehicle': c.selectedVehicle, 'vehicleNames': c.vehicleNames,
            'specs': c.specs,
            'soundTheme': c.selectedSoundTheme, 'soundThemes': c.soundThemes,
            'parameters': c.parameters, 'soundSweepActive': c.soundSweepActive,
            'audioError': c.error, 'throttleInput': c.throttleInput,
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
        if name == 'toggle':
            c.toggle()
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
