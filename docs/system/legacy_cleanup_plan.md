# Legacy search cleanup plan

Goal: the current session (Best guess, `GuessBlocks` in `experiment/block_arms.py`) is what people and agents see first when they read the
search code. Older searches move to `experiment/legacy/`. Everything stays in git, so every move is reversible.

## Done (2026-11-27)

1. The app offers two searches: Best guess (default) and Building blocks (previous). Sound families (`tuning`), Sound map (`map`) and the five
   Building blocks variants (`blocks-random`, `-robust`, `-pbo`, `-duel`, `-infogain`) left the menu (`desktop/src/SourceSearch.tsx`) and
   `backend/bridge.py`. The variants' code stays in `experiment/block_arms.py`: the benchmark uses their mixins.
2. The Sound map sessions (`RegionMapDiscovery`, `StyleMapDiscovery`, `HeardMapDiscovery`, `map_regions`, `map_style` and the constants only
   they use) moved to `experiment/legacy/map_search.py`. Importers updated: `tests/test_source_search.py`, `tools/benchmark_sound_map.py`.
   The map tests stay in `tests/test_source_search.py`: they share a test class with `SoundMapDiscovery` tests.
3. The old benchmark docs are marked out of date; current result: `docs/research/benchmark_guess_results.md`.

## Next (after the pilot, with all tests running)

Best guess still inherits through `BlockDiscovery` -> `SoundMapDiscovery` -> `TuningDiscovery` -> `LevelDiscovery` -> `StyleDiscovery` ->
`SourceDiscovery`. To move those to legacy:

1. Make the session stand alone: copy into it the few parent methods it uses (start and motion pair, choice feedback, Bayesian
   Bradley-Terry posterior and Thompson sample, export, history save hooks), with the tests running after each step.
2. Decide whether Building blocks stays as a fallback. If not, move `BlockDiscovery` and its parents to `experiment/legacy/`; if it stays,
   it keeps its chain and only the unused classes (`OpenDiscovery`, `StyleDiscovery`-only helpers) move.
3. Move the old benchmark harness arms that only compare Building blocks variants into a legacy section of `tools/benchmark_blocks.py`
   or keep them as they are; they are cheap to keep.

Do this only after the pilot: it touches the core of the session participants use.
