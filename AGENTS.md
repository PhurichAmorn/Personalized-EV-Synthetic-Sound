# Project instructions

## Purpose and scope

EV Sound Lab is an internal desktop research prototype for driving a simplified EV model and exploring procedural in-cabin sound. It includes an interactive A/B sound-search demo. Treat vehicle specifications, sound mappings, and experiment results as provisional research artifacts, not validated OEM behavior or production calibration.

For user setup and launch instructions, see [README.md](README.md).

## Project map

- `desktop/`: Tauri desktop shell and React interface; `backend/`: Python simulator sidecar, controller, gamepad input, and audio output monitor.
- `simulation/vehicle_model.py`: longitudinal vehicle and powertrain simulation.
- `audio/`: standalone C++ sound behavior, synthesis, presets, validation and device output. `audio/__init__.py`: required native desktop binding.
- `experiment/`: interactive search, `preference_gp.py`, and experiment records.
- `tests/`: automated checks; `tools/`: development utilities.

Keep UI, simulation, audio, and experiment responsibilities separated. Check relevant callers and docs before changing shared inputs, state, or data flow.

## Behavior references

- [Sound behavior](docs/sound_behavior.md): sound inputs, synthesis mapping, tuning parameters, and research references.
- [Interactive search](docs/interactive_search.md): A/B workflow, candidate mutations, parameter bounds, and data persistence.
- [Pedal behavior](docs/pedal_behavior.md): pedal map, coasting, regeneration, braking, and known calibration limits.
- [README.md](README.md): user-facing overview, launch instructions, and current application features.

These docs are the source of truth for documented behavior and assumptions. Update the relevant doc when changing that behavior; avoid copying detailed parameter tables into this file.

## Working rules

- Preserve existing simulation, audio, UI, and experiment behavior unless the request explicitly changes it.
- Keep changes within the requested layer; do not alter vehicle physics while changing sound, or sound generation while changing UI.
- Preserve phase continuity, smoothing, audio headroom, and experiment-record integrity when touching audio or search code.
- `experiment_data/` contains local participant/session data and must remain untracked. Do not expose or overwrite it during code changes.
- Do not describe procedural sounds or vehicle presets as exact manufacturer reproductions or validated calibrations.
- Use the existing project environment. `./launch.sh` prepares dependencies and runs Tauri in development mode. Automated checks: `.venv/bin/python -m unittest discover -s tests -v` and `cd desktop && npm run build`.
- For Tauri changes, use `cd desktop && npm run tauri dev` while editing. Release packaging is deferred for this research prototype.
- If C++ audio code changed, rebuild its Python binding with `.venv/bin/python setup.py build_ext --inplace` before checking the Tauri app. Report any build or launch failure instead of claiming the app is updated.
