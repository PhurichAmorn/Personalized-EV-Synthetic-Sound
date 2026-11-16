# Sound map: guardrail + generator

Generates a varied library of EV sounds with no listening and no training.

- **Guardrail** (`score.py`): rule-based psychoacoustic check with [MoSQITo](https://github.com/Eomys/MoSQITo).
  It rejects a sound if, at cruising or full-pedal pitch, sharpness > 1.3 acum, roughness > 0.3 asper or pulsing > 0.4.
  The limits were read off the listener's labels (`labelled.ts`). They reject both dropped sounds (Growl, Sci-fi sweep) and Pulse,
  and pass all 22 kept sounds. They miss the early Digital and the 7.5x Electric whine (both only "Maybe"; a tonality measure would cover the whine).
- **Generator** (`generate.py`): MAP-Elites. A grid of kinds of sound (3 pitch registers x 5 brightness steps x 6 textures = 90 boxes)
  starts from the kept sounds, then mutates and crosses settings of the app's own synth (`desktop/src/plainSource.ts`).
  Each box keeps the passing sound with the most room under the guardrail limits.
- **Listening page** (`page/sound-map.html`): grid of the library; click to hear, mark bad sounds, copy the marks.

## Setup (any OS)

Needs Node (the app's `desktop/node_modules`, so run `npm ci` in `desktop/` first) and Python 3.12.

```
python -m venv .venv-soundmap
.venv-soundmap/bin/pip install -r tools/sound_map/requirements.txt      # Windows: .venv-soundmap\Scripts\pip
```

## Run

```
python tools/sound_map/score.py         # guardrail self-check on the labelled sounds, about 4 min; must print "guardrail check OK"
python tools/sound_map/generate.py 40   # 40 rounds x 140 sounds, about 45 min on 8 cores; out/library.json is rewritten every round
```

Everything is written to `tools/sound_map/out/` (git-ignored). To view: publish `page/sound-map.html` with `out/library.json` and `out/synth.js` beside it.

## Known gap

The check renders the source loop with pitch shift, pedal-following filter, swell/pump and drift at two fixed pitches.
It skips the granular player used in Rising/Evolving mode, the pitch glide between the two pitches, reverb, chorus and vibrato.
Next step: run each winner through the app's real chain (`desktop/public/audio/granular-processor.mjs` + the 22 s simulated drive) and check the worst moment.
