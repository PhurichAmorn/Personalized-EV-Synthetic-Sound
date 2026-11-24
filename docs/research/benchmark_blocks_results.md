# Block-session benchmark: results

Run 2026-11-23 to 2026-11-24 on Laptop B. Plan: [benchmark_blocks_plan.md](benchmark_blocks_plan.md) (written before the run; section 9 added the four secondary arms and section 10 their decision criteria, both before any result of those arms). Raw report: [benchmark_blocks_report_logistic0.5.txt](benchmark_blocks_report_logistic0.5.txt). Reproduced 2026-11-24 on GitHub Actions (25 chunks, ~100 min wall clock; raw report [benchmark_blocks_report_logistic0.5_github.txt](benchmark_blocks_report_logistic0.5_github.txt)): every Current - Random cell and every secondary verdict matches Laptop B (differences at most 0.002), so the result does not depend on the machine. Harness: `tools/benchmark_blocks.py`; arms shared with the app in `experiment/block_arms.py`.
All numbers here are for the session as it was until 2026-11-24 (pair 14 replays pair 4; 9 challenger pairs). The app now plays 10 challenger pairs and no replay; `REPLAY=1` reproduces these results, and the new default has not been benchmarked yet.
All results are from **synthetic preference profiles**. They show how the selection methods behave under the stated assumptions, not that real listeners prefer the sounds.

## Setup in one paragraph

Eight arms play the app's `BlockDiscovery` session against hidden simulated listeners: 5 oracle families (matched, multimodal, interaction, label, psycho) x 40 profiles x 25 seeds = 1,000 sessions per oracle, budget and arm. Budgets 12, 17 (the app's session) and 30 pairs (adaptive pairs 9, 9, 22). Primary noise: logistic, tau = 0.5 SD. Both good / Neither calibrated on the lab's real exports (thresholds +3.0 and 0 SD). Outcome: the shortlist's #1 is in the profile's top 10% of 15,614 sounds. Contrasts are paired by (profile, seed) with a profile-level bootstrap 95% CI. Core arms: Current, Random, InfoGain, IEC. Secondary arms: PBOGP, Duel, Robust, Pairs. The code and thresholds were not changed between the core and secondary runs; the core rows are identical in both reports, so the run reproduces.

## 1. Primary result: Current against Random (top-10% retrieval)

| Oracle | 12 pairs | 17 pairs | 30 pairs |
|---|---|---|---|
| matched | +0.036 | **+0.073** | **+0.071** |
| multimodal | +0.036 | +0.022 | **+0.055** |
| interaction | **+0.054** | **+0.059** | **+0.074** |
| label | +0.041 | +0.037 | +0.012 |
| psycho | **+0.209** | **+0.113** | **+0.213** |
| **pooled** | **+0.075** [+0.058, +0.092] | **+0.061** [+0.044, +0.077] | **+0.085** [+0.067, +0.104] |

Bold = BETTER by the plan's rule (CI above 0 and difference at least 0.05). Tally of the 15 primary contrasts: **9 BETTER, 6 no detectable difference, 0 worse.**

Reading:
- Current beats Random reliably but modestly. At 17 pairs the pooled means are 0.509 and 0.448.
- The pooled gain leans on **psycho** (+0.11 to +0.21); without it the pooled gain at 17 pairs is about +0.04. Psycho is also the hardest oracle in absolute terms (Current 0.24, Random 0.13 at 17 pairs).
- **Label** shows no effect on any metric: the pool, the gate and the shortlist do the work there (Random reaches 0.70 at 30 pairs, Current 0.71).
- The algorithm's gain at 17 pairs is worth roughly 8 to 9 extra random pairs (rough linear interpolation of Random from 17 to 30; the structures differ).

## 2. Secondary arms against the criteria written in advance (plan section 10)

Top-10%, pooled over oracles, 17 pairs, primary noise.

| # | Contrast | Result | Rule | Verdict |
|---|---|---|---|---|
| 1 | PBOGP - Current | -0.003 [-0.018, +0.013] | adopt if CI above 0, at least +0.05, and no oracle worse | **Not adopted.** PBOGP is also worse on psycho at 17 pairs (-0.048, CI below 0). Current stays. |
| 2 | PBOGP - InfoGain | -0.022 [-0.039, -0.005] | the kernel helps if CI above 0 and at least +0.03 | **The kernel does not help**; it is slightly worse. Keep the linear model. |
| 3 | Duel - Current | -0.062 [-0.082, -0.043] | build the hybrid if at least -0.02 pooled, or clearly better (CI above 0, at least +0.05) on 2 or more oracles | **Not met.** Duel is better only on psycho at 17 pairs (+0.042, under the bar). |
| 4a | Current - Pairs | +0.075 [+0.058, +0.092] | equivalence band +-0.03 | **Above the band**: the tournament plus model helps. |
| 4b | Random - Pairs | +0.014 [-0.002, +0.031] | equivalence band +-0.03 | **Borderline, not met**: the upper bound is 0.001 over the band, so equivalence is not claimed. |
| 5 | Robust - Current | -0.038 [-0.048, -0.028] | equivalence band +-0.03 | **Below the band**: resetting the champion to the model's best is worse than winner-stays. The noise critique of winner-stays is not supported here. |

Other secondary results (top-10%, pooled at 17 pairs): InfoGain - Current **+0.019** [+0.005, +0.034], below the 0.05 bar, so "no detectable difference"; its regret is lower (-0.035 SD [-0.053, -0.018]). IEC - Current **-0.091** [-0.112, -0.070], WORSE pooled; the difference is negative in all 15 cells (the CI excludes 0 in 14).

Per-arm pooled means (top-10% / regret in SD):

| Pairs | Current | InfoGain | PBOGP | Robust | Random | IEC | Duel | Pairs |
|---|---|---|---|---|---|---|---|---|
| 12 | .477 / 1.34 | .501 / 1.29 | .494 / 1.34 | .461 / 1.37 | .402 / 1.45 | .394 / 1.49 | .285 / 1.68 | .279 / 1.69 |
| 17 | .509 / 1.28 | .528 / 1.24 | .506 / 1.31 | .471 / 1.33 | .448 / 1.38 | .418 / 1.44 | .447 / 1.39 | .434 / 1.43 |
| 30 | .625 / 1.08 | .660 / 1.03 | .621 / 1.12 | .578 / 1.17 | .540 / 1.21 | .505 / 1.28 | .494 / 1.33 | .460 / 1.37 |

## 3. What the budget does

Current at 30 pairs against 17: +0.09 to +0.16 on every oracle. 17 against 12: +0.03 to +0.065 on four oracles and -0.016 on psycho (the finishing pairs slightly hurt there). The 30-pair budget is 22 adaptive pairs against 9, and the simulated listener does not tire, so the budget effect is an upper bound.

## 4. Other metrics (core arms, Current - Random, 17 pairs)

| Oracle | top-5% | shortlist top-5% |
|---|---|---|
| matched | +0.038 | +0.083 |
| multimodal | +0.038 | +0.064 |
| interaction | +0.066 | +0.081 |
| label | +0.026 | +0.019 |
| psycho | +0.140 | +0.230 |

The shortlist metric (any of the up to 5 shortlisted sounds is in the top 5%) favours Current more than #1 alone, and every arm gains 0.08 to 0.12 from showing five sounds instead of one. Top-5% and shortlist top-5% were aggregated by Laptop B from the session CSVs (plain means with the same profile-level bootstrap); the harness `report` does not print them.

## 5. What the results mean

1. The current design (linear Bayesian Bradley-Terry model, Thompson sampling with a distance bonus, winner stays) is the best of the eight methods tested under these assumptions. No alternative cleared a pre-registered bar.
2. **Model expressiveness is not the bottleneck at 17 pairs:** the kernel model (PBOGP) did no better than the linear one, and a better acquisition on the same linear model (InfoGain) helped only slightly.
3. **The duel trades retrieval for breadth.** It finds the best sound less often (0.447 against 0.509 at 17 pairs; at 17 pairs its regret is worse on every oracle except psycho) but its held-out accuracy is higher (0.61 against 0.59 at 17, 0.66 against 0.61 at 30), because it samples the whole space and learns the global taste. This matches a listener's report that duel sessions sound more diverse.
4. **The champion structure helps at 12 and 30 pairs** (Random over Pairs +0.07 to +0.18 on four oracles) but not clearly at 17, and the psycho oracle reverses it (random pairs beat random challengers by 0.11 at 17 and 30 pairs). When the model fits poorly, exploring beats staying.
5. The finishing pairs (replay, fine-tune, check) help on four oracles and slightly hurt psycho.

## 6. Limits and what is not yet done

- Synthetic profiles chosen by the authors, not calibrated to a population. Psycho (measured octave bands) carries much of the pooled gain; label shows none.
- **PBOGP and Duel are untuned** (kernel length scales 3, 2 steps and 0.3 acum; candidate count 400; all fixed guesses). Their results are for those settings only. The plan to tune on separate development profiles and confirm on fresh ones has not been run.
- **Sensitivity (section 6b) done for Current - Random only.** The advantage is not robust by the pre-registered rule: it disappears at 17 pairs under very noisy answers (logistic 1.0). The other arms' verdicts were not re-run under other noise.
- Held-out accuracy tracks how well each arm's model fits the oracle (0.50 to 0.73) and the breadth of its samples, not retrieval; it is exploratory only.
- The 30-pair budget has no fatigue. Real listeners have not been tested; human sessions come next.
- Random - Pairs misses the equivalence band by 0.001; the verdict is stated as borderline, not as equivalence.

## 6b. Sensitivity runs (Current - Random, 2026-11-24, GitHub Actions)

Design and rule written before the runs: plan section 11. Current and Random only, 5 oracles x 40 profiles x 10 seeds (400 sessions per oracle, budget and arm), one run per condition. Raw reports: [benchmark_blocks_sensitivity/](benchmark_blocks_sensitivity/).

Pooled Current - Random, top-10% (95% CI); bold = BETTER (CI above 0 and at least 0.05):

| Condition | 12 pairs | 17 pairs | 30 pairs |
|---|---|---|---|
| primary: logistic 0.5 (25 seeds) | **+0.076** [+0.058, +0.093] | **+0.061** [+0.045, +0.077] | **+0.085** [+0.067, +0.103] |
| logistic 0.25 | **+0.134** [+0.109, +0.158] | **+0.137** [+0.115, +0.160] | **+0.065** [+0.041, +0.088] |
| logistic 1.0 | **+0.052** [+0.029, +0.076] | -0.003 [-0.027, +0.021] | **+0.054** [+0.028, +0.081] |
| flip 0.1 | **+0.057** [+0.033, +0.081] | **+0.065** [+0.042, +0.086] | **+0.099** [+0.076, +0.123] |
| flip 0.25 | **+0.054** [+0.028, +0.080] | +0.024 [+0.002, +0.048] | **+0.099** [+0.073, +0.126] |
| no noise | **+0.063** [+0.040, +0.086] | **+0.052** [+0.030, +0.075] | +0.017 [-0.002, +0.037] |
| Both good / Neither removed | **+0.106** [+0.085, +0.130] | **+0.064** [+0.042, +0.086] | **+0.092** [+0.068, +0.116] |

Verdict against the rule (pooled sign positive in all six conditions, and CI above 0 at 17 pairs in at least 4 of 6): the second part holds (5 of 6), the first fails because **logistic 1.0 at 17 pairs is -0.003**. **Not robust by the rule written in advance.** Current beats Random in five of six alternative conditions at 17 pairs, and at 12 and 30 pairs it is positive in all, except that at 30 pairs with no noise the gain is +0.017.

Reading:
- The gain is clearest for a low-noise listener (logistic 0.25: +0.14) and for the lab-calibrated Both good / Neither. It vanishes at 17 pairs when the listener is very noisy (logistic 1.0), where answers carry little signal for any method.
- Psycho changes sign under some conditions at 17 pairs (logistic 1.0: -0.098; no noise: -0.090) and is the largest positive elsewhere (logistic 0.25: +0.400; Both/Neither removed: +0.153). The pooled result depends on that oracle.
- Removing Both good / Neither does not hurt Current; the lab-calibrated Both good / Neither is not what produces the gain.
- 10 seeds give wider CIs than the primary 25.

## 7. Decision

Keep Building blocks (Current) as the search to evaluate with listeners. InfoGain is a small, consistent possible improvement (lower regret) but under the bar. Duel is kept as an exploration tool for listening tests, not as the production search. Next: optional tuning of PBOGP and Duel on development profiles; human pilot.
