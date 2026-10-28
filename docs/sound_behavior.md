# Sound behavior

## Purpose and scope

This document is the shared behavior contract for the simulator's interior sound. It records what drives the sound, how it should respond, which code parameters may be tuned, and the references behind the design. Keep it concise and change it only when that contract, its inputs, or its planned themes change; detailed tuning experiments belong in code history or development notes.

The sound is an original procedural approximation. It does not change vehicle physics, reproduce a manufacturer's recording, or claim a validated OEM sound map. This document describes behavior shared across vehicle presets, not separate sound specifications for each car.

## Baseline profiles

The intended theme categories are:

- **Comfort**
- **Sport**
- **Futuristic / Deepness Emotion**

Comfort, Sport, and Deep are selectable procedural baselines and separate experiment labels. In new searches they are starting seeds, not fixed sound families. They share continuous oscillators, the existing four vehicle inputs, phase continuity, and smoothed controls. No vehicle physics changes are involved.

| Baseline | Carrier range | Gain | Richness | Character |
| --- | --- | --- | --- | --- |
| Comfort | 125–150 Hz | 0.32 | 0.045 | Soft, buoyant carrier; narrow pitch travel and muted harmonics |
| Sport | 90–297 Hz | 0.32 | 0.48 | Speed-led pitch; fast load response and stronger acceleration harmonics |
| Deep | 70–169 Hz foundation | 0.32 | 0.22 | Sustained orchestral-style ensemble over a continuous rising traction tone |

| Baseline | Bass amplitude | Rolloff reference | Detuning | Load-colour strength | Regen coefficient |
| --- | --- | --- | --- | --- | --- |
| Comfort | 0.04 | 520 Hz | 0.2% | 0.30 | 0.20 |
| Sport | 0.12 | 900 Hz | 0.05% | 1.50 | 0.34 |
| Deep | 0.22 | 550 Hz | 0.15% | 0.85 | 0.30 |

All share the same profile gain; this does not guarantee equal perceived loudness. These are audition baselines and starting seeds, not restrictions on the current GP or evolutionary search. Existing saved candidates retain their stored profiles.

Ranges describe the carrier, not every partial. Richness scales the two upper partials and their load-dependent contribution; the lower tonal anchor remains stable. All profiles keep the same master gain, but Comfort intentionally has a quieter cruising envelope. These are starting settings for listening and tuning, not validated comfort or preference results.

| Response setting | Comfort | Sport | Deep |
| --- | --- | --- | --- |
| Steady-cruise propulsion multiplier (`drive_cruise_gain`) | 0.18 | 0.72 | 0.35 |
| Additional acceleration richness (`acceleration_richness`) | 0.025 | 0.18 | 0.10 |
| Propulsion attack / release | 160 / 300 ms | 70 / 130 ms | 220 / 400 ms |
| Regen attack / release | 220 / 320 ms | 140 / 240 ms | 300 / 450 ms |
| Regen harmonic emphasis (`electric_regen_richness`) | 0 | 0.45 | 0 |
| Pitch smoothing | 220 ms | 100 ms | 180 ms |
| Traction layer mix (`traction_mix`) | 0 | 0 | 0.40 |
| Final ensemble blend (`orchestral_mix`) | 0 | 0 | 0.50 |
| Repeating phrase interval (`traction_cycle_s`) | Disabled | Disabled | Disabled in current baseline; archived profiles may retain it |

Positive acceleration is normalized by 8 m/s² and smoothed over 180 ms. Its square root blends propulsion from the cruise multiplier toward full presence. Actual motor load still scales the resulting sound: pedal request alone cannot produce a sustained propulsion sound without delivered load. Negative acceleration does not activate this emphasis; actual negative motor load controls regen.

## Inputs

The sound engine receives the following driving inputs through `SoundEngine.set_driving_parameters`:

| Input | Range / meaning | Sound role | Current Deep implementation |
|---|---|---|---|
| `speed_kmh` | Actual vehicle speed; finite and ≥ 0. | Small pitch variation in Comfort; stronger pitch variation in Sport; continuous rising foundation in Deep. | Exponential progression (`speed_pitch_saturation = 3`, reference `180 km/h`). Carrier = `electric_start_hz` (or `electric_pitch_offset + electric_pitch_scale × base_hz`) `+ electric_pitch_scale × 180 × progression`. Deep foundation spans `70–169 Hz`, smoothed over 180 ms. A separate 250 ms speed smoother drives its quieter descending regen layers. |
| `accelerator_percent` | Driver request, `0–100%`. | Driver intent and tonal richness. | Normalize to `0–1`, apply `throttle_gamma = 1.25`, and smooth over 100 ms. It changes propulsion presence and harmonics without restarting a pitch phrase in the current Deep baseline. |
| `signed_motor_load` | Achieved torque / drive or regen reference; `−1…+1`. | Main effort / body; regen character. | Positive load drives the propulsion envelope (220 ms attack / 400 ms release); negative load drives a separate, softer oscillator mix (300 ms attack / 450 ms release), scaled by `regen_gain = 0.45`. |
| `acceleration_m_s2` | Actual acceleration; only positive values add emphasis. | Presence, harmonic richness, and Deep layer prominence. | Normalize by `8 m/s²`; sustained acceleration raises presence and richness. The existing small transient boost remains. Deep's traction mix grows from 20% to 100% of its configured mix as smoothed acceleration rises. No threshold-triggered pitch or level dips. |
| `operating_state` | `off`, `starting`, or `ready`. | Startup / driving / silence. | Driving sound is active when ready; starting uses the existing short startup cue. |
| `profile` | Selected source palette. | Sound structure and initial settings. | Public baselines: Comfort, Sport, Deep. The five existing motor ratios are `0.5, 1, 1 + detune, 1.94, 2.9`; new search candidates can add quieter moving and high-register partials near `4.1` and `5.15`. Baseline profile gain is `0.32`. Pitch span/offset can be explored in the pilot. |
| `master_volume` | Playback multiplier, `0–1`. | Output level. | Sound-engine playback level is smoothed over 50 ms. Separate from profile gain; the pilot WAV player uses a fixed multiplier of 1.0. |
| `sound_enabled` | Boolean. | Enables / mutes sound. | Sound-engine playback fades using the existing smoothing. |


Pedal request and delivered motor load are separate inputs: pedal position represents driver intent, while motor load reflects what the vehicle model actually delivers after its limits. Sound processing does not feed back into vehicle behavior.

## Overall behavior

- Speed changes pitch slightly in Comfort, more strongly in Sport, and continuously raises Deep's foundation and traction register. The foundation pitch rise flattens at higher speeds.
- Accelerator request and delivered propulsion load shape loudness and tonal richness.
- Positive acceleration changes presence and harmonic richness, with a restrained transient at onset. Current Deep baseline has no repeating pitch phrase or simulated gear event.
- Actual negative motor load produces a softer regeneration character. A brake request alone does not imply regeneration when the motor is not regenerating.
- Changes in pitch, level, mute, and theme should transition smoothly.
- `off` is silent. `starting` may play a brief startup cue. In `ready`, the driving sound is quiet or silent while stopped with no propulsion, and responds while the vehicle moves or applies motor torque.

Sound is intended to support driving feedback and a chosen mood. It should remain controlled and readable; it is not a source of vehicle warnings, road noise, or simulated friction-brake noise.

## Parameters that may be changed

Numeric sound tuning is changed in code, not through a user-facing tuning panel.

`OrderSoundConfig` exported by `audio` (native defaults in `audio/config.cpp`) controls the retained internal order-synthesis prototype. It also supplies common speed-curve, intent, transient and regen-gain settings used by Deep. Order-specific fields such as `dominant_order`, order amplitudes and the load-bass curve do not alter the current Deep oscillator palette. Its adjustable parameters are grouped here:

- **Pitch mapping:** `speed_pitch_reference_kmh`, `speed_pitch_curve`, `speed_pitch_saturation`.
- **Tonal balance:** `dominant_order`, `order_amplitudes`, `low_frequency_weight`, `high_frequency_attenuation`, `rpm_dynamic_gain_curve`.
- **Pedal and load response:** `throttle_gamma`, `throttle_gain_curve`, `throttle_harmonic_curve`, `throttle_brightness_curve`, `load_gain_curve`, `load_bass_curve`, `load_harmonic_curve`.
- **Acceleration and regeneration response:** `acceleration_reference_m_s2`, `acceleration_dynamic_gain`, `acceleration_harmonic_boost`, `acceleration_brightness_boost`, `regen_gain`, `regen_harmonic_mix`, `regen_brightness`.
- **Response and output:** the `*_smoothing_s` and `regen_smoothing` timing fields, `master_gain`, and optional `noise_gain`.

Theme-level values are in `SOUND_THEMES` exported by `audio` (defined in `audio/config.cpp`), including carrier range, richness, bass balance, cutoff, and load response. `master_volume` and `sound_enabled` are runtime playback inputs, separate from synthesis tuning.

Deep's `orchestral_mix = 0.50` blends a sustained procedural string/horn-like ensemble over the motor/phrase combination. Root, open fifth, and octave voices each have three slightly detuned oscillators and five softly filtered partials. Richness opens the supporting partials; speed shifts the shared register; delivered effort shapes the overall swell. No instrument recordings, melody track, bow-noise layer, or random texture is used. This is an orchestral-style synthesized texture, not an acoustic-instrument model. Regen uses a quieter version of the same ensemble. The mix smooths over 200 ms; archived profiles default to zero ensemble blend.

Sport regen uses a slightly faster 140 ms onset and more second/third-partial energy (`electric_regen_richness = 0.45`). Its existing regen gain remains 0.34. The harmonic adjustment normalizes post-filter squared partial amplitudes to retain approximately the same signal energy; perceived loudness still needs listening evaluation. Other profiles and archived profiles default to zero additional regen emphasis.

Profile response fields include `drive_cruise_gain`, `acceleration_richness`, drive/regen attack and release, pitch smoothing, traction mix, cycle timing, `traction_cycle_mix`, and phrase colour. New search candidates also expose `electric_whirl`, `electric_pulse`, and `electric_shimmer`, each smoothly controlled from 0 to 1. Whirl moves an upper partial without retriggering phase; pulse applies a bounded, roughly RMS-normalized modulation to propulsion; shimmer adds two filtered clean partials. These are procedural oscillator effects, not recordings or an engine sample. The search's `ensemble` control blends the existing chordal layer, while `phrase` controls the stage and timed-phrase blend. All ten current controls and mappings are shared across Comfort, Sport, and Deep; Deep uses a quieter ensemble/phrase seed and a moderate first opening sound. See [interactive search](interactive_search.md) for bounds and search behavior.

Archived profiles without new fields default to zero for these new effects. Archived timed Deep profiles retain their previous phrase timing and full cycle mix when `traction_cycle_mix` is absent. New Deep baseline still sets `traction_cycle_s = 0` and uses speed-based traction stages. Profiles retain oscillator phase and smooth control transitions across A/B switches. Gain remains fixed at `0.32` in current search candidates; equal perceived loudness has not been calibrated.

## References and design basis

These references inform the choice of sound inputs and broad design ideas. They do not define this project's exact parameters or certify its sound as realistic.

- [Zhang et al. (2022), Applied Sciences 12, 10768](https://doi.org/10.3390/app122110768): procedural EV sound design and tonal-order principles.
- [Prpic, Gherri, and Lugli (2024), “A perspective review on the role of engine sound in speed perception and control: state of the art and methodological suggestions,” *Frontiers in Psychology*, 15, 1391271](https://doi.org/10.3389/fpsyg.2024.1391271): research rationale for treating in-cabin sound as potentially relevant to speed perception and control, alongside preference and sound quality. The review finds evidence that reducing engine sound can affect speed perception, but notes that artificial-EV-sound research is sparse and methods vary; it does not establish that this simulator improves driving.
- [Hyundai Active Sound Design manual](https://ownersmanual.hyundai.com/full_webhelp/NE1a/2025/en_US/id2315B40J05Z.html): examples of speed, accelerator, driving mode, and selectable sound settings as design inputs.
- [Hyundai Kona technical description](https://hyundai.com.sg/global-stories/230313-02-All-newKONAUpscaledMultiplayerAcceleratesHyundai%E2%80%99sElectrificationVisionwithExtendedRangeandAdvancedFeatures/): speed, torque, motor state, and acceleration as sound-related signals.
- [BMW IconicSounds description](https://www.press.bmwgroup.com/canada/article/detail/T0331989EN/bmw-m-gmbh-and-hans-zimmer-co-develop-the-emotionally-engaging-drive-system-sound-for-electrified-bmw-m-models?language=en): driver feedback, vehicle state, and recuperation as sound-design ideas.
- [BMW (2022), “New soundscapes for pure-electric driving pleasure: BMW IconicSounds Electric”](https://www.press.bmwgroup.com/canada/article/detail/T0363642EN/new-soundscapes-for-pure-electric-driving-pleasure%3A-bmw-iconicsounds-electric?language=en): different mode responses, evolving sound textures, and Expressive-mode harmonic stages with reduced level at constant speed. Inspiration for behavior only; our layer frequencies and transitions are original settings, not BMW's algorithm.
- [“Tonalness and unpleasantness of non-stationary tonal components mimicking train acceleration and deceleration”](https://www.sciencedirect.com/science/article/pii/S0003682X26001908): distinguishes continuously changing motor-related tones from discontinuous PWM-related tones. Deep borrows the perceptual idea of changing traction sounds; it does not simulate a train inverter or reproduce its electrical switching.
- [Formula E Season 3 onboard sound](https://www.youtube.com/watch?v=j-7k-TWx1JE) and [Taycan RWD acceleration clip](https://www.youtube.com/watch?v=sghkzN3oFTk): exploratory references used for earlier prototype sound palettes, not calibration targets for the planned themes.

The chosen mappings, gain values, and response times are project design decisions. Listening evaluation is needed to assess comfort and perceived quality.

## DSP implementation

`audio/` is a standalone C++17 audio engine. `engine.cpp` owns input mapping, layer scheduling, smoothing, startup, mixing and debug history; `dsp.cpp` contains electric, orchestral and traction kernels; `order.cpp` contains engine-order synthesis and native Butterworth noise filtering; `random.cpp` preserves the original seeded PCG64 random draws; `config.cpp` owns presets, defaults and validation. `output.cpp` owns PortAudio devices, stream lifecycle and the native callback. None of these core files imports or links Python, NumPy, SciPy or sounddevice.

`audio/bindings.cpp` is the separate pybind11 adapter. `audio/__init__.py` is the only active Python audio bridge: it loads the required native engine, exports preset/configuration data, and locates the existing PortAudio library. Python configuration dataclasses exist for UI/experiment serialization; their defaults and validation come from C++. Vehicle simulation and experiment algorithms remain Python and unchanged by this audio migration.

The callback renders into supplied mono/stereo float buffers using preallocated workspace and a bounded grain pool. Native setters and rendering synchronize state with mutexes; this desktop prototype does not claim hard real-time scheduling. Callback exceptions produce silence, abort the stream, and surface through device-health checks. Start failures close streams; device refresh requires closed streams. Offline inspection through `_callback` is rejected while native playback is open, so it cannot advance a live engine's oscillator state.

Sound generation uses the native C++ engine through `audio/_native_dsp`. `./launch.sh` builds this required binding and stops if compilation fails. Runtime native playback failures require recovery/restart; there is no alternate Python renderer.

Native tests compile the C++ core without Python headers and check random draws, silence/headroom/stereo, allocations at normal callback size, concurrent input/lifecycle changes, and device failure cleanup. Experiment fingerprints include the actual native sources and bridge; existing participant records are never rewritten.

For a Python-independent build and WAV rendering:

```sh
cmake -S audio -B build/audio -DCMAKE_BUILD_TYPE=Release
cmake --build build/audio
ctest --test-dir build/audio --output-on-failure
build/audio/evsound_render /tmp/ev-comfort.wav Comfort 5 48000
```

`evsound` is the reusable native library target. `evsound_render` renders a fixed example drive to a PCM16 stereo WAV; it does not open an audio device. Programmatic playback uses `evsound::Engine::start()` and the system PortAudio runtime (`EV_SOUND_PORTAUDIO_LIBRARY` may provide its path). Call `prepare()` before offline rendering when reserving a specific block capacity. BeamNG/FMOD integration is outside this implementation.


## Local pilot workflow and records

The **Personalize sound** entry now runs the interactive GP or evolutionary preference search with live A/B driving, ratings, local records, satisfaction saving, and resume. See [interactive search](interactive_search.md) for exact mappings and algorithm behavior. The listening-pilot backend below remains an internal reference and is not the public interactive flow.

| Pilot control | DSP setting | Allowed exploratory range |
|---|---|---|
| Pitch span | Profile `electric_pitch_scale` | 0.5–1.5 |
| Pitch offset | Profile `electric_pitch_offset` | 0–60 Hz |
| Speed curve saturation | `speed_pitch_saturation` | 0.5–3.0 |
| Regen presence | `regen_gain` | 0.2–0.7 |

These ranges are temporary pilot bounds, not finalized global, theme or personalization settings.

Each new session writes to the gitignored `experiment_data/<timestamp>_<session ID>/` directory. `session.json` contains context, stimulus data, source fingerprints and bounds. `events.jsonl` contains exact candidate profile/configuration snapshots, generated WAV file hashes and levels, listening events, ratings, preferences, notes and session closure. Complete comparisons can be joined to their candidates with `pair_id`; unscored pairs remain distinguishable. Generated WAVs preserve the actual audition sounds.

The comparison uses fixed playback gain but does not match perceived loudness. Keep system volume and output device consistent. This pilot is for development exploration; neither the parameter space nor the study protocol is finalized.

### Acceleration sound response

Comfort emphasizes gentle effort/regen feedback and recedes during steady cruising. Sport retains stronger speed-related pitch feedback and responds faster to delivered effort, with more acceleration richness. Deep now keeps its sustained orchestral foundation over a softer speed-driven traction layer. Its carrier starts at 70 Hz and rises toward 169 Hz with the compressed speed curve; traction pitch follows that carrier and speed-dependent layer frequencies. At constant speed it settles instead of repeating a 2.5-second rise. Reducing `traction_mix` from 0.72 to 0.40 keeps the lower foundation strongest in sampled renders, avoiding a downward jump in the dominant measured tone.

Saved Deep profiles with a nonzero `traction_cycle_s` still use the earlier timed phrase: the cycle clock advances with smoothed pedal intent and delivered effort, and equal-power envelopes crossfade two phase-continuous voices. Previously saved morph-enabled profiles also remain playable. Timing, pitch excursion, morph mix, and stage colour smooth over 300 ms when switching profiles; other response controls blend over 250 ms. Listening remains necessary to judge perceptual smoothness.

Regeneration retains a separate, quieter speed-driven layer: its four voices crossfade over 18–42, 55–85, and 95–135 km/h and descend naturally as speed falls. Current Deep propulsion uses these speed-driven stages at reduced mix; archived Deep profiles without cycle timing also retain them. All stage/cycle timings are original audition settings based on the requested behavior, not measured train or BMW calibration or simulated transmission gears.

The profile-level `electric_growl` coefficient (0–1) shapes the motor's harmonic color. Baseline audition remains available through the SOUND selector outside personalization.

### Power-gauge meaning

The POWER target follows accelerator position (`0–100%`) only while actual motor torque is positive. The signed display approaches rising propulsion over 350 ms and release/regen over 140 ms, using the same response across the zero crossing. It represents driver-requested power rather than shaft power. POWER and CHARGE are derived from one signed display value, so they cannot fill simultaneously. Both directions pass smoothly through zero, including a short positive display tail when actual regen begins. The marker follows the displayed sign instead of jumping to CHARGE when the raw regen flag changes. At a zero target, display tails below 0.1% snap to zero. The separate telemetry graph shows modeled motor torque.

## Exploration notes

Unimplemented sound ideas, including slow LFO / organic drift as a possible naturalness parameter, are tracked in [sound_ideas.md](sound_ideas.md). They are not current behavior.
