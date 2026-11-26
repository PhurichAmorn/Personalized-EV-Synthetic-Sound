import json
import queue
import subprocess
import sys
import threading
import unittest


class DesktopSidecarTest(unittest.TestCase):
    def test_sidecar_reports_state_and_exits_on_quit(self):
        process = subprocess.Popen([sys.executable, '-m', 'backend.sidecar'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, bufsize=0)
        # A reader thread instead of select(): select works on pipes only on POSIX (WinError 10093 on laptop B, 2026-11-20).
        lines = queue.Queue()
        threading.Thread(target=lambda: [lines.put(line) for line in iter(process.stdout.readline, b'')], daemon=True).start()
        try:
            def read_until(predicate):
                for _ in range(40):
                    try:
                        message = json.loads(lines.get(timeout=0.25))
                    except queue.Empty:
                        continue
                    if predicate(message):
                        return message
                self.fail('Sidecar did not respond')

            self.assertEqual(read_until(lambda m: m.get('event') == 'hello')['data']['version'], 1)
            process.stdin.write(b'{"id":1,"command":"snapshot","payload":{}}\n')
            reply = read_until(lambda m: m.get('id') == 1)
            self.assertEqual(reply['result']['vehicle'], 'BeamNG Vivace E')
            process.stdin.write(b'{"id":3,"command":"unknown","payload":{}}\n')
            self.assertIn('Unknown command', read_until(lambda m: m.get('id') == 3)['error'])
            process.stdin.write(b'{"id":2,"command":"quit","payload":{}}\n')
            self.assertEqual(read_until(lambda m: m.get('id') == 2)['result'], {})
            self.assertEqual(process.wait(timeout=3), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()


if __name__ == '__main__':
    unittest.main()
