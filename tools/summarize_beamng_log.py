"""Summarise an EV_SOUND_BEAMNG_LOG recording as one line per second.

  PowerShell:  $env:EV_SOUND_BEAMNG_LOG = "$PWD\beamng_log.csv"; .\\launch_windows.cmd
  then:        .venv\\Scripts\\python.exe -m tools.summarize_beamng_log beamng_log.csv
"""
import csv, sys
from collections import defaultdict

rows = defaultdict(list)
with open(sys.argv[1]) as handle:
    for row in csv.DictReader(handle):
        rows[int(float(row['t']))].append(row)
base = min(rows)
number = lambda row, key: float(row[key]) if row[key] != '' else float('nan')
print(f"{'s':>4} {'km/h':>6} {'thr':>5} {'brk':>5} {'torque min..max':>17} {'load field':>10} {'app load':>9} {'regen shown':>11}")
for second in sorted(rows):
    group = rows[second]
    mean = lambda key: sum(number(r, key) for r in group) / len(group)
    torques = [number(r, 'motor_torque') for r in group]
    print(f"{second - base:>4} {mean('speed_kmh'):>6.1f} {mean('throttle'):>5.2f} {mean('brake'):>5.2f} "
          f"{min(torques):>8.1f}..{max(torques):<7.1f} {mean('motor_load_field'):>10.2f} {mean('app_signed_load'):>9.2f} "
          f"{max(number(r, 'app_regen') for r in group):>11.2f}")
