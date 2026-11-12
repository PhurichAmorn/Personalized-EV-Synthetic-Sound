# Sound behavior: existing procedural method

## Purpose and design contract

This document defines the project's original procedural oscillator method. Keep it as the baseline and comparison method while exploring source-first sound design. Its intended outcome is a continuous, vehicle-responsive sound with clear, smooth changes in pitch, tonal colour, drive presence, and regeneration. Avoid strong oscillation, unstable level, or effects that obscure the relationship to vehicle state.

This is a durable behavior guide, not a feature log. Small implementation or parameter edits do not require a documentation change. Update it when the method, sound-to-state contract, or intended listening outcome changes materially. Source code remains authoritative for exact DSP values.

## Current method

The driving sound is generated procedurally by the native C++17 engine in `audio/`. Python does not synthesize a fallback sound: `audio/__init__.py` loads the required pybind11 extension, and `backend/controller.py` passes simulator state and the active profile to `SoundEngine.set_driving_parameters(...)`. The engine renders through its native audio callback. Public presets/search profiles do not use BMW, Kia, or other manufacturer recordings. They use the electric oscillator or engine-order synthesis paths, not the source-audio granular renderer being considered for future research. A legacy native grain branch remains for older or partial-blend profiles; its buffer is generated internally from synthetic tones.

The sound is built from continuous oscillator layers:

- **Electric tone:** a speed-linked fundamental with related lower and upper partials, smoothed pitch, filtered colour, and configurable harmonic richness.
- **Engine-order tone:** an optional harmonic-order synthesizer. The Sport **ICE Inspired** recipe uses a virtual RPM curve and an order-based pulse texture; it is synthetic and does not simulate real cylinders or use an engine recording.
- **Deep layers:** a speed-linked traction tone and a sustained chordal/orchestral-style oscillator layer. The current Deep baseline has no repeating phrase cycle.
- **Transient and response shaping:** smooth drive and regeneration envelopes, pedal-linked presence, acceleration emphasis, and bounded startup cue.

Oscillator phase is kept continuous across profile changes. Profile values and control targets are smoothed; a limiter-shaped output mix constrains peaks. The renderer is mono duplicated to output channels. It is a research sound design, not an OEM reproduction or validated cabin calibration.

## Vehicle inputs and sound mapping

The controller sends vehicle speed, accelerator position, signed motor load, longitudinal acceleration, operating state, active sound profile, and playback volume.

| Input | Role in sound |
| --- | --- |
| Speed | Drives a bounded, saturating speed progression. This changes electric pitch and Deep traction register; the order recipe derives virtual RPM from the same speed progression. |
| Accelerator | Represents driver intent. A smoothed, gamma-shaped pedal signal affects propulsion presence and harmonic colour. For ICE Inspired it also adds a bounded virtual-RPM rise, strongest at low speed. |
| Signed motor load | Positive load drives propulsion level. Negative load drives a separate, quieter regeneration layer. A brake request alone does not create regenerative sound. |
| Longitudinal acceleration | Positive acceleration adds smoothed presence and harmonic emphasis. It does not replace motor load. |
| Operating state | `off` mutes; `starting` plays a short startup cue; `ready` enables driving response. |
| Playback volume | Separate smoothed output multiplier; not a sound-profile parameter. |

Pedal request and delivered motor load stay separate: pedal means intent; signed load reflects what the simulator delivered after vehicle limits. Sound processing does not feed back into vehicle physics. See [Vehicle physics](vehicle_physics.md) for the simulator mapping.

## Current themes and recipes

The three dashboard themes are **Comfort**, **Sport**, and **Deep**. Each has two audition recipes:

| Theme | Recipes | Main distinction |
| --- | --- | --- |
| Comfort | Clean Electric; Warm Motor | Restrained or warmer, fuller electric tone with gentle response. |
| Sport | Electric Sport; ICE Inspired | Faster, brighter electric response or synthetic engine-order character with throttle-linked virtual RPM. |
| Deep | Traction Glide; Orchestral Rise | Low speed-linked traction foundation or a stronger sustained chordal layer with a quicker pitch rise. |

Recipe selection is an audition choice. A new personalization session starts from the mode's baseline and uses its own recorded candidate profiles; changing a dashboard recipe does not rewrite saved sessions.

## Standalone sound experiments

The left sidebar's **Sound Lab** selects a regular in-page workspace with a manual source-response trial and a BMW M spectral reconstruction player. It has no modal layer. The earlier Play preview timed sweep and its tone-layer tuning, preset, save/undo, and effects controls have been removed from the active dashboard.

`SteadySource.tsx` plays four original source stems. A Resting–Full expression slider applies fixed pitch, brightness, and layer-balance targets from `sourceClimb.ts`; the foundation remains untransposed while upper voices climb by up to five semitones. Optional stereo convolution reverb follows the transformed mix. Targets are smoothed, and no automatic climb occurs. The player defaults to granular synthesis and offers ordinary sample playback for comparison, both using the same fixed manual response mapping and no vehicle inputs. Granular mode schedules 160 ms Hann-windowed grains at 40 ms hops with four-way overlap, a fixed source scan rate with ±12 ms waveform-similarity alignment between neighboring grains, and no random scatter or pitch jitter. Its overlap-add renderer runs in an AudioWorklet; live listening and platform qualification remain outstanding. A spectrum/waveform monitor shows this player's output, with trigger alignment and Hold graph available.


The former tone renderer and history utilities remain in source but have no active dashboard controls. The standalone rising-organ WAV can still be generated by `tools/render_organ_preview.py`; it is no longer shown on the dashboard. See [Source-first sound approach](../design/source_first_sound_approach.md) for source-design provenance and experiment limitations.

## Runtime and maintenance

`audio/engine.cpp`, `audio/dsp.cpp`, `audio/order.cpp`, and `audio/config.cpp` implement the native engine, synthesis layers, order synthesizer, and profiles. `audio/bindings.cpp` exposes the engine to Python. `./launch.sh` builds the required extension before starting the Tauri app. If native loading or audio output fails, the app reports that failure; no Python fallback renderer exists.

For research findings, OEM design references, and analyzed clip trends, see [Sound design research](../research/sound_design_research.md). The separate proposed method is described in [Source-first sound approach](../design/source_first_sound_approach.md). For interactive candidate groups and search policy, see [Interactive algorithm](interactive_algorithm.md).


## Live simulator source audition

Sound Lab now accepts app-simulator telemetry through the existing desktop snapshot. The snapshot includes raw normalized signed motor torque as motorLoad, distinct from the smoothed power/charge display. Driving inputs is the default source-control mode; Manual comparison remains available. The current map raises all tonal stems together from −7 to +1 semitones using a smoothstep of the shaped positive pedal/motor-load expression. Speed no longer controls register; RPM still controls activity near rest. Pedal intent and positive motor load control harmonic presence and low-pass brightness; negative motor load relaxes the sound. Targets are smoothed and paused/off/starting or telemetry-stale states mute the source. The spectral and room renderer settings remain fixed. This path does not read the separate BeamNG UDP listener.

A sourceAudition bridge command suppresses native engine output while the browser source player is active and restores the existing native volume afterward. Active preference sessions and native debug sweeps block source audition. Sound Lab offers Start/Stop vehicle and uses the existing W/S and controller driving inputs. The Python sidecar must be restarted after updating this integration; older snapshots show a restart message instead of allowing mixed native/source playback.

Granular rendering now runs on the audio thread via `desktop/public/audio/granular-processor.mjs`, replacing the UI-thread lookahead timer. Each output sample advances active grains with the audio-rate pitch parameter. Regression tests exercise the same rendering core and worklet message boundary without UI callbacks. This removes dependence on UI timers; it does not establish real-device performance or listening quality. Driving/listening qualification remains required before participant sessions.

The live source map has no stationary idle tone. Motion activity follows a smoothstep from zero RPM to 12% of the selected vehicle’s RPM ceiling; without RPM telemetry it falls back to 0–15 km/h. Pedal intent can open activity separately (3–15% pedal). Standstill holding torque alone does not activate sound. Gain uses a continuous 350 ms exponential smoothing time constant to zero, without a final forced silence ramp. This activity gain is applied before convolution, so the room decays naturally after excitation falls to zero. This replaces the former narrow 0.5–3 km/h gate. Source WAVs and manual comparison are unchanged.

The driving-map upper texture is restrained (glass gain 0.1–0.35), the foundation stays full, and load-driven low-pass cutoff spans roughly 1300–2200 Hz before the regen adjustment. Pitch targets use a 350 ms smoothing time constant; driving gain also uses 350 ms, while layer/filter controls retain 150 ms smoothing. This keeps the initial driving trial in a lower register rather than extending into a bright upper sweep.

### Original granular template and drive capture

Sound Lab exposes only the original source renderer; the BMW/reference comparison panel is no longer mounted. Offline reconstruction scripts and assets remain available for past experiments, but are not part of this template. The source itself remains unchanged. Granular playback adjusts each grain’s source offset within ±12 ms of the fixed scan position to maximize waveform similarity with the preceding grain at the overlap. This reduces phase mismatch; it does not guarantee transparent pitch shifting of every multi-tone source. The alignment reference is the previous grain’s actual read position at the hop, avoiding lookahead pitch prediction. Waveform matching still cannot guarantee transparent transposition of every polyphonic source. Reverb remains post-transform, and driving still mutes at rest.

The source player’s **Record acceleration** button records its actual post-mapping, post-reverb, post-volume output using MediaRecorder. Start the source, begin recording, drive with the app controls, stop recording, then download the clip. Format depends on browser support. It captures this player only, not the microphone or native engine. No live recording or listening qualification has been performed for this template.

The main dashboard START button starts the original granular player directly during the click gesture, alongside the existing vehicle command. Its settings/recording controls stay in Sound Lab; the dashboard shows a compact waveform and status with the instrument cluster. Both views retain one player instance. Native audio is muted while this source is active, and is restored when the source is stopped or unmounted. Experimental search remains on the native renderer.

The granular template’s main level is propulsion-led: `activity * (0.9 * propulsion + 0.03 * regen)`. There is no speed-only gain floor during coasting. Negative motor load leaves a restrained regen trace instead of sustaining the propulsion tone; the room tail remains downstream. Gain falls with a 180 ms time constant and rises with 350 ms smoothing. This follows the native baseline’s load-responsive intent, but is not an exact reproduction of its separate regen voice.

### Sound response and onset controls

Dashboard and Sound Lab share Exponential (`x²`), Linear (`x`), and Logarithmic (`log(1+9x)/log(10)`) response choices. They shape effort for layer balance, brightness and Steady pitch; Rise/Evolving retain their RPM/speed-led pitch maps. Propulsion level blends 65% unshaped effort with 35% curve-shaped effort, avoiding excessive suppression of partial controller input while preserving the curve choices and full-input endpoint. Exponential is the default. The chooser sets onset to about 95% target amplitude: Exponential 0.8 s, Linear 0.65 s, Logarithmic 0.5 s. This makes the options differ even with binary keyboard throttle. At a sustained full input all curves still reach the same endpoint. Only the three-function chooser is exposed. Two equal smoothed gain stages before reverb provide a zero-slope onset, including when audio loads after the vehicle has begun moving. Falling targets retain the quiet regen/coasting policy and natural room decay. Settings are session-only.

Siemens documents Kia EV6 Slow/Normal/Fast accelerator sound-response options in its [EV6 article](https://blogs.sw.siemens.com/simcenter/how-kia-ev6-inspires-your-senses-with-active-sound-design/). It does not disclose those curves or timing constants. The formulas and onset above are this prototype’s implementation, not recovered Kia calibrations.

### Five-second steady and evolving sources

The Source chooser now selects two distinct five-second stem sets. Steady is stationary original audio (174.8 Hz root). Evolving is authored by `tools/render_evolving_source.py`: rising 4.5-second phrases enter every 2.5 seconds, from 160 to about 269 Hz (9 semitones), with complementary two-second equal-power fade-in/out envelopes. Combined phrase-envelope power remains constant through the two-second overlap; the incoming low phrase takes over early using a quintic handoff over normalized time raised to 0.75, reducing masking by the outgoing high tail. Notes and per-voice timbre are unchanged by this envelope adjustment; overlapping moving voices support the fades without a stationary anchor. Waveform interference can still vary instantaneous level. Two phrase entrances wrap periodically into each five-second buffer. The source generator checks finite levels and loop boundaries. RMS of the combined dry source is matched to 0.13. The authored rises are audible in the WAV itself, before granular playback.

The earlier processing-only evolving cycle and the Rise and hold source option are removed. Both sources pass through the same granular renderer, throttle/load pitch mapping, level response and post-transform room. The register depends on pedal/positive motor load rather than vehicle speed. Changing source crossfades the old and new granular renderers over 160 ms. Ordinary sample playback is still available for comparison; source selection is disabled during that playback mode. This is an original interpretation of overlapping deep rising phrases, not an exact reproduction of the native Deep profile. Listening quality remains unverified.

The main dashboard sound-theme row exposes Evolving as the default driving selection. START explicitly selects its source and starts the browser renderer during the click gesture. Selecting Deep, Sport or Comfort stops that renderer and restores the native theme; subsequent START respects the selected native mode. Sound Lab remains available for source experiments.

The dashboard sound button is now **Granular synthesis**, with a synchronized Steady / Rise / Evolving mode chooser. Steady and Rise use the same stationary buffers: Steady uses a gentle power-driven register; Rise climbs with speed and opens under acceleration. Evolving selects the distinct authored rising-phrase buffers and keeps input transformation. The chooser in Sound Lab shares the same dashboard state; mode persists across vehicle stop/start within the session. Switching Steady/Rise does not reload or restart the shared source; pitch transitions use existing smoothing. Switching to/from Evolving retains the source crossfade.

### Comfort-like Steady and Sport-like Rise mapping

Steady and Rise retain the same stationary source. Steady uses normalized propulsion power (`state.power`, the existing smoothed dashboard power signal) for register, level, layer balance and brightness; speed, RPM and acceleration do not increase its expression. Its register moves from −7 to −2 semitones with shaped power. Negative motor load suppresses propulsion expression and retains only the quiet regen policy.

Rise uses `−7 + 8*(1−exp(−speedKmh/70))` semitones: it continues climbing beyond 90 km/h while remaining below +1 semitone. Positive measured vehicle acceleration (new `acceleration` snapshot field, m/s²) adds upper-layer presence and filter opening rather than a temporary pitch boost that could fall during an otherwise continuing speed climb. Load still controls level and release, so speed alone does not sustain sound during coasting. Without the new field, acceleration expression defaults to zero until the sidecar restarts. Evolving retains its prior source and load-driven transformation.

The shared stationary source’s harmonic rolloff is slightly less steep to add definition without new detuning, noise, or low-frequency layers. The already-liked evolving WAVs are unchanged.

### Launch climb calibration

Steady remains power-only, but its pitch now uses the shaped power directly over −7 to −1 semitones, removing the additional smoothstep that flattened low-power changes. Rise register combines 65% normalized RPM, 25% speed register and 10% normalized propulsion power. RPM register uses `(1−exp(−4*rpm/maxRpm))/(1−exp(−4))`, clipped to physical input range; speed register keeps the unbounded-in-speed, bounded-in-pitch exponential. If RPM telemetry is absent, the RPM share falls back to speed register. Rise retains the −7 to +1 semitone bounds and acceleration-driven brightness. Evolving combines 60% RPM register with 40% of its existing load-driven register; without RPM it retains that existing register. Level gating, quiet regen and source WAVs are unchanged.

### Low string ensemble and continuous high-speed evolution

Both GS sources use the original `tools/source_voice.py` harmonic voice: low fundamental, smooth body resonances around 350/700 Hz, rolled-off upper harmonics and subtle vibrato. This is additive cello/viola-inspired synthesis, not a sampled or physically modeled bowed instrument. Steady/Rise share a stationary source. Evolving contains overlapping 160–269 Hz rises without a stationary anchor, with two entrances per five-second buffer. Each phrase lasts 4.5 seconds with a two-second equal-power overlap. A quintic handoff over normalized time raised to 0.75 keeps both outgoing and incoming voices audible. Combined dry source RMS remains 0.13.

All modes start at −10 semitones. Steady reaches −1 with power. Rise reaches at most +1 through its RPM/speed/power blend. Evolving uses its RPM/load blend up to +1 below 100 km/h; above 100 it adds `4*(1−exp(−max(speed−100,0)/80))` semitones, continuing the same pitch trajectory without a threshold jump.

At 100 km/h Evolving requests source-scan hold, rather than blending to a different stationary source. The scan completes the current rise to the 2.2-second point of its 2.5-second phrase interval, decelerating over the last 0.25 seconds of source distance. If already past that point, it holds the current upper region. Grains continue reading and transposing the same evolving buffer. There is no threshold-related gain fade, separate sustained source or phrase restart. Slowing below 100 releases hold and ramps scan speed back to normal over 0.2 seconds. The ambient air layer keeps scanning. Explicit source-mode changes still use their separate 160 ms crossfade.

Ordinary sample playback remains a comparison and does not implement scan hold. Native Deep/Sport/Comfort are unchanged. Real-time performance and listening quality remain unqualified; offline tests cover scan completion, no source replacement, held playback continuity and resumption.

### Warm base and spatial depth calibration

The low ensemble now emphasizes the lower companion voice and softens the upper string layer. Harmonic formants move to approximately 350/700 Hz with stronger upper rolloff, retaining the same phrase frequencies and phase-continuous source construction. Room response is darker (180–2400 Hz), with 22 ms predelay, distinct stereo early reflections and a designed 1.8-second decay in a 2.2-second impulse buffer. Live and exported steady spatial mix use 68% dry / 32% wet gains. This is a source-colour/room adjustment only: driving maps, phrase notes, overlap and same-source high-speed hold remain unchanged.

### Explicit GS refresh

Clicking GS or its next-mode button now explicitly refreshes playback. The old player fades out; source WAVs are fetched with `cache: no-store`, decoded buffers are replaced, and a new AudioContext loads a fresh worklet module. Native audio stays muted during this replacement. The old context closes after its fade. Asynchronous loading resolves the latest selected mode/settings before constructing nodes, preventing stale selections from winning a load race. Ordinary vehicle START remains a non-forced start; source and mapping tuning are unchanged.

The synthesized string sources now include deterministic irregular bow motion from `organic_motion`: slow bounded pitch drift, slightly varying vibrato and independent small pressure variations per voice. The fixed seeds and five-second periodic motion preserve repeatable loops. This changes source micro-expression only; pitch trajectories, phrase overlap, driving maps and live room parameters are retained. The separate baseline Hall comparison now emphasizes measured late reflections; that stronger comparison effect is not applied to live GS.

The source-first GS stems are stereo: quiet dark early reflections are baked into the five-second source loops so depth is present during sustained playback. Granular playback shares grain positions/envelopes across the source channels and preserves their stereo relationship, including source-switch fades. This internal source coloration is separate from the optional hall convolution and does not change driving or phrase mapping.

Evolving phrases now rise throughout their full 4.5-second duration, including the outgoing fade, rather than reaching a fixed pitch early. Below the existing 100 km/h scan-hold threshold, repeated overlapping source rises combine with the same RPM/speed/power register and acceleration brightness response as Rise. Steady remains power-led. All three retain their slower, deeper launch playback; idle/regen level behavior is unchanged.

### Shared-source style trial

All three GS styles now default to the same stationary stem set. Evolving transforms that source in the audio worklet with two granular voices: overlapping 4.5-second, nine-semitone rises at 2.5-second intervals, using the same complementary two-second envelopes as the authored arrangement. Stereo grain positions stay paired. The driving register is applied on top of each voice's phrase pitch; chorus and room remain downstream. The existing 100 km/h hold now settles the transformation's phrase clock, preserving the same source and ongoing driving pitch changes. Below the threshold the phrase clock resumes smoothly. Air is not pitch-cycled.

Sound Lab retains the previous authored Evolving source as an explicit comparison option. It disables the additional transformation to avoid doubling the rise. Source changes and transformation-mode changes crossfade; Steady and Rise retain their existing driving maps. This trial has not yet been qualified by listening.

“Simulated style comparison” replays an identical 22-second acceleration/cruise/regen/stop trace through the live multi-stem renderer without driving the vehicle. Changing style or Evolving source arrangement while playing restarts the trace. Replay also resets the source renderer and phrase clock. Simulated inputs are independent of live telemetry/staleness; the dashboard's GS button restores live driving input. A preferred style or no preference can be marked for the current visit only. This is a listening trial, not an algorithm study or persistent experiment record. Source-generation search remains unimplemented.

### Manual source-character qualification

Sound Lab exposes four normalized source-generation macros: body (low-mid harmonic weighting), harmonic character (harmonic decay and spectral rolloff), ensemble (companion-voice balance and small periodic detuning), and natural movement (repeatable phase/vibrato and pressure variation). Generate source renders a deterministic five-second stereo source in a background Web Worker. Three tonal stems replace the shared stationary stems; the original quiet air stem is retained. Source-internal early reflections are included. Generated tonal mix RMS is normalized to 0.13 with a 0.7 peak ceiling, before fixed driving transforms and effects. This is RMS/headroom management, not perceptual loudness matching or a listening qualification.

The trial starts in Rise with the existing simulated drive. Sliders are pending edits until Generate source is clicked. A generated source restarts a running simulated drive or crossfades into live granular playback, and stays available across all three shared-source styles during the current visit. Original-source reset is explicit. The authored Evolving comparison uses its original source; generating selects the shared-source transformation. Device-rate conversion occurs before installation into the worklet. Chorus, reverb, granular engineering settings and driving maps are not source-search dimensions. No preference model, candidate proposal policy, automatic saving or participant record is added by this manual qualification trial.

### Source-family discovery trial

Source families are now the primary Sound Lab selection, with the previous four controls under a collapsed Fine tuning section. The six original generators share a 174.8 Hz reference and common source preparation: bowed harmonic ensemble, rounded odd-harmonic electronic tone, vowel-formant harmonic tone, inharmonic glass modes, dark FM metal, and a breath-like periodic noise/tonal mixture. These are different synthesis structures, not six parameter presets of the bowed generator. They are synthetic interpretations, not sampled instruments or manufacturer reproductions.

Choosing a family renders only that source in the worker. In simulated mode, it replays the fixed drive, including after the previous drive has ended. The selected source works across shared-source Steady, Rise and Evolving. Downstream mapping, chorus and reverb are unchanged; source RMS/headroom management is common, but perceived loudness can differ. Original source reset and the earlier authored Evolving comparison remain available. These six anchors qualify broad source diversity before any family blending or preference model; they do not implement an infinite pool, adaptive search, automatic saving or a completed personalization experiment.

### Offline signal checking

`audio.signal_checks.check_signal` evaluates normalized mono/stereo source or rendered audio without a learned model. Policy `continuous-ev-v1` returns pass, review or reject, individual findings, measurements and thresholds. Rejection covers invalid/overloaded samples, estimated inter-sample overload, full-scale flat tops, silent source loops, missing explicitly expected audio, and strong source-loop value/slope discontinuities. Suspected isolated impulses, short internal dropouts, scaled flat-topped distortion and persistent high-band energy/prominent upper tones request review. These diagnostics do not infer pleasantness, certify listening comfort or establish aliasing from output alone. Thresholds are engineering starting points, not universally validated perceptual boundaries.

Only explicitly looping sources receive a wrap-boundary check. Rendered launch/idle/stop silence is allowed; an optional sample-aligned boolean intent mask suppresses intentional gaps and enables missing-expected-audio checks. Stereo channel power is retained to avoid hiding faults through mono cancellation. Checks return reports without mutating or repairing audio.

The offline family-render finalizer now checks both raw source loops and the full post-transformation/effect render. Its simulation remains an approximation of the browser graph. Qualification covers all six families through Steady, Rise and Evolving on the same input trace, plus the deliberate defect pool and unit fixtures. UFO-like modulation and fast flutter can remain technically valid and pass; their desirability belongs to preference assessment. No model-based aesthetics gate, automatic candidate rejection policy, live output monitor or per-audio-callback analysis is enabled in the app by this first pipeline.

Run `.venv/bin/python -m tools.check_signals input.wav --output artifacts/signal-report.json`; add `--loop` only for a repeating source. `--repeats 3` measures check time independently of file reading. `tools.benchmark_signal_checks` reproduces the qualification report after the source-family renders are prepared. Costs for synthesis and mapped rendering are separate from diagnostic time.

### Source-discovery qualification

The separate dashboard source-discovery trial uses signal checks as an admission gate. Its background Node/Python development renderer checks each raw source loop and the Rise mapped sweep, both before preview normalization/fades and after preview preparation. Rise is the agreed screening proxy; Steady and Evolving remain playable through the same source without separate qualification. A review or reject finding withholds the candidate and records its recipe/reason; bounded replacement proposals are tried without assigning dislike labels. No automatic repair or Audiobox gate is used. These rules can conservatively withhold unusual but acceptable sounds and cannot guarantee pleasantness.

Ready candidate stems play through the existing live granular graph with fixed exponential response, chorus and reverb. The identical simulated drive is optional. The offline qualification graph approximates browser DSP and tests one trajectory, not every live-input trajectory or output-device gain. Source generation/rendering runs outside the vehicle-control thread; it is not instant. Six initial candidates measured about 10 seconds each cold on this M2 environment and nearly immediate cached lookup. Playback still requires a listening review; no comfort or convergence claim follows from passing diagnostics.

Air and tone now uses softly detuned harmonic clusters instead of its previous dense nonharmonic noise cloud. This changes that family deliberately to reduce wind-like rushing while retaining a tonal core and stereo reflections. Legacy noiseCenter/noiseWidth recipe keys now control the harmonic cluster’s spectral focus and width. It does not remove the separate shared background-air stem from the renderer.

The development renderer now synthesizes a candidate’s source once, reuses identical float32 stems for Steady/Evolving qualification, and records stage timings in cached/exported metadata. A three-role measurement fell from 13.7 to 10.7 seconds after source reuse and the Airy revision (combined comparison, not an isolated benchmark). That former all-style path processed 66 seconds of simulated driving audio per candidate plus offline effects, preview preparation and signal checking; the current Rise-only path processes 22 seconds. Two new sources, or replacement candidates withheld for faults/similarity, take longer. No checking stage was removed.

Source-discovery admission now renders/checks only Rise, retaining source-loop checks and pre/post-preview signal checks. Steady/Evolving are no longer prepared as offline candidate WAVs or separate qualification jobs. Cached/exported metadata explicitly records qualification_modes=["rise"]; the common source stems still support all live styles. This reduces preparation work but does not establish that Rise covers every artifact in other trajectories.

A controlled single-rounded-source integration fixture took 9.95 seconds with three-style qualification and 3.66 seconds with Rise-only qualification on this machine. These are observed test runtimes, not fixed latency guarantees; two new candidates and replacements still add preparation time.

### Controller partial-throttle response

All GS modes now start at −11 rather than −14 semitones: the extra launch-depth term is one semitone times `(1-register)^2`, tapering to zero at the existing upper endpoint. Propulsion level uses the effort/curve blend described above, while harmonic colour retains the shaped response. With matched 20% pedal/load (and 20% power in Steady), full activity and exponential response, target drive gain is 0.1296 rather than 0.036. Sustained full-input gain remains 0.9; upper pitch endpoints, quiet regen, idle/coasting silence, release smoothing, source audio, chorus and reverb are unchanged. Faster attack retains the existing two-stage zero-slope onset. Rise qualification initializes pitch from the shared mapping instead of a separately hard-coded launch value. These engineering adjustments require controller listening review.

### Evolving cycle timing and gentle cruise

Shared-source Evolving now varies its phrase clock with `0.25 + 0.75*max(pedal,power)`, using normalized positive demand. Full pedal immediately requests the original 1× cycle speed even while displayed power catches up; 20% pedal/power requests 0.4×. The usual 2.5-second phrase-entry cadence therefore becomes approximately 6.25 seconds at sustained 20% demand. The core smooths cycle-speed changes over a 250 ms time constant without resetting phrase phase. This changes rise/envelope timing, not grain length, hop or global pitch mapping. Steady/Rise and the previous authored-source comparison retain their existing timing. High-speed hold at 100 km/h still prevents subsequent phrase resets.

For shared-source Evolving, low-speed settled cruising also reduces propulsion level smoothly by up to 60%. The attenuation fades in over 0–5 km/h, remains eligible up to 30 km/h, and fades out by 70 km/h; demand above 25% progressively removes it by 65%, and positive acceleration removes it by 0.8 m/s². Missing acceleration telemetry disables this inference. Strong acceleration/full demand retain their established presence, and regen gain, idle silence and room release remain unchanged. Cycle speed remains controlled by demand rather than this level attenuation. Listening/controller validation is still required.
