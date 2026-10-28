# Tauri migration status

Tauri/React is the sole development UI. `./launch.sh` prepares Python and npm dependencies, builds the required C++ audio binding, then runs `tauri dev`. The old QML launcher, views, and UI-only tests have been retired. Python controller, gamepad input, and audio output monitoring remain in `backend/` for the sidecar. PySide6 remains necessary for their QtCore and QtMultimedia APIs.

The Tauri sidecar runs `.venv/bin/python -m backend.sidecar` from this checkout. Driving, presets, interactive A/B search, session history, TRACE replay, and separate telemetry and sound signal windows are available. Session data stays under local, gitignored `experiment_data/`; no participant data migration was needed. The orphaned QML manual experiment dialog was removed; its `experiment/experiment_manager.py` service remains because controller and backend tests still use it.

Release packaging is deferred. The app currently requires this checkout and its Python environment. Check with `.venv/bin/python -m unittest discover -s tests -v`, `cd desktop && npm run build`, and `node --experimental-strip-types --test desktop/src/client.test.ts`.
