# Sound map: guardrail + generator

Generates a varied library of EV sounds with no listening and no training. The checked library is the pool of the app's
sound-map search (`experiment/source_search.py` `SoundMapDiscovery`, see `docs/system/interactive_algorithm.md`).

- **Guardrail** (`score.py`): rule-based psychoacoustic check with [MoSQITo](https://github.com/Eomys/MoSQITo).
  It rejects a sound if, at cruising or full-pedal pitch, sharpness > 1.3 acum, roughness > 0.3 asper, pulsing > 0.4, or crowding > 70
  (pairs of audible partials above 1 kHz closer than a quarter critical band after the pedal-following low-pass; heard as noise or wind).
  The limits were read off the listener's labels (`labelled.ts`; crowding from the sound-map marks of 2026-11-16). They reject both dropped
  sounds (Growl, Sci-fi sweep) and Pulse, and pass all 22 kept sounds. They miss the early Digital and the 7.5x Electric whine (both only "Maybe").
  Not covered by any rule: bells heard as "too high" and the darkest sounds heard as "too dark"; the closest metrics would also reject kept sounds.
- **Generator** (`generate.py`): an open archive, no grid and no size limit. Two voices (`desktop/src/mapVoice.ts`): the app's plain synth
  (`plainSource.ts`; air stays 0 as in every preset) and the generic `blocks` voice (`sourceDesigner.ts`: harmonic slope, two resonant peaks,
  FM, noise band, waveshaper, amplitude modulation, inharmonic partials; each block off unless switched on). Starts from random sounds
  (`--seeds` adds the listener's kept sounds), then mutates and crosses them. Effects are searched per sound too: tone, resonance, tremolo,
  reverb, chorus, engine vibrato (up to 20 cents; never baked into the loop) and body EQ. A passing sound is kept if it clearly differs from
  every kept sound on at least one heard trait: octave-band spectrum (0.4), pitch (7 semitones), inharmonic share (0.4), roughness (0.15),
  pulsing (0.2), chorus (1.2) or vibrato (12 cents); all steps provisional (v2's smaller steps were heard as alike). Among near-copies the one with more room under the limits stays
  (novelty search with local competition). The archive grows until new sounds stop being different.
- **Full-drive check** (`drive.py`, `drive.ts`, `chain.ts`): renders each winner through the app's real chain (granular player, drive mapping,
  `labEngine` nodes replayed offline) over the 22 s simulated drive and applies the guardrail to the worst moment. Rising decides; Evolving is
  recorded only (it rejects the kept Pure tone: pulsing 0.46). Sounds that fail are dropped.
- **Listening page** (`page/sound-map.html`): map of the library (across = spectral centre, up = pitch, colour = voice); click to hear a
  sound on the 22 s drive (the same render the check judged), mark bad sounds, copy the marks.

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
python tools/sound_map/drive.py library    # full-drive check of every kept sound; writes experiment/sound_map_pool.json for the app
python tools/sound_map/drive.py pool       # Evolving check of the pool; sounds that pass may be used when the driver picks Evolving in pair 1
# roles (2026-11-18): stack sounds carry per-player trends (body / middle / top: level at rest, at full drive, pedal-or-speed mix).
# generate.py prints a coverage table at the end and writes <library>.trials.jsonl (every try, passed or not: data to learn safe settings from).
# Sparkle (texture 4) is no longer generated: its pings clicked (softer start, full tail and slow bloom did not help).
# app pool from the per-style libraries (12 diverse per style + 12 blends from the old pool):
python tools/sound_map/build_pool.py experiment/sound_map_pool.json saved/pool.style-electric.json saved/pool.style-strings.json saved/pool.style-glass.json saved/pool.style-choir.json saved/pool.style-plain.json --blends old_pool.json
# phase 2: checked variations of every pool sound (one move each), written into the pool file (about 1 h with 14 workers):
LIMIT_F=0.2 python tools/sound_map/variations.py experiment/sound_map_pool.json
# style libraries (5 texture families: electric, strings, glass, choir, plain; at least half the layers of that family), one per run:
LIMIT_F=0.2 SEED=11 LIBRARY=library.style-strings.json python tools/sound_map/generate.py 20 --style strings
LIMIT_F=0.2 LIBRARY=library.style-strings.json POOL=$PWD/tools/sound_map/out/pool.style-strings.json python tools/sound_map/drive.py library
python -m tools.benchmark_sound_map        # simulated listeners: sound-map search vs random challengers
python tools/sound_map/calibrate.py 600    # quick check vs full-drive check on 600 sounds, about 17 min; suggests quick limits
```

Everything else is written to `tools/sound_map/out/` (git-ignored). To view: publish `page/sound-map.html` with `out/library.json` and
`out/synth.js` beside it. Marks are kept per library (a new run makes new sounds).

## Known gaps

The quick check skips chorus, vibrato and body EQ (the full-drive check renders them). The full-drive check skips reverb tails beyond the drive, and level:
everything is judged at a fixed 70 dB. Blocks sounds pass the guardrail far less often than plain ones (about 1 in 4 random ones; mostly roughness).
The guardrail limits were read off plain-synth sounds only; new kinds of sound (FM, noise, grit) have not been labelled yet.
