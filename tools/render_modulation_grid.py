"""One-off calibration: amplitude-modulate a base source at several rates/depths, render each through
the real Rise pipeline, and measure envelope-modulation depth on the final clip.

Run from the project root:
  .venv/bin/python -m tools.render_modulation_grid artifacts/modulation_grid
  .venv/bin/python -m tools.render_modulation_grid --selftest

The envelope metric is a proxy (not asper/vacil). Compare against the depth-0 baseline, not absolute values.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse,csv,json,random,shutil,subprocess,sys
import numpy as np
from scipy.io.wavfile import read,write
from audio.signal_checks import MODULATION_BANDS as BANDS,modulation_depth

PROJECT=Path(__file__).resolve().parents[1]
RATES=(2,4,8,20,30,50,70,100,150)  # Hz; all multiples of 0.2 so the 5 s source loop stays seamless.
DEPTHS=(.1,.2,.4)


def selftest():
    rate=48000;t=np.arange(rate*10)/rate;carrier=np.sin(2*np.pi*220*t)
    flat=modulation_depth(carrier,rate)
    for hz,band in [(70,'rough_30-150'),(4,'fluct_0.5-20')]:
        modulated=modulation_depth(carrier*(1+.3*np.sin(2*np.pi*hz*t)),rate)
        expected=.3/np.sqrt(2)
        assert abs(modulated[band]-expected)<.03,(hz,modulated)  # sinusoidal AM depth m gives rms m/sqrt(2).
        assert modulated[band]>10*flat[band],(hz,flat,modulated)
    print('selftest ok')


def run(args,cwd=PROJECT):
    done=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=600)
    if done.returncode:raise RuntimeError((done.stderr or done.stdout)[-600:])


def render_variant(base,recipe_path,out,rate,depth):
    """Modulate the base stems, then render + finalize exactly as SourceRenderer does for mode 'rise'."""
    source=out/'src';source.mkdir(parents=True,exist_ok=True)
    for index in range(3):
        sr,stem=read(base/f'stem-{index}.wav');time=np.arange(len(stem))/sr
        write(source/f'stem-{index}.wav',sr,(stem*(1+depth*np.sin(2*np.pi*rate*time))[:,None]).astype(np.float32))
    target=out/'out'
    run(['node','tools/render_family_evaluation.mjs','rise',str(target),str(recipe_path),str(source)])
    run([sys.executable,'-m','tools.finalize_family_evaluation',str(target)])
    clips=json.loads((target/'clips.json').read_text())['clips']
    clip=next(c for c in clips if c['scene']=='rise')
    sr,audio=read(target/'candidate_rise.wav')
    return audio,sr,clip


def main():
    parser=argparse.ArgumentParser();parser.add_argument('out',nargs='?',default='artifacts/modulation_grid')
    parser.add_argument('--recipe',help='recipe JSON; default is the glass reference');parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--selftest',action='store_true');args=parser.parse_args()
    if args.selftest:return selftest()
    from experiment.source_search import make_recipe
    out=(PROJECT/args.out);out.mkdir(parents=True,exist_ok=True)
    recipe=json.loads(Path(args.recipe).read_text()) if args.recipe else make_recipe(random.Random(0),'glass')
    recipe_path=out/'recipe.json';recipe_path.write_text(json.dumps(recipe))
    base=out/'base'
    shutil.rmtree(base,ignore_errors=True)
    run(['node','tools/render_family_evaluation.mjs','rise',str(base),str(recipe_path)])  # writes stem-0..3.wav
    jobs=[(0,0.)]+[(rate,depth) for depth in DEPTHS for rate in RATES]
    def work(job):
        rate,depth=job;name=f'am_{rate:03d}Hz_d{int(depth*100):02d}'
        audio,sr,clip=render_variant(base,recipe_path,out/'variants'/name,rate,depth)
        shutil.copyfile(out/'variants'/name/'out'/'candidate_rise.wav',out/f'{name}.wav')
        shutil.rmtree(out/'variants'/name)
        print('done',name,flush=True)
        return {'name':name,'source_rate_hz':rate,'depth':depth,**modulation_depth(audio,sr),'lufs':clip['lufs'],'signal_check':clip['signal_check']['decision'],'findings':';'.join(f['code'] for f in clip['signal_check']['findings'])}
    with ThreadPoolExecutor(args.workers) as pool:rows=list(pool.map(work,jobs))
    baseline=rows[0]
    for row in rows:
        for band in BANDS:row[band+'_excess']=float(np.sqrt(max(row[band]**2-baseline[band]**2,0)))
    with open(out/'results.csv','w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=[*rows[0],'heard'],restval='');writer.writeheader();writer.writerows(rows)
    print(f"{'file':20}{'fluct':>8}{'grain':>8}{'rough':>8}{'peakHz':>8}  check")
    for row in rows:print(f"{row['name']:20}{row['fluct_0.5-20_excess']:8.3f}{row['grain_20-30_excess']:8.3f}{row['rough_30-150_excess']:8.3f}{row['peak_hz']:8.1f}  {row['signal_check']} {row['findings']}")
    print('Excess = above the depth-0 baseline. Wrote',out/'results.csv','; listen to',out,'*.wav and fill the heard column.')


if __name__=='__main__':main()
