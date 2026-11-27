# Block-session benchmark, Run A2: 40 / 60 / 80 / 120 / 160 pairs, with and without answer noise

> **Out of date (2026-11-27).** This run is for the old Building blocks session. The standard session is now Best guess; see [Best guess results](benchmark_guess_results.md).

Run 2026-11-26 on GitHub Actions (runs 45762073013 noise-free, 45762077891 logistic 0.5), 25 chunks each, 5 oracle families x 40 profiles x 10 seeds,
arms current / random / infogain (400 sessions per oracle, budget and arm). Reports: `benchmark_blocks_report_runA2_noisefree.txt`, `benchmark_blocks_report_runA2_logistic0.5.txt`.
The noise-free report was regenerated from `all_sessions.csv` because the workflow filtered on `none` while sessions store `none:0.0` (workflow fixed).
**Synthetic listeners only.** Extends Run A (`benchmark_blocks_runA_long.md`) to 120 / 160 pairs and adds a noise-free control.

## Pooled top-10% (Random / Current / InfoGain)

| Pairs | logistic 0.5 | Current - Random | noise-free | Current - Random |
|---|---|---|---|---|
| 40 | .597 / .653 / .729 | +.057 | .873 / .908 / .892 | +.035 |
| 60 | .651 / .761 / .784 | +.110 | .945 / .933 / .923 | -.011 |
| 80 | .691 / .777 / .848 | +.086 | .968 / .949 / .941 | -.020 |
| 120 | .765 / .846 / .891 | +.081 | .984 / .967 / .977 | -.017 |
| 160 | .786 / .856 / .914 | +.070 | .988 / .983 / .995 | -.005 |

Regret gap (Random - Current): .15-.18 at every budget with noise; .18 -> .03 without noise.
Held-out accuracy .63-.69 with noise and .65-.67 without, for every arm (Random equal or higher).

## Findings

- The gap does not grow with longer sessions. With noise Current - Random stays +.06 to +.11 (BETTER at every budget); InfoGain - Current stays +.02 to +.08, almost all of it from psycho (+.23 to +.30).
- Without noise Current's edge disappears and is slightly negative at 80 and 120 pairs (-.02): label (60-160) and psycho (60-120) are significantly worse than Random.
- Current's advantage is therefore robustness to noisy answers, not better learning: the preference model reaches the same held-out accuracy as Random even with perfect answers.
- Best-heard top-10% is .94-.99 for all arms: a top-10% sound is almost always heard, so the metric saturates and the limit is the final selection and the model, not the sound pool.

## Caveats

- Simulated listeners; 400 sessions per cell, so differences under about 3 points are within noise.
- The mechanism (re-testing the champion averages out noise) is a hypothesis, not tested.
- Top-10% saturates; a stricter metric (top-5%, top-1%) was not recomputed here.
