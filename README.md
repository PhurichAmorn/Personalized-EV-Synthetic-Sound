# EV Sound Lab: Personalized EV Driving Sound through Interactive Preference Learning

EV Sound Lab is a desktop research prototype for personalizing procedural electric-vehicle sounds through interactive preference learning. Users compare sound pairs and provide preferences to guide the search; the process does not require listening while driving. Gaussian-process and evolutionary search are explored as methods within the broader interactive preference-learning approach. A simplified vehicle simulator is included as an optional interaction context.

**Research group:** Makoto Fukumoto Lab, FIT

## Stack

| Layer | Tech |
| --- | --- |
| Desktop shell | Tauri 2 + Rust — `desktop/src-tauri/` |
| Frontend | React 19 + TypeScript + Vite — `desktop/src/` |
| Simulator and experiment backend | Python 3.12 + PySide6 — `simulation/`, `experiment/`, `backend/` |
| Audio engine | C++17 + pybind11 — `audio/` |
| Audio output | PortAudio + sounddevice |
| Controller input | pygame + SDL |
| Numerical/audio utilities | NumPy + SciPy |
| Native build and tests | CMake |

A desktop audio output device is required to listen. A game controller is optional; keyboard controls are available.

## Repository layout

```text
├── audio/                  # C++ synthesis engine and Python bindings
├── backend/                # Python simulator sidecar and input/audio services
├── desktop/                # React frontend and Tauri/Rust shell
├── docs/                   # Research, sound behavior, and implementation notes
├── experiment/             # Preference search and session management
├── simulation/             # Vehicle and powertrain model
├── tests/                  # Python and native engine tests
├── tools/                  # Development utilities
├── launch.sh               # Environment setup and desktop development launcher
└── requirements.txt        # Python dependencies
```

## Getting started

### Requirements

Python 3.12, Node.js/npm, Rust, and a C++17 compiler. On macOS, install Xcode Command Line Tools if a compiler is not available.

### Setup

```sh
git clone https://github.com/PhurichAmorn/Personalized-EV-Synthetic-Sound.git ev-sound-lab
cd ev-sound-lab
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup.py build_ext --inplace
cd desktop
npm ci
npm run tauri dev
```

This starts the Tauri window, Vite frontend, and Python simulator sidecar. After setup, `./launch.sh` from the repository root checks the environment and starts the app. `cd desktop && npm run dev` starts Vite only; it does not start the Tauri shell or simulator sidecar. The launcher requires the native audio extension to build successfully and stops with an error if compilation fails.

## License

MIT. See [LICENSE](LICENSE).

## Research notes

- [Sound behavior and references](docs/sound_behavior.md)
- [Interactive search and experiment records](docs/interactive_search.md)
- [Pedal, coast, regen, and braking behavior](docs/pedal_behavior.md)
