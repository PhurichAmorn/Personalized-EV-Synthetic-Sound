"""Bounded development render/cache worker. No PCM is sent over the sidecar protocol."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,threading,time
import numpy as np
from scipy.io.wavfile import read,write

PROJECT=Path(__file__).resolve().parents[1]
CACHE=PROJECT/'desktop/public/audio/source-search-cache'
VERSION_FILES=['experiment/source_render_queue.py','desktop/src/sourceDesigner.ts','desktop/src/sourceRecipe.ts','desktop/public/audio/granular-processor.mjs','desktop/src/drivingSoundMapping.ts','desktop/src/simulatedDrive.ts','desktop/src/audioAutomation.ts','audio/signal_checks.py','tools/render_family_evaluation.mjs','tools/finalize_family_evaluation.py']

class SourceRenderer:
    """Thread-safe: source discovery renders both sounds of a pair at once (one child process per call)."""
    def __init__(self):
        self.processes=set();self.lock=threading.Lock();self.closed=False;self.cancelled=threading.Event()
        # scipy.signal costs ~0.5 s (seconds on Windows with antivirus) to import: load it off the startup path.
        threading.Thread(target=lambda:__import__('tools.finalize_family_evaluation'),daemon=True).start()
    def cancel(self):
        self.cancelled.set()
        with self.lock:
            for process in self.processes:
                if process.poll() is None:process.terminate()
    def close(self):
        self.closed=True;self.cancel()
    def _run(self,args):
        if self.closed or self.cancelled.is_set():raise RuntimeError('Render cancelled')
        process=subprocess.Popen(args,cwd=PROJECT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        with self.lock:self.processes.add(process)
        try:
            try:out,err=process.communicate(timeout=120)
            except subprocess.TimeoutExpired:
                process.kill();process.communicate();raise RuntimeError('Source render timed out')
        finally:
            with self.lock:self.processes.discard(process)
        if self.closed or self.cancelled.is_set():raise RuntimeError('Render cancelled')
        if process.returncode:raise RuntimeError('Source render failed: '+(err or out)[-600:])
    def __call__(self,recipe):
        self.cancelled.clear()
        node=shutil.which('node')
        if not node:raise RuntimeError('Node.js is required for source discovery in this development build')
        stamp=''.join(hashlib.sha256((PROJECT/path).read_bytes()).hexdigest() for path in VERSION_FILES)
        for path in ['desktop/public/audio/original_steady_air.wav','desktop/public/audio/original_steady_room_ir.wav']:
            stamp+=hashlib.sha256((PROJECT/path).read_bytes()).hexdigest()
        key=hashlib.sha256((json.dumps(recipe,sort_keys=True,separators=(',',':'))+stamp).encode()).hexdigest()[:32]
        directory=CACHE/key;ready=directory/'ready.json'
        if ready.exists():return json.loads(ready.read_text())
        CACHE.mkdir(parents=True,exist_ok=True)
        directory.mkdir(exist_ok=True);(directory/'recipe.json').write_text(json.dumps(recipe))
        checks=[];traces={};descriptor=[];timings={};started=time.monotonic()
        try:
            for mode in ['rise']:
                target=directory/mode;target.mkdir(exist_ok=True)
                stage=time.monotonic()
                args=[node,'tools/render_family_evaluation.mjs',mode,str(target),str(directory/'recipe.json')]
                self._run(args)
                timings[mode+'_source_and_drive_seconds']=time.monotonic()-stage
                stage=time.monotonic()
                # In-process: numpy/scipy are already loaded, saving ~1 s of interpreter start per sound.
                # ponytail: cancel takes effect only after this step (~1.5 s); use a worker process if that matters.
                from tools.finalize_family_evaluation import finalize
                try:finalize(target)
                except Exception as exc:raise RuntimeError('Source effects/checks failed: '+str(exc)[-600:]) from exc
                if self.closed or self.cancelled.is_set():raise RuntimeError('Render cancelled')
                timings[mode+'_effects_and_checks_seconds']=time.monotonic()-stage
                meta=json.loads((target/'clips.json').read_text())
                for clip in meta['clips']:
                    checks.append({'mode':mode,'stage':clip['scene'],'decision':clip['signal_check']['decision'],'findings':clip['signal_check']['findings']})
                    if clip.get('pre_normalization_check'):
                        checks.append({'mode':mode,'stage':clip['scene']+'-before-preview-normalization','decision':clip['pre_normalization_check']['decision'],'findings':clip['pre_normalization_check']['findings']})
                    if clip.get('source_loop_check'):checks.append({'mode':mode,'stage':'loop','decision':clip['source_loop_check']['decision'],'findings':clip['source_loop_check']['findings']})
                if any(c['decision']!='pass' for c in checks):raise ValueError('Candidate needs signal review: '+','.join(sorted({f['code'] for c in checks for f in c['findings']})))
                sr,audio=read(target/f'candidate_{mode}.wav')
                filename=f'{mode}.wav';write(directory/filename,sr,np.round(np.clip(audio,-1,1)*32767).astype(np.int16))
                traces[mode]=f'/audio/source-search-cache/{key}/{filename}'
                if mode=='rise':
                    raw=np.fromfile(target/'candidate_source.f32',dtype='<f4').reshape(-1,2)
                    spectrum=np.sum(abs(np.fft.rfft(raw,axis=0))**2,axis=1)
                    frequencies=np.fft.rfftfreq(len(raw),1/48000)
                    edges=[0,100,180,300,500,800,1200,1800,2600,4000,6500,12000,24001]
                    descriptor=[float(spectrum[(frequencies>=a)&(frequencies<b)].sum()/max(spectrum.sum(),1e-20)) for a,b in zip(edges[:-1],edges[1:])]
                    for stem in range(3):shutil.copyfile(target/f'stem-{stem}.wav',directory/f'stem-{stem}.wav')
                shutil.rmtree(target)
            urls=[f'/audio/source-search-cache/{key}/stem-{i}.wav' for i in range(3)]+['/audio/original_steady_air.wav?v=17']
            result={'id':key,'label':' + '.join(layer['method'].title() for layer in recipe['layers'])+(' · reference' if recipe['seed']==0 else ' · variant '+key[:6]),'recipe':recipe,'audio_descriptor':descriptor,'urls':urls,'traces':traces,'qualification_modes':['rise'],'checks':checks,'renderer_hash':hashlib.sha256(stamp.encode()).hexdigest(),'audio_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.wav')},'timings':dict(timings,total_seconds=time.monotonic()-started),'render_note':'Raw source and Rise-only driving qualification approximate browser DSP; Steady/Evolving are playable but not separately qualified. Live input can produce other trajectories.'}
            temp=directory/'ready.tmp';temp.write_text(json.dumps(result));temp.replace(ready)
            return result
        except Exception:
            shutil.rmtree(directory,ignore_errors=True);raise


def trim_cache(protected):
    """Evict oldest unreferenced audio at 1 GiB; current/favourite audio is protected."""
    if not CACHE.exists():return
    directories=[path for path in CACHE.iterdir() if path.is_dir()]
    sizes={path:sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) for path in directories}
    total=sum(sizes.values())
    for path in sorted(directories,key=lambda p:p.stat().st_mtime):
        if total<=1024**3:break
        if path.name not in protected:shutil.rmtree(path);total-=sizes[path]
