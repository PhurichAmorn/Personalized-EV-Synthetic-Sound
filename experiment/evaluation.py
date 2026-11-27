"""Blind evaluation after a session (agreed 2026-11-27, after Fukumoto 2026, IJAE-D-26-00011): the driver's first choice before any learning
(baseline = pair-2 winner) and the session's final sound (podium #1), played A-B-A-B while driving, each play rated 1-7. Which sound is A is
counterbalanced over participants. The ratings are written into the session record (evaluation.ratings, evaluation.scores)."""
import json
import random
from datetime import datetime, timezone

PLAYS = 4  # A-B-A-B: each sound twice


class Evaluation:
    def __init__(self, history):
        self.history = history; self.state = None

    def _records(self):
        for path in sorted(self.history.root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            try: yield json.loads(path.read_text(encoding='utf8'))
            except (OSError, ValueError): continue

    def sessions(self):
        """Finished sessions that can be evaluated (they name a baseline and a final), newest first; rated ones say so."""
        return [{'id': d['id'], 'created': d.get('created', ''), 'participant': bool(d.get('participant')), 'rated': bool(d['evaluation'].get('ratings'))}
                for d in self._records() if (d.get('evaluation') or {}).get('baseline') and d['evaluation'].get('final')]

    def start(self, ident):
        data = self.history.get(ident); ev = data.get('evaluation') or {}
        if not ev.get('baseline') or not ev.get('final'): raise ValueError('This session has no baseline and final sound to evaluate')
        # Counterbalance: the sound played first is the one that went first less often in the evaluations so far (a tie: a coin).
        firsts = [d['evaluation']['order'][0] for d in self._records() if (d.get('evaluation') or {}).get('order')]
        n_base, n_final = firsts.count('baseline'), firsts.count('final')
        first = 'baseline' if n_base < n_final else 'final' if n_final < n_base else random.choice(('baseline', 'final'))
        second = 'final' if first == 'baseline' else 'baseline'
        self.state = {'session': ident, 'order': [first, second] * (PLAYS // 2), 'ratings': [],
                      'sounds': {k: data['candidates'][ev[k]]['recipe'] for k in ('baseline', 'final')}}
        return self.view()

    def view(self):
        s = self.state
        if not s: return None
        step = len(s['ratings']); done = step == PLAYS
        out = {'session': s['session'], 'step': step, 'total': PLAYS, 'done': done}
        if not done:  # blind: a letter and the recipe only (no label, no baseline/final)
            which = s['order'][step]; out['letter'] = 'A' if which == s['order'][0] else 'B'
            out['candidate'] = {'id': f"eval-{s['session'][:8]}-{out['letter']}", 'label': '', 'recipe': s['sounds'][which], 'urls': [], 'traces': {}}
        return out

    def rate(self, rating):
        s = self.state
        if not s or len(s['ratings']) == PLAYS: raise ValueError('No evaluation running')
        if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 7: raise ValueError('Rate from 1 to 7')
        step = len(s['ratings'])
        s['ratings'].append({'play': step + 1, 'sound': s['order'][step], 'rating': rating, 'time': datetime.now(timezone.utc).isoformat()})
        if len(s['ratings']) == PLAYS:
            data = self.history.get(s['session'])
            mean = lambda k: sum(r['rating'] for r in s['ratings'] if r['sound'] == k) / (PLAYS // 2)
            data['evaluation'].update(order=s['order'], ratings=s['ratings'], scores={'baseline': mean('baseline'), 'final': mean('final')},
                                      same_sound=data['evaluation']['baseline'] == data['evaluation']['final'], rated=s['ratings'][-1]['time'])
            self.history.write(s['session'], data)
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
    e = Evaluation(h); v = e.start('a' * 32); first = e.state['order'][0]
    assert v['letter'] == 'A' and v['candidate']['recipe'] == rec['candidates'][rec['evaluation'][first]]['recipe']
    for r in (6, 3, 7, 4): v = e.rate(r)
    assert v['done']; saved = h.get('a' * 32)['evaluation']
    assert saved['scores'][first] == 6.5 and saved['scores'][e.state['order'][1]] == 3.5 and e.sessions()[0]['rated']
    print('evaluation self-check OK')
