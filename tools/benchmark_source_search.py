"""Simulated-listener benchmark: how close does source discovery get to a hidden target sound?
Real renders take 3-5 s, so sessions use a library of real renders (tools/build_source_library.py): library recipes keep their real
descriptor; recipes outside the library (the current search's own proposals) go through a kNN surrogate fitted on the library.
Usage: python -m tools.benchmark_source_search [seeds] [pool]"""
import hashlib,json,random,sys,time
import numpy as np
from experiment.source_search import METHODS,MAX_COMPARISONS,PLAYOFF_PAIRS,SourceDiscovery,make_broad_recipe,preference_features

def hellinger(a,b):return float(np.linalg.norm(np.sqrt(np.maximum(a,0))-np.sqrt(np.maximum(b,0)))/np.sqrt(2))
def vector(recipe):
    layers=recipe['layers']
    return np.concatenate([preference_features(recipe),[np.mean([l['shape'].get('rootRatio',1) for l in layers])],
                           [np.mean([l.get('controls',{}).get(k,.5) for l in layers]) for k in ('body','character','ensemble')]])

class Surrogate:
    def __init__(self,rows,k=1):  # k=1: every candidate is a real library sound, like random draws
        self.x=np.stack([vector(r['recipe']) for r in rows]);self.y=np.array([r['descriptor'] for r in rows]);self.k=k
        self.scale=self.x.std(0)+1e-6
    def __call__(self,recipe):
        d=np.linalg.norm((self.x-vector(recipe))/self.scale,axis=1);nearest=np.argsort(d)[:self.k]
        descriptor=self.y[nearest].mean(0).tolist()
        return {'id':hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:32],'recipe':recipe,'label':'bench','audio_descriptor':descriptor}

key=lambda recipe:json.dumps(recipe,sort_keys=True)
class Library:
    """Renderer: exact descriptor for library recipes, surrogate otherwise."""
    def __init__(self,rows):
        self.rows=rows;self.exact={key(r['recipe']):r['descriptor'] for r in rows};self.surrogate=Surrogate(rows) if rows[0]['recipe']['layers'][0]['method']!='blocks' else None
    def __call__(self,recipe):
        if key(recipe) in self.exact:
            return {'id':hashlib.sha256(key(recipe).encode()).hexdigest()[:32],'recipe':recipe,'label':'bench','audio_descriptor':self.exact[key(recipe)]}
        return self.surrogate(recipe)

class RandomDiscovery(SourceDiscovery):
    """Same session protocol (pairs, ratings, playoff); proposals are random draws from the pool's library."""
    def _proposals(self):
        return [self.renderer.rows[self.rng.randrange(len(self.renderer.rows))]['recipe'] for _ in range(8)]

def run_session(render,target,rng,noise=.7,search=SourceDiscovery):
    rate=lambda d:int(min(7,max(1,round(7-14*hellinger(d,target)+rng.gauss(0,noise)))))
    d=search(renderer=render);d.start()
    def ready():
        while d.busy:time.sleep(.002)
        assert not d.error,d.error
    seen=[];curve=[]
    for _ in range(MAX_COMPARISONS):
        ready();pair=list(d.pair)
        for i in pair:d.heard(i)
        seen+=[hellinger(d.candidates[i]['audio_descriptor'],target) for i in pair];curve.append(min(seen))
        if d.pair_mode=='choice':  # parent check: direct choice, same noisy rule as the final round
            a,b=(hellinger(d.candidates[i]['audio_descriptor'],target)+rng.gauss(0,.03) for i in pair);d.feedback(choice='A' if a<b else 'B')
        else:d.feedback({'A':rate(d.candidates[pair[0]]['audio_descriptor']),'B':rate(d.candidates[pair[1]]['audio_descriptor'])})
    for _ in range(PLAYOFF_PAIRS):
        pair=list(d.pair);curve.append(curve[-1])
        for i in pair:d.heard(i)
        a,b=(hellinger(d.candidates[i]['audio_descriptor'],target)+rng.gauss(0,.03) for i in pair)
        d.playoff_feedback('A' if a<b else 'B')
    final=d._bt_order()[0][0];d.close()
    return hellinger(d.candidates[final]['audio_descriptor'],target),curve,np.array(d.candidates[final]['audio_descriptor'])

# An approach = pool (render library) + search. Each pool lists the searches that apply to it; every pool gets its own oracle.
# 'current' only applies to the old pool: its proposals and model are built on the six family presets.
POOLS={'old-pool':('.cache/source_library.json',{'current':SourceDiscovery,'random':RandomDiscovery}),
       'open-pool':('.cache/open_library.json',{'random':RandomDiscovery})}

def main(seeds=40,only=None):
    engine=np.array(json.load(open('tools/benchmark_target_engine.json'))['descriptor'])  # synthetic engine: listener-approved reference sound
    old=np.array([r['descriptor'] for r in json.load(open(POOLS['old-pool'][0]))]);rng=random.Random(3)
    # Shared targets so pools are compared on the same sounds; "dark tonal" = sounds from the old pool.
    targets={'dark tonal (sound from old pool)':[old[rng.randrange(len(old))] for _ in range(seeds)],'synthetic engine':[engine]*seeds}
    for pool_name,(path,searches) in POOLS.items():
        if only and pool_name!=only:continue
        try:rows=json.load(open(path))
        except FileNotFoundError:print(f'\n[{pool_name}] no library at {path}; build it with tools/build_source_library.py');continue
        render=Library(rows);pool=np.array([r['descriptor'] for r in rows]);own=random.Random(5)
        pool_targets=dict(targets)
        if pool_name!='old-pool':pool_targets[f'sound from {pool_name}']=[pool[own.randrange(len(pool))] for _ in range(seeds)]
        for target,items in pool_targets.items():
            oracle=np.array([min(hellinger(p,t) for p in pool) for t in items])
            print(f'\n[{pool_name}, {len(pool)} sounds] target {target}  oracle {oracle.mean():.3f}  (n={len(items)})')
            print(f'  {"search":9} {"final":>6} {"gap":>6} {"spread":>7}   best-so-far at turn 5/10/14/20')
            for name,search in searches.items():
                out=[run_session(render,t,random.Random(i),search=search) for i,t in enumerate(items)]
                final=np.array([o[0] for o in out]);curve=np.mean([o[1] for o in out],0)
                finals=[o[2] for o in out];spread=np.mean([hellinger(a,b) for i,a in enumerate(finals) for b in finals[i+1:]])
                print(f'  {name:9} {final.mean():6.3f} {(final-oracle).mean():6.3f} {spread:7.3f}   '+' / '.join(f'{curve[k-1]:.3f}' for k in (5,10,14,20)))

if __name__=='__main__':main(*(int(a) for a in sys.argv[1:2]),*sys.argv[2:3])
