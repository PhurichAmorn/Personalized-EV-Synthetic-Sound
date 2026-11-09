# Source-first sound approach

## Purpose and status

This is the proposed second sound-generation method. It guides an original sound material first, then evaluates a renderer and vehicle-state mapping for that material. It is separate from the existing procedural oscillator method in [Sound behavior](../system/sound_behavior.md).

**Status:** design and listening exploration. The app has no source-first vehicle renderer yet. The dashboard's Rising Organ Preview is a standalone WAV, not a mapped sound or a personalization candidate.

## Intended outcome

Create a clean, distinctive, smooth sound with more tonal depth and connected movement than the current oscillator baseline. Notes or layers should blend from low to high without large, distracting oscillation. Vehicle response should be audible and understandable, while the sound remains pleasant as a continuous interior ambience.

Kia, BMW, Mercedes-Benz, and other OEM examples are references for broad sound character and state response. The goal is an original, researchable sound informed by those examples, not a reproduction of a manufacturer's recording, proprietary patch, or exact calibration.

## Separate the design decisions

Keep these parts independently controllable during early study:

1. **Sound material:** composed or recorded tonal and textural layers. Use clean, documented, original or licensed material. Do not use noisy public-video mixes as clean source samples.
2. **Renderer:** turns material into continuous playback. Granular resynthesis is one candidate; layered crossfades or another method may work better. The renderer has not been selected.
3. **Vehicle mapping:** links speed, accelerator, signed motor load, acceleration, and regeneration to renderer controls. The current C++ sound API does not accept measured motor RPM.
4. **Personalization:** lets listeners compare a small number of coherent sound-character groups after the material and mapping are listenable. Do not search every grain control independently.

Real sound design may require revisiting these parts together. Separate them during experiments to make comparisons interpretable, then combine them after each part has a usable baseline.

## Candidate sound direction

- Keep a stable low foundation and introduce related mid/high layers gradually.
- Prefer smooth, monotonic pitch or spectral movement where it communicates increasing speed or driver intent.
- Make the sound have depth through layered tone and restrained space treatment, not persistent warble or excessive echo.
- Keep pulse, detune, and other periodic movement low unless a controlled listening comparison shows it helps.
- Keep road, wind, rain, speech, and recording crackle out of source material used to evaluate the synthesis design.
- Make drive and regeneration responses distinguishable, but do not let either overwhelm the continuous character.
- Treat pedal-response curve as a separate mapping choice: early rise and flatten, near-linear, and late rise are hypotheses. Do not tie Slow/Normal/Fast curves to a sound style or assume a curve reveals the renderer.

These are listening goals, not measured OEM settings or universal psychoacoustic limits. Research evidence and its limits are summarized in [Sound design research](../research/sound_design_research.md).

## What the current preview tells us

`tools/render_organ_preview.py` creates an ascending C3–C6 organ-like note sequence with overlapping envelopes and short fixed early reflections. It tests whether adjacent notes can join smoothly and whether a simple tonal source is worth exploring. It has no vehicle inputs, granular processing, or personalization. Do not treat it as evidence that the source-first method is complete or that an organ character is the intended final sound.

The earlier BMW Hans Zimmer source audition was removed after listening exposed pitch fluctuation and unrelated source dropouts. It did not validate granular synthesis or the proposed architecture.

## Evaluation order

1. **Approve a raw sound direction by listening.** Render a clean source without vehicle mapping. Check timbre, low-to-high continuity, layer balance, level, and noise.
2. **Choose and qualify a renderer.** Compare candidate renderers with the same source and fixed settings. Check clicks, repetition, pitch artifacts, clipping, and sustained CPU/audio stability.
3. **Study mapping with a fixed sound.** Use a repeatable vehicle input trace. Change one input-to-sound relationship at a time, such as pedal response or speed progression. Do not simultaneously tune pedal, load, and acceleration as independent full-strength controls.
4. **Add personalization after qualification.** Expose only perceptually distinct grouped controls. Keep a stable renderer and mapping version within a search block, and record source identity, renderer/mapping versions, and candidate settings.

Compare preference separately from perceived state clarity, comfort, and fatigue. Match playback level when the study asks about timbre or mapping rather than loudness.

## Decisions still open

- Whether the source material is composed from oscillators/notes, captured from physical sounds, or layered from both.
- Whether granular synthesis, crossfaded layers, or another renderer gives the cleanest continuous result.
- Which small set of sound groups listeners can distinguish and meaningfully personalize.
- Which input curves provide useful feedback without adding unwanted wobble or masking the sound character.

Do not represent any of these as settled until a listening comparison or study supports the choice.

## Full-recording spectral reconstruction experiment

`tools/reconstruct_reference.py` analyzes the supplied local BMW M MP3 into every complex STFT coefficient, with a 2048-sample Hann window and 512-sample hop. Its separate render command resynthesizes the saved model through inverse STFT without reopening the MP3. This is a full-information spectral representation of a recording, not an inferred OEM synthesizer, a compact parametric patch, or a separated clean drive-sound source. Speech, road noise, compression, and other content in the source remain present.

Sound Lab exposes the 14.408-second decoded reference and reconstruction as independent A/B players. Those players do not use tone-editor controls or vehicle inputs. The analysis model and numerical comparison live under ignored `artifacts/bmw_m_reconstruction/`. The browser WAVs preserve the decoded reference level and sample rate; no pitch shifting, noise filtering, or normalization is applied. Reconstruction error is checked against the decoded reference, which cannot establish similarity to the vehicle independently of that recording. Human listening remains necessary to assess the reference's usefulness as sound-design material.

## Source format: steady, evolving, or multiple regions

Published workflows do not establish a single universal source format. Siemens describes looping a complete sample for pitched playback, choosing different source positions in granular synthesis, and separate base/torque layers (https://community.sw.siemens.com/articles/en_US/Knowledge/Introduction-to-Simcenter-Testlab-Sound-Designer). A Harman patent describes pitch modification from a sample recorded at a particular RPM; a disclosed method is not proof of deployment in a given vehicle (https://patents.google.com/patent/US20230139893A1/en). Audi documents 32 recorded/synthesized elements weighted and modulated from driving data, without publishing their waveforms or complete source organization (https://www.audi-mediacenter.com/system/production/uploaded_files/17630/file/d18dd93f5e2a4e248ddfaa5092d2d211b40711fe/enPress_Information_Audi_e-tron_GT_Craftmanship.pdf?1601472520=&disposition=attachment).

A steady source is therefore a valid project starting point, not a demonstrated reconstruction of BMW's source method. An evolving source may supply different grain regions, and several sustained intensity/register variants can be crossfaded rather than forcing all changes from one sample. Layer count, source-region count, and driving-mode count are distinct. Granular synthesis is a rendering method; pitch motion still needs explicit controls or mappings. Sustained sources may contain subtle texture without an authored acceleration sweep. One fixed-pitch sample may lose its intended character under extreme transposition; qualify the renderer and usable range by listening.

`tools/render_steady_source.py` now creates an original 12-second, fixed-pitch 48 kHz mono source at about 174.67 Hz from a softened harmonic core, sustained upper-register harmony, restrained FM glass texture, and very quiet spectrally shaped periodic noise. It uses no BMW audio, acceleration sweep, effects, or vehicle input. It exports a periodic raw source, separately mixed stems, and a listening copy with short boundary fades. Sound Lab provides that listening copy and the raw-source download. The result is an unqualified sound-design candidate, not an OEM replica or a completed granular renderer. Stable pitch, level, peak headroom, stem reconstruction, and the loop boundary are checked numerically; pleasantness and perceived smoothness remain listening questions.

The active source-design trial starts with one steady source. The three arrangements above remain alternative renderer/material designs, not three sounds that must all be developed now. Sound Lab gives the steady source its own primary continuous-loop player and waveform, with short start/stop fades and an independent listening-volume control. Source looping does not repeat the audition-copy boundary fades. Reference playback, source playback, and the existing tone-editor audition stop competing players; leaving Sound Lab closes the source player. No vehicle mapping or granular processing has been added to this trial.

The steady-source trial now uses a sustained cinematic pad with constant component frequencies and no detuning, rhythmic pulses, or acceleration sweep. The spectrum display is the default for comparing frequency balance; an alternative waveform uses rising-zero-crossing alignment to reduce phase drift. Hold graph freezes the plot. A compound stationary sound can still have a changing instantaneous waveform; this does not establish pitch change. Numerical pitch/level checks are separate from subjective listening.

The latest steady trial increases the low-mid core and lowers the sustained harmony's register for depth. It also exports an optional stereo room version: a deterministic diffuse room response with 18 ms predelay, approximately 1.5 s decay, and a 28% wet blend. Circular convolution keeps the room response continuous at the source-loop boundary. Dry and spatial versions share the same digital RMS target; no pitch rise, detuning, moving pan, or vehicle mapping is applied. Sound Lab defaults to the spatial version and offers a Spatial reverb checkbox plus separate dry/spatial downloads. This source-player reverb is independent of the tone editor's mix-effects controls. The dry source remains the material for future renderer tests.

## Manual climb trial (no vehicle mapping)

The primary source player now offers one Resting–Full expression slider. A fixed smoothstep gesture raises the pad and glass stems from 0 to +5 semitones, opens their low-pass cutoff from 1600 to 4000 Hz, increases pad/glass presence, and slightly relaxes the untransposed foundation. The air and foundation do not change playback rate. Targets settle with a 150 ms time constant. This is pitched sample playback, not granular synthesis or the native driving renderer. It changes sample traversal speed as well as pitch. The stereo room impulse is convolved after the transformed stem mix, keeping room timing independent of the pitch shift. No automatic climb occurs without slider input.

The source gesture is a standalone audition control; it is not part of the tone editor's saved configuration, undo history, or participant search space. It must be qualified by listening at low/high/mid positions and during slow/rapid movement and release before connecting vehicle signals. Sound Lab retains the BMW spectral reconstruction player but removes the reference recording player.

Sound Lab now shows only the manual source-response trial and BMW spectral reconstruction. The older Play preview timed sweep, preset controls, automated pitch journey, and tone-layer editing section have been removed from this dashboard. Its former save/undo controls belonged to that removed tone editor; the manual source trial remains a separate listening experiment.

## Smooth source-phrase audition

`tools/render_reference_sweep.py` now renders authored legato pitch phrases from the original raw source. The former automatic reference-pitch/energy transfer was rejected after listening and is no longer used. The current renderer does not read BMW audio, estimate its pitch, or follow its loudness envelope. Two broad climbs and releases use minimum-jerk interpolation with zero pitch velocity and acceleration at the phrase knots, over a restrained 0–6-semitone span. Continuous cubic interpolation traverses the periodic source without restarting chunks. A gentle low-pass spectral blend opens with pitch while global gain remains fixed apart from playback boundary fades. A stationary stereo room response follows the pitch processing.

Sound Lab labels this as an original Smooth phrase demo and retains the BMW reconstruction for comparison. The plotted line is the actual authored pitch control, not an estimated vehicle signal. This is still pitched sample playback, with coupled sample-traversal speed and pitch; it is not granular synthesis or vehicle mapping. Numerical checks cover phrase-join continuity, pitch-speed bounds, constant gain controls, finite output and headroom. Naturalness and stylistic similarity remain listening evaluations.

## Fixed-mapping granular trial

The manual source player now has Granular synthesis (default) and Ordinary sample playback modes. Both use the existing normalized expression gesture, upper-voice pitch target, spectral opening, layer gains, and optional post-mix room response. The grain renderer (`desktop/src/granularPlayer.ts`) uses 160 ms Hann windows, four-way overlap, 40 ms output hops, independent fixed-speed source scanning, and smoothly controlled per-grain playback rate. It introduces no stochastic pitch, density, or position changes. The selected mode changes the renderer, not the input mapping, and switching stops playback before restarting the audition. There is no vehicle input or BMW-contour control in this path.

Normalized overlap is unity at neutral pitch, but transposed overlapping grains can still introduce phase coloration or roughness; smoothness is not guaranteed by the envelope alone. The renderer now runs in an AudioWorklet with audio-frame grain spawning, audio-rate pitch control, and explicit stop/unmount cleanup. This removes the former UI-thread scheduling dependency; live performance and listening quality remain unqualified. Compare neutral, middle, and maximum expression in both modes before choosing a renderer or adjusting grain parameters.

The granular/manual comparison now also accepts live app-simulator inputs. Its fixed driving map separates speed-driven register from pedal/load-driven expression, with source muting on stale telemetry and temporary suppression of native driving audio. The steady material is unchanged. This connects the experimental browser renderer for foreground audition; it does not validate the renderer or connect BeamNG. See the live-audition section of the sound-behavior guide for limits and restart requirements.
