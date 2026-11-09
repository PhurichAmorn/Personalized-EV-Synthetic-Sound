import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from tools import finalize_family_evaluation as finalizer

class SourceScreeningTest(unittest.TestCase):
    def test_normalized_preview_does_not_hide_original_overload(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);frames=48000
            tone=np.repeat((2*np.sin(2*np.pi*440*np.arange(frames)/48000))[:,None],2,axis=1).astype('<f4')
            controls=np.column_stack([np.ones(frames),np.full(frames,1300)]).astype('<f4')
            for suffix,audio in [('direct',tone),('filtered',np.zeros_like(tone)),('automation',controls),('source',tone)]:audio.tofile(root/f'candidate_{suffix}.f32')
            (root/'render_manifest.json').write_text(json.dumps({'families':[{'id':'candidate','label':'test'}],'mode':'rise'}))
            with patch.object(finalizer,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):finalizer.finalize()
            clips=json.loads((root/'clips.json').read_text())['clips']
            raw=next(c for c in clips if c['scene']=='source')
            self.assertEqual(raw['pre_normalization_check']['decision'],'reject')
            self.assertNotEqual(raw['signal_check']['decision'],'reject')
