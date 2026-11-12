"""Render N random recipes with the real renderer and save recipe+descriptor (oracle/surrogate data for benchmark_source_search.py).
Usage: python -m tools.build_source_library [old|open] [count]   -> .cache/<pool>_library.json (old pool keeps .cache/source_library.json)"""
import json,random,shutil,sys
from concurrent.futures import ThreadPoolExecutor
from experiment.source_search import METHODS,make_broad_recipe,make_open_recipe
from experiment.source_render_queue import CACHE,SourceRenderer

def main(pool='old',count=600):
    rng=random.Random(7);render=SourceRenderer();count=int(count)
    if pool=='old':recipes=[make_broad_recipe(rng,rng.choice(METHODS),n) for n in (1,2,3) for _ in range(count//3)];out='.cache/source_library.json'
    else:recipes=[make_open_recipe(rng,n) for n in (1,2,3) for _ in range(count//3)];out=f'.cache/{pool}_library.json'
    def one(recipe):
        try:result=render(recipe)
        except Exception as exc:return {'recipe':recipe,'rejected':str(exc)[:200]}
        shutil.rmtree(CACHE/result['id'],ignore_errors=True)  # ~10 MB of WAVs per render; only the descriptor is kept
        return {'recipe':recipe,'descriptor':result['audio_descriptor']}
    with ThreadPoolExecutor(8) as executor:rows=list(executor.map(one,recipes))
    kept=[r for r in rows if 'descriptor' in r]
    json.dump(kept,open(out,'w'));print(len(kept),'kept,',len(rows)-len(kept),'rejected by signal checks ->',out)

if __name__=='__main__':main(*sys.argv[1:3])
