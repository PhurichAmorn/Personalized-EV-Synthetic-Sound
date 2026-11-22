import json
import random
import tempfile
import unittest
from pathlib import Path

from experiment import sound_blocks as sb
from experiment.source_search import BlockDiscovery


def fake_table(path, fail_from=None):
    """Every sweep combination, sharpness .35-.65 over the low-pass points; points at or above fail_from Hz fail the drive check.
    Spectra differ by body, top and top level (gap >= .4 for any change of those); synth knobs leave the spectrum unchanged (gap 0)."""
    entries = {}
    for k, sound in sb.sweep_items():
        s = sb.full(sound)
        ok = [{'rise': fail_from is None or c < fail_from, 'evolving': fail_from is None or c < fail_from} for c in sb.CUTOFFS]
        level = [-4 * list(sb.BODIES).index(s['body']), -4 * list(sb.TOPS).index(s['top']), -4 * list(sb.TOP_LEVELS).index(s['level'])]
        bands = [[0.] + [level[i % 3] * (1 + (i % 2)) for i in range(8)] for _ in sb.CUTOFFS]
        entries[k] = {'sound': sound, 'S': [.35, .45, .55, .65], 'pass': ok, 'bands': bands}
    Path(path).write_text(json.dumps({'created': 'test', 'cutoffs': sb.CUTOFFS, 'limits': {}, 'entries': entries}))


class BlockDiscoveryTest(unittest.TestCase):
    def session(self, table=None, seed=3):
        d = BlockDiscovery(table_path=table or '/nonexistent/table.json'); d.start(); d.rng = random.Random(seed)
        return d

    def test_flow_motion_starts_playoff_replay_and_changes(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'table.json'; fake_table(path)
        d = self.session(path); rows = []
        # pair 1: Rising vs Evolving, the same sound in both motions
        self.assertEqual({d.candidates[i]['recipe']['motion'] for i in d.pair}, {'rise', 'evolving'})
        self.assertEqual(len({json.dumps(d._sound(i), sort_keys=True) for i in d.pair}), 1)
        d.feedback(choice='A' if d.candidates[d.pair[0]]['recipe']['motion'] == 'evolving' else 'B')
        self.assertEqual(d.motion, 'evolving'); self.assertEqual(d.pairs, 17)
        starts = set()
        for _ in range(2): starts |= {json.dumps(d._sound(i), sort_keys=True) for i in d.pair}; rows.append(list(d.pair)); d.feedback(choice='A')
        self.assertEqual(len(starts), 4)  # pairs 2-3: the four starts, two per pair
        playoff = list(d.pair); winners = {r[0] for r in rows}
        self.assertTrue(set(playoff) <= winners)  # pair 4: opening winners
        d.feedback(choice='A')
        blocks = lambda i: d._sound(i)
        for n in range(5, 18):
            if not d.active: break
            if n == 14: self.assertEqual(d.pair, playoff[::-1])  # pair 14: pair 4 again, A and B swapped
            elif n < 17:
                a, b = d.pair; o = lambda i: d.candidates[i]['origin']
                new = a if o(a).get('parent') == b else b; self.assertEqual(o(new).get('parent'), next(i for i in d.pair if i != new))  # champion vs a challenger
                differ = sum(blocks(a)[k] != blocks(b)[k] for k in blocks(a))
                if n <= 13: self.assertEqual(o(new)['kind'], 'broad'); self.assertGreaterEqual(differ, 2)  # pairs 5-13: 2 blocks at once
                else: self.assertEqual(o(new)['kind'], 'change')  # pairs 15-16: one big change (pitch or brightness first; a top swap also clears synth knobs)
            d.feedback(choice='A')
        self.assertFalse(d.active); self.assertEqual(d.completed, 17)
        data = d.export()
        self.assertTrue(data['liked']); self.assertEqual(len(data['repeats']), 1); self.assertTrue(data['table']['checked'])
        self.assertTrue(d._bt_order())
        d.close()

    def test_both_good_on_the_motion_pair_keeps_rising(self):
        d = self.session(); d.feedback(choice='good')
        self.assertEqual(d.motion, 'rise')
        d.close()

    def test_table_gates_unsafe_sounds_and_records_reached_brightness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.json'; fake_table(path, fail_from=2800)
            d = self.session(path)
            for _ in range(40):
                if not d.active: break
                for i in d.pair:
                    r = d.candidates[i]['recipe']
                    self.assertTrue(r['checked']); self.assertLess(r['fx']['tone'], 2800)  # nothing measured as failing is ever offered
                    self.assertLessEqual(r['blocks']['brightness'], .55)  # brightness stops where the safe low-pass stops
                d.feedback(choice='B')
            self.assertTrue(d.export()['table']['checked'])
            d.close()

    def test_changes_measured_too_close_are_never_offered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.json'; fake_table(path)
            d = self.session(path); groups = set()
            for _ in range(40):
                if not d.active: break
                for i in d.pair:
                    o = d.candidates[i]['origin']
                    if o.get('kind') == 'change':
                        groups.add(o['group'])
                        if o['group'] in ('body', 'level', 'synth'):
                            self.assertGreaterEqual(d._gap(d.candidates[o['parent']]['recipe'], d.candidates[i]['recipe']), sb.MIN_GAP)
                d.feedback(choice='A')
            self.assertNotIn('synth', groups)  # synth knobs measured with no spectrum change: never offered as a single change
            d.close()

    def test_no_brightness_guess_without_table(self):
        d = self.session()
        for _ in range(40):
            if not d.active: break
            for i in d.pair: self.assertNotRegex(d.candidates[i]['origin'].get('summary', ''), 'darker|brighter')  # also inside broad changes
            d.feedback(choice='A')
        d.close()

    def test_final_list_at_most_two_per_top_and_clearly_different(self):
        d = self.session()
        for _ in range(40):
            if not d.active: break
            d.feedback(choice='A')
        tops = [d._sound(i)['top'] for i in d.finalists]
        self.assertTrue(d.finalists); self.assertLessEqual(max(tops.count(t) for t in tops), 2)
        for a in d.finalists:
            for b in d.finalists:
                if a != b: self.assertTrue(d._distinct(a, b))
        d.close()

    def test_champion_beaten_just_before_the_replay_is_replaced(self):
        d = self.session()
        for _ in range(12): d.feedback(choice='A')  # through pair 12
        a, b = d.pair; champ = d.champion; challenger = b if a == champ else a
        d.feedback(choice='A' if d.pair[0] == challenger else 'B')  # pair 13: the challenger wins
        d.feedback(choice='A')  # pair 14: the replay
        o = d.candidates[next(i for i in d.pair if d.candidates[i]['origin'].get('kind') == 'change')]['origin']  # the new sound of pair 15
        self.assertEqual(o['parent'], challenger)  # pair 15 starts from the pair-13 winner
        d.close()

    def test_loudness_from_the_table_sets_playback_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'table.json'; fake_table(path)
            t = json.loads(path.read_text())
            for k, e in t['entries'].items(): e['sones'] = [4.5] * 4 if sb.full(e['sound'])['top'] == 'glass' else [9.] * 4
            t['loudness'] = {'target_sones': 9.}; path.write_text(json.dumps(t))
            d = self.session(path)
            for i in d.pair:
                r = d.candidates[i]['recipe']
                self.assertAlmostEqual(r['fx']['gain'], 10 ** .5 if r['blocks']['top'] == 'glass' else 1, places=3)  # half as loud: +10 dB
            d.close()

    def test_partners_only_from_the_heard_list_space_fixed_no_bell_on_bell(self):
        d = self.session(); seen = set()
        for _ in range(40):
            if not d.active: break
            for i in d.pair:
                s = d._sound(i); v = d.candidates[i]['recipe']['voice']['stack']
                self.assertEqual(s['space'], 'large')
                if s['partner']:
                    seen.add(s['partner'])
                    self.assertIn(s['partner'], sb.PARTNERS[s['top']])
                    self.assertEqual(v['timbres'][sb.PARTNER_LAYER], sb.TOPS[s['partner']]); self.assertEqual(v['timbres'][2], sb.TOPS[s['top']])
                o = d.candidates[i]['origin']
                if o.get('kind') == 'change' and o['group'] == 'synth' and s['top'] == 'bell': self.assertNotIn('bell', o['summary'])
            d.feedback(choice='B')
        self.assertTrue(seen)  # partners are reachable in a session
        d.close()

    def test_a_change_that_just_lost_is_not_offered_again_next(self):
        repeats = broad = 0
        for seed in range(6):
            d = self.session(seed=seed)
            for _ in range(5): d.feedback(choice='A')  # motion, starts, playoff
            lost = {}
            for _ in range(7):  # broad pairs: the champion always wins
                champ = d.champion; new = next(d._sound(i) for i in d.pair if i != champ)
                if d.candidates[next(i for i in d.pair if i != champ)]['origin'].get('kind') == 'broad':
                    broad += 1; repeats += any(new.get(k) == v for k, v in lost.items())
                here = d._sound(champ); lost = {k: v for k, v in new.items() if here.get(k) != v and k != 'brightness'}
                d.feedback(choice='A' if d.pair[0] == champ else 'B')
            d.close()
        self.assertGreater(broad, 20); self.assertLessEqual(repeats, broad // 10)  # rare: only when nothing else is left

    def test_four_starts_one_per_style_and_playoff_is_a_new_pair(self):
        self.assertEqual({s['top'] for s in sb.STARTS.values()}, {'glass', 'plain', 'bell', 'moody'})
        for seed in range(12):
            d = self.session(seed=seed); d.feedback(choice='A'); met = []; tops = set()
            for _ in range(2): tops |= {d._sound(i)['top'] for i in d.pair}; met.append(frozenset(d.pair)); d.feedback(choice='good')
            self.assertEqual(tops, {'glass', 'plain', 'bell', 'moody'})
            self.assertNotIn(frozenset(d.pair), met)  # pair 4 is not a replay of an opening pair (all four won: Both good)
            d.close()

    def test_pair_17_checks_a_tuned_pick_against_its_untuned_start_and_changes_are_shown(self):
        checked = shown = 0
        for seed in range(8):
            d = self.session(seed=seed)
            pick = lambda: 'A' if d.champion is None or d.pair[0] == d.champion else 'B'
            for n in range(1, 17):
                if n == 5: d.feedback(choice='B' if d.pair[0] == d.champion else 'A')  # first broad pair: the challenger wins, so the champion is tuned
                else: d.feedback(choice=pick())
                last = d.snapshot()['lastChange']
                if n in (5, 6): self.assertTrue(last and last['items'] and all(i['side'] in 'AB' and i['text'] for i in last['items'])); shown += 1
                if n == 3: self.assertIsNone(d.snapshot()['lastChange'])  # starts changed nothing
            if (d.confirm or {}).get('kind') != 'tuning': d.close(); continue
            first, root = d.pair if d.pair[0] == d.confirm['first'] else d.pair[::-1]
            self.assertEqual(d._root(first), root); self.assertIn(d.candidates[root]['origin']['kind'], ('opening', 'motion')); self.assertNotEqual(first, root)
            d.feedback(choice='A' if d.pair[0] == first else 'B')
            self.assertEqual(d.export()['tuning_check'], {'pick': first, 'start': root, 'chose': 'pick'}); checked += 1
            d.close()
        self.assertGreater(shown, 8); self.assertGreater(checked, 0)

    def test_both_good_marks_both_liked(self):
        d = self.session(); d.feedback(choice='A'); pair = list(d.pair); d.feedback(choice='good')
        liked = {x['id'] for x in d.export()['liked']}
        self.assertTrue(set(pair) <= liked)
        d.close()


if __name__ == '__main__':
    unittest.main()
