"""Standalone frozen Audiobox experiment; never used by the app or candidate selection."""
from pathlib import Path
import hashlib,importlib.metadata,json,platform,resource,statistics,time
import torch
from audiobox_aesthetics.infer import initialize_predictor
from huggingface_hub import hf_hub_download

ROOT=Path('artifacts/audiobox_family_eval_2026-11-06')

def synchronize(device):
    if device.type=='mps':torch.mps.synchronize()
    elif device.type=='cuda':torch.cuda.synchronize()


def main():
    torch.set_num_threads(4)
    manifest=json.loads((ROOT/'clips.json').read_text())
    checkpoint=hf_hub_download('facebook/audiobox-aesthetics','model.safetensors')
    begin=time.perf_counter()
    predictor=initialize_predictor()
    synchronize(predictor.device)
    report={'hardware':'Apple M2, 16 GB unified memory','platform':platform.platform(),'cpu_threads':torch.get_num_threads(),'model':'facebook/audiobox-aesthetics','weights_sha256':hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),'device':str(predictor.device),'model_load_cached_seconds':time.perf_counter()-begin,'parameters':sum(p.numel() for p in predictor.model.parameters()),'precision':str(predictor.model.precision),'versions':{name:importlib.metadata.version(name) for name in ['audiobox_aesthetics','torch','torchaudio']},'scope':'Frozen model; common controls and -24 LUFS clips; source versus offline Rise approximation. No rejection thresholds or preference learning.','results':[],'benchmarks':[]}
    def predict(path):
        synchronize(predictor.device);start=time.perf_counter()
        scores=predictor.forward([{'path':path}])[0]
        synchronize(predictor.device)
        assert all(torch.isfinite(torch.tensor(value)).item() for value in scores.values())
        return scores,time.perf_counter()-start
    warmup=manifest['clips'][0]['path']
    try:
        _,report['warmup_seconds']=predict(warmup)
    except RuntimeError as error:
        report['mps_failure']=str(error)
        predictor.device=torch.device('cpu');predictor.model.to('cpu')
        report['device']='cpu';_,report['warmup_seconds']=predict(warmup)
    def save():
        report['max_process_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2)
        if torch.backends.mps.is_available():report['mps_driver_allocated_mib']=torch.mps.driver_allocated_memory()/(1024**2)
        (ROOT/'scores.json').write_text(json.dumps(report,indent=2))
    for clip in manifest['clips']:
        scores,seconds=predict(clip['path'])
        row={**clip,'scores':scores,'inference_seconds':seconds,'device':str(predictor.device)}
        report['results'].append(row);save()
        print(clip['family'],clip['scene'],json.dumps(scores),f'{seconds:.3f}s',flush=True)
    primary_device=predictor.device
    for device in dict.fromkeys([str(primary_device),'cpu']):
        predictor.device=torch.device(device);predictor.model.to(predictor.device)
        for scene in ['source','rise']:
            clip=next(c for c in manifest['clips'] if c['family']=='bowed' and c['scene']==scene)
            predict(clip['path'])
            runs=[];scores=None
            for _ in range(3):scores,seconds=predict(clip['path']);runs.append(seconds)
            report['benchmarks'].append({'device':device,'scene':scene,'clip_seconds':clip['seconds'],'runs_seconds':runs,'median_seconds':statistics.median(runs),'scores':scores})
            save();print('BENCHMARK',device,scene,statistics.median(runs),flush=True)
    assert len(report['results'])==12
    save()
    print('Saved',ROOT/'scores.json',flush=True)


if __name__=='__main__':main()
