"""Score and publish the standalone listening pool; model remains outside app selection."""
from pathlib import Path
import hashlib,json,shutil,time
import torch
from audiobox_aesthetics.infer import initialize_predictor
from huggingface_hub import hf_hub_download
from tools.score_family_evaluation import synchronize

ROOT=Path('artifacts/audiobox_stress_pool_2026-11-06')
PUBLIC=Path('desktop/public/audio/stress-pool-v1')


def main():
    torch.set_num_threads(4)
    manifest=json.loads((ROOT/'clips.json').read_text())
    predictor=initialize_predictor()
    start=time.perf_counter()
    predictor.forward([{'path':manifest['clips'][0]['path']}]);synchronize(predictor.device)
    manifest['warmup_seconds']=time.perf_counter()-start
    manifest['model']='facebook/audiobox-aesthetics 0.0.4; frozen pretrained weights, no fine-tuning'
    manifest['device']=str(predictor.device)
    manifest['weights_sha256']=hashlib.sha256(Path(hf_hub_download('facebook/audiobox-aesthetics','model.safetensors')).read_bytes()).hexdigest()
    PUBLIC.mkdir(parents=True,exist_ok=True)
    for clip in manifest['clips']:
        synchronize(predictor.device);start=time.perf_counter()
        scores=predictor.forward([{'path':clip['path']}])[0];synchronize(predictor.device)
        assert all(torch.isfinite(torch.tensor(v)).item() for v in scores.values())
        clip['scores']=scores;clip['inference_seconds']=time.perf_counter()-start
        filename=f"{clip['id']}-{clip['sha256'][:10]}.wav"
        shutil.copyfile(clip['path'],PUBLIC/filename)
        clip['url']=f'/audio/stress-pool-v1/{filename}'
        (ROOT/'scores.json').write_text(json.dumps(manifest,indent=2))
        print(clip['id'],json.dumps(scores),flush=True)
    assert len(manifest['clips'])==9
    (PUBLIC/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (PUBLIC/'ATTRIBUTION.txt').write_text('Model predictions: Meta Audiobox Aesthetics, Tjandra et al. 2025. https://github.com/facebookresearch/audiobox-aesthetics ; model/code CC BY 4.0 with MIT third-party portions. Audio: original EV Sound Lab synthetic sources, offline Rise approximation, modified for this listening experiment. Scores are model predictions, not listener ratings or certified comfort judgments.\n')
    lines=['# Audiobox controlled-defect listening pool','',manifest['method'],'',f"All clips: 10 seconds, {manifest['target_lufs']:.2f} LUFS. Frozen model on {manifest['device']}. No rejection thresholds or app sound changes.",'','| Clip | PQ | CE | PC | CU |','|---|---:|---:|---:|---:|']
    for clip in manifest['clips']:
        s=clip['scores'];lines.append(f"| {clip['label']} | {s['PQ']:.3f} | {s['CE']:.3f} | {s['PC']:.3f} | {s['CU']:.3f} |")
    lines+=['','PQ: production quality; CE: enjoyment; PC: complexity; CU: source-material usefulness. High complexity is not a quality target. Comparisons should use the clean reference within this pool; earlier family scores used different durations and normalization.','', 'The 10-kHz probe is largely outside the model’s resampled bandwidth; loudness matching also changes its underlying reference level. A changed score therefore does not establish detection of the high whistle. User ratings are needed to validate which probes are actually unpleasant. No audio was played automatically.']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('Published nine graded clips:',PUBLIC/'manifest.json')


if __name__=='__main__':main()
