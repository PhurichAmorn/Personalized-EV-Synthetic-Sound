"""Blind evaluation after a session (agreed 2026-11-27, after Fukumoto 2026, IJAE-D-26-00011): the driver's first choice before any learning
(baseline = pair-2 winner) and the session's final sound (model #1), shown as Sound A and Sound B. The driver switches between them freely
while driving (as in the session pairs) and rates each 1-7. Which sound is A is counterbalanced over participants. The ratings, the side
assignment and how often each sound was played are written into the session record (evaluation.ratings, evaluation.sides, evaluation.plays)."""
import json
import random
from datetime import datetime, timezone


class Evaluation:
    def __init__(self, history):
        self.history = history; self.state = None

    def _records(self):
        for path in self.history.root.glob('*.json'):
            try: yield json.loads(path.read_text(encoding='utf8'))
            except (OSError, ValueError): continue

    def start(self, ident=None):
        """ident None: the session just finished in this run."""
        ident = ident or self.history.session
        if not ident: raise ValueError('No finished session to evaluate')
        data = self.history.get(ident); ev = data.get('evaluation') or {}
        if not ev.get('baseline') or not ev.get('final'): raise ValueError('This session has no baseline and final sound to evaluate')
        # Counterbalance: Sound A is the one that was A less often in the evaluations so far (a tie: a coin).
        sides = [d['evaluation']['sides']['A'] for d in self._records() if (d.get('evaluation') or {}).get('sides')]
        n_base, n_final = sides.count('baseline'), sides.count('final')
        a = 'baseline' if n_base < n_final else 'final' if n_final < n_base else random.choice(('baseline', 'final'))
        self.state = {'session': ident, 'sides': {'A': a, 'B': 'final' if a == 'baseline' else 'baseline'}, 'plays': {'A': 0, 'B': 0}, 'done': False,
                      'sounds': {k: data['candidates'][ev[k]]['recipe'] for k in ('baseline', 'final')}}
        return self.view()

    def view(self):
        s = self.state
        if not s: return None
        # blind: letters and recipes only (no label, no baseline/final)
        return {'session': s['session'], 'done': s['done'],
                'pair': [{'id': f"eval-{s['session'][:8]}-{x}", 'letter': x, 'label': '', 'recipe': s['sounds'][s['sides'][x]], 'urls': [], 'traces': {}} for x in 'AB']}

    def played(self, letter):
        if not self.state or letter not in ('A', 'B'): raise ValueError('No evaluation running')
        self.state['plays'][letter] += 1

    def rate(self, ratings):
        s = self.state
        if not s or s['done']: raise ValueError('No evaluation running')
        if not isinstance(ratings, dict) or set(ratings) != {'A', 'B'} or any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 7 for v in ratings.values()):
            raise ValueError('Rate both sounds from 1 to 7')
        data = self.history.get(s['session'])
        data['evaluation'].update(sides=s['sides'], ratings={s['sides'][x]: ratings[x] for x in 'AB'}, plays={s['sides'][x]: s['plays'][x] for x in 'AB'},
                                  same_sound=data['evaluation']['baseline'] == data['evaluation']['final'], rated=datetime.now(timezone.utc).isoformat())
        self.history.write(s['session'], data); s['done'] = True
        return self.view()

    def cancel(self):
        self.state = None


if __name__ == '__main__':  # self-check on a temporary history
    import tempfile
    from pathlib import Path
    from experiment.source_history import SourceHistory
    root = Path(tempfile.mkdtemp()); h = SourceHistory(None, root)
    rec = {'id': 'a' * 32, 'created': '', 'history': [], 'final': None, 'finalists': [], 'candidates': {'b': {'recipe': {'x': 1}}, 'f': {'recipe': {'x': 2}}},
           'evaluation': {'baseline': 'b', 'final': 'f'}}
    (root / f"{'a' * 32}.json").write_text(json.dumps(rec))
    e = Evaluation(h); v = e.start('a' * 32); a = e.state['sides']['A']
    assert v['pair'][0]['recipe'] == rec['candidates'][rec['evaluation'][a]]['recipe']
    e.played('A'); e.played('A'); e.played('B'); v = e.rate({'A': 6, 'B': 3})
    assert v['done']; saved = h.get('a' * 32)['evaluation']
    assert saved['ratings'][a] == 6 and saved['plays'][a] == 2 and saved['sides']['A'] == a
    e.start('a' * 32); assert e.state['sides']['A'] != a  # counterbalanced against the saved one
    print('evaluation self-check OK')
