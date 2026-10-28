# Sound exploration notes

Unimplemented ideas for future listening experiments. These are not part of the current sound behavior contract.

## Slow LFO / organic drift

**Status:** idea only; not implemented.

**Hypothesis:** slow, low-depth modulation can reduce the static, synthetic quality of sustained EV tones and improve perceived naturalness.

Possible modulation targets:

- Amplitude: `0.05–0.4 Hz`, `1–3%` depth.
- Pitch: `0.02–0.15 Hz`, `±3–6 cents`; larger depth risks sounding detuned or warbly.
- Filter cutoff: `0.05–0.5 Hz`, `5–10%` depth.
- Two unsynchronized slow rates (for example `0.11` and `0.17 Hz`) to hide an obvious cycle.
- Seeded random walk or sample-and-hold instead of a pure periodic LFO; seeded per candidate for repeatable A/B comparison.

**Search parameter candidate:** one macro such as `organic` or `motion` (`0–1`) combining mostly amplitude and cutoff drift with very small pitch drift. Keep rates fixed or profile-specific rather than adding separate rate and depth search dimensions.

**Risks:** periodic modulation can sound robotic; pitch modulation can weaken tonalness and speed perception; loudness differences can confound A/B preference. Any prototype needs RMS matching, phase continuity across A/B switches, and deterministic seeds recorded with candidate data.

**Related implementation:** existing `electric_pulse` provides rhythmic modulation and `electric_whirl` moves an upper partial. This idea is distinct: slow decorrelation of sustained layers.
