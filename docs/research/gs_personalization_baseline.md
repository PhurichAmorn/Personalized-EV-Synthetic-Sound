# GS personalization: perceptual controls and baseline proposal

Research date: 2026-11-05. The controlled baseline comparison is implemented in Sound Lab; model/group personalization remains a proposal. Live driving audio is unchanged. Recorded cello and a measured Great Hall response are integrated into offline comparison clips only; human listening qualification is outstanding.

## Recommendation

Qualify a source and renderer before personalizing them. Then search a few perceptually meaningful controls with source-specific bounds. Keep fault prevention, scheduling and loudness calibration outside preference search. Treat source character, granular texture, driving expression and room acoustics as distinct groups, with interactions tested deliberately.

The existing research notes already propose linked register/tone/response/regen groups. They apply to native recipes. Current GS source-generation parameters, worklet grain settings and reverb controls are not connected to that native search; a new candidate representation and renderer adapter would be required. Old participant sessions must retain their renderer/version and original data.

## Research findings and limits

1. **Dobrowohl, Milne and Dean (2019), Timbre Preferences in the Context of Mixing Music.** Twenty-eight listeners manipulated four attributes: low-pass filtering, oscillator blend, distortion and inharmonicity. Results support consistent but individual timbre preferences and listeners' ability to adjust sounds toward their taste. This was music mixing, not EV cabin sound. It supports a small set of audible dimensions, not those four exact controls or universal preferred ranges. [Publisher](https://www.mdpi.com/2076-3417/9/8/1695).
2. **Cartwright and Pardo (2011), Interactive Learning for Creativity Support in Music Production.** Discusses the large synthesizer parameter space, listener-dependent timbre similarity and learning from successive examples/feedback. This is a conceptual approach, not validation of a deployed EV optimizer. [Author-hosted paper](https://interactiveaudiolab.github.io/assets/papers/CartwrightPardo_CC2011_SAC.pdf).
3. **Gonzalez et al. (2017), Preferential Bayesian Optimization.** Uses pairwise comparisons to infer latent preferences and select later comparisons. Modeling candidate correlations matters. Supports a preference surrogate over our candidate representation; it does not decide which sound dimensions are appropriate. [ICML/PMLR](https://proceedings.mlr.press/v70/gonzalez17a.html).
4. **Han, Lostanlen and Lagrange (2024), Learning to Solve Inverse Problems for Perceptual Sound Matching.** Relates synthesis-parameter changes to auditory-feature changes using local linearization. Shows why raw parameter error and perceptual sound error differ. This is target matching, not preference learning. Project implication: calibrate control sensitivity using rendered audio, then verify with listeners. [Paper](https://arxiv.org/abs/2311.14213).
5. **Masuda and Saito (2023), Quality-diversity for Synthesizer Sound Matching.** Finds diverse sound matches spread across interpretable spectral features. Supports keeping multiple coherent character families rather than prematurely collapsing to one. Sound matching is a different objective from liking. [Publisher](https://www.jstage.jst.go.jp/article/ipsjjip/31/0/31_220/_article).
6. **Truax, granular synthesis overview.** Explains that grain envelopes affect clicks/spectrum and describes pitch-synchronous processing. Classic examples use short grains; that is not a universal preset for sustained EV sound. Our 160 ms grains are a long-grain overlap-add choice. [Author's overview](https://www.sfu.ca/~truax/gran.html).

## Parameter groups proposed for GS

These labels and mappings are project recommendations, not established universal perceptual axes. Render and listen to low/middle/high settings per source before adoption.

| Group | Listener-facing change | Candidate controls | Initial treatment |
| --- | --- | --- | --- |
| Source family | Synthetic/string/other material | Source identity and generator preset | Small curated categorical choice; not an arbitrary numeric interpolation |
| Register | Lower/higher, restrained/broader climb | Source tuning and mapped pitch endpoints | One bounded macro first |
| Tone | Darker/brighter | Harmonic tilt, low-pass cutoff and upper-layer amount | One linked macro; hold overall loudness constant |
| Body | Leaner/fuller ensemble | Fundamental/lower-voice blend and harmonic structure | Add after distinguishing it from register/brightness |
| Granular texture | Coherent/more textured | Grain duration with linked hop/overlap, limited scan variation | Qualify first; then optional bounded macro |
| Driving expression | Gentle/assertive | Input-response shape, onset, brightness response | One macro using fixed driving traces |
| Space | Intimate/hall-like | Wet level, early/late energy, damping; bounded decay | One linked macro initially; separate width/decay later if needed |

A practical first continuous search would use register, tone, expression and space, with source family chosen in a small discovery stage. Add body/texture only if listening demonstrates useful independent differences. Six labels do not imply six dimensions must be optimized simultaneously.

### Granular baseline

Retain the current 160 ms Hann grain / 40 ms hop / four-way overlap as an engineering reference. Keep random pitch, random scatter and random panning at zero. Keep the audio-thread renderer and waveform-alignment rules fixed. These are prototype choices, not a published standard or a qualified optimum.

Before exposing texture to personalization, compare 100, 160 and 240 ms with hop tied to duration/4, using the same source, pitch trajectory and level. Test neutral pitch and the actual transposition range. Reject clicks, missing grains and unstable level rather than treating these as aesthetic preferences. Qualify the current same-source high-speed hold separately from ordinary loop playback.

The worklet currently fixes grain duration and overlap in code. The proposed duration variants and texture macro do not yet exist in the app.

## What 'parameter-aware' means

Each candidate should contain source identity/hash, physical parameter values, macro values, source-specific bounds, renderer/mapping version, random seed where relevant, driving trace and listening gain. Render descriptors can include spectral centroid/tilt, attack time, modulation energy and stereo/reverb measures. They describe sound; they are not a pleasantness score.

First measure local sensitivity: vary one macro around the baseline, render the same drive, compare acoustic changes, then check whether people can hear and describe the difference. Normalize search steps to meaningful audible changes rather than equal fractions of unrelated raw ranges. Do not infer perceptual independence from different variable names.

Then train a preference model on the listener's comparisons. A nonlinear GP preference model with regularized, dimension-specific scales is a defensible continuation of the existing PBO direction. It can learn that a listener likes moderate rather than maximal brightness and that room/tone interact. With a small feedback budget, inferred relevance remains uncertain.

Keep three kinds of 'weight' separate:

- **DSP/mapping coefficients:** engineering choices about how inputs and layers combine.
- **Sensitivity/scaling:** how large a parameter change must be to create a comparable audible change.
- **Preference/importance:** learned from a listener's comparisons, with uncertainty.

A GP length scale is not a reliable causal importance percentage, especially with correlated controls or few comparisons. Avoid hand-writing a universal warmth/brightness/space preference score. Start with balanced exploration of qualified groups; adapt proposals using evidence. Retain Equal/Neither and revisit alternative source families when uncertain.

## Concrete source candidates

### Recorded cello comparison source

[VSCO 2 Community Edition](https://versilian-studios.com/vsco-community/) supplies original orchestral WAVs under CC0. A sustained cello-section sample is a reasonable reference candidate for the requested warm ensemble character. It is a musical reference, not an EV standard or a demonstrated personal favorite.

Verified file: [susvib_C3_v1_1.wav](https://github.com/sgossner/VSCO-2-CE/blob/master/Strings/Cello%20Section/susvib/susvib_C3_v1_1.wav).

Downloaded copy: `artifacts/gs_baseline_research/vsco_cello_C3_v1.wav`. Metadata/provenance: `source_candidate.json`. Measurements: 44.1 kHz stereo, 9.237 seconds, peak approximately 0.093 full scale, RMS approximately -34.2 dBFS. Dominant low-band spectral peak is approximately 261 Hz; the filename's octave label should not be assumed to follow a particular pitch convention.

For a lower reference near our stationary source's 175 Hz root, a roughly seven-semitone downward preparation is a candidate, to be auditioned. Do not mistake the sample's quiet recording gain for a preferred or safe playback level. Pick a stable region, verify mono compatibility, prepare a five-second loop and retain the original recording as a reference. The natural ensemble/vibrato may itself interact with granulation and must be checked.

Alternative: [Philharmonia sound samples](https://philharmonia.co.uk/resources/sound-samples/) offers orchestral recordings, allowing use in commercial works but restricting redistribution as unchanged samples/sampler instruments. Its current published terms should be retained with any selected asset. No Philharmonia sample was downloaded here.

### Hall depth

[Queen Mary/C4DM measured room responses](https://isophonics.net/content/room-impulse-response-data-set) include the Great Hall, Octagon and classroom, measured with omnidirectional and B-format microphones. Published license: Creative Commons Attribution-Noncommercial-Share-Alike, with C4DM attribution and the requested dataset citation. This is a concrete research hall candidate; it is not an unrestricted production asset. B-format recordings need appropriate decoding, not direct assignment to stereo channels.

OpenAIR is another relevant University of York collection, but its current room/download pages timed out in this investigation. A specific OpenAIR hall file and its current license were not verified, so do not treat it as a cleared asset.

Use a dry source plus separate room processing. Preserve the direct sound so acceleration cues stay readable. For an initial artistic trial, approximately two seconds of decay, 20–35 ms predelay and a modest wet level are starting hypotheses, not published EV recommendations. A measured hall response's actual decay/colour should be inspected rather than assumed from its name. Stereo room depth is not equivalent to full surrounding sound; that requires a suitable binaural/spatial renderer and playback setup.

## Proposed baseline qualification

1. Compare the current procedural source with the recorded cello candidate at matched register and listening level, without driving or hall effects.
2. For the promising source, compare ordinary sample playback and neutral granular playback; then apply the same driving/transposition trace to both. This isolates processing coloration from source preference.
3. Add a fixed hall response; compare dry/wet at matched total listening level. Then qualify loop boundaries, sustained high-speed operation, re-acceleration and regen on identical traces.
4. Freeze a versioned baseline before source/renderer personalization. Start with broad macro contrasts, later combine groups to learn interactions.
5. Keep source, mapping and room judgments separately logged. Match the feedback task if claiming algorithm superiority; current native Evolutionary ratings and GP pairwise feedback are different interaction packages.

No source or reverb can be called universally safe or preferred from a file alone. Qualification here covers technical integrity, comfortable pilot listening and calibrated playback; physical sound level depends on the actual output system. No listening or physical-SPL qualification was performed in this investigation.

## Implemented comparison workflow

Open Sound Lab and find **Baseline comparison**. Vehicle input is unnecessary: the clips include a neutral tone or the same synthetic 0–120 km/h acceleration/hold/lift-off/stop trace. Start with Source (ordinary, dry, neutral); compare current synthesized strings with the recorded cello. Renderer enables ordinary/granular choices and defaults to the shared drive trace. Hall enables dry/measured-room comparison. Choices pause and reset the clip; press Play again. The live GS renderer stops when the comparison begins. Original native audio remains muted during the comparison workspace, including pauses between clips; restarting GS or leaving the workspace releases that ownership.

The reference recording is prepared as a five-second stereo loop at roughly the procedural source's register (-7 semitones from the original). Original stereo channels are retained; the earlier mono preparation measured -0.98 dB loss. The measured room uses matched Great Hall x06y06 W/X/Y files; raw 96 kHz data is resampled to 48 kHz and projected to virtual horizontal ±45-degree cardioids assuming legacy FuMa scaling, with a final 20 ms taper. It is stereo projection, not binaural surround. The actual room window is two seconds; no claim about a certified decay time is made. Original hall license retrieved inside the archives is CC BY-NC-SA **4.0**. Attribution and transformation details ship with the comparison clips.

Sixteen PCM16 stereo clips are normalized using a BS.1770 mono/stereo gated implementation to a common -24 LUFS technical reference, with a 4x polyphase peak estimate below 0.7 full scale. The loudness implementation is not a certified meter and does not establish safe physical SPL. Neutral granular transparency is checked numerically after startup. The drive renders use the actual public grain core, app pitch/level map and envelope targets, over fixed recorded inputs; they are a controlled single-source comparison, not a byte-identical reproduction of the multi-stem dashboard graph. Per-stem timbre changes and evolving scan hold are deliberately outside this first comparison.

**Export selection** downloads candidate choices, clip/source hashes, renderer/mapping hashes, playback volume and reference level. It does not automatically adopt the sound as the driving preset or enroll it in preference search. The listener must identify the preferred baseline first.

Rebuild: run `tools/fetch_baseline_hall.py`, then `tools/prepare_gs_baseline.py`, `node tools/render_gs_baseline.mjs`, and `tools/prepare_gs_baseline.py finalize` using the project Python environment. The original VSCO recording/provenance must already be present under `artifacts/gs_baseline_research/`. Output is `desktop/public/audio/baseline-v1/`, with manifest and attribution.

## Prototype feedback and revised comparison

Prototype feedback accepted both source families, found little renderer difference, and found the hall contrast weak. This is not a participant study result or evidence that those dimensions have zero preference relevance. Both source families remain available. Neutral ordinary/granular similarity is an intended transparency result; the renderer was not made artificially rough to manufacture a difference.

The procedural source now uses seeded irregular bow motion: a bounded slow phase drift, softly varying vibrato and less than 1.8% bow-pressure variation per voice. Independent seeds provide ensemble variation while preserving a five-second periodic boundary and repeatable candidate playback. No pitch scatter or random grain scheduling was introduced. Note trajectories, loop overlap and driving maps are unchanged.

The original hall response placed about 81% of its energy in the first 80 ms, and the original 75/25 dry/wet comparison produced a weak room contrast. The hall preparation now suppresses the strongest early/direct arrival using a smooth gate, retains the later reflection field and uses a 60/40 direct/reflection mix before total loudness matching. The procedural neutral tail increased from about -46.6 to -36.8 dBFS in the first second after excitation ends. This is a stronger room **comparison**, not a change to the live GS reverb. Attribution describes the additional direct-arrival suppression. Human preference and audibility still require listening.

Source depth is separate from the hall comparison. Procedural stems now contain quiet, dark stereo early reflections (26–147 ms) baked into their periodic loops, without feedback or a long tail. The live granular core preserves the two source channels with shared grain positions, alignment and envelopes, including source-switch crossfades. Both ordinary and granular comparison renders preserve stereo. “Dry” means no additional hall processing; the procedural source already includes these early reflections. Pitch trajectories, driving maps, evolving overlap and the separate hall tail are unchanged. This is stereo width/early-reflection coloration, not binaural or calibrated surround rendering.
