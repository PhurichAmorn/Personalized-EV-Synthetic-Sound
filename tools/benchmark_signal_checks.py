"""Qualify and time signal checks on the source families, styles and defect probes."""
from pathlib import Path
import hashlib,json,platform,statistics
import numpy as np
from audio.signal_checks import check_signal,POLICY
from tools.check_signals import read_normalized

ROOT=Path('artifacts/signal_checks_2026-11-06')


def main():
    rows=[]
    def measure(label,path,loop=False,raw=False,group='family'):
        if raw:rate=48000;audio=np.fromfile(path,dtype='<f4').reshape(-1,2)
        else:rate,audio=read_normalized(path)
        durations=[]
        for _ in range(3):
            result=check_signal(audio,rate,loop=loop);durations.append(result['elapsed_ms'])
        rows.append({'label':label,'group':group,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'median_check_ms':statistics.median(durations),'runs_ms':durations,**result})
        print(label,result['decision'],round(statistics.median(durations),1),'ms',','.join(item['code'] for item in result['findings']),flush=True)
    original=Path('artifacts/audiobox_family_eval_2026-11-06')
    families=json.loads((original/'clips.json').read_text())['families']
    for family in families:measure(f"{family['id']} · raw source loop",original/f"{family['id']}_source.f32",loop=True,raw=True,group='source')
    for mode,directory in [('rise',original),('steady',ROOT/'steady'),('evolving',ROOT/'evolving')]:
        for family in families:measure(f"{family['id']} · {mode}",directory/f"{family['id']}_{mode}.wav",group='drive')
    stress=Path('artifacts/audiobox_stress_pool_2026-11-06')
    for clip in json.loads((stress/'clips.json').read_text())['clips']:measure(clip['id'],Path(clip['path']),group='stress')
    report={'policy':POLICY,'hardware':'Apple M2, 16 GB unified memory','platform':platform.platform(),'repeats':3,'timing':'Median warm check time, excludes file reads, synthesis, mapping render and audio playback; no model inference; no controlled concurrent BeamNG test.','results':rows}
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/'qualification.json').write_text(json.dumps(report,indent=2))
    text=['# Signal-check qualification and runtime','',report['timing'],'','Reject = engineering failure; review = a conservative heuristic flag, not a taste judgment; pass = no detected issue, not certified pleasantness. Thresholds are provisional and versioned.','','| Condition | Result | Median ms | Findings |','|---|---|---:|---|']
    for row in rows:text.append(f"| {row['label']} | {row['decision']} | {row['median_check_ms']:.1f} | {', '.join(f['code'] for f in row['findings']) or '—'} |")
    text+=['','Source loops are checked before audition fades. Rendered styles include source transformation, driving envelope, filter, chorus and room through the offline render approximation, not a live dashboard capture. All three styles use the same recorded input trace. Launch/idle/end silence is not considered a short dropout. Callers can provide sample-aligned expected activity for stronger missing-audio diagnostics.','', 'This set contains no sample overload; overload, full-scale plateaus, invalid samples, broken-loop joins and expected-silence context are covered by synthetic unit fixtures.','', 'UFO modulation and fast flutter can pass: they are valid modulated signals, not proof of a rendering failure. Signal checks cannot replace preference learning or certify listening comfort. High-band detections cannot establish aliasing from output alone, so they request review and never identify a family as disliked.','', 'The checker is integrated into the offline family-render finalizer. It is not a real-time monitor, automatic source repairer, or a candidate acceptance gate in the app. No Audiobox prediction is used.']
    (ROOT/'REPORT.md').write_text('\n'.join(text)+'\n')
    for group in ['source','drive','stress']:
        times=[row['median_check_ms'] for row in rows if row['group']==group]
        print(group,'range_ms',round(min(times),1),round(max(times),1),'median_ms',round(statistics.median(times),1),flush=True)


if __name__=='__main__':main()
