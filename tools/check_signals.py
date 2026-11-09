"""Run offline signal checks and optional timing benchmarks on WAV files."""
import argparse,hashlib,json,platform,statistics,time
from pathlib import Path
import numpy as np
from scipy.io.wavfile import read
from audio.signal_checks import check_signal,POLICY


def read_normalized(path):
    rate,data=read(path)
    if data.dtype.kind=='u':audio=(data.astype(float)-128)/128
    elif data.dtype.kind=='i':audio=data.astype(float)/(-float(np.iinfo(data.dtype).min))
    else:audio=data
    return rate,audio


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='+',type=Path)
    parser.add_argument('--loop',action='store_true',help='Only use for audio intended to repeat as a source loop')
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.repeats<=20:parser.error('repeats must be between 1 and 20')
    rows=[]
    for path in args.paths:
        start=time.perf_counter();rate,audio=read_normalized(path);read_ms=(time.perf_counter()-start)*1000
        durations=[]
        for _ in range(args.repeats):
            report=check_signal(audio,rate,loop=args.loop);durations.append(report['elapsed_ms'])
        row={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'read_ms':read_ms,'median_check_ms':statistics.median(durations),'runs_ms':durations,**report}
        rows.append(row)
        print(f"{path.name}: {report['decision']} · {row['median_check_ms']:.1f} ms · "+', '.join(item['code'] for item in report['findings']))
    result={'policy':POLICY,'platform':platform.platform(),'note':'Offline checks, no model inference. Timing excludes WAV read time; no controlled concurrent BeamNG workload. Review is not a quality verdict. Stereo retained.','files':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))


if __name__=='__main__':main()
