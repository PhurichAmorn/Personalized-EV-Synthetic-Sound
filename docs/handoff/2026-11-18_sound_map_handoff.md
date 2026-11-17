# Handoff: sound-map search and layered sounds (2026-11-18)

Temporary session record for moving the work off the VPS (down for about a week). Not a stable guide: stable behaviour lives in
[interactive algorithm](../system/interactive_algorithm.md) and [`tools/sound_map/README.md`](../../tools/sound_map/README.md).
Branch: `sound-map-search`. Working rules: commit and push only on the owner's word, commits under the owner's name with no
assistant attribution, never touch or commit `experiment_data/`.

## Where things stand

| Piece | State |
|---|---|
| Sound-map search in the app (Personalize sound, selector "Sound map") | Pushed up to `870b128` (pool v4: vibrato capped at 8 cents, opening from the middle ring). |
| Region search (`RegionMapDiscovery`, policy `source-map-regions-1`) | Built, tests pass, **in this handoff's commit**. The app's "Sound map" now uses it: 6 regions (k-means on the 9 traits); pairs 1-3 each region's typical sound (same for everyone); pairs 4-10 regions compete (Thompson sample of region win rates); pairs 11-19 winner stays, challengers from the best region (70%) or the runner-up; two Neither answers open the next region; pair 20 podium #1 vs #2. Simulated listeners (400, v4 pool): top 10% in 44% of sessions vs 37% (v5) and 35% (random). |
| GS sound picker | Pushed (`d572b3f`): dropdown of each saved session's final sound; choice kept across restarts. |
| Octave-stack voice (`desktop/src/stackVoice.ts`, map voice kind `stack`) | Built. The same note in 3-5 octave layers, each with its own texture and slow swell, played by the granular player like any sound; a fixed after-player low peak and low-pass (the engine stage) keeps it deep. |
| Layered textures (the stack as a frame) | Built. Each layer picks one of 12 textures: plain, strings, hollow, glass, sparkle, air, choir, strings pad, cello, electric, plain synth voice, blocks voice. Inside a stack: no chorus, no detuned copies (ensemble 0, detune 0). The generator excludes air. |
| Pools | App pool unchanged: `experiment/sound_map_pool.json` (v4, plain + blocks, 118 sounds). Listening-only pools in `tools/sound_map/out/` (git-ignored): `library.stack.json` (67 stacks), `library.frame.json` (layered textures, no air, pulsing limit 0.2: 75 grown, **61 pass the full drive**, pulsing at most 0.19;
`out/frame_pool.json`). Electric is in 70 of the layers (it stands out, so novelty favours it); cap a texture's share if the pool
sounds too electric. Saved copies (tracked, since `out/` is git-ignored): `tools/sound_map/saved/layered_pool.json` (app-pool format, 61 sounds), `saved/library.layered.json` and `saved/library.stack.json` (full libraries with genomes, for merging and phase 2). **To make the layered pool the app pool**: copy `saved/layered_pool.json` to `experiment/sound_map_pool.json` (not done yet: the owner has not decided). |
| Listening page | https://claude.ai/artifact/H89g7zWjEHCqK8wdyvjLjE (private). Pool switch (current / octave stacks / layered textures), feeling ratings (Calm, Sport, Deep / futuristic, None / mixed; clear or a bit) saved to the page's store, Octave-layer clips. |

## Findings to keep

- **Chorus was a stand-in for depth.** Layers give dimension; the layered voice runs with no chorus.
- **Ghostly sessions came from the pool**: v3 had 61% of sounds over 10 cents of vibrato. Capped at 8 cents (v4).
- **Low fifths read as roughness** (partials one root apart): fifths only from 220 Hz up.
- **Listening marks on layered textures (2026-11-18, 33 marked of 75)**: marked sounds pulsed more (median pulsing 0.30 vs 0.17) and
  held air far more often (12/33 vs 5/42). Wind = air texture (removed). "Up and down like a jet ski" = beating of detuned copies
  (removed inside stacks). Clicking = sparkle pings; kept as they are, the stricter pulsing limit (`LIMIT_F=0.2`) drops the clicky ones
  (on the marks it would have dropped 28 of 33 marked, kept 25 of 42 unmarked).
- **Local competition** (generator): near-copies that are both comfortably inside the guardrail (margin >= 0.25) now keep the more
  novel one; always keeping the safer one had pulled stacks to their darkest settings.
- **Layer texture is invisible to the model and the "distinct" measure** (9 traits). Needed before phase 2 can steer.
- Shepard tone: tried (additive and granular with crossfade: clicks measured 1.5x vs 6.95x without prevention); parked in favour of
  stacks (the owner wants the layered feel, not an endless rise, and not high).

## Running on another machine

App only (sessions, GS, BeamNG): `git pull`, then `./launch.sh`. No generation needed; pools are files.
Cost measured on the VPS (Core Ultra 7 265F): building a heavy layered sound about 1.9 s once per sound (cached), playback about 3% of
one core. On a laptop expect 2-3x. Avoid building new sounds while BeamNG runs (see plan item 2).

Regenerating pools (heavy). Use the i7 laptop, not the Mac (no cooling), and cap workers:

```
python -m venv .venv-soundmap && .venv-soundmap/bin/pip install -r tools/sound_map/requirements.txt
cd desktop && npm ci && cd ..
node tools/sound_map/build.mjs
# layered-texture pool (separate files; the app pool is untouched):
WORKERS=4 LIMIT_F=0.2 LIBRARY=library.frame.json .venv-soundmap/bin/python tools/sound_map/generate.py 40 --voices stack --textures all
WORKERS=4 LIMIT_F=0.2 LIBRARY=library.frame.json POOL=$PWD/tools/sound_map/out/frame_pool.json .venv-soundmap/bin/python tools/sound_map/drive.py library
```

On the VPS (16 cores) one layered pool took about 25 min; with 4 workers on a laptop expect 2-3 h. Run **one generation per machine at
a time**: two runs share `out/` (batch files, `tmp/`) and break each other.

Splitting across machines (islands): each machine grows its own library with a different `SEED` (VPS used 1) and the same code and
settings; `merge.py` combines them with the generator's own archive rule and refuses libraries made with other settings (`config`).
`--resume` continues a saved library (for Colab disconnects); the library is saved after every round. Google Colab: open
`tools/sound_map/colab.ipynb` (File > Open notebook > GitHub, branch `sound-map-search`) and Run all; it saves to Google Drive
`ev-sound-map/library.seedN.json`. Free Colab works (about 2 cores, slow); a paid plan only adds longer sessions and sometimes cores.

```
python tools/sound_map/merge.py out/library.seed1.json out/library.seed4.json -o out/library.frame.json
# full-drive check, optionally split: --part 1/2 here, --part 2/2 elsewhere, copy the part files next to the library, then --parts 2
LIMIT_F=0.2 LIBRARY=library.frame.json POOL=$PWD/tools/sound_map/out/frame_pool.json python tools/sound_map/drive.py library --part 1/2
```

Offline test sets:
`python tools/sound_map/orchestra.py octaves` (also `orchestra`, `shepard`). Checks: `.venv/bin/python -m unittest discover -s tests -v`
(errors from a missing `libpulse.so.0` are environment-only) and `cd desktop && npm run build`.

## Plan

Phase 1 (fixed pool), to finish:
1. Owner listens to the regenerated layered pool; decide whether it becomes the app pool (stacks alone, or mixed with plain + blocks).
2. Laptop safety: save the chosen sound's built loop to disk so GS loads it instantly in BeamNG; build the next challenger early in
   a session so there is never a wait.
3. Pair 1 asks Rising or Evolving. The full-drive check must then also gate Evolving (today only Rising is gated).
4. Feeling groups (Calm, Sport, Deep / futuristic): owner (and optionally one more person) rates sounds on the page; fit which traits
   predict each feeling; label every sound; use feeling groups as the opening regions (a starting point, not a hard filter).
   Labelling is hard on the current sounds; discuss before relying on it.
5. Add a texture trait to the model (which textures are in the layers) and to "distinct".
6. Run sessions with other people; analyse the session JSONs (do people end on different sounds and textures?).

Phase 2 (fine-tune around the favourite):
- Pairs 17-20 offer variations of the favourite (swap one layer's texture, levels, low-pass, pitch, swell).
- Precompute offline: about 10 guardrail-checked, audibly different neighbours per pool sound, so the laptop never generates during a
  session. `tools/sound_map/grow.py` (live-growing prototype, simulation only) has the variation and check code to reuse.
- Needs the texture trait first; then simulated listeners vs pool-only, then real listeners.

Proposed, waiting for the owner: per-pair "why" reasons and a session report (explainability); a mid-session "happy with your
favourite?" check; research notes into `docs/research/` (grouping, preference learning; sources gathered 2026-11-17).
Parked: learning pairs (EUBO), the 200 Hz pitch ceiling.
