"""Build the Sound Lab roughness/chord listening pack from the modulation-grid and companion-test renders.

  .venv/bin/python -m tools.build_listening_check
Writes 16-bit WAVs and manifest.json to desktop/public/audio/roughness-check-v1/.
Labels are blind (shuffled, parameters only in the manifest/export); the unmodified reference is shown openly.
"""
from pathlib import Path
import csv,hashlib,json,random
import numpy as np
from scipy.io.wavfile import read,write

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'desktop/public/audio/roughness-check-v1'
WOBBLE=[(4,.2),(4,.4),(8,.4),(20,.4),(30,.4),(50,.4),(70,.2),(70,.4),(100,.4),(150,.4)]
CHORD_FAMILIES=['glass','bowed','airy']
CHORD_SETS=['orig','unison_octave','sub_octave']


def pack(src,name):
    rate,audio=read(src);assert audio.dtype==np.float32 and np.abs(audio).max()<=1
    path=OUT/name;write(path,rate,np.round(audio*32767).astype(np.int16))
    return {'url':f'/audio/roughness-check-v1/{name}','seconds':round(len(audio)/rate,1),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUT.mkdir(parents=True,exist_ok=True);rng=random.Random(7);clips=[]
    grid=ROOT/'artifacts/modulation_grid'
    proxy={row['name']:row for row in csv.DictReader(open(grid/'results.csv'))}
    def wobble(rate,depth):
        name=f'am_{rate:03d}Hz_d{int(depth*100):02d}';row=proxy[name]
        return {'kind':'modulation','source_rate_hz':rate,'depth':depth,'proxy_fluct_excess':float(row['fluct_0.5-20_excess']),'proxy_grain_excess':float(row['grain_20-30_excess']),'proxy_rough_excess':float(row['rough_30-150_excess'])},name
    params,name=wobble(0,0.);clips.append({'id':'w_ref','group':'wobble','set':'wobble','reference':True,'label':'Reference (unmodified)','params':params,**pack(grid/f'{name}.wav','w_ref.wav')})
    order=WOBBLE[:];rng.shuffle(order)
    for i,(rate,depth) in enumerate(order,1):
        params,name=wobble(rate,depth);clips.append({'id':f'w{i:02d}','group':'wobble','set':'wobble','reference':False,'label':f'Wobble sound {i}','params':params,**pack(grid/f'{name}.wav',f'w{i:02d}.wav')})
    companion={(r['fam'],r['set']):r for r in json.load(open(ROOT/'artifacts/companion_test/results.json'))}
    for s,family in enumerate(CHORD_FAMILIES,1):
        order=CHORD_SETS[:];rng.shuffle(order)
        for letter,interval in zip('ABC',order):
            row=companion[(family,interval)]
            clips.append({'id':f'c{s}{letter}','group':'chord','set':f'chord{s}','reference':False,'label':f'Set {s} · Sound {letter}','params':{'kind':'companion','family':family,'interval_set':interval,'proxy_rough':row['rough'],'proxy_peak_hz':row['peak']},**pack(ROOT/f'artifacts/companion_test/{family}_{interval}.wav',f'c{s}{letter}.wav')})
    (OUT/'manifest.json').write_text(json.dumps({'version':1,'target_lufs':-24.0,'clips':clips},indent=1))
    print(len(clips),'clips,',round(sum(p.stat().st_size for p in OUT.glob('*.wav'))/1e6),'MB')


if __name__=='__main__':main()
