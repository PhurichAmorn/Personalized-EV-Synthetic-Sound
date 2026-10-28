import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class LauncherTests(unittest.TestCase):
    def test_launch_from_other_directory_and_cache_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project with spaces'
            binary = project / '.venv' / 'bin'
            binary.mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1] / 'launch.sh', project)
            (project / 'requirements.txt').write_text('example\n')
            python = binary / 'python'
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> calls.txt\n')
            python.chmod(0o755)
            self.fake_npm(project)
            for _ in range(2):
                subprocess.run(['sh', str(project / 'launch.sh')], cwd=temporary, check=True, capture_output=True,
                               env=dict(os.environ, PATH=f'{project / "fake-bin"}:{os.environ["PATH"]}'))
            calls = (project / 'calls.txt').read_text().splitlines()
            self.assertEqual(calls.count('-m pip install -r requirements.txt'), 1)
            self.assertEqual((project / 'desktop' / 'npm-calls.txt').read_text().splitlines(),
                             ['run tauri -- dev', 'run tauri -- dev'])

    def test_build_failure_stops_before_starting_desktop(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            binary = project / '.venv' / 'bin'
            binary.mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1] / 'launch.sh', project)
            (project / 'requirements.txt').write_text('example\n')
            python = binary / 'python'
            python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> calls.txt\nif [ "$1" = setup.py ]; then exit 1; fi\n')
            python.chmod(0o755)
            self.fake_npm(project)
            result = subprocess.run(['sh', str(project / 'launch.sh')], check=False, capture_output=True,
                                    env=dict(os.environ, PATH=f'{project / "fake-bin"}:{os.environ["PATH"]}'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Native audio build failed', result.stderr.decode())
            self.assertFalse((project / 'desktop' / 'npm-calls.txt').exists())

    def test_installs_desktop_dependencies_when_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            binary = project / '.venv' / 'bin'
            binary.mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parents[1] / 'launch.sh', project)
            (project / 'requirements.txt').write_text('example\n')
            python = binary / 'python'
            python.write_text('#!/bin/sh\nexit 0\n')
            python.chmod(0o755)
            self.fake_npm(project)
            (project / 'desktop' / 'node_modules' / '.bin' / 'tauri').unlink()
            subprocess.run(['sh', str(project / 'launch.sh')], check=True, capture_output=True,
                           env=dict(os.environ, PATH=f'{project / "fake-bin"}:{os.environ["PATH"]}'))
            self.assertEqual((project / 'desktop' / 'npm-calls.txt').read_text().splitlines(),
                             ['ci', 'run tauri -- dev'])

    @staticmethod
    def fake_npm(project):
        (project / 'desktop' / 'node_modules' / '.bin').mkdir(parents=True)
        (project / 'desktop' / 'node_modules' / '.bin' / 'tauri').touch()
        (project / 'desktop' / 'node_modules' / '.bin' / 'tauri').chmod(0o755)
        binary = project / 'fake-bin'
        binary.mkdir()
        npm = binary / 'npm'
        npm.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> npm-calls.txt\nif [ "$1" = ci ]; then touch node_modules/.bin/tauri; fi\n')
        npm.chmod(0o755)
