# Project architecture and repository map

## Purpose

This guide shows where project responsibilities live and how the desktop, vehicle model, experiment search, and sound engine connect. Read it before moving code across layers or deciding where a new feature belongs. It describes durable ownership boundaries; exact implementation details stay in code.

## Repository ownership

| Path | Responsibility | Read with |
| --- | --- | --- |
| `desktop/` | React/TypeScript interface and Tauri 2 desktop shell | `desktop/src/`, `desktop/src-tauri/` |
| `backend/` | Python sidecar, simulator controller, UI command bridge, keyboard/controller input, audio output monitoring | `backend/sidecar.py`, `backend/controller.py`, `backend/bridge.py` |
| `simulation/` | Vehicle and powertrain state updates from pedal inputs and elapsed time | [Vehicle physics](vehicle_physics.md) |
| `audio/` | Native C++ sound engine, synthesis, presets, validation, PortAudio output, and Python binding | [Sound behavior](sound_behavior.md) |
| `experiment/` | Interactive comparison policies, candidate profiles, local session persistence | [Interactive algorithm](interactive_algorithm.md) |
| `tools/` | Offline audio analysis and rendering utilities; not part of normal runtime | [Sound design research](../research/sound_design_research.md) |
| `tests/` | Automated checks for backend, simulation, audio, and UI-facing bridge behavior | Relevant source module |
| `docs/` | Durable behavior/design guidance, research findings, and integration proposals | [Documentation guide](../README.md) |
| `experiment_data/` | Local participant and search records; gitignored | Never overwrite or publish as source material |

The root [README](../../README.md) covers setup, dependencies, and launching. `./launch.sh` starts the development app; `cd desktop && npm run dev` runs Vite only.

## Runtime data flow

```text
React UI
  ↕ Tauri commands/events
Rust desktop shell
  ↕ newline-delimited JSON over standard input/output
Python backend.sidecar
  ├─ SimulatorController → VehicleModel
  ├─ live search → candidate profiles and local session records
  └─ Pybind11 binding → native C++ SoundEngine → PortAudio
```

The UI sends commands and displays snapshots. The Python controller owns live application state and passes pedal inputs to the vehicle model. The experiment search proposes sound profiles but does not alter vehicle physics. The controller passes vehicle state and the active profile to the C++ engine. Sound output does not feed back into simulated torque or acceleration.

## Change boundaries

- Change `simulation/` when vehicle motion, braking, battery limits, or pedal behavior changes. Keep its intended behavior in [Vehicle physics](vehicle_physics.md).
- Change `audio/` when synthesis or sound-to-state mapping changes. Keep the existing method's behavior contract in [Sound behavior](sound_behavior.md); keep the source-first proposal separate in [Source-first sound approach](../design/source_first_sound_approach.md).
- Change `experiment/` when candidate generation, comparison feedback, or preference policy changes. Keep the search goal and current policy in [Interactive algorithm](interactive_algorithm.md).
- Change `desktop/` or `backend/` when the interface, transport, or command flow changes. Update this guide only when ownership or data flow changes in a lasting way.

Do not move responsibilities between layers just to avoid a small interface change. Keep UI presentation, vehicle physics, audio rendering, and search policy independently understandable and recordable.
