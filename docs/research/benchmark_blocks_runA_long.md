# Block-session benchmark, Run A: longer sessions (40 / 60 / 80 pairs)

> **Out of date (2026-11-27).** This run is for the old Building blocks session. The standard session is now Best guess; see [Best guess results](benchmark_guess_results.md).

Run 2026-11-25 on GitHub Actions (run 45597126228, workflow `benchmark.yml`), 50 chunks, 10 seeds, 5 oracle families x 40 profiles, logistic noise 0.5.
Full output: `benchmark_blocks_report_runA_long.txt`. Harness: `tools/benchmark_blocks.py` (adds `heard10`).
**Synthetic listeners only.** Draft for review; not yet cleaned up.

## Why

Professor asked for more comparisons per session. Earlier runs covered 12/17/30 pairs. Run A extends to 40/60/80.
Metric: top-10% = how often the final sound is in the listener's top 10% of the 15,614-sound pool. Best-heard = same, for the best sound the listener actually heard (run C).

## Pooled over the 5 oracle families

| Pairs | Current | InfoGain | Random | Current - Random |
|---|---|---|---|---|
| 40 | 0.653 | 0.729 | 0.597 | +0.06 |
| 60 | 0.761 | 0.784 | 0.651 | +0.11 |
| 80 | 0.777 | 0.848 | 0.691 | +0.09 |

Regret (lower better): Current 0.98 / 0.84 / 0.79, InfoGain 0.92 / 0.81 / 0.72, Random 1.13 / 1.02 / 0.95.
Held-out accuracy is flat across arms (0.63-0.67).

## By oracle family (top-10%, Current / InfoGain / Random)

| Family | 40 | 60 | 80 |
|---|---|---|---|
| interaction | .71 / .80 / .65 | .80 / .82 / .70 | .82 / .86 / .74 |
| label | .79 / .72 / .75 | .83 / .78 / .81 | .84 / .83 / .85 |
| matched | .76 / .81 / .65 | .84 / .87 / .70 | .88 / .91 / .73 |
| multimodal | .80 / .79 / .69 | .86 / .85 / .75 | .89 / .90 / .79 |
| psycho | .21 / .52 / .24 | .47 / .60 / .30 | .47 / .74 / .34 |

## Findings

- More pairs help: Current goes 0.65 -> 0.78 from 40 to 80 pairs.
- Current beats Random on interaction, matched, multimodal, psycho (at 60-80 pairs; CIs exclude 0). On label it ties Random (-0.01 to +0.04).
- Current's gain over Random does not grow with length (+0.06 / +0.11 / +0.09); the earlier 12/17/30 gain was +0.06 to +0.09.
- Psycho is the weak family: Current is at Random level at 40 pairs (0.21 vs 0.24) and plateaus at 0.47. InfoGain reaches 0.74 at 80.
- InfoGain leads on average mostly because of psycho; on multimodal the two tie.
- Best-heard top-10% is 0.94 (40) to 0.99 (80) for all arms, Random within about 1 point. At these budgets the limit is the selected final sound, not what was heard; the metric does not separate the arms.

## Caveats

- Simulated listeners; results depend on the oracle families and noise level.
- Benchmark brightness grid (0.25 steps) differs from session start values; not fixed.
- Run B (knobs-fixed pool) not run; waits on which parameters get frozen.
