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

## Limits

- Smaller than the pre-registered size; rerun at full size (GitHub Actions) before citing the numbers in a report.
- The new-sound bias strength is a rough calibration.
- Both sessions use the same linear Bradley-Terry model; the comparison is about how pairs are chosen and how the final sound is picked.
