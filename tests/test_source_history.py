import hashlib, json, pathlib, tempfile, time, unittest
from experiment.source_history import SourceHistory
from experiment.source_search import OpenDiscovery


def renderer(recipe):
    key = hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:32]
    weights = [.01 + (i == int(key, 16) % 12) for i in range(12)]  # distinct bands, so pairs pass the similarity check
    return {'id': key, 'label': 'x', 'recipe': recipe, 'urls': ['/a'], 'traces': {'rise': '/a.wav'}, 'audio_descriptor': [w / sum(weights) for w in weights]}


class SourceHistoryTest(unittest.TestCase):
    def setUp(self):
        self.discovery = OpenDiscovery(renderer=renderer)
        self.history = SourceHistory(self.discovery, pathlib.Path(tempfile.mkdtemp()))
        self.addCleanup(self.discovery.close)

    def test_autosave_list_preview_delete(self):
        self.history.begin()
        self.discovery.start()
        while self.discovery.busy:
            time.sleep(.02)
        self.history.save()
        self.assertEqual(self.history.listing(), [])  # nothing rated yet
        self.discovery.feedback({'A': 5, 'B': 3}, {})
        self.history.save()
        (row,) = self.history.listing()
        self.assertEqual(row['completed'], 1)
        self.assertTrue(row['created'].count(':') >= 2)
        saved = self.history.get(row['id'])
        ident = saved['history'][0]['pair'][0]
        self.assertNotIn('urls', saved['candidates'][ident])  # audio is regenerated, never stored
        self.history.render(row['id'], ident)
        for _ in range(100):
            if self.history.preview.get('status') == 'ready':
                break
            time.sleep(.02)
        self.assertEqual(self.history.preview['url'], '/a.wav')
        self.history.clear()
        self.assertEqual(self.history.preview, {})
        before = (self.history.root / f"{row['id']}.json").read_text()
        self.assertTrue(self.history.star(row['id'], True))
        self.assertTrue(self.history.listing()[0]['starred'])
        self.assertEqual((self.history.root / f"{row['id']}.json").read_text(), before)  # session record untouched
        self.assertFalse(self.history.star(row['id'], False))
        self.assertFalse(self.history.listing()[0]['starred'])
        self.history.star(row['id'], True)
        self.assertTrue(self.history.delete(row['id']))
        self.assertEqual(self.history.listing(), [])
        self.assertEqual(self.history.starred(), set())  # deleting drops its star
        with self.assertRaises(ValueError):
            self.history.get('../etc/passwd')
        with self.assertRaises(ValueError):
            self.history.star('../etc/passwd', True)


if __name__ == '__main__':
    unittest.main()
