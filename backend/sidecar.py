"""Local simulator process. Standard output carries protocol messages only."""

import os
import socket
import sys

from PySide6.QtCore import QCoreApplication, QSocketNotifier, QTimer

from backend.bridge import DesktopBridge
from backend.protocol import decode_command, encode_message
from backend.audio_output_monitor import AudioOutputMonitor
from backend.controller import SimulatorController
from backend.gamepad_input import GamepadInput
from backend.beamng_telemetry import decode_ev_sound_packet


class Sidecar:
    def __init__(self, app):
        self.app = app
        self.controller = SimulatorController(app)
        self.bridge = DesktopBridge(self.controller)
        self.gamepad = GamepadInput(app)
        self.controller.gamepad = self.gamepad
        self.gamepad.devicesChanged.connect(self.controller.controllerDevicesChanged)
        self.gamepad.batteryChanged.connect(self.controller.controllerBatteryChanged)
        self.gamepad.stateChanged.connect(self.controller.setGamepadState)
        self.gamepad.navigation.connect(lambda action: self.send({'event': 'navigate', 'data': action}))
        self.audio_monitor = AudioOutputMonitor(self.controller, app)
        self.buffer = bytearray()
        self.input = QSocketNotifier(0, QSocketNotifier.Type.Read, app)
        self.input.activated.connect(self.read_input)
        self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.telemetry_notifier = None
        try:
            self.telemetry_socket.setblocking(False)
            self.telemetry_socket.bind(('127.0.0.1', 4445))
            self.telemetry_notifier = QSocketNotifier(self.telemetry_socket.fileno(), QSocketNotifier.Type.Read, app)
            self.telemetry_notifier.activated.connect(self.read_telemetry)
        except OSError as exc:
            self.telemetry_socket.close()
            self.telemetry_socket = None
            self.controller.set_beamng_error(f'BeamNG telemetry unavailable: {exc}')
        self.display = QTimer(app)
        self.display.setInterval(33)
        self.display.timeout.connect(self.publish_state)
        self.display.start()
        self.startup = QTimer(app)
        self.startup.setSingleShot(True)
        self.startup.timeout.connect(lambda: self.controller.setSoundStarting(False))
        app.aboutToQuit.connect(self.close)
        self.send({'event': 'hello', 'data': {'version': 1}})
        self.publish_state()

    @staticmethod
    def send(message):
        sys.stdout.write(encode_message(message))
        sys.stdout.flush()

    def publish_state(self):
        self.send({'event': 'state', 'data': self.bridge.snapshot()})

    def read_telemetry(self, _fd=None):
        while self.telemetry_socket is not None:
            try:
                packet, address = self.telemetry_socket.recvfrom(2048)
            except BlockingIOError:
                return
            except OSError as exc:
                self.controller.set_beamng_error(f'BeamNG telemetry receive failed: {exc}')
                return
            if address[0] not in ('127.0.0.1', '::1'):
                continue
            try:
                self.controller.receive_beamng_telemetry(decode_ev_sound_packet(packet))
            except ValueError as exc:
                self.controller.set_beamng_error(f'Invalid BeamNG telemetry: {exc}')

    def read_input(self, _fd=None):
        chunk = os.read(0, 65536)
        if not chunk:
            self.app.quit()
            return
        self.buffer.extend(chunk)
        if len(self.buffer) > 65536 and b'\n' not in self.buffer:
            self.buffer.clear()
            self.send({'event': 'error', 'data': 'Command too large'})
            return
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            ident = None
            try:
                ident, command, payload = decode_command(line)
                if command == 'quit':
                    result = {}
                    self.send({'id': ident, 'result': result})
                    self.app.quit()
                    return
                was_running = self.controller.running
                result = self.bridge.snapshot() if command == 'snapshot' else self.bridge.command(command, payload)
                if self.controller.running and not was_running:
                    self.controller.setSoundStarting(True)
                    self.startup.start(1550)
                    if command in ('toggle','vehicleStart'):
                        result = self.bridge.snapshot()
                elif not self.controller.running and was_running:
                    self.startup.stop()
                self.send({'id': ident, 'result': result})
            except (ValueError, TypeError) as exc:
                self.send({'id': ident, 'error': str(exc)} if ident is not None else
                          {'event': 'error', 'data': str(exc)})
            except Exception as exc:
                self.send({'id': ident, 'error': str(exc)} if ident is not None else
                          {'event': 'error', 'data': str(exc)})

    def close(self):
        self.bridge.source_discovery.close()
        self.input.setEnabled(False)
        self.display.stop()
        if self.telemetry_notifier is not None:
            self.telemetry_notifier.setEnabled(False)
        if self.telemetry_socket is not None:
            self.telemetry_socket.close()
        self.startup.stop()
        self.audio_monitor.close()
        self.gamepad.close()
        self.controller.search.close()
        self.controller.experiment.close()
        self.controller.shutdown()


def main():
    app = QCoreApplication(sys.argv)
    Sidecar(app)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
