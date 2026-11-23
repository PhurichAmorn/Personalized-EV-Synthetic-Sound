# Block-session benchmark: plan and contrast list

Written 2026-11-23, **before the full run**. Commit this file first; the git history is the record that the plan came before the results.
Code: `tools/benchmark_blocks.py` (harness), `experiment/source_search.py` (`BlockDiscovery`, `adaptive`, `_order_broad`).
All results are from **synthetic preference profiles**. They show how the selection methods behave under stated assumptions, not that real
listeners like the sounds. Human evidence comes from a separate study.

## 1. Question

With a limited number of A/B answers, does the app's challenger selection (Current) find sounds a hidden listener ranks highly more often
than random challengers, and does that hold when the listener's taste is not in the model's form, when answers are noisy, and when the
session is longer?

## 2. Design

| Part | Choice |
|---|---|
| Session | The app's `BlockDiscovery`. Motion pair skipped (Rising only). Starts, playoff, replay, fine-tune pairs, Bradley-Terry shortlist, Both good / Neither: the app's code, the same for every arm. |
| Arms | **Current** (Thompson sample + distance), **Random** (shuffled challengers), **InfoGain** (EUBO-style, 200 posterior draws), **IEC** (crossover with the sound with most wins, no model). Arms differ only in the order of broad challengers (pairs 5 to 13, and their extension). |
| Budgets (pairs played) | **12** = 3 opening + 9 adaptive, scored right after (learner only). **17** = the app's session (9 adaptive). **30** = adaptive stretched to 22; the 8 fixed pairs unchanged. |
| Oracles | matched (additive taste in the model's form, reference), multimodal (two peaks), interaction (pitch x brightness, top x level), label (random value per body/top/partner combination), psycho (measured octave bands from the table). Each is independent of the model's feature vector except matched. |
| Profiles | 40 per oracle (profile = oracle seed). |
| Seeds | 25 per profile (session seed: starts order, arm randomness, answer noise). Same profile and seed for every arm (paired). |
| Ground truth | 15,614 sounds the safe-area table allows (body x top x partner x level x pitch x synth knobs x 5 brightness targets). Utilities z-scored over this set per profile. |
| Primary noise | Logistic, tau = 0.5 SD: P(pick better) = 1/(1+exp(-gap/tau)). |
| Sensitivity noise | none; logistic tau = 0.25 and 1.0; flip with eps = 0.1 and 0.25. |
| Both / Neither | Kept as in the app. Both good when both sounds are above +3.0 SD, Neither when both are below 0 SD (the profile's average sound). **Calibrated 2026-11-23** on the real exports (19 block sessions, 311 choices: Both good 1.6%, Neither 2.3%). With these thresholds the simulated Current arm at 17 pairs gives Both good 2.7% and Neither 2.5% (5 oracles x 4 profiles x 3 seeds). The first guess of +-0.5 SD gave 49% Both good and 0.1% Neither, which does not match the real listener. The real data come from the lab's own sessions, not a population. |

Sessions in the primary design: 5 oracles x 40 profiles x 25 seeds x 3 budgets x 4 arms = 60,000 (about 6 h on the lab laptop).

## 3. Outcomes

| Outcome | Definition |
|---|---|
| **Top-10% retrieval (primary)** | 1 if the shortlist's #1 is in the profile's top 10% of the 15,614 sounds, else 0 |
| Regret (secondary) | best utility in the ground-truth set minus the #1's utility, in SD |
| Top-5% retrieval | as above at 5% |
| Shortlist top-5% | 1 if any of the up to 5 shortlisted sounds is in the top 5% |
| Held-out pair accuracy (exploratory) | the learned model's pair prediction on 3,000 random sound pairs whose utility gap exceeds 0.5 SD |

## 4. Contrasts

Every contrast is paired by (profile, seed) and reported with a **profile-level bootstrap 95% CI** (resample the 40 profiles, 1,000 times,
within each oracle), as the difference in the outcome mean.

**Primary (15 contrasts): Current minus Random, top-10% retrieval, primary noise.**
5 oracles x 3 budgets (12, 17, 30). All 15 are reported whatever they show. No multiple-testing correction; the confidence intervals are the
result, and the pooled estimate below is the headline.

**Headline (1):** the same contrast pooled over all five oracles at budget 17 (profiles weighted equally across oracles).

**Secondary (30): InfoGain minus Current, IEC minus Current**, each over the same 15 cells, top-10% retrieval and regret.

**Budget effect (5):** Current at 30 minus Current at 17, and at 17 minus 12, top-10% retrieval, per oracle (the 17 vs 12 contrast tests what the finishing phase adds).

**Sensitivity:** repeat the 15 primary contrasts under each alternative noise condition in section 2, and with Both good / Neither removed
(forced choice). A primary result is called robust if the sign of the difference holds in all conditions.

**Exploratory (not claimed as findings):** held-out accuracy, top-5% and shortlist outcomes, per-profile detail, any comparison not listed.

## 5. Decision rule

- **Current is better than Random** in a cell if the 95% CI of its top-10% difference is above 0 **and** the point difference is at least 0.05 (5 percentage points). A difference with a CI that spans 0, or below 0.05, is reported as **no detectable difference**, not as evidence of equality.
- **Current is worse** if the CI is below 0.
- The paper states the count of cells in each outcome (better / no difference / worse) before discussing any single cell.
- If Current is not better than Random in most cells, the claim is "the pool, gate and ranking do the work", and the paper says so. This outcome is allowed.
- Same rule for the secondary contrasts (InfoGain and IEC against Current).

## 6. Checks before the full run (none of these use benchmark results)

1. Calibrate the Both / Neither thresholds on the real session exports (section 2). **Done 2026-11-23:** real Both good 1.6%, Neither 2.3%; thresholds +3.0 SD and 0 SD.
2. Check the psycho oracle's independence: its correlation with the model's brightness features over the ground-truth set. If it is high (say above 0.8), redesign it before running. **Done 2026-11-23 (second machine, 12 profiles):** correlation 0.26 to 0.37, multiple R on brightness terms at most 0.38. Passes.
3. Check the label oracle's misspecification: how much of its variance the model's one-hot features can explain (linear fit R^2 over the ground-truth set). Record it. If it is above 0.9 it is effectively matched and is replaced. **Done 2026-11-23 (second machine, 12 profiles):** R^2 0.26 to 0.57, mean 0.41. Passes.
4. Confirm `python -m unittest tests.test_block_discovery` still passes, and that Current at budget 17 reproduces the default session (the pair sequence at adaptive 9 equals the app's).
5. Smoke runs are code checks only; their numbers are not used to change this plan.

## 7. Reporting

- A table of the 15 primary contrasts (difference and CI), the headline, then the secondary and budget contrasts.
- Figures: top-10% retrieval and regret against budget for the four arms (per oracle); robustness across noise conditions.
- State: synthetic profiles are assumptions, not calibrated to a population; one listener's labels were the only real data (used only for the Neither rate); the 30-pair budget has no fatigue.
- Any change to this plan after the run is listed in the paper as a deviation, with the reason.

## 8. Limits stated in advance

- The oracle families are chosen by the authors; they cover some forms of misspecification, not all.
- The ground-truth set is the table's reachable sounds on a brightness grid; sounds off the grid are scored directly but not in the truth set.
- IEC and InfoGain are adaptations to a finite, table-gated sound space; weak adaptations would look like weak methods.
- Neither, Both and noise levels are assumptions; the sensitivity runs show how much the conclusion depends on them.
- Simulated oracles do not tire, so the 30-pair budget is optimistic.
