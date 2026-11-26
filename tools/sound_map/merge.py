"""Merge sound-map libraries grown on different machines (islands: same code and settings, different SEED) into one, with the
generator's own archive rule (generate.insert): a clearly different sound is added, a near-copy keeps the better of the two.
  python tools/sound_map/merge.py out/library.a.json out/library.b.json [...] -o out/library.frame.json
Then run the full-drive check on the merged library (drive.py library, optionally split with --part)."""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import insert


def merge(libraries):
    configs = [json.dumps(lib.get('config'), sort_keys=True) for lib in libraries]
    if None in [lib.get('config') for lib in libraries] or len(set(configs)) > 1:
        raise SystemExit('merge: the libraries were made with different settings or code (config differs); regenerate them alike')
    archive, added, replaced = [], 0, 0
    for lib in libraries:
        for entry in lib['sounds']:
            result = insert(archive, entry)
            added += result == 'added'; replaced += result == 'replaced'
    first = libraries[0]
    log = [{'merged': [{'created': lib['created'], 'kept': len(lib['sounds']), **{k: lib['log'][-1][k] for k in ('gen', 'tried', 'passed')}} for lib in libraries],
            'gen': max(lib['log'][-1]['gen'] for lib in libraries), 'tried': sum(lib['log'][-1]['tried'] for lib in libraries),
            'passed': sum(lib['log'][-1]['passed'] for lib in libraries), 'kept': len(archive)}]
    return {'created': time.strftime('%Y-%m-%d %H:%M'), 'limits': first['limits'], 'distinct': first['distinct'], 'config': first['config'],
            'log': log, 'sounds': archive}, added, replaced


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('libraries', nargs='+'); ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    libs = [json.load(open(p)) for p in a.libraries]
    merged, added, replaced = merge(libs)
    json.dump(merged, open(a.out, 'w'), indent=1)
    print(f"merged {' + '.join(str(len(l['sounds'])) for l in libs)} sounds -> {len(merged['sounds'])} distinct ({replaced} near-copies kept the better one) -> {a.out}")
