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

**Current app policy: open pool (`source-open-mutation-gp-v1`, `OpenDiscovery`).** The family-preset trial described after this section is kept in code (`SourceDiscovery`) as the baseline. It was replaced in the app because sessions stayed inside the six family presets and, in the [simulated-listener benchmark](source_search_benchmark.md), did no better than random proposals.

- **Pool.** Every layer uses the generic `blocks` voice. It combines a harmonic series (slope, even-harmonic gain, up to 48 partials, optional inharmonic stretch) with two optional resonant peaks and a low-pass, and adds optional half-order pulse lope, FM, a looping noise band, a tanh waveshaper and amplitude modulation. Root pitch is 0.4–2 times the reference (about 70–350 Hz). Recipes have 1–3 layers, all drawn at random. Families are not inputs, and the loudness normalization and signal checks are unchanged.
- **Same flow as before.** 20 listening steps (14 rated pairs, then 4 diverse finalists and a 6-pair Bradley-Terry final round), the 0.10 audio-distance gate, and an explicit final choice.
- **Opening (pairs 1–3).** Random open recipes.
- **Later pairs.** Each pair has two slots:
  - *Exploit:* a mutation or crossover of the three best-rated sounds, picked by a GP upper bound. The GP regresses the ratings on the foundation layer's parameters scaled to 0–1, with a fixed RBF kernel.
  - *Explore:* the random newcomer the GP is least certain about.
  - Mutation perturbs each parameter, sometimes switches a block on or off or adds or removes a peak or layer. This lets a session move away from its starting sounds while keeping coverage.
- **Status.** The policy is untested with listeners and has not been benchmarked: the open-pool render library is not built yet. The GP length and noise and the mutation scale are untuned defaults.

### Family-preset baseline (`SourceDiscovery`)

Personalize sound contains a separate, in-memory source-first discovery trial (`source-diversity-preference-model-bt-playoff-v1`), capped at 20 listening steps: 14 rated discovery pairs plus a 6-pair final round. The listener rates each auditioned sound separately from 1–7; there are no A/B winner, tie, or neither buttons. Its first three pairs cover six reference families. Later pairs use fresh broad recipes, balancing foundation-method exposure and one-, two-, and three-layer arrangements against prior shown candidates. Every other pair after the opening six candidates reuses a promising candidate, capped at three ratings per candidate, against a fresh source from another foundation family. Each fresh pair matches layer count and supporting-layer families so its main contrast is foundation family. Each layer independently draws body (0.20–0.95), harmonic character (0.10–0.90), ensemble depth (0.15–0.90), and applicable spectral tilt, formant, FM, modal-stretch or texture-focus parameters. Bowed, glass and airy layers also draw a pad tuning: the original (0.75, 1.5, 2 x root) or sub-octave (0.5, 1, 2 x root; recipe field `companionSub`). Sub-octave was rated comfortable and fuller in a one-listener check ([research](../research/sound_design_research.md#modulation-roughness-and-chord-tuning-check-source-discovery)). Source movement stays at 0.5; chorus/reverb and driving mapping remain fixed. Foundation register varies by 0.85–1.15 times the reference; auxiliary pitch ratios vary by 0.8–1.4. These ranges are sampled for broad exploration, not refined toward a current winner. The five-second source is shared across Steady, Rise and Evolving. This is a bounded procedural sound space, not an arbitrary-audio or infinite-quality generator.

The preference model (ridge regression on foundation family, layer mix and layer count, with an exploration bonus) orders proposals among the four least-exposed families, but the least-exposed family always takes one slot of the next pair, so one early low rating cannot starve a family. In simulated 9-pair sessions each family kept at least two sounds, with at most a two-sound spread; without this floor a family could drop to one sound or fewer. Repeat anchors are selected by rating score and remaining exposure capacity. After pair 14, up to four finalists are chosen by mean 1–7 rating shrunk toward neutral 4 (prior weight 2), preferring audio descriptors at least 0.10 apart when available. The final round is a round-robin of those finalists (6 A/B pairs, random order and side; Prefer A, Like both equally, or Prefer B). Finalists are then ordered by Bradley-Terry strength fitted to those choices; each finalist's shrunk rating enters as one weak virtual game against a neutral item, so ratings only break ties or cover skipped pairs. The listener can finish early and pick any finalist; the model never picks for them. The ordering is a small-sample estimate (6 choices, one listener), not a guarantee of preference. Rationale and sources: [Interactive search research](../research/interactive_search_research.md#final-ranking-by-pairwise-comparison). New candidates remain broad; there is no local mutation or parent recombination. The session ends automatically after the final round without preparing another pair. Fine tuning and learned candidate generation remain later work.

Source power-band descriptors also screen current-pair and recent-trial similarity independently of recipe distance. A provisional Hellinger-distance floor of 0.10 blocks spectrally near-identical candidates; skipped recipes/distances are exported separately from technical failures. This is a coarse engineering proxy, not proof of perceptual distinction. Bounded preparation can return a recoverable error rather than silently relaxing the diversity gate. Family/arrangement exposure balance and the 20-comparison endpoint are covered by automated tests; audible distinction and whether users prefer this broad-first flow still require a listener pilot.

Listen using live keyboard/controller driving; source discovery no longer exposes a simulated-playback selector. The offline qualification trace remains simulated. Rise is the initial style; style, live input mode, response, spatial setting and volume are logged with ratings. Listening is encouraged, but ratings can be submitted as soon as both scores are selected; audition timing is logged separately and does not gate voting.

No favourites or bookmarks: the final choice comes only from the ranked finalists, so a separate star list added clicks without feeding the model. Finishing does not automatically pick the model's top finalist. Export trial downloads JSON containing recipes, seeds, render/audio hashes, diagnostics, auditions, feedback, finalists and playoff history. Nothing writes participant records automatically. Closing or starting a new trial clears in-memory choices: export first. Cache audio is anonymous and disposable; every sound from the running trial is protected from eviction so finalists can replay.

Candidate labels join the methods used by the source roles; `+` means a synthesized mixture. A single method can still be a new, parameterized source. Labels distinguish seed references from variants using a short candidate ID, and Source recipe exposes the exact settings. Parameter variation can still produce similar-feeling timbres; recipe diversity is not a perceptual guarantee.

Preparation uses the raw source plus the Rise driving sweep as its sole qualification proxy. It does not rerun qualification when the listener selects Steady or Evolving; all three share the candidate source. Exported qualification_modes records this scope.

Source discovery opens through the dashboard’s Personalize sound button, using the same GS player and live telemetry. During an active trial the panel occupies the existing dashboard personalization slot; the ordinary dashboard and Sound Lab do not show a separate discovery section. The portal container stays mounted when the panel closes. Change style with the dashboard GS next-mode button; the trial has no separate Style selector. START preserves the trial candidate instead of launching the original template. Native theme switches are disabled while the source trial is active. The old Original granular template control section is no longer rendered. Its component remains mounted as the shared audio engine, with audio errors forwarded to the dashboard. Personalize sound uses the existing setup/comparison panel classes for source discovery rather than stacking the new experiment above the legacy form; finalists use a matching panel. The retained Sound Lab views are separate comparison/stress tools.

Opening rounds include fresh fallback recipes within the existing eight-render attempt budget. A withheld reference no longer leaves only the same two seeds to retry. Retry generates a fresh fallback pool; it does not lower technical or diversity thresholds. Preparation errors report ready count, similarity skips and rendering/check failures, including the latest renderer reason when present.

The vehicle auto-starts through an idempotent vehicleStart command once the app is ready, avoiding toggle-based restarts and respecting audio-error/debug states. Personalize sound and the dashboard no longer show vehicle start/stop buttons. The session controls use a compact card without a Session setup heading.
