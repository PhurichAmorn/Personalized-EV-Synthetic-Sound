# Legacy search cleanup plan (not done yet)

Goal: Building blocks (`BlockDiscovery`) is the only search in the app. The two older searches are hidden from the listener and moved out of the main code path, so people and agents reading `experiment/source_search.py` see the current system first. Everything stays in git, so the move is reversible.

## What can move, and what cannot

- **Cannot move yet: Sound families (`TuningDiscovery`).** `BlockDiscovery` inherits through `SoundMapDiscovery` -> `TuningDiscovery` -> `LevelDiscovery` -> `StyleDiscovery` -> `SourceDiscovery`. These stay in `source_search.py` until Building blocks stops inheriting from them (separate refactor, done with the tests running).
- **Can move: the Sound map session classes** `RegionMapDiscovery`, `StyleMapDiscovery`, `HeardMapDiscovery` (about 260 lines, `source_search.py` lines 1314-1576). Nothing in Building blocks uses them.

## Steps

1. Move the three Sound map classes (and constants only they use) to `experiment/legacy/map_search.py`.
2. `backend/bridge.py`: keep only `'blocks': BlockDiscovery()` in `self.searches`.
3. `desktop/src/SourceSearch.tsx`: remove the search dropdown (`tuning` / `map` / `blocks`); the session always uses blocks.
4. Tests: move the map tests from `tests/test_source_search.py` to a legacy test file; fix imports in `tools/benchmark_sound_map.py` and `tools/sound_map/grow.py`.
5. Docs: mark the Sound map and Sound families sections in `docs/system/interactive_algorithm.md` as legacy.
6. Run all Python tests and the desktop build; check one block session end to end.

## Later (separate step)

Make `BlockDiscovery` stand alone (copy the few parent methods it uses), then move `SourceDiscovery`, `StyleDiscovery`, `LevelDiscovery`, `TuningDiscovery` and `SoundMapDiscovery` to legacy as well.

## Open

- The study baseline (menu of the 4 starts) is a question for the professor; see the study discussion.
