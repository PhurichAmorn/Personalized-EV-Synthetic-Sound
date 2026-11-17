# Interactive algorithm and search behavior

## Purpose and design contract

The search should help a listener find a sound character they prefer, then allow an explicit final choice. It should expose coherent, audible contrasts, avoid treating a whole-sound choice as proof about one parameter, and let listeners stop early. A 15–20 comparison block is a prototype usability target, not a literature-proven optimum.

This document keeps the search goal beside a concise description of the implemented policy so agents can see both intended behavior and current limits. It is not a session-by-session log. Update it when feedback, search stages, candidate representation, or the research goal changes materially; routine UI or parameter edits alone do not require changes.

The primary Personalize sound interface now runs source discovery, described below. The earlier session-flow sections describe the retained native-profile search; its form is shown only for an already active legacy session. New native-profile sessions use the current probe mapping. Older saved sessions keep their stored algorithm and profile mapping when resumed. Sessions remain local under `experiment_data/interactive/`.

## Session flow

1. Choose **Personalize sound**, participant alias, mode (**Comfort**, **Sport**, or **Deep**), and one of three methods.
2. Compare Sound A and B while using the simulator. New sessions begin with four comparisons: the mode's two sound recipes; low versus high register; clean versus rich tone; then gentle versus pronounced state response.
3. Continue through a 20-comparison block, or finish early. Pair 10 is not a checkpoint. At pair 20, finish or continue into another block. **I'm satisfied** asks which of the current pair to save. **Pause search** preserves progress.
4. Use **Neither · new pair** when both sounds are disliked. Both candidates are rejected and replaced without consuming a comparison. **Like both equally** records no direction. It also fits when the sounds are hard to distinguish.

Evolutionary feedback is two independent 1–7 liking scores, one for each sound. GP preference + BO and Recipe window pilot use Prefer A, Like both equally, or Prefer B. The third method is a recipe-aware pairwise proposal policy, not a separate learned model. Each method keeps its feedback format and candidate-selection rule.

## Current comparison schedule

The initial candidates use six mode recipes and four linked groups: register, tone, response, regeneration. Sport ICE supports only register and response adjustments; unsupported fields are not exposed as effective changes.

| Comparisons | Purpose | What changes |
| --- | --- | --- |
| 1 | Compare mode character | The two recipes for the selected mode. |
| 2–4 | Probe dimensions | Register, tone, then response, one linked group per pair on the first recipe. |
| 5–14 | Tune | Repeat register, tone, response, regeneration; one 0.25 normalized step around current setting per pair. |
| 15–17 | Combine | Compare all learned group settings, then register+response, then tone+regeneration across the recipe families. |
| 18 | Branch challenge | Compare current branch with the other recipe using current group settings. |
| 19–20 | Small adjustment | Register, then tone, with a 0.12 normalized step. |

Bounds are recipe-specific and stored with each candidate. Normalized values map into physical profile fields; `0.25` is one quarter of that field's available normalized window, not a constant Hz change. The bounds are provisional listening-study limits, not universal comfort or hearing-safety thresholds. See [Sound design research](../research/sound_design_research.md).

The schedule is designed for comparison and exploration. A whole-recipe win does not show which single feature caused the preference. Combined candidates are packages, not isolated causal tests. The app randomizes A/B order and stores each candidate's recipe, controls, full profile, bounds, parents, probe reason, and listening gain.

## Session records and replay

`session.json` stores the participant alias, mode, selected vehicle snapshot, seed, mapping and DSP hashes, candidate profiles, comparisons, ratings/preferences, audition aggregates, favorite, and pause/satisfaction history. Driving summaries sample at 5 Hz and store aggregate duration/ranges, not a full input trace. Trace replay restores the exact candidate profile but plays it using current vehicle inputs; it does not recreate the original waveform or drive trace.

Favorite selection is explicit. The saved favorite is not automatically the highest evolutionary score or model prediction. Existing participant data is local and gitignored; docs and code changes should not rewrite it.

## UI behavior tied to search

- New/resumed sessions select Sound A. Both candidates must be heard before feedback; an Evolutionary returning candidate can keep its previously recorded score.
- The setup supports early satisfaction, pause/resume, and continuation in 20-comparison blocks.
- **TRACE** displays saved candidates and preferences. Replay uses the current simulator state. Session deletion removes that local session.
- **View → Telemetry** and **View → Sound signal** open separate windows. Sound analysis is an estimate of the rendered output, not calibrated cabin loudness.
- Keyboard arrows and controller D-pad navigate UI focus; Enter/A confirms and Escape/B backs out. Driving controls and sound selection remain separate.

## Versioning

New sessions use schema version 3, probe version 2, and algorithm IDs `three-lineage-probe-v1`, `gp-preference-probe-v1`, or `recipe-pairwise-v2`. Stored candidates include full profiles so future DSP changes do not silently change old audition sounds. Legacy mappings remain supported only where the loader recognizes their version; schema 1–2 numeric-GP sessions are not loaded.

For research findings and the proposed character-first redesign, see [Interactive preference research](../research/interactive_search_research.md). That redesign is a proposal; current app behavior is the schedule above.

## Source discovery trial

### Sound-map search (phase 1, `source-map-regions-1`, `RegionMapDiscovery`): selectable per session

Goal: test whether the same A/B session works over **generated** sounds instead of hand-made families, so the final sound is not limited to a
fixed preset set. Personalize sound now has a search selector: *Sound families (baseline)* = `TuningDiscovery` (`source-tuning-v1`, the default; hand-made families, variants and tuning moves, described in `experiment/source_search.py`), *Sound map (generated)* = this.

- **Pool.** `experiment/sound_map_pool.json`, frozen from `tools/sound_map` (see its README): an open archive (no grid, no size limit) of
  sounds made with the plain synth or the generic `blocks` voice (FM, noise band, waveshaper, amplitude modulation, inharmonic partials),
  each kept only if it passed the rule-based guardrail (MoSQITo sharpness, roughness, pulsing, plus partial crowding), the full 22 s Rising
  drive check, and sounds different from every other kept sound. Built live in the app (`levels.ts` kind `map`, stems from `mapVoice.ts`).
  v1 (2026-11-16) was 90 plain-synth sounds in a pitch x sharpness x texture grid; its one session ended on a near-copy of the listener's
  own Cinematic pad (octave-band distance 0.13), which led to v2. v2 (233 sounds, 2026-11-17) played every sound dry (no chorus, vibrato or
  body EQ) with the app's small too-similar steps; the listener heard most sounds as alike and plain, which led to v3: chorus, engine vibrato
  (up to 20 cents) and body EQ are searched per sound, and every "distinct" step is larger (chorus and vibrato count as traits). In the
  v3 pool 61% of sounds had over 10 cents of vibrato and a session sounded ghostly (2026-11-17), so v4 (118 sounds) caps vibrato at 8 cents
  and starts half of new sounds dry (vibrato median 3.1 cents).
- **Session, regions (current, 2026-11-17).** Broad then narrow. The pool is split into 6 regions (k-means on the 9 traits). Pairs 1-3: each
  region's most typical sound, the same opening for every listener. Pairs 4-10: two regions per pair, picked by a Thompson sample of each
  region's win rate, each played by the model's best guess in that region. Pairs 11-19: winner stays as below, with challengers from the
  best region (70%) or the runner-up; two Neither answers open the next region. Pair 20 and shortlist as below. Reason: the random start and
  rim-first opening made sessions feel random and could start in an odd corner; the listener asked for about 10 pairs of broad clues first.
- **Session, v5/v6 (kept in code as `SoundMapDiscovery`).** v6 adds pair 1: one sound (nearest the pool centre) Rising vs Evolving; the choice sets the motion for the rest (Both good / Neither keep Rising); Evolving uses only sounds that also pass in Evolving (`drive.py pool`), the whole pool until that check is run. The regions session opens with the same pair 1 (its region pairs then start one pair later). v5: Rising only. 20 direct choices with the tuning search's answers (Prefer A / B, Both good, Neither). Pairs 1-3: six sounds spread
  around the middle ring of the pool (v4 and before: as far apart as the whole pool allows, from a random first sound). Pairs 4-5: playoff of the opening winners.
  Pairs 6-19: the champion against the unheard pool sound with the highest Thompson-sampled utility, never a near-copy of the champion (backend
  check on spectrum, pitch, inharmonicity, roughness and pulsing; the app's spectrum-and-pitch check is used for the tuning search only). Winner stays: a challenger that wins becomes champion and defends next. Pair 20 plays the shortlist's #1
  against #2 as they stand, so the last answer decides which of the top two leads. The shortlist is in model order among sounds heard at
  least twice (v4; v3 put the champion first after a champion-vs-runner-up pair 20, and in simulation one noisy last game often put a
  weaker sound there).
- **Model.** Bayesian Bradley-Terry (as `TuningDiscovery`) over 9 traits that work for both voices (pitch, sharpness, roughness, pulsing,
  inharmonicity, spectral centre, voice, chorus, vibrato), each as z and z^2 so a middle value can be preferred.
- **Simulated listeners (2026-11-16, `tools/benchmark_sound_map.py`, 300 per condition, hidden ideal-point taste, noisy answers).** The shortlist's
  top sound was in the listener's top 5% of the pool in about 31% of sessions, the same as random challengers (30%, +-5%). Linear-only features,
  posterior-mean or full-spread sampling, radial-basis features and a nearness bonus were all within that noise. Interpretation (project): with
  about 90 sounds and 20 pairs, the best-vs-challenger structure and the shortlist do the work; the model should only matter once the pool is
  large, i.e. with phase 2. So phase 1 tests the pool and the session with listeners, not the model.
  On the v2 pool (233 sounds, 2026-11-17): pick in the listener's top 5% in 22% of sessions vs 25% for random challengers (+-5%), top 10% in
  40% vs 39%. Still a tie: 20 pairs hear under a tenth of the pool, and the pair policy is the open question below.
  On the v3 pool (99 sounds, 2026-11-17): 26% vs 28% (+-5%), top 10% 42% vs 45%; a tie.
  On the v4 pool (118 sounds, 400 per condition, 2026-11-17): regions 26% top 5% (+-4%), top 10% 44%, median rank 12%; v5 23%, 37%, 15%;
  random challengers 18%, 35%, 15%. First version ahead of random on top 10%; still to be checked by listeners.
- **Not built (phase 2).** Growing new sounds around the listener's favourites between pairs (mutation + the same guardrail).
- **Open question: pair design (deferred, 2026-11-17).** Champion vs challenger ("winner stays", added after the first session) is one
  choice, kept for now. The alternative to discuss: pairs chosen to learn the listener's taste, which need not include the favourite (e.g. two
  sound types against each other to see which way the listener leans), as in preferential BO acquisitions (EUBO, information gain). In
  simulation every pair policy tied with random on the 90-sound pool, so compare them once the sound space is wider.
- **Status.** Untested with listeners. The guardrail limits come from one listener's labels.

### Level search (previous default: `source-levels-v1`, `LevelDiscovery`)

Goal unchanged: help a listener with no sound in mind find one they enjoy. A sound is now built from settings instead of a style:
a simplified base sound (Type: Strings / Choir / Glass, Brightness and Register, 3 settings each) plus six transformation
effects applied after the granular player (chorus, reverb, vibrato, pedal-following tone, body resonance, tremolo; 2-3 settings each).
Exact values and everything held fixed are in `desktop/src/levels.ts` and shown in Sound Lab ("Search setup").

Why: Sound Lab listening tests (2026-11-14, one listener) found that tone colour works best in the base sound (it keeps its
character as pitch rises), while space, motion and pedal response only work after the player. A blind test found the
simplified Strings, Choir and Glass "very similar" to the original styles, so the seven styles were replaced.

Session: 20 direct choices. Pairs 1-2 compare the three types (neutral effects); pairs 3-6 change one base setting; later pairs
change one setting, effects first. Even pairs put the best sound against a one-setting change of it; odd pairs pair changes of
the best sound and of the best sound of another type. One Bradley-Terry model over one-hot settings (ridge 1) learns a value per
setting from every choice and picks the next changes (learned gain, a bonus for settings not heard yet, momentum). Shortlist and
settle rule as in StyleDiscovery. Sounds are built and played live in the app through the Sound Lab engine (`labEngine.ts`):
no offline render, so no automatic signal check per sound; every change is one whole setting, so the audio near-copy gate is
not used. Limits: about 24 setting values for 20 choices, so effects that appear together early (the neutral effects) are
partly confounded; effect amounts are not yet confirmed by ear.

### Base-style exploration (baseline, previous default: `source-style-explore-v1`, `StyleDiscovery`)

Agreed 2026-11-11; it replaces the open-pool policy below in the app, and that policy stays in code as a baseline.

**Build status.** Built in the app:
- the opening, direct choices on every pair, exploration by tuned versions and parent checks, and the trace;
- Bradley-Terry ranking of sounds and styles;
- direction learning;
- the shortlist ending.

Tuning moves one generic group by half its range: deep lowers pitch by 1.26× per step (about 4 semitones) and raises body; bright moves harmonic character; full moves ensemble; moving moves movement. Electric and Jet ignore the four source controls, so they get pitch moves only.

A pair never shows two tunings of the same sound. If every tuning of the best sound is a near-copy, the pair falls back to tunings of the next-ranked sounds; up to 20 renders are tried per pair.

Not yet built: per-style sound groups (stage 2) and blends (stage 3).

**Preference model and direction learning.** A single Bradley-Terry model over what sounds are made of: style (one-hot) plus net group steps along the tuning chain ("more deep" twice = +2), fitted by ridge logistic regression (strength 1) on every choice. It ranks sounds, chooses which sound to build on, and gives each move its learned effect. A new deeper Choir therefore inherits the evidence about Choir and about "deeper" instead of starting from zero.

This replaced per-sound Bradley-Terry. In the 2026-11-11 15:52 session that version kept building on base Cluster, because winning parent checks made Cluster look strong, while Choir won the cross-style pairs (6 of the last 8). Replaying that session's choices, the feature model leaves Cluster at pair 8 and builds on deeper Choir from pair 13.

The next tuning of a sound prefers, in order: the move that just beat its parent (momentum), then the higher learned effect, then a 0.3 bonus for moves not yet tried on that sound. A sound that beat its own tunings in its last 2 parent checks is left alone, and the search builds on the next-ranked sound.

Known limit: moves that always come together in a chain share credit (in the replay, the inaudible "moving" got credit next to "deep"); parent checks, which change one thing at a time, reduce this.

**Ending.** All 20 steps are discovery pairs; there is no final round. In the 2026-11-11 session it only confirmed the order the discovery ranking already had. The listener chooses from a shortlist: up to 5 audibly distinct sounds with at least 2 choices each, top 3 shown, #4–5 behind "Show more".

**Goal.** Help a listener who has no sound in mind explore EV sounds and end with one they enjoy and would choose again. The search is not trying to find a hidden target. People without a clear target construct their preference while comparing options (Slovic 1995; Payne, Bettman & Johnson 1992), so the tool offers good, clearly different options and follows the listener's lean. Random open-pool sounds were often unpleasant (in one session 7 of 11 new random sounds were rated 1), which wastes turns and gives a poor first impression.

**Base styles (7).** Strings, Pure tone, Choir, Glass, Cluster, Electric (after the IONIQ 5 N Evolution mode) and Jet (after the Supersonic mode); names and measurements are in [sound design research](../research/sound_design_research.md#base-styles-names-and-measured-character-2026-11-11). Engine and Cello are parked; Metal is merged into Cluster.

**Feedback.** Every pair is a direct choice: Prefer A / Like both equally / Prefer B. Pairwise choices are steadier than separate 1–7 scores (one session rated the same sound 6 and later 3). The 1–7 rating code is kept but not shown.

**Session (20 steps, as now).**

| Pairs | Content |
| --- | --- |
| 1–4 | Opening: all 7 styles once, paired for contrast (for example Strings vs Choir, Cluster vs Jet, Pure tone vs Electric); pair 4 puts the 7th style against the style preferred so far, which also re-checks the leader. |
| 5–20 | Exploration around the listener's lean (see below). |

**Exploration pair types (pairs 5–14).**
- *Tuned version:* one sound group of a preferred sound (deep, bright, rough, metallic, airy, moving) moved by a clearly audible step; it must pass the 0.10 audio-distance gate against its parent. The group-to-parameter map is defined per style.
- *Parent check:* a tuned version next to its own parent, so the comparison directly shows whether the change helped.
- *Blend:* the two most preferred styles layered (one as the main layer, the other mixed in at 30%, 50% or 70%), giving sounds no single style has. Layering uses the existing multi-layer recipe; averaging parameters across different style types is not meaningful.
- *Unheard or lower-ranked style:* occasionally, so four opening choices do not lock the direction.

**Learning.** A Bradley-Terry model over what each sound is made of (style, sound-group moves, blend share) fitted to all choices, with group trends (which directions the listener likes) carried across styles. It replaces the rating-based GP. A preference GP (Chu & Ghahramani 2005) is the heavier alternative if needed.

**Trace.** Every sound records its origin (base style, tuned version with the changed parameters, or blend with its share), and each pair records the choice. The export holds session metrics.

**Measuring success.** With listeners: satisfaction with the final sound; whether they choose it again later (liking can change with repeated exposure; Münder et al. 2025); whether different people end in different places; time taken. Benchmark (later): simulated listeners with different hidden tastes over the styles, not one target sound.

**Current app policy: open pool (`source-open-groups-gp-v4`, `OpenDiscovery`).** The family-preset trial described after this section is kept in code (`SourceDiscovery`) as the baseline. It was replaced in the app because sessions stayed inside the six family presets and, in the [simulated-listener benchmark](source_search_benchmark.md), did no better than random proposals.

- **Pool.** Every layer uses the generic `blocks` voice. It combines a harmonic series (slope, even-harmonic gain, up to 48 partials, optional inharmonic stretch) with two optional resonant peaks and a low-pass, and adds optional half-order pulse lope, FM, a looping noise band, a tanh waveshaper and amplitude modulation. Root pitch is 0.4–2 times the reference (about 70–350 Hz). Recipes have 1–3 layers, all drawn at random. Families are not inputs, and the loudness normalization and signal checks are unchanged.
- **Same flow as before.** 20 listening steps (14 rated pairs, then 4 diverse finalists and a 6-pair Bradley-Terry final round), the 0.10 audio-distance gate, and an explicit final choice.
- **Opening (pairs 1–3).** Random open recipes.
- **Later pairs.** Each pair has two slots:
  - *Exploit:* a tuned version of one of the three best-rated sounds. Tuning moves exactly one **sound group** by a fixed, audible step (30% of each parameter's range), more or less, and leaves everything else unchanged. A GP upper bound picks the parent, group and direction, so the choice comes from the listener's ratings, not chance. The GP regresses ratings on the foundation layer's parameters (plus ensemble and movement) scaled to 0–1, with a fixed RBF kernel.
  - *Explore:* the random newcomer the GP is least certain about. Newcomers draw every parameter and the layer count at random, so the whole open pool stays reachable.
  - **Sound groups** (named after listener timbre dimensions such as depth, brightness and roughness): deep (pitch, low peak, even harmonics), bright (cutoff, harmonic slope, upper peak), resonant (peak strength and width), rough (drive, AM depth and rate), metallic (FM amount, index, ratio, inharmonicity), airy (noise amount, width, centre) and moving (lope, ensemble, movement). Every parameter belongs to a group, so grouping limits how one step moves, not which sounds exist. "Less" of a feature that is off is skipped as inaudible; "more" can switch a feature on.
  - **Parent check (pairs 5, 8, 11 and 14).** The current best sound returns next to one tuning of itself, so the tuning is judged directly against its parent and a lucky first rating is re-checked. If a newcomer outscores it, the newcomer becomes the parent. Skipped once the best sound has 3 ratings or is settled. The listener answers with a direct choice (Prefer A / Like both equally / Prefer B), because the same sound was rated 6 and then 3 in one session and pairwise choices are steadier than separate scores. The parent keeps its ratings; the tuned sound gets an inferred rating of the parent's mean +1, 0 or −1 (`rating_source: choice`, `inferred_rating` in the trace). Legacy option: `PARENT_CHECK_MODE='rating'` keeps the 1–7 sliders on these pairs (`rating_source: rating-1-7`).
  - **Shrinking step.** Each parent's step starts at 30% and halves after a tuning scores below it, at most once per pair, down to 20%. A loss at 20% marks the parent as settled. Rough and moving always use 30%. Idea from the 1/5 success rule of evolution strategies (Rechenberg): big steps while far from a good sound, smaller when close. Steps of 10–15% sounded like copies.
  - **Group trends.** For each group and direction (for example `deep+`, `rough-`) the search averages how much a tuned sound's rating changed against its parent, shrunk toward 0 with prior weight 2, and adds it to the GP score of new tunings. A lesson such as "deeper helps" then carries over to other parents, which the distance-based GP alone cannot do. Same idea as per-band weights from rating changes in EQ preference learning (Sabin & Pardo 2008). Exported as `preference_model.group_trends`.
  - Every tuned sound must also pass the 0.10 audio-distance gate against its own parent, except rough and moving tunings: the spectrum descriptor cannot hear roughness or movement, so those keep the full step instead.
- **Trace.** Every candidate stores `origin`: `new` (random) or `tuned`, with parent, parent score, group, direction, step and each changed parameter as `[old, new]`. Each history row lists `origin_by_candidate` as a one-line summary (a returning parent is labelled as such). `session_metrics` reports tuned-vs-parent wins, ties and losses, the best rating and the first pair that reached it, and each parent's current step. Origins are in the export only; listeners are not told what changed.
- **Status.** The policy is untested with listeners and has not been benchmarked: the open-pool render library is not built yet. The GP length and noise and the group step are untuned defaults. One simulated session with real renders ran end to end.

### Family-preset baseline (`SourceDiscovery`)

Personalize sound contains a separate, in-memory source-first discovery trial (`source-diversity-preference-model-bt-playoff-v1`), capped at 20 listening steps: 14 rated discovery pairs plus a 6-pair final round. The listener rates each auditioned sound separately from 1–7; there are no A/B winner, tie, or neither buttons. Its first three pairs cover six reference families. Later pairs use fresh broad recipes, balancing foundation-method exposure and one-, two-, and three-layer arrangements against prior shown candidates. Every other pair after the opening six candidates reuses a promising candidate, capped at three ratings per candidate, against a fresh source from another foundation family. Each fresh pair matches layer count and supporting-layer families so its main contrast is foundation family. Each layer independently draws body (0.20–0.95), harmonic character (0.10–0.90), ensemble depth (0.15–0.90), and applicable spectral tilt, formant, FM, modal-stretch or texture-focus parameters. Bowed, glass and airy layers also draw a pad tuning: the original (0.75, 1.5, 2 x root) or sub-octave (0.5, 1, 2 x root; recipe field `companionSub`). Sub-octave was rated comfortable and fuller in a one-listener check ([research](../research/sound_design_research.md#modulation-roughness-and-chord-tuning-check-source-discovery)). Source movement stays at 0.5; chorus/reverb and driving mapping remain fixed. Foundation register varies by 0.85–1.15 times the reference; auxiliary pitch ratios vary by 0.8–1.4. These ranges are sampled for broad exploration, not refined toward a current winner. The five-second source is shared across Steady, Rise and Evolving. This is a bounded procedural sound space, not an arbitrary-audio or infinite-quality generator.

The preference model (ridge regression on foundation family, layer mix and layer count, with an exploration bonus) orders proposals among the four least-exposed families, but the least-exposed family always takes one slot of the next pair, so one early low rating cannot starve a family. In simulated 9-pair sessions each family kept at least two sounds, with at most a two-sound spread; without this floor a family could drop to one sound or fewer. Repeat anchors are selected by rating score and remaining exposure capacity. After pair 14, up to four finalists are chosen by mean 1–7 rating shrunk toward neutral 4 (prior weight 2), preferring audio descriptors at least 0.10 apart when available. The final round is a round-robin of those finalists (6 A/B pairs, random order and side; Prefer A, Like both equally, or Prefer B). Finalists are then ordered by Bradley-Terry strength fitted to those choices; each finalist's shrunk rating enters as one weak virtual game against a neutral item, so ratings only break ties or cover skipped pairs. The listener can finish early and pick any finalist; the model never picks for them. The ordering is a small-sample estimate (6 choices, one listener), not a guarantee of preference. Rationale and sources: [Interactive search research](../research/interactive_search_research.md#final-ranking-by-pairwise-comparison). New candidates remain broad; there is no local mutation or parent recombination. The session ends automatically after the final round without preparing another pair. Fine tuning and learned candidate generation remain later work.

Source power-band descriptors also screen current-pair and recent-trial similarity independently of recipe distance. A provisional Hellinger-distance floor of 0.10 blocks spectrally near-identical candidates; skipped recipes/distances are exported separately from technical failures. This is a coarse engineering proxy, not proof of perceptual distinction. Bounded preparation can return a recoverable error rather than silently relaxing the diversity gate. Family/arrangement exposure balance and the 20-comparison endpoint are covered by automated tests; audible distinction and whether users prefer this broad-first flow still require a listener pilot.

Listen using live keyboard/controller driving; source discovery no longer exposes a simulated-playback selector. The offline qualification trace remains simulated. Rise is the initial style; style, live input mode, response, spatial setting and volume are logged with ratings. Listening is encouraged, but ratings can be submitted as soon as both scores are selected; audition timing is logged separately and does not gate voting.

No favourites or bookmarks: the final choice comes only from the ranked finalists, so a separate star list added clicks without feeding the model. Finishing does not automatically pick the model's top finalist. Export trial downloads JSON containing recipes, seeds, render/audio hashes, diagnostics, auditions, feedback, finalists and playoff history. Nothing writes participant records automatically. Closing or starting a new trial clears in-memory choices: export first. Cache audio is anonymous and disposable; every sound from the running trial is protected from eviction so finalists can replay.

Candidate labels join the methods used by the source roles; `+` means a synthesized mixture. A single method can still be a new, parameterized source. Labels distinguish seed references from variants using a short candidate ID, and Source recipe exposes the exact settings. Parameter variation can still produce similar-feeling timbres; recipe diversity is not a perceptual guarantee.

Preparation uses the raw source plus the Rise driving sweep as its sole qualification proxy. It does not rerun qualification when the listener selects Steady or Evolving; all three share the candidate source. Exported qualification_modes records this scope.

Source discovery opens through the dashboard’s Personalize sound button, using the same GS player and live telemetry. During an active trial the panel occupies the existing dashboard personalization slot; the ordinary dashboard and Sound Lab do not show a separate discovery section. The portal container stays mounted when the panel closes. Change style with the dashboard GS next-mode button; the trial has no separate Style selector. START preserves the trial candidate instead of launching the original template. Native theme switches are disabled while the source trial is active. The old Original granular template control section is no longer rendered. Its component remains mounted as the shared audio engine, with audio errors forwarded to the dashboard. Personalize sound uses the existing setup/comparison panel classes for source discovery rather than stacking the new experiment above the legacy form; finalists use a matching panel. Sound Lab shows only the base-style picker: each style replays the same simulated drive. The earlier baseline, Audiobox and roughness listening panels were removed on 2026-11-10 (in git history).

Opening rounds include fresh fallback recipes within the existing eight-render attempt budget. A withheld reference no longer leaves only the same two seeds to retry. Retry generates a fresh fallback pool; it does not lower technical or diversity thresholds. Preparation errors report ready count, similarity skips and rendering/check failures, including the latest renderer reason when present.

The vehicle auto-starts through an idempotent vehicleStart command once the app is ready, avoiding toggle-based restarts and respecting audio-error/debug states. Personalize sound and the dashboard no longer show vehicle start/stop buttons. The session controls use a compact card without a Session setup heading.
