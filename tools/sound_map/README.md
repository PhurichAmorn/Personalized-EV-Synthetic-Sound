# Sound map: guardrail + generator

Generates a varied library of EV sounds with no listening and no training. The checked library is the pool of the app's
sound-map search (`experiment/source_search.py` `SoundMapDiscovery`, see `docs/system/interactive_algorithm.md`).

- **Guardrail** (`score.py`): rule-based psychoacoustic check with [MoSQITo](https://github.com/Eomys/MoSQITo).
  It rejects a sound if, at cruising or full-pedal pitch, sharpness > 1.3 acum, roughness > 0.3 asper, pulsing > 0.4, or crowding > 70
  (pairs of audible partials above 1 kHz closer than a quarter critical band after the pedal-following low-pass; heard as noise or wind).
  The limits were read off the listener's labels (`labelled.ts`; crowding from the sound-map marks of 2026-11-16). They reject both dropped
  sounds (Growl, Sci-fi sweep) and Pulse, and pass all 22 kept sounds. They miss the early Digital and the 7.5x Electric whine (both only "Maybe").
  Not covered by any rule: bells heard as "too high" and the darkest sounds heard as "too dark"; the closest metrics would also reject kept sounds.
- **Generator** (`generate.py`): MAP-Elites. A grid of kinds of sound (3 pitch registers x 5 brightness steps x 6 textures = 90 boxes)
  starts from the kept sounds, then mutates and crosses settings of the app's own synth (`desktop/src/plainSource.ts`; air stays 0 as in
  every preset). Each box keeps the passing sound with the most room under the limits, plus 4 runners-up.
- **Full-drive check** (`drive.py`, `drive.ts`, `chain.ts`): renders each winner through the app's real chain (granular player, drive mapping,
  `labEngine` nodes replayed offline) over the 22 s simulated drive and applies the guardrail to the worst moment. Rising decides; Evolving is
  recorded only (it rejects the kept Pure tone: pulsing 0.46). A failing winner is replaced by its box's best passing runner-up.
- **Listening page** (`page/sound-map.html`): grid of the library; click to hear a sound on the 22 s drive (the same render the check judged),
  mark bad sounds, copy the marks.

## Setup (any OS)

Needs Node (the app's `desktop/node_modules`, so run `npm ci` in `desktop/` first) and Python 3.12.

```
python -m venv .venv-soundmap
.venv-soundmap/bin/pip install -r tools/sound_map/requirements.txt      # Windows: .venv-soundmap\Scripts\pip
```

## Run

```
python tools/sound_map/score.py            # guardrail self-check on the labelled sounds, about 4 min; must print "guardrail check OK"
python tools/sound_map/drive.py labelled   # full-drive self-check; must print "full-drive check OK"
python tools/sound_map/generate.py 40      # 40 rounds x 140 sounds, about 12 min on 16 cores; out/library.json is rewritten every round
python tools/sound_map/drive.py library    # full-drive check of every winner; writes experiment/sound_map_pool.json for the app
python -m tools.benchmark_sound_map        # simulated listeners: sound-map search vs random challengers
```

Everything else is written to `tools/sound_map/out/` (git-ignored). To view: publish `page/sound-map.html` with `out/library.json` and
`out/synth.js` beside it. Marks are kept per library (a new run puts new sounds in the same boxes).

## Known gaps

The check skips reverb tails beyond the drive, vibrato and chorus settings of library sounds (they use the search defaults), and level:
everything is judged at a fixed 70 dB. Neighbouring boxes can sound alike (66 of 90 sounds have a near-twin under the app's 0.10 distance),
because every sound comes from one synth and each box keeps its safest sound.
