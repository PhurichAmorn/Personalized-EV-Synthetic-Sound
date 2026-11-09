import hashlib,json,unittest
from pathlib import Path
import numpy as np
from scipy.io.wavfile import read
from tools.prepare_gs_baseline import integrated_loudness


class StressPoolTest(unittest.TestCase):
    def test_published_pool_has_nine_matched_scored_clips(self):
        root=Path('desktop/public/audio/stress-pool-v1')
        manifest=json.loads((root/'manifest.json').read_text())
        self.assertEqual({clip['id'] for clip in manifest['clips']},{'clean','shrill','ufo','flutter','noise','clicks','distortion','dropouts','high_whistle'})
        self.assertEqual(len(manifest['clips']),9)
        for clip in manifest['clips']:
            self.assertTrue(clip['url'].startswith('/audio/stress-pool-v1/'))
            path=root/Path(clip['url']).name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),clip['sha256'])
            rate,audio=read(path)
            self.assertEqual((rate,audio.shape),(48000,(480000,2)))
            self.assertTrue(np.isfinite(audio).all())
            self.assertLess(np.max(abs(audio)),.351)
            self.assertAlmostEqual(integrated_loudness(audio),manifest['target_lufs'],delta=.05)
            self.assertEqual(set(clip['scores']),{'PQ','CE','PC','CU'})
            self.assertTrue(all(np.isfinite(value) for value in clip['scores'].values()))


if __name__=='__main__':unittest.main()
