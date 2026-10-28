# BeamNG EV sound integration

## Goal

Let a participant drive a BeamNG vehicle using BeamNG physics and hear this project’s synthesized EV motor sound inside BeamNG’s audio mix. BeamNG remains responsible for vehicle motion. The first version sends vehicle state to the sound renderer; it does not send modeled torque back into BeamNG.

## Reference implementation: BeamEngineSim

[BeamEngineSim](https://github.com/spidermodders/BeamEngineSim) connects Ange’s Engine Simulator to BeamNG.drive. Its README describes these parts:

- `EngineSimulator`: a modified Engine Simulator fork; its simulation runs on a separate thread.
- `EngineSimulatorMod`: BeamNG mod, including vehicle Lua and sound markers.
- A UDP bridge: BeamNG sends RPM, throttle, and ignition state to Engine Simulator; Engine Simulator sends torque back.
- `AudioPlugin`: FMOD plugin that replaces BeamNG’s `BeamNGBlendLayerDSP.dll`. It preserves other game audio and feeds Engine Simulator audio into the player car’s engine and exhaust sounds.
- Optional profiling/tuning adjusts BeamNG’s engine settings to the loaded simulated engine.

These details are from the repository README and layout. The exact packet schema and plugin callbacks must be confirmed in source before reusing them. The repository describes a combustion-engine simulator, so reuse its connection pattern, not its engine model or torque feedback, for the EV sound study.

## Proposed architecture

```text
BeamNG vehicle Lua mod
    | timestamped vehicle-state UDP packets
    v
EV audio plugin / renderer  <---- sound parameters / experiment selection ----  EV Sound Lab UI
    |
    v
BeamNG FMOD audio mix (vehicle engine sound source)
```

BeamNG’s own EV powertrain controls physics. Sound renderer receives state and generates audio. Keep the current Python application for experiment control and UI. Port or reuse the existing native C++ DSP in an FMOD-compatible component; do not put Python in the audio callback.

## Current implementation readiness (2026-10-26)

The audio engine is now standalone C++17 in `audio/`; its waveform kernels,
input mapping, presets, seeded random sources, filter setup and device output do
not depend on Python. Desktop integration is isolated in `bindings.cpp` and
`audio/__init__.py`. CMake builds a native library and offline WAV renderer without
Python. Native tests and Python-reference waveform comparisons cover current
behavior. BeamNG work remains deferred while testing the existing desktop app.

Before creating the FMOD adapter:

1. Reuse the standalone native engine from the game adapter; do not link the
   desktop pybind11 adapter or use its PortAudio output inside FMOD.
2. Adapt game-provided buffers and actual sample rate to the core render method.
   Reserve workspace before playback. Replace desktop mutex synchronization with
   a suitable nonblocking state handoff if required by the host callback contract.
3. Keep networking, configuration construction and file access outside the audio
   callback; retain the last validated state and handle stale telemetry explicitly.
4. The desktop Python binding is not suitable for a Python-free FMOD callback.
   Reuse the standalone C++ core directly in any future FMOD adapter.
5. Build/test the Windows adapter and verify the chosen BeamNG/FMOD version. The
   macOS desktop extension and native WAV tests do not establish game compatibility.

Input semantics need one explicit correction before wiring telemetry: the current
`SoundEngine.set_driving_parameters` derives virtual sound RPM from vehicle speed;
its accelerator argument is percent (0–100), and signed motor load is normalized
(−1–1). It does not accept measured motor RPM. Preserve this speed-based behavior
for the initial experiment. Using actual motor RPM, as suggested in the signal
mapping below, would be a separate sound-behavior change and must be agreed and
validated explicitly. OutGauge documents speed in m/s and throttle/brake in 0–1;
convert speed to km/h and throttle to percent. Its timestamp is documented as
unimplemented (zero), so measure local receive times for the initial cadence and
staleness checks rather than treating it as a valid sender timestamp.

Reference review confirmed the BeamEngineSim README's FMOD replacement, Lua mod,
and UDP architecture. Individual plugin callbacks and packet definitions could
not be fetched during this review; treat them as unverified. Local Git history
also could not be reviewed because this workspace has no `.git` metadata.

## Build order

### 1. Prove BeamNG can send state to the app

First prove telemetry without building an audio plugin:

1. Start a UDP listener in a small local Python script on `127.0.0.1` and a chosen port. Log each received datagram with time and source address.
2. Enable BeamNG’s built-in UDP protocol in **Options → Other → Protocols**. Start with OutGauge if available; BeamNG documents it as carrying basic vehicle state such as speed and pedals. Follow BeamNG’s protocol page for the enabled protocol’s port and packet format.
3. Drive, change throttle/brake, and confirm packets arrive and values change plausibly. Record packet rate, units, and whether packets stop when the vehicle is paused or the game closes.
4. Treat this as a transport proof only. Built-in telemetry may not expose EV motor RPM/load/regen needed for sound mapping.
5. For richer signals, add a BeamNG Lua mod/vehicle extension that reads the active vehicle’s electrics and EV powertrain values and sends a compact UDP message to the listener. Include timestamp/sequence, speed, accelerator, brake, motor RPM, signed motor load or torque, regen if available, and validity flags. Inspect actual values in the chosen vehicle before fixing field names; BeamNG notes that electrics vary by vehicle and can be inspected with `dump(electrics)`.
6. Validate units and behavior against BeamNG gauges and controlled pedal/speed changes. Then replace the logger with a state adapter that calls the existing sound engine’s input API.

Minimal listener shape (packet decoding depends on chosen BeamNG protocol):

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1", 4444))
while packet := sock.recv(4096):
    print(packet)
```

For the first pass, using the built-in protocol avoids writing the game mod. For motor-specific values, use a Lua bridge as BeamEngineSim does: a vehicle/game-side mod sends state over UDP to a local process. Its README confirms this bridge pattern, but does not document packet details.

### 2. Render the sound inside BeamNG

- Build a small FMOD-compatible audio plugin/source that receives the sound state and renders the EV sound into the game’s engine audio path.
- Keep the game’s other audio layers intact; expose a volume control and a clean disconnect/fallback to stock vehicle sound.
- Initially feed the plugin the same validated telemetry packets used by the logger. Test startup, disconnect, stale packets, pause, and vehicle changes.
- BeamEngineSim provides a concrete reference for the audio integration layer: its plugin replaces `BeamNGBlendLayerDSP.dll` and routes audio into engine/exhaust sound. Confirm current BeamNG version/API compatibility before copying that replacement/install technique.

### 3. Connect experiment controls

Connect EV Sound Lab’s experiment controls to plugin parameters or the renderer over a separate local control channel. Preserve candidate identity and sound configuration in experiment records. Do not change sound parameters from telemetry packets.

### 4. Consider physics feedback only if required

If the study later needs a custom EV motor model to change vehicle acceleration, implement and validate that as a separate BeamNG powertrain task. Do not send torque feedback as part of the audio-only integration: it changes vehicle behavior and could confound sound-preference results.

## Signal mapping

| BeamNG signal | Sound-engine use | Notes |
|---|---|---|
| Vehicle speed | Current speed/pitch progression | Convert to km/h if adapter expects current project units. |
| Accelerator | Pedal intent | BeamNG electrics commonly expose normalized throttle input. |
| Motor RPM | Order oscillator pitch | Prefer actual EV motor RPM when available; wheel speed can estimate it only when gearing/traction assumptions hold. |
| Motor torque/load or power | Sound intensity/body | Use signed direction if available so drive and regen can be distinguished. |
| Brake/regen | Regenerative sound blend | Brake input is not necessarily equal to regenerative torque; inspect actual powertrain signals. |
| Acceleration | Transient emphasis | Derive from speed if direct acceleration is unavailable; smooth and validate. |

Current project entry point is `SoundEngine.set_driving_parameters(...)`; verify its exact argument semantics before wiring the adapter. Keep BeamNG networking outside the audio callback. Audio callback should consume the latest validated state snapshot and continue smoothing/limiting as it does now.

## First proof-of-concept acceptance criteria

- Listener receives packets only from local BeamNG session and rejects malformed/non-finite values.
- Packet cadence and state changes are visible while driving.
- Speed and pedal values agree directionally with BeamNG UI; units are documented.
- Missing motor-specific values are explicitly marked unavailable, not silently guessed.
- Closing or disconnecting BeamNG stops state updates and causes a controlled sound fade/fallback.
- No vehicle torque or physics is changed by the audio-only prototype.

## References

- [BeamEngineSim GitHub repository and README](https://github.com/spidermodders/BeamEngineSim)
- [BeamNG protocols](https://docs.beamng.com/modding/protocols/)
- [BeamNG vehicle electrics](https://docs.beamng.com/modding/vehicle/vehicle_system/electrics/)
- [BeamNG Lua extensions](https://docs.beamng.com/modding/programming/extensions/)
