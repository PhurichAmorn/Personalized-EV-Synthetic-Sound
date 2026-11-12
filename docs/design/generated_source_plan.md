# Generated source material plan

**Status: proposal. Nothing in this document is implemented.** It covers only the first step: generating source sounds with a text-to-audio model and checking their quality. The listener-facing selection flow and tuning sliders are separate later work.

Background and citations: [personalization approaches report](../research/personalization_approaches.md) and its [sound generation notes](../research/personalization_approaches_notes/sound_generation_techniques.md).

## Change of approach

| | Current | Proposed |
| --- | --- | --- |
| Where sound character comes from | Six original synthetic generators (additive/FM), all at a 174.8 Hz root | A library of external source clips: text-to-audio renders first, recordings later |
| What gets tuned | Generator macros (body, harmonic character, ensemble, movement) | Granular rendering and driving response of a chosen source |
| Granular settings | One fixed configuration for every source (160 ms Hann grains, 40 ms hop, no scatter) | Per-source settings, and some exposed to the listener |
| Source length | 5-second loops | Longer clips with randomized grain read positions |

Rationale: the report traces low diversity to synthetic sources at a shared root plus one global grain configuration. Real-world practice supports source-plus-granular: Hyundai documents granular synthesis from source material, and a Hyundai-affiliated study (Lazaro et al., JAES 2022) found that sample source, grain duration, grain envelope and RPM range each changed listener ratings. Other OEMs do not disclose their method, so this is one documented industry approach, not a universal one.

The existing generators and the native procedural engine remain as baselines.

## Generation tool

Stable Audio Open (Stability AI, 2024): text-to-audio latent diffusion, stereo 44.1 kHz, up to about 47 s, trained on Creative Commons audio. Two variants to compare:

- `stabilityai/stable-audio-open-1.0` (about 1B parameters, higher quality).
- `stabilityai/stable-audio-open-small` (about 341M parameters, faster).

Both are gated on Hugging Face under the Stability AI Community License (free for research and for organizations under USD 1M revenue). Verify the current license text before generating.

Expected strengths: drones, pads, textures, mechanical and sci-fi tones. Expected weaknesses: no reliable pitch control, artifacts, muddy low end, clips that are not loopable. The pilot below tests these expectations; they are not measured yet.

Generation runs on the GPU PC. The Mac is for listening through the existing granular player.

## Pilot steps

1. **Setup (GPU PC).** Separate Python environment, not the project `.venv`. Accept both model licenses on Hugging Face and log in with `huggingface-cli login`.
2. **Prompt set.** 30–50 prompts spread across clearly different characters, for example: bowed strings, choir/vocal pad, warm analog synth, glassy/bell, metallic, turbine/mechanical hum, airy/breath, sci-fi drone, brass, organ. Keep prompts as a committed text/JSON file.
3. **Generate.** 2–3 seeds per prompt, 10–20 s per clip, both model variants. Record generation time per clip.
4. **Condition each clip** (offline script):
   - Trim silence and fade edges.
   - Estimate pitch. Tonal clips are shifted to the 174.8 Hz root; clips with no stable pitch are tagged as texture.
   - Normalize to the same RMS (0.13) and peak ceiling (0.7) used by the current generated sources.
   - Compute comfort metrics (loudness, sharpness, roughness, tonality) with MoSQITo and tag clips over provisional caps. Do not delete them yet; the pilot should show whether the caps agree with listening.
5. **Listen** on the Mac, each clip in two forms: raw, and through the existing granular player with a scripted drive. Note per clip: quality (1–5), artifacts, whether it survives granular pitch mapping, and whether it is a candidate for the library.
6. **Decide.** Continue if a useful share of clips survive granular playback and the survivors are clearly more diverse than the six current families. Also choose which model variant to keep and whether audio-to-audio variation (`stable-audio-tools` init audio) is worth testing next.

## Storage and git policy

Generated audio is **not committed**. It is large, regenerable, and subject to the model license; the project already keeps rendered audio out of git (`/.cache/`, `/artifacts/`, listening packs in `.gitignore`).

Commit instead:

- The generation and conditioning scripts (under `tools/`).
- The prompt file.
- A manifest per batch: prompt, seed, model id and revision, steps, guidance scale, duration, conditioning settings, metric values, listening notes.

The manifest makes any clip reproducible. Store audio under `.cache/generated_sources/` (already ignored) on both machines and copy batches from the PC to the Mac with a shared drive or `rsync`. If a curated set must later be shared with collaborators, use a shared drive rather than git.

## Out of scope for this step

- Listener selection flow (about 15 diverse clips, narrowed to 2–3, then tuning).
- Which granular parameters become listener sliders.
- Audio-to-audio variation of chosen clips.
- Descriptor-based (CataRT-style) grain selection by vehicle state.
- Comfort filters inside the search loop.

These follow from the report's recommended direction and get their own documents once the pilot shows the generated material is usable.

## Open questions

- Does generated material still sound good after pitch shifting across the driving range?
- Should texture (unpitched) clips be layered under a tonal source, or used alone?
- Which comfort caps match what listeners actually reject?
- Is the small model good enough, given its speed?
