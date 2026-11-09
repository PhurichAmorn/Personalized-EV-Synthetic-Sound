import subprocess,unittest
from unittest.mock import Mock,patch
from experiment.source_render_queue import SourceRenderer

class SourceRenderQueueTest(unittest.TestCase):
    def test_cancel_never_launches_another_child(self):
        renderer=SourceRenderer();renderer.cancel()
        with patch('experiment.source_render_queue.subprocess.Popen') as process:
            with self.assertRaisesRegex(RuntimeError,'cancelled'):renderer._run(['node'])
            process.assert_not_called()

    def test_timeout_kills_child_and_crash_is_reported(self):
        renderer=SourceRenderer();process=Mock()
        process.communicate.side_effect=[subprocess.TimeoutExpired('node',120),('','')]
        with patch('experiment.source_render_queue.subprocess.Popen',return_value=process):
            with self.assertRaisesRegex(RuntimeError,'timed out'):renderer._run(['node'])
            process.kill.assert_called_once()
        process=Mock(returncode=1);process.communicate.return_value=('','worker error')
        with patch('experiment.source_render_queue.subprocess.Popen',return_value=process):
            with self.assertRaisesRegex(RuntimeError,'worker error'):renderer._run(['node'])

    def test_rise_only_qualification_and_exact_cache_replay(self):
        import tempfile
        from pathlib import Path
        recipe={'version':1,'seed':937,'layers':[{'role':'foundation','method':'rounded','gain':1,'shape':{'tilt':.2}}]}
        renderer=SourceRenderer();self.addCleanup(renderer.close)
        with tempfile.TemporaryDirectory() as folder,patch('experiment.source_render_queue.CACHE',Path(folder)):
            clip=renderer(recipe)
            self.assertEqual(set(clip['traces']),{'rise'})
            self.assertEqual({check['mode'] for check in clip['checks']},{'rise'})
            self.assertEqual(clip['qualification_modes'],['rise'])
            self.assertTrue(any(check['stage']=='loop' for check in clip['checks']))
            self.assertFalse((Path(folder)/clip['id']/'steady.wav').exists())
            with patch.object(renderer,'_run',side_effect=AssertionError('Cache hit must not render')):
                cached=renderer(recipe)
                self.assertEqual(cached['audio_hashes'],clip['audio_hashes'])
