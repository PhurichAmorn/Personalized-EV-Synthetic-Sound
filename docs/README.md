# Documentation guide

These documents help developers, researchers, and AI agents understand the project's goal, behavior contracts, current methods, and research basis. They are durable guides, not a change log. Read the relevant guide before changing a system layer; use source code for exact current implementation values.

## Start here

| Document | What it covers | Use it when |
| --- | --- | --- |
| [Project architecture](system/project_architecture.md) | Repository ownership, runtime flow, and boundaries between UI, backend, physics, search, and audio | Locating a feature or changing data flow/layer ownership |
| [Vehicle physics](system/vehicle_physics.md) | Intended vehicle and pedal behavior, limits, and calibration caveats | Changing acceleration, coasting, braking, or regeneration |
| [Interactive algorithm](system/interactive_algorithm.md) | Search purpose, listener feedback, candidate schedule, persistence, and current version | Changing comparisons, algorithms, candidate generation, or session records |
| [Source-search benchmark](system/source_search_benchmark.md) | Simulated-listener benchmark for source-discovery approaches: procedure, targets, metrics, results | Changing the source pool or search, or comparing approaches |
| [Sound behavior](system/sound_behavior.md) | Existing procedural C++ method and its vehicle-state mapping | Changing the current sound engine or defining its role as the baseline |
| [Source-first sound approach](design/source_first_sound_approach.md) | Proposed new method: sound material, renderer, mapping, listening goals, and validation order | Working on the second sound-generation method; it is not yet integrated |
| [Generated source plan](design/generated_source_plan.md) | Proposed pilot: text-to-audio source clips, conditioning, listening check, and git policy for generated audio | Generating or evaluating new source material; not implemented |

## Research and integration references

- [Sound design research](research/sound_design_research.md): findings from acoustics/music studies, OEM references, and the supplied audio analyses. Each finding states its source and limits.
- [Interactive preference research](research/interactive_search_research.md): IEC, pairwise GP/PBO, and music-preference evidence; distinguishes research results from project proposals.
- [Personalization approaches](research/personalization_approaches.md): literature review of alternatives to rating-based IEC, granular and AI source generation, OEM EV sound practice, and comfort guards; [supporting notes](research/personalization_approaches_notes/). Some sources were seen only as abstracts or snippets; the notes flag them.
- [GS personalization baseline](research/gs_personalization_baseline.md): perceptual control groups, granular qualification, parameter sensitivity and recorded-string/hall baseline comparison; audition implemented, parameter search still proposed.
- [BeamNG integration](integrations/beamng_audio_integration.md): how to run the app from BeamNG telemetry with the overlay (implemented), plus the proposed in-game FMOD audio path (not implemented).

The repository [README](../README.md) covers setup and technology stack. Tauri is the current desktop UI; no migration-status document is maintained.

## How to read and update these documents

- **Design intent** says what a method should achieve and what constraints matter.
- **Implementation snapshot** briefly describes how the current app realizes that intent. Code is authoritative for exact values and control flow.
- **Research finding** summarizes what a cited paper, standard, manufacturer, or supplied audio sample supports. It must also state important limits.
- **Proposal** describes a method that has not been implemented. Never present it as current system behavior.

Do not update a guide for every code, UI, or tuning edit. Update it when a stable outcome, behavioral contract, layer boundary, research conclusion, or implementation status changes enough to affect future work. Keep experimental details in code, session records, or a focused analysis rather than growing these guides into a chronological diary.

Generated files under `artifacts/` are disposable outputs, not canonical requirements. Prefer the maintained guides and cited research above; recreate outputs with their documented tools when needed.
