import logging

from PySide6.QtCore import QObject, QTimer
from PySide6.QtMultimedia import QMediaDevices


class AudioOutputMonitor(QObject):
    """Debounce system device changes; restart only audio, never the vehicle."""
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.devices = QMediaDevices(self)
        self.signature = self.output_signature()
        self.attempts = 0
        self.reopen = QTimer(self)
        self.reopen.setSingleShot(True)
        self.reopen.setInterval(750)
        self.reopen.timeout.connect(self.recover)
        self.devices.audioOutputsChanged.connect(self.schedule)
        self.health = QTimer(self)
        self.health.setInterval(1000)
        self.health.timeout.connect(self.check)
        self.health.start()

    @staticmethod
    def output_signature():
        device = QMediaDevices.defaultAudioOutput()
        fmt = device.preferredFormat()
        return bytes(device.id()), fmt.sampleRate(), fmt.channelCount()

    def schedule(self):
        self.attempts = 0
        self.reopen.start()

    def check(self):
        signature = self.output_signature()
        if signature != self.signature:
            self.signature = signature
            self.schedule()
        c = self.controller
        if c.running or c.soundSweepActive:
            try:
                failed = c.audio.stream is None or not c.audio.stream.active
            except Exception:
                failed = True
            if failed and not self.reopen.isActive() and self.attempts < 3:
                self.reopen.start()
            elif not failed:
                self.attempts = 0

    def recover(self):
        c = self.controller
        self.attempts += 1
        logging.getLogger('Audio').info('Refreshing system audio output (attempt %s/3).', self.attempts)
        try:
            try:
                c.audio.stop()
            except Exception:
                pass  # A removed device can reject stop/close; the stream is detached.
            c.audio.refresh_devices()
            if c.running or c.soundSweepActive:
                c.audio.start()
                if c.soundSweepActive:
                    c.audio.set_order_parameters(c.sweep_rpm, c.sweep_throttle)
                else:
                    c._update_audio()
            c._set_audio_error('')
            if not c.running and not c.soundSweepActive:
                self.attempts = 0
        except Exception as exc:
            c._set_audio_error(f'Audio output unavailable: {exc}')
            if self.attempts < 3:
                self.reopen.start(2000)

    def close(self):
        self.health.stop()
        self.reopen.stop()
