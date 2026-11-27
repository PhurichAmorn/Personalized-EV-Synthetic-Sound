# Best guess session: simulated-listener results

Run 2026-11-27 on the lab Mac with `tools/benchmark_blocks.py` (arms `current` = Building blocks, `guess` = Best guess,
`experiment/block_arms.py` `GuessBlocks`). This replaces the [Building blocks benchmark](benchmark_blocks_results.md) as the current result:
that one compared pair-selection methods inside the old Building blocks session, which is no longer the standard session.

**Synthetic listeners only.** The results show how the searches behave under the benchmark's assumptions (five oracle families of hidden
taste, logistic answer noise 0.5 SD), not that real drivers prefer the sounds. The blind evaluation after each session tests that.

## Setup

Same harness and oracles as the Building blocks benchmark, but a **smaller run than the pre-registered one**: 5 oracles x 20 profiles x 5 seeds
(100 sessions per oracle, budget and arm; the pre-registered size is 40 x 25). Outcome: the final sound is in the listener's top 10% of the
15,614 sounds the table allows. Paired by (oracle, profile, seed); 95% CI from a profile-level bootstrap. No plan was written before this run.

A second run adds a listener who favours sounds not heard before (`NEW_BIAS=0.3` SD, about 65% for the new sound between equal sounds),
calibrated to the real Building blocks sessions, where the challenger won 65% of champion pairs (2026-11-27, 37 local sessions).

## Results (top-10% retrieval)

| Pairs | Building blocks | Best guess | Difference [95% CI] |
| --- | --- | --- | --- |
| 12 | 0.53 | 0.58 | +0.04 [-0.03, +0.11] |
| 17 (the app) | 0.58 | 0.69 | +0.11 [+0.04, +0.18] |
| 30 | 0.63 | 0.73 | +0.10 [+0.04, +0.16] |
| 17, listener favours new sounds | 0.52 | 0.66 | +0.14 [+0.07, +0.21] |

At 17 pairs Best guess is ahead on 4 of 5 oracle families (label: 0.61 vs 0.63). Regret 1.05 vs 1.19 SD; held-out pair accuracy 0.64 vs 0.59.

## Model features tried (17 pairs)

Pitch and brightness enter the model as a value and its square (a curve). Thompson draws of a curve favour the ends, and two test sessions
showed it (9 of 15 challengers at 47 or 119 Hz). Two alternatives were tried and **not adopted** (benchmark arms `guesslevels`, `guessboth`):

| Features | No bias | Favours new sounds |
| --- | --- | --- |
| Curve (kept) | **0.69** | **0.66** |
| One category per level | 0.59 | 0.57 |
| Curve and categories | 0.70 | 0.60 |

Categories spread the challengers evenly but lose the sharing between neighbouring levels, which 17 answers need.

## Pair-choice comparison: plan (written 2026-11-28, before any result)

Ten arms on the Best guess session (`tools/benchmark_blocks.py`, `GUESS_ARMS`). All share the model (Bayesian Bradley-Terry over the 31
block features), the 15,614 sounds, and the shared rules (A and B clearly different, no pair twice). Only the pair choice differs:

| Arm | Report name | Sound A | Sound B |
| --- | --- | --- | --- |
| `guess` | Bradley-Terry, greedy vs Thompson (the app) | Highest posterior mean | Best under one Thompson sample |
| `grandom` | Random pairs | Random | Random |
| `ggreedy` | Greedy | Highest mean | Second highest mean |
| `gexplore` | Pure explore | Highest mean | Largest SD of the difference |
| `gdts` | Double Thompson (Wu & Liu 2016), linear version | Thompson sample 1 | Thompson sample 2 |
| `gbrochu` | Expected improvement (Brochu et al. 2007) | Best heard so far | Highest expected improvement over A |
| `grucb` | Relative UCB (Zoghi et al. 2014), linear version | Highest mean + 1 SD | Highest (difference + 1 SD of it) |
| `gpbo` | Dueling Thompson (Gonzalez et al. 2017), linear version | Thompson sample | Largest variance of P(B beats A) |
| `geubo` | EUBO (Lin et al. 2022) | Pair with highest E[max(u(A), u(B))], among the top 100 by mean and top 100 by mean + 2 SD | |
| `giga` | Interactive genetic algorithm (Fukumoto 2026 settings) | Population 8, 4 pairs per generation, tournament 2, elitism 1, 2-point crossover 90%, mutation 5%; no model; final = best of the last finished generation | |

The dueling-bandit and PBO papers work on separate arms or Gaussian processes; these are their pair rules on our linear model. IGA gets
pairwise answers (win = fitness 1) instead of 1-7 ratings.

Size: 5 oracles x 40 profiles x 25 seeds; budgets 17 (the app), 20, 30, 50, 80 pairs; two listeners (no bias; NEW_BIAS = 0.3).
50 and 80 pairs cannot be driven: they show each method's ceiling (IGA needs generations).

Decision rules (top-10% retrieval, pooled over oracles, paired to `guess`, profile-level bootstrap 95% CI), at 17 pairs, both listeners:

1. **Switch to another arm** if its difference to `guess` has a CI above 0 and is at least +0.05 in both listener conditions.
2. **Double Thompson** (`gdts`, less repetition of the best guess): switch if its difference is at least -0.02 (point estimate) in both conditions.
3. **Session length:** keep 17 unless `guess` at 20 is at least +0.03 over 17 (CI above 0); 30+ is reported only.
4. IGA, Greedy, Pure explore and Random are reported for comparison; no decision depends on them.

## Limits

- Smaller than the pre-registered size; rerun at full size (GitHub Actions) before citing the numbers in a report.
- The new-sound bias strength is a rough calibration.
- Both sessions use the same linear Bradley-Terry model; the comparison is about how pairs are chosen and how the final sound is picked.
