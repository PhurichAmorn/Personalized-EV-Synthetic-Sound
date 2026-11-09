"""Time the gamepad polling that runs on the backend thread (20 ms poll, 500 ms device scan).
Run from the repo root:  .venv\\Scripts\\python.exe -m tools.time_gamepad"""
import os, sys, time
from PySide6.QtCore import QCoreApplication
from backend.gamepad_input import GamepadInput

app = QCoreApplication(sys.argv)
pad = GamepadInput(app)
pad.timer.stop()
if hasattr(pad, 'error'):
    sys.exit('gamepad unavailable: ' + pad.error)
print('devices:', pad.api.get_count())
def timed(label, fn, n):
    worst = total = 0.0
    for _ in range(n):
        t = time.perf_counter(); fn(); d = time.perf_counter() - t
        total += d; worst = max(worst, d)
        time.sleep(.02)
    print(f'{label}: avg {total / n * 1000:.1f} ms, worst {worst * 1000:.0f} ms over {n} calls')
timed('event.pump', pad.pygame.event.pump, 50)
timed('scan (runs 2x/second)', pad.scan, 10)
timed('full poll', pad.poll, 50)
