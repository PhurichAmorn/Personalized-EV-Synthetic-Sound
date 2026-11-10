# Project instructions

## Purpose and scope

EV Sound Lab is an internal desktop research prototype for exploring personalized, vehicle-responsive EV cabin sound through interactive preference learning. The simplified vehicle is an experimental context; it is not a validated vehicle model or production calibration. OEM sound references inform original sound design, not claims of exact reproduction.

For user setup and launch instructions, see [README.md](README.md).

## Project map

Read [the project architecture guide](docs/system/project_architecture.md) for repository ownership and runtime data flow. Main layers:

- `desktop/`: Tauri shell and React interface.
- `backend/`: Python sidecar, controller, command bridge, gamepad, and audio monitoring.
- `simulation/`: vehicle and powertrain model.
- `audio/`: native C++ sound engine and Python binding.
- `experiment/`: interactive candidate search and local session records.
- `beamng/`: BeamNG telemetry protocol mod (sends vehicle state to the app over local UDP).
- `tools/`: offline rendering and analysis.
- `tests/`: automated checks.

## Project documents

[Documentation guide](docs/README.md) explains each document's purpose and when to read it.

- [Vehicle physics](docs/system/vehicle_physics.md): intended vehicle and pedal behavior.
- [Interactive algorithm](docs/system/interactive_algorithm.md): search goal, listener feedback, and current comparison policy.
- [Sound behavior](docs/system/sound_behavior.md): existing procedural oscillator method and state mapping; baseline method.
- [Source-first sound approach](docs/design/source_first_sound_approach.md): separate proposed method; not integrated into driving audio.
- [Research notes](docs/research/sound_design_research.md) and [interactive search research](docs/research/interactive_search_research.md): evidence and limits behind design choices.
- [BeamNG integration](docs/integrations/beamng_audio_integration.md): telemetry mod, UDP receiver, and always-on-top overlay are implemented. BeamNG's own drivetrain sound is not muted. The in-game FMOD path is a proposal only.

## How to use documentation

These documents are durable project goals, behavior contracts, architecture boundaries, and research summaries—not a changelog. Read the relevant guide before changing its code layer. Keep intended outcome distinct from implementation status; label proposals as not implemented. Research claims should identify their source and limits; separate published findings from project interpretation.

Do not update docs for every feature, UI, or parameter edit. Update a guide when project intent, a stable behavior contract, a layer boundary, a significant research conclusion, or method status changes. Source code is authoritative for exact implementation values. Keep temporary experiments in their own analysis or session record rather than adding them to stable guides.

## Working rules

- Preserve existing simulation, audio, UI, and experiment behavior unless the request explicitly changes it.
- Keep changes within the requested layer; do not alter vehicle physics while changing sound, or sound generation while changing UI.
- Preserve phase continuity, smoothing, audio headroom, and experiment-record integrity when touching audio or search code.
- `experiment_data/` contains local participant/session data and must remain untracked. Do not expose or overwrite it during code changes.
- Do not describe procedural sounds or vehicle presets as exact manufacturer reproductions or validated calibrations.
- Preserve the existing procedural sound method as a baseline while source-first sound design remains a separate research direction.
- Use the existing project environment. `./launch.sh` prepares dependencies and runs Tauri in development mode. Automated checks: `.venv/bin/python -m unittest discover -s tests -v` and `cd desktop && npm run build`.
- For Tauri changes, use `cd desktop && npm run tauri dev` while editing. Release packaging is deferred for this research prototype.
- If C++ audio code changed, rebuild its Python binding with `.venv/bin/python setup.py build_ext --inplace` before checking the Tauri app. Report any build or launch failure instead of claiming the app is updated.
