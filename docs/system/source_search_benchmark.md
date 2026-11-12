# Source-search benchmark

Measures how well a source-discovery **approach** finds a sound the listener has in mind, without a human in the loop. An approach is a **pool** (what sounds can be made) plus a **search** (how pairs are proposed and the final sound chosen). Every approach runs through the same simulated session so differences come only from the approach.

Code: `tools/benchmark_source_search.py`. Run: `.venv/bin/python -m tools.benchmark_source_search 80` (80 sessions per row, a few seconds).

## How a run works

1. **Hidden target.** A target sound's 12-band spectrum (`audio_descriptor`, bands 0–24 kHz) is chosen. The search never sees it.
2. **Simulated session.** The real `SourceDiscovery` session runs unchanged: 14 rated pairs, 4 finalists, 6-pair Bradley-Terry playoff (20 turns, about 28 different sounds heard).
3. **Simulated listener** (pseudo-user) stands in for the person:
   - rating of each sound: `clip(round(7 − 14·d + N(0, 0.7)), 1, 7)`, where `d` is the distance to the target. Closer is rated higher, the noise mimics human inconsistency.
   - playoff: picks the sound closer to the target, with small noise (σ = 0.03).
4. **Result.** The session's final choice (top of the Bradley-Terry order) is compared to the target.
5. Repeat for many sessions and average.

**Distance** `d` is the Hellinger distance between spectra: 0 = identical spectrum, 1 = no overlap. It ignores rhythm, roughness and pitch motion.

**Rendering.** Real renders take about 3 s, too slow for hundreds of sessions. A kNN surrogate (k = 3) predicts each recipe's spectrum from a library of real renders (`tools/build_source_library.py`, 600 recipes, saved to `.cache/source_library.json`, git-ignored and regenerable). The surrogate only knows recipes similar to the library, so each new pool needs its own library.

## Targets

| Name | What it is | What it tests |
|---|---|---|
| dark tonal (sound from pool) | A different random sound from the pool in each session. Pool sounds are dark, low-mid and tonal (most energy 100–800 Hz, almost none above 1.2 kHz). | The search alone: the sound is guaranteed to exist, so a miss is the search's fault (in-domain target). |
| synthetic engine | Engine-style source approved by listening (`tools/benchmark_target_engine.json`), made with the app's own synthesis. | The whole approach: is the sound reachable with this pool, and does the search reach it (out-of-domain target). |

## Searches

| Name | Proposals | Everything else |
|---|---|---|
| current | Family balancing plus ridge preference model (the app's algorithm) | Same session |
| random | Random recipes from the same pool generator | Same session |

New pools go in `POOLS`, new searches in `SEARCHES`. Each pool gets its own oracle.

## Metrics

| Metric | Meaning | Lower is better? |
|---|---|---|
| **oracle** | Distance from the target to the closest sound in the pool library. Answers "can this pool make the sound?" No session involved. 0 = the sound exists in the pool. | yes |
| **final** | Distance from the session's final choice to the target. What the listener would actually get. | yes |
| **gap** | `final − oracle`: how far short of the best possible the search ended. | yes |
| **best-so-far at turn 5/10/14/20** | Closest sound heard by that turn. Shows whether and how fast the search approaches the target within the 20-turn budget. Turns 15–20 are the playoff, which re-uses heard sounds, so the value equals turn 14. | yes |
| **spread** | Mean distance between final choices of different sessions. For one fixed target (synthetic engine) it shows how consistent sessions are. For varying targets (dark tonal) it shows whether different listeners end up with different sounds. A low value across varying targets means sessions collapse to the same sound. | depends |

Reading: a high oracle means the pool is the limit; a large gap with a low oracle means the search is the limit.

## Basis in research

- Pseudo-user replacing the human with a hidden function that rates on fixed levels: Takagi, *Interactive evolutionary computation*, Proc. IEEE 2001; Takagi 2008 pseudo-IEC user.
- Virtual users with a target in design space to test interactive search for EV sounds: Petiot et al., ICED 2019, Proceedings of the Design Society (details not yet verified from the full text).
- Optimality gap per iteration, simulated user, random variant of the method as baseline, 50 trials, Mann–Whitney U with Bonferroni: Koyama, Sato & Goto, *Sequential Gallery*, ACM TOG 2020.
- Score of the method's current best guess (final pick): González et al., *Preferential Bayesian Optimization*, ICML 2017.
- In-domain vs out-of-domain sound-matching targets: Masuda & Saito, ISMIR 2021 and TASLP 2023.
- Audio distance to target as sound-matching measure: Yee-King, Fedden & d'Inverno, IEEE TETCI 2018.
- 10–20 pairwise judgments sufficient for 4 audio parameters (supports the 20-turn budget): Nielsen, Nielsen & Larsen, IEEE/ACM TASLP 2015.
- Coverage of a behaviour space (basis for spread): Mouret & Clune 2015; Pugh, Soros & Stanley 2016.
- The pool-limited oracle is this project's adaptation of the known-optimum used with synthetic test functions.

## Limits

- The listener is a distance function, so the benchmark checks search logic, not taste. Confirm promising approaches with real listening.
- The 12-band spectrum is coarse; two different-sounding sources can score close.
- The surrogate averages nearby library renders, so it cannot represent recipes outside its library.
- `SourceDiscovery` is unseeded, so results move by about ±0.01 between runs; use 80+ sessions and a significance test before claiming a difference.

## Current results (old pool, 80 sessions each)

| Target | Search | Oracle | Final | Gap | Best heard by turn 5/10/14/20 |
|---|---|---|---|---|---|
| dark tonal (sound from pool) | current | 0.000 | 0.208 | 0.208 | 0.245 / 0.212 / 0.199 / 0.199 |
| dark tonal (sound from pool) | random | 0.000 | 0.225 | 0.225 | 0.269 / 0.240 / 0.213 / 0.213 |
| synthetic engine | current | 0.168 | 0.281 | 0.113 | 0.333 / 0.283 / 0.273 / 0.273 |
| synthetic engine | random | 0.168 | 0.272 | 0.105 | 0.317 / 0.287 / 0.268 / 0.268 |

Current and random do not differ beyond run-to-run noise. The pool cannot fully make the synthetic engine (oracle 0.168), and the search ends well short of what the pool allows for both targets.
