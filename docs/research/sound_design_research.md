# Sound design research: evidence and project findings

## Research aim

Explore how an in-cabin EV sound can communicate vehicle state while matching a driver's sound preference. These are separate outcomes: a sound may be preferred without clearly communicating speed, acceleration, or regeneration, and a clear cue may not be pleasant. The prototype should measure both before claiming that personalization improves the driving experience.

This project generates an interior ambience sound. Exterior AVAS warning-sound findings and regulations are not directly transferable; they are noted only where methods or psychoacoustic measures may help.

This file is a source-indexed reference, not a claim that every cited technique is used in the app. Read each finding with its stated task, participants/material, and limits. OEM publications explain design goals or high-level behavior, not proprietary DSP. Analysis of supplied videos describes mixed recordings; it cannot recover vehicle inputs or isolate clean source audio by itself.

The pilot recipe windows and render measurements below are project-specific snapshots, not universal standards or permanent values. Revisit them when a listening study materially changes a guardrail; source code remains authoritative for exact active settings.

## Findings to recall

- **No universal favorite sound or frequency window:** listener groups and preferences differ. Frequency results depend on sound level, background, and listener; treat them as screening clues, not comfort or safety limits.
- **Related layers matter:** selected harmonic/subharmonic combinations can improve particular impressions, but the successful combinations are stimulus-specific. Group related controls instead of randomizing every partial independently.
- **Measure preference and usefulness separately:** liking a sound does not prove that it communicates speed, load, or regeneration. Combine preference with character descriptions and, where needed, a state-identification task.
- **OEM methods vary:** published material describes granular processing, composed source libraries, recorded/processed drive sounds, and soundscapes. Granular synthesis is one option, not a universal EV method. Exact input curves and DSP architectures are generally undisclosed.
- **The supplied clips are not synchronized experiments:** speech, road/wind/rain, compression, edits, and unknown driving state can affect measured features. A pitch or spectral change in a video is not proof of throttle/speed mapping.
- **Project implication:** preserve the current oscillator method as baseline. Evaluate an original source-first method as a separate approach; do not call either an OEM replica.

## What prior work suggests

- EV interior sound is commonly described along **Comfort/Calm**, **Power**, and **Futuristic/Deepness** dimensions. These are useful design families, not universal listener types or proof that every participant wants one of each.
- Sound changes should form a coherent whole. Studies have evaluated combinations of low-frequency amplification, high-frequency filtering, lower-order additions, harmonic relationships, and pitch transposition. A study of 27 listeners found that selected added subharmonics improved some preference and sound-image ratings; the preferred combinations were not identical for every listener.
- Avoid treating a single frequency range as universally pleasant. In reviewed studies, louder tonal components in roughly 600–900 Hz could reduce pleasantness, while lower-frequency components were less disturbing in the tested conditions. These results depend on source, level, playback, and listener.
- Loudness, sharpness, roughness, fluctuation strength, and tonality are established sound-quality measures. They help describe or screen synthesized candidates, but do not replace listening tests or predict an individual's preference by themselves.
- Preference-based Bayesian optimization is a reasonable way to personalize a constrained set of sound designs. It does not solve poor candidate design: the search space must contain coherent, listenable combinations first.

## How studies elicit sound character and preference

Studies use complementary tasks because preference alone says which sound wins, but not what listeners heard in it:

- **Open description:** let listeners use their own words after hearing a candidate. Petiot et al. paired word association with ratings for pleasantness and appropriateness. Novices tended to use character words; experts used more composition terms. This argues for plain-language labels and an optional free-text prompt, not technical parameter names.
- **Bipolar character scales:** rate concepts such as smooth–rough, light–heavy, or calm–powerful. EV studies use semantic differential scales to capture several impressions alongside preference. Music timbre research also uses descriptors such as bright–dark and smooth–rough; these are useful shared vocabulary, but their meanings can vary by listener and context.
- **Pairwise preference:** compare two complete sound concepts, then ask which is preferred (including equal/neither). This makes a clear choice task, but does not prove which component caused the choice when multiple traits differ.
- **Controlled design factors:** vary designed groups or sound components in a planned matrix, then relate those factors to preference and character ratings. Petiot et al. tested 17 synthesized sounds made from four components and found different listener subgroups favored different combinations. This supports retaining several branches rather than treating one vote as a universal recipe.
- **Listener-directed adjustment:** in music-mixing research, listeners adjusted four synthesizer timbre attributes, then rated mixes. They consistently preferred their own mixes, while settings differed substantially across individuals. This supports personal exploration after a listener finds a promising character; it does not support assuming one timbre setting suits everyone.

### Recommended elicitation for this prototype

Keep preference and character as separate records. For each pair, first collect the method's existing preference response. Then use a compact optional character check on selected comparisons (for example, after the first broad contrast and at the end): choose up to two plain-language descriptors that stood out, plus an optional “describe it in your own words” field. At the final choice, ask both which candidate they prefer and what they want the sound to feel like. Do not make character tags determine the winner or force every listener to use music vocabulary.

Use a small, stable descriptor set for analysis, such as **smooth–rough**, **light–full**, **subtle–assertive**, **electric–engine-like**, and **calm–dramatic**. Treat these as hypotheses to validate in pilot listening, not established universal dimensions. Keep a separate pleasantness/preference response: a listener can find a sound powerful or futuristic without liking it. Record self-described terms too, so the selected vocabulary does not constrain what participants can express.

Early comparisons should expose broad, coherent style signatures. Later composition comparisons should test combinations of liked or interesting group traits. Only offer fine adjustment after the listener marks a direction as promising. A character label is descriptive feedback; preference is the decision signal. This helps distinguish “I like this sound” from “this sounds bright/engine-like/orchestral,” without prematurely tuning exact Hz values.

## Frequency and modulation evidence for candidate bounds

There is no validated universal “pleasant frequency window” for an EV ambience sound. The best direct evidence tests specific tones in actual or recorded vehicle backgrounds, not the isolated oscillator controls in this prototype.

| Parameter / feature | Published evidence | Practical starting guardrail for this prototype | Confidence |
| --- | --- | --- | --- |
| Tonal frequency | Lennström et al. tested interior tones from 200–900 Hz. Tones around 200–400 Hz were less disturbing in their conditions; tones from 600–900 Hz became less pleasant as level increased for a more tone-sensitive listener group. A separate study found greater annoyance for highly audible tones above 5 kHz than below 800 Hz. | Keep the main tonal identity in the existing low/mid register; avoid making narrow upper tones (especially 600–900 Hz and above) prominent. Compare spectral balance at matched loudness; do not treat 200–400 Hz as a guaranteed preference band. | Medium for annoyance in tested recordings; low for synthetic ambience preference. |
| Added harmonics / subharmonics | Gwak et al. reported improved impressions for selected harmonic/subharmonic additions; the review notes lower added tones below about 600 Hz helped dynamic impression. Particular combinations appealed to different listener groups. | Use related partials as fixed family recipes. Explore the level of a small number of lower supporting partials, rather than randomizing each partial frequency and level independently. | Low to medium; small study and particular source sounds. |
| Loudness | ISO 532-1 provides a method for estimating perceived loudness. Vehicle studies show level can change the pleasantness of tonal components and can confound preference. | Loudness-match A/B candidates before interpreting timbre preference. Treat the target loudness as a controlled listening-test choice, not a published universal comfort number. | High for using the metric; no universal comfortable target. |
| Whirl / detune | No universal acceptable detune window found for a synthesized EV ambience. | Lock deliberate whirl/detune at zero for the first qualified candidates. Test a subtle level later as its own contrast. | Evidence gap; conservative engineering choice. |
| Pulse / periodic modulation | Automotive studies measure roughness and fluctuation strength, but do not give a general preferred modulation depth for an EV ambience. The current DSP's pulse rate is about 2.5–4.7 Hz across the current carrier range, so it can be heard as a repeated amplitude wobble. | Set pulse depth to zero for initial candidates. If studied later, use one low-depth, isolated contrast and measure fluctuation/roughness plus preference. | Evidence gap; recommendation targets the reported wobble and confounding risk. |
| Shimmer / upper-band energy | Sharpness and tonal prominence relate to annoyance or satisfaction in some EV studies, but do not determine liking on their own. | Keep shimmer off in the first candidates; introduce it only after base timbres are listenable and compare at matched loudness. | Medium for metric relevance; low for preferred shimmer amount. |
| Pitch and response to driving state | EV sound-design studies commonly use speed-related pitch or spectral change to create dynamic impression and operational feedback; they do not establish one preferred pitch slope for all listeners. | Keep the pitch/level mapping monotonic and stable within a family. Search response strength and smoothness as a linked pair, then test whether listeners can identify speed/load changes. | Medium for state-linked mapping; no universal slope. |

These bounds are **screening limits for a pilot**, not standards. They favor stable, moderate candidates and reserve uncertain modulation for a controlled test. Convert them into the app's normalized control bounds only after rendering candidates and checking the resulting spectrum and loudness; normalized `0–1` values do not correspond to consistent perceptual steps across controls.

## Modulation, roughness and chord-tuning check (source discovery)

Status: a one-listener calibration, not a validated standard. The caps below are provisional engineering screens. A post-render gate using these caps was built and then reduced to monitoring. With absolute caps (fluctuation > 0.25, grain > 0.12) it flagged the clips rated unpleasant, but it also held back 11 of 103 previously passing candidates, 10 of them in the grain band next to the 25 Hz grain rate. Those were probably normal texture, not faults. Taste is judged by listener votes, so `audio/signal_checks.py` now only records `metrics.modulation` (all three bands) for each clip of 6 s or longer and never blocks on it. Wobble is controlled at generation instead: no generator parameter adds 2–30 Hz amplitude modulation (the only periodic movement is a slow 0.4 Hz swell and a very small 5.2 Hz pitch vibrato, scaled by `movement`), and any new family (for example engine or pulse) must keep it out or justify it with a listening check.

### Published findings and limits

- **Listener preference varies; character factors recur.** A systematic review of 46 papers (Song, Kim & Yun 2024, "Auditory experience in vehicles: A systematic review and future research directions", *Heliyon* 10, e34838; read from the PDF, no link checked) reports comfort, power and futuristic factors; perceived refinement fell as sharpness and roughness rose, powerfulness rose with loudness, booming and modulation, and pleasantness fell with modulation. One 31-listener study found high-frequency filtering, low-frequency boost and pitch change led to preferred sounds, with preferences differing by person. Limit: review-level summary, mostly conventional-vehicle interior noise.
- **Annoyance combines several metrics.** Zwicker's psychoacoustic annoyance combines loudness (N5), sharpness (penalty above about 1.75 acum), roughness and fluctuation strength ([summary](https://www.johndcook.com/blog/2016/07/28/quantifying-how-annoying-a-sound-is/); constants not checked against the original book).
- **Modulation rate matters.** Fluctuation strength covers about 0.5–20 Hz and is worst near 4 Hz ([CAA review](https://jcaa.caa-aca.ca/index.php/jcaa/article/download/1647/1394/1784)). Roughness comes from about 30–150 Hz modulation, usually unpleasant, with a model peak near 70 Hz ([Frontiers 2020](https://www.frontiersin.org/articles/10.3389/fnbeh.2020.588834); [Siemens](https://community.sw.siemens.com/articles/en_US/Knowledge/sound-modulation-metrics-fluctuation-strength-and-roughness)). The 70 Hz is a model weighting, not a fixed human optimum.
- **Tone frequency and level.** For exterior-EV tones, annoyance ratings rose from about 3/10 at 350 Hz to 7/10 at 2 kHz, and equal 65 dBA levels gave very different annoyance ([Bazilinskyy et al. 2025](https://arxiv.org/pdf/2510.25593)). Limit: exterior AVAS, simple tones, small sample.
- **Dissonance and novelty.** Dissonance affected preference among sounds of similar tonality ([INTER-NOISE 2023](https://ince.publisher.ingentaconnect.com/contentone/ince/incecp/2023/00000268/00000003/art00091)); novelty related negatively to preference for acceleration sounds ([HFES 2022](https://katalog.lib.cas.cz/KNAV/EdsRecord/edo,ejs61056528)). Only abstracts were read for the web sources.

### Project measurement (2026-11-06)

`tools/render_modulation_grid.py` amplitude-modulates a base source (Glass reference) at 2–150 Hz and 10–40 % depth, renders each through the real Rise pipeline, loudness-matches to -24 LUFS, and measures envelope-modulation depth on the final clip. The metric is an **uncalibrated envelope proxy**, compared with the unmodulated baseline; a synthetic self-test checks depth recovery. Findings:

- Slow modulation (2–8 Hz) emerges at the rate applied, at about 85–90 % of the applied depth, so granular pitch shift does not move it. 20–30 Hz modulation appears in the grain-rate band.
- All 28 renders passed the existing signal checks, so those checks do not catch modulation.
- Nearly all candidate sounds carry a baseline envelope component near 43 Hz (roughness-band depth 0.26–0.44). It sits in the static source before granular processing. Hypothesis: beating between the foundation and the 0.75 x root pad voice (partials 0.25 x root, about 44 Hz apart). Supporting evidence: Rounded, whose companions are unison and octave, measured lowest, and the unison/octave tuning removed the peak. Not confirmed with a calibrated roughness metric.

One listener (the developer), headphones, player volume 20 %, 20 clips (`desktop/src/RoughnessListeningCheck.tsx`):

| Clip | Rating |
| --- | --- |
| Reference, 4 Hz at 20 % | comfortable |
| 4 Hz at 40 % | unpleasant |
| 8 Hz at 40 % | borderline |
| 20 Hz and 30 Hz at 40 % | unpleasant |
| 50, 70, 100, 150 Hz at 40 % (and 70 Hz at 20 %) | comfortable |

Proxy values: comfortable up to fluctuation-band excess 0.12; unpleasant at 0.23 (4 Hz) and at grain-band excess 0.12-0.13. Fast modulation was comfortable even at 40 % depth and proxy excess up to 0.15. Possible reason, unchecked: roughness needs a carrier well above the modulation rate, and these sounds are low (about 75-340 Hz).

Provisional caps for generated sources: fluctuation-band excess at most about 0.12; grain-band excess below 0.12 (use 0.06 until points between 0.02 and 0.12 are tested); 30-150 Hz band monitor-only. Design implication: avoid pulse or modulation rates of about 2-30 Hz at meaningful depth. Idle-engine firing rates fall in that range, so an engine-like family must start higher or stay shallow. This is not evidence that engine-like modulation at 30-100 Hz is acceptable to other listeners.

Chord tuning (pad voices): three sounds per set for glass, bowed and airy. The original tuning (x0.75, x1.5, x2) and sub-octave (x0.5, x1, x2) were all rated comfortable, and sub-octave was tagged "fuller / richer" in all three sets. Unison/octave tuning had the lowest proxy roughness but was rated borderline in all three. So the roughness proxy does not predict this listener's comfort. No favourites were marked, and wobble tags and "difference from reference" were left blank, so detectability is unknown.

Implemented from this: recipe option `companionSub` (sub-octave pad tuning) for bowed, glass and airy layers; references and other families keep the original tuning.

Limits: one listener, one base sound, one playback level, no blind repeat. Rerun with more listeners, other base sounds, 6 and 12 Hz, and 20-30 Hz at 10-20 % depth before treating any cap as general.

## Provisional recipe windows for the next search

The six dashboard recipes now have versioned pilot windows in `experiment/recipes.py`. A normalized linked-group control of `0`, `0.5`, or `1` selects its low endpoint, approved preview, or high endpoint. Intermediate values interpolate through the preview. Structural choices stay fixed within each recipe: electric versus engine-order synthesis, harmonic ratios, traction/orchestral identity, and zero additional whirl, pulse, and shimmer. Controls move related physical fields together rather than independently mixing arbitrary extremes.

| Recipe | Linked groups | Main pitch window at 0 and 180 km/h, from low/high endpoints | Strongest pilot-render peak |
| --- | --- | --- | --- |
| Comfort Clean Electric | Register, tone, load response, regen | 112–142 Hz at 0; 130–185 Hz at 180 | −16.0 dBFS |
| Comfort Warm Motor | Register, tone, load response, regen | 83–114 Hz at 0; 115–175 Hz at 180 | −13.7 dBFS |
| Sport Electric Sport | Register, tone, load response, regen | 53–95 Hz at 0; 188–307 Hz at 180 | −7.7 dBFS |
| Sport ICE Inspired | Virtual RPM register, pedal rev response | Fourth-order tone: 80–97 Hz at idle; up to 480–580 Hz at speed ceiling | −14.7 dBFS |
| Deep Traction Glide | Register, tone, load response, regen, layer balance | 55–88 Hz at 0; 133–210 Hz at 180 | −16.4 dBFS |
| Deep Orchestral Rise | Register, tone, load response, regen, layer balance | 81–113 Hz at 0; 198–275 Hz at 180 | −19.4 dBFS |

These are **carrier or dominant engine-order** ranges, not a claim that no harmonics exist above them. Sport's upper register endpoint was narrowed after a test setting concentrated more energy in the 600–900 Hz band. The chosen high endpoint keeps the second motor partial below roughly 600 Hz at the speed ceiling. This is an engineering screen informed by [Lennström et al. (2019)](https://ltu.diva-portal.org/smash/record.jsf?pid=diva2%3A1429700), not a psychoacoustic safety threshold. Coupled tone and response fields follow the related-partial approach described by [Gwak et al. (2014)](https://doi.org/10.1121/1.4898742). ICE currently offers only two effective sound controls because the native engine-order texture and regen curves are global configuration; adding nominal controls that do not change the rendered sound would mislead the search.

The repeatable review command is `.venv/bin/python tools/render_recipe_review.py artifacts/recipe_window_review`. It generates low/base/high WAVs for every recipe, each with the same five two-second segments: startup, 40 km/h steady, 110 km/h steady, 20–100 km/h acceleration, and 100–60 km/h regeneration. `metrics.csv` records unnormalized peak and RMS dBFS plus a 600–900 Hz spectral-energy share. Across the 90 rendered segments, all peaks remained below −7.7 dBFS; endpoint switching and baseline recipe switching passed continuity and headroom checks. Within each mode, paired baseline spectra were clearly different, but this does **not** establish that listeners can distinguish every nearby candidate.

Base steady-110-km/h RMS differs by about 4.0 dB between Comfort recipes, 8.5 dB between Sport recipes, and 1.6 dB between Deep recipes. The in-app Recipe window pilot applies saved per-recipe attenuation factors derived from those measurements while comparing candidates. RMS is not perceived loudness; before using cross-recipe choices as research evidence, use a common listening-level procedure, ideally guided by [ISO 532-1](https://www.iso.org/standard/63077.html) or listener matching. The window endpoints and sound quality still need a human listening pass; approved base previews alone do not validate every extreme.

## Version 2 linked probe bounds

`probe_profile(mode, recipe_id, controls)` keeps recipe version 1 untouched and adds four linked search groups: register/speed-pitch contour, harmonic tone, drive response, and regeneration. At normalized center (`0.5` for each supported group), it exactly reproduces the chosen recipe. Each mode's `mode_bounds(mode)` unions the existing version 1 physical windows, so a candidate can move across its mode's recipe starting regions instead of staying inside one recipe's narrow box. These are **draft screening bounds**, not final comfort or safety limits.

| Mode | Register/speed-pitch | Harmonic tone | Drive response | Regeneration |
| --- | --- | --- | --- | --- |
| Comfort | Offset 70–125 Hz; scale 0.10–0.34 | Richness 0.025–0.20; cutoff 350–650 Hz; depth 0.025–0.16; growl 0.05–0.36 | Cruise gain 0.12–0.44; acceleration richness 0.012–0.06; attack 0.10–0.22 s; release 0.22–0.40 s | Gain 0.12–0.32; attack 0.17–0.28 s; release 0.24–0.42 s |
| Sport | Electric offset 0–12 Hz; scale 0.75–1.18; ICE order scale 1.20–1.45 | Richness 0.30–0.58; cutoff 700–1050 Hz; depth 0.08–0.18; growl 0.75–1.0 | Cruise gain 0.55–0.85; acceleration richness 0.12–0.24; attack 0.05–0.11 s; release 0.09–0.19 s; ICE throttle RPM boost 2400–3800 | Gain 0.24–0.45; regen richness 0.30–0.60; attack 0.10–0.20 s; release 0.17–0.30 s |
| Deep | Offset 25–50 Hz; scale 0.43–0.90 | Richness 0.15–0.30; cutoff 450–900 Hz; depth 0.10–0.27; growl 0.08–0.25 | Cruise gain 0.27–0.62; acceleration richness 0.06–0.16; attack 0.16–0.45 s; release 0.30–0.70 s | Gain 0.20–0.40; attack 0.22–0.40 s; release 0.35–0.55 s |

ICE Inspired supports only register and response probes: its current order-synthesis path exposes virtual RPM scale and throttle RPM boost, but no effective recipe-specific tone or regen controls for steady playback. It must not show fake controls. Whirl, pulse, and shimmer remain outside these opening groups.

The first version 2 render screen covered every supported group endpoint across all six recipes and six states (startup, low/high steady speed, acceleration, lift-off, and regen). Maximum sample peak was 0.353 full scale (existing test ceiling: 0.45); largest 600–900 Hz energy share was 8.83%; matched-state endpoint RMS difference ranged from 0.00416 to 0.08372. These are digital signal checks, not proof of perceived audibility, comfort, loudness equality, or safe physical SPL. Human in-app listening remains required before treating bounds as qualified.

## Literature and standards

| Source | Useful finding | Relevance and limit |
| --- | --- | --- |
| Gwak, D. Y., Yoon, K., Seong, Y., & Lee, S. (2014). [Application of subharmonics for active sound design of electric vehicles](https://doi.org/10.1121/1.4898742). *The Journal of the Acoustical Society of America*, 136(6), EL391. | Proposes adding subharmonics to existing EV components, using psychoacoustics and harmonic theory; subjective evaluation found improvements for selected designed stimuli. | Supports designing related partials as a recipe rather than independently randomizing them. Small listening study; not a universal formula. |
| Lennström, D., Gutierrez Melian, A., Nykänen, A., Becker, J., & Sottek, R. (2019). [Perception of tones below 1 kHz in electric vehicles](https://ltu.diva-portal.org/smash/record.jsf?pid=diva2%3A1429700). *InterNoise 2019*, 3675–3685. | Tests tone pleasantness and detectability from 200–900 Hz in EV interior recordings; findings varied with frequency, level, and listener sensitivity. | Direct frequency evidence, but not a universal synthetic-sound target. |
| Lennström, D., Lindbom, T., & Nykänen, A. (2013). [Prominence of tones in electric vehicle interior noise](https://ltu.diva-portal.org/smash/get/diva2%3A1011065/FULLTEXT01.pdf). *INTER-NOISE 2013*, 508–515. | Reports annoyance in relation to tonal audibility and frequency; at higher prominence, tones above 5 kHz were more annoying than those below 800 Hz in tested conditions. | Supports screening for prominent high-frequency tones, not a hard upper-frequency cutoff for all desired sound. |
| Swart, D. J., & Bekker, A. (2018). [The subjective dimensions of sound quality of standard production electric vehicles](https://doi.org/10.1016/j.apacoust.2017.08.012). *Applied Acoustics*. | Identifies perceptual dimensions used to describe production EV interior sound. | Grounds the Comfort/Power/Futuristic family framing in EV sound research. |
| Swart, D. J., Bekker, A., & van der Westhuizen, D. (2018). [Electric vehicle sound stimuli data and enhancements](https://doi.org/10.1016/j.dib.2018.10.074). *Data in Brief*, 21, 1337–1346. | Documents EV interior stimuli and enhancement methods, including transposition, harmony/order addition, filtering, and modulation. | Useful for planning controlled contrasts and retaining reproducible candidate stimuli. |
| Swart, D. J., & Bekker, A. (2019). [The relationship between consumer satisfaction and psychoacoustics of electric vehicle signature sound](https://doi.org/10.1016/j.apacoust.2018.09.019). *Applied Acoustics*. | Relates listener satisfaction to sound descriptors and psychoacoustic metrics; reported Comfort/Calm, Power, and Futuristic dimensions. | Supports measuring preference and sound-quality attributes together, while keeping subjective satisfaction as its own outcome. |
| Petiot, J.-F., Kristensen, L., & Maier, A. (2013). [How should an electric vehicle sound? User and expert perception](https://pure.strath.ac.uk/ws/portalfiles/portal/133014925/Petiot_etal_ASME_DETC_2013_How_should_an_electric_vehicle_sound_user_and_expert_perception.pdf). *ASME IDETC/CIE*. | 40 participants evaluated 17 synthesized EV sounds with open word association and pleasantness/appropriateness scales. Novices and experts used different vocabularies; preference varied across listeners and component combinations. | Supports collecting listener language and structured impressions beside preference, and keeping multiple sound directions open. Exterior sound study; its preferences do not directly transfer to in-cabin ambience. |
| Dobrowohl, F. A., Milne, A. J., & Dean, R. T. (2019). [Timbre Preferences in the Context of Mixing Music](https://doi.org/10.3390/app9081695). *Applied Sciences*, 9(8), 1695. | 28 listeners adjusted four synthesizer timbre attributes in music loops and later ranked mixes. They preferred their own mixes, while approaches varied substantially between individuals. | Supports individual, listener-directed timbre exploration. Music-mixing task differs from vehicle ambience and does not establish preferred EV parameter ranges. |
| Wallmark, Z. (2019). [Semantic Crosstalk in Timbre Perception](https://doi.org/10.1177/2059204319846617). *Music & Science*. | Found consistent associations for some bright/dark and smooth/rough descriptions across natural and synthesized timbres; high-frequency energy related to brightness ratings. | Supports plain-language character scales as descriptive prompts, not as direct substitutes for acoustic measures or preference. |
| Dahlstedt, P. (2001). [Creating and Exploring Huge Parameter Spaces: Interactive Evolution as a Tool for Sound Generation](https://research.chalmers.se/en/publication/59128). *Proceedings of the International Computer Music Conference*. | Describes iterative listener selection from populations of synthesized sounds to explore large parameter spaces. | Supports interactive audition and selection for broad discovery; does not establish an optimal comparison count or guarantee coherent candidates. |
| Münder, M., & Carbon, C.-C. (2022). [A literature review (2000–2022) on vehicle acoustics: Investigations on perceptual parameters of interior soundscapes in electrified vehicles](https://doi.org/10.3389/fmech.2022.974464). *Frontiers in Mechanical Engineering*. | Reviews EV interior perception, sound-design studies, and listening-test approaches; reports that preferred modifications and sound concepts vary. | Broad map of the field. Review findings combine studies with different vehicles, playback setups, and participant groups. |
| ISO. [ISO 532-1:2017, Acoustics — Methods for calculating loudness — Part 1: Zwicker method](https://www.iso.org/standard/63077.html). | Standard method for estimating perceived loudness of stationary and time-varying sounds. | Candidate loudness can be compared more meaningfully than by waveform peak alone; it does not define what is liked. |
| ECMA International. [ECMA-418-2, Psychoacoustic Metrics for ITT Equipment, 4th edition (2025)](https://ecma-international.org/publications-and-standards/standards/ecma-418/). | Specifies psychoacoustic metrics including tonality and modulation-related measures such as roughness and fluctuation strength. | Possible analysis reference for generated signals. It is an IT equipment standard, not an EV sound recipe or preference standard. |

## Candidate sound families to explore

These are starting hypotheses for this prototype, not claims of objectively enjoyable sound.

| Family | Coherent sound recipe | Candidate controls to explore together |
| --- | --- | --- |
| **Comfort / smooth** | Stable, soft motor tone; gentle pitch and level response; restrained upper harmonics. | Pitch travel + response time + harmonic balance. Keep modulation low. |
| **Power / sporty** | Clear speed/load-linked rise with stronger but controlled lower harmonic support. | Pitch trajectory + harmonic balance + acceleration emphasis. Avoid strong periodic pulse or wobble. |
| **Futuristic / deep** | Sustained low foundation with a restrained related-tone or chordal layer and slow timbral change. | Foundation/layer balance + interval recipe + slow movement. Keep phrase and modulation depth bounded. |

For all families, preserve the link between sound and driving state: speed should produce a trackable pitch/spectral change, acceleration/load should affect presence, and regeneration should have a distinguishable but non-confusable cue. Do not let decorative modulation obscure those mappings.

## OEM sound-profile references

Manufacturer profiles show broad character alternatives and strong state linkage. Their marketing descriptions are design references, not measured psychoacoustic specifications. Features and names vary by model, model year, trim, and market.

| Manufacturer / system | Published profile range and behavior | Design lesson for this project |
| --- | --- | --- |
| [Hyundai IONIQ 5 N, N Active Sound+](https://www.hyundaimotorgroup.com/en/amp/CONT0000000000119732) | Hyundai describes N Active Sound Plus and N e-Shift as part of the IONIQ 5 N experience. The project's reviewed material distinguishes engine-like, electric-performance, and jet/cinematic character ideas; it does not disclose complete DSP mappings. | Multiple sound characters and discrete shift events can exist within one driving mode. Treat source/style and event behavior as separate design dimensions. |
| [BMW IconicSounds Electric](https://www.bmw-m.com/en/topics/magazine-article-pool/bmw-m-iconicsounds-electric.html) | BMW describes acoustic feedback responding to accelerator movement and intensifying with speed and driving demand. The public article does not provide the full DSP mapping. | Preserve a legible state relationship while changing emotional intensity and timbre. |
| [BMW Neue Klasse HypersonX](https://www.bmwgroup.com/en/news/allgemein/2025/hypersonx.html) | BMW describes everyday Personal sound and a more detailed, expanded Sport soundscape. It reports 43 sound signals across the vehicle experience; that is not 43 driving modes. | Sound can be designed as part of broader vehicle interaction. Keep welcome/UI cues separate from continuous propulsion sound. |
| [Mercedes-Benz EQE Sound Experience](https://mercedes-benz-media.co.uk/releases/1412) | The reviewed material names sound worlds including Silver Waves, Vivid Flux, and Roaring Pulse, and describes driving-responsive interior sound. It does not publish exact synthesis patches or input curves. | Contrasting synthetic identities are plausible. Choose a stable timbral goal first, then map it coherently to vehicle state. |
| [Kia EV6 e-ASD (Siemens Simcenter)](https://blogs.sw.siemens.com/simcenter/how-kia-ev6-inspires-your-senses-with-active-sound-design/) | The settings show Stylish, Dynamic, and Cyber sound styles alongside a separate Slow/Normal/Fast accelerator-response control. Exact response curves are not published. | Treat sound character and pedal-response shape separately; compare curves under the same sound style before combining them. |
| [Audi e-tron Sport Sound](https://www.audi.com/en/emotive-design-and-revolutionary-technologythe-audi-e-tron-gt-quattro-and-the-audi-rs-e-tron-gt-2021-13655/e-tron-sport-sound-13782) | Audi describes a sound assembled from multiple individual sound elements and linked to vehicle signals. Audi does not identify this system as granular synthesis. | A source library plus state-driven layer selection is a distinct architecture from granular resynthesis. |
| [Porsche Taycan Electric Sport Sound](https://newsroom.porsche.com/en_US/products/taycan/sound-18556.html) / [2026 E-Shift](https://newsroom.porsche.com/christophorus/en/2026/420/e-shift.html) | Porsche describes enriching selected real powertrain sounds and minimizing unwanted drive noise. The E-Shift article describes software-created engine-speed cues and simulated shifts. | Natural motor character, filtering, and discrete events can be composed. A virtual ICE character is optional, not a requirement for every sound mode. |

These systems suggest a useful separation for candidate design:

1. **Mode** is the driving context (Comfort, Sport, or Deep) and sets response intent and guardrails.
2. **Character family** is the sound material (electric motor-like, engine/order-like, synthetic/space-like, musical/orchestral, or low-frequency/EDM-like). These are candidate hypotheses, not user categories or fixed recipes.
3. **State mapping** links speed, throttle/load, acceleration, and regeneration to pitch, spectral change, level, or discrete events. Keep this mapping shared across candidates during the first tone comparison block; tune it later only as a separate research question.

Observed listening hypotheses include a train-like mid-speed sweep and a deep synthetic sound. They require direct listening and signal analysis before assigning specific controls. A sound label or OEM profile name cannot reveal its underlying DSP parameters.

### Kia EV6 pedal-response curve reference

The [Siemens Simcenter article on Kia EV6 active sound design](https://blogs.sw.siemens.com/simcenter/how-kia-ev6-inspires-your-senses-with-active-sound-design/) shows the custom sound settings and describes three sound styles plus a separate accelerator-pedal response selector (Slow, Normal, Fast). Hyundai Motor Group's [e-ASD description](https://www.hyundaimotorgroup.com/en/tag/e-ASD) says pedal position can change both sound volume and tone. Its [EV6 e-ASD article](https://www.hyundaimotorgroup.com/ko/story/CONT0000000000085370) says Fast response makes tone change steeply after a small pedal input, while Slow response is less sensitive.

The graph in the settings image appears to show three volume-versus-pedal response shapes. The project's visual reading is: **early rise then flatten** (fast/saturating), **steady rise** (near-linear), and **late rise then steep finish** (slow/late response). These are qualitative readings of a UI graphic, not extracted calibration data. The article text presents pedal-response speed separately from Stylish/Dynamic/Cyber sound style, so the curves should initially be treated as Slow/Normal/Fast response alternatives—not assigned one-to-one to the three sound themes. Exact curve samples and the profile-to-curve mapping are not published.

**Design implication for this project:** keep sound recipe and pedal-response curve independently selectable. Use normalized pedal position \(p\in[0,1]\) to produce a response amount \(r(p)\), then apply that shared response amount to a restrained gain change and a linked timbre change. Prototype three shapes—early-saturating, near-linear, and late-rising—without claiming they reproduce Kia's calibration. Keep speed/motor speed as the continuous motion trajectory, and use pedal/load for the driver's immediate intent and power; avoid counting pedal, load, and acceleration as three independent full-strength boosts when they describe the same event. Test the curves on identical speed and pedal traces, then check whether listeners hear the intended response and prefer a particular feel.

## Project implications from prior work

The steps below are research-informed recommendations, not implemented app behavior or a locked study protocol.

1. **Define what the sound must communicate.** Select a small set of states to test (for example, speed change, acceleration/load, and regeneration). Write down the intended sound cue for each and keep this mapping consistent within each family.
2. **Make qualified family prototypes.** Build one stable, moderate-level candidate for Comfort, Power/Sport, and Futuristic/Deep. Use related partials and preset-specific linked controls. Lock signature traits; do not let opening candidates combine unrelated extremes.
3. **Set safe, audible ranges per family.** Tune bounds for perceptible but controlled differences, rather than applying the same normalized radius to every parameter. Remove or tightly bound whirl/pulse when they produce unwanted wobble. Keep level differences from dominating preference comparisons.
4. **Check signals before involving participants.** Inspect time and spectrum plots; compare loudness and, where practical, sharpness, roughness, fluctuation strength, and tonality. Treat metric values as screening information, not an automatic preference score.
5. **Run interactive preference learning within a family.** Keep paired candidates close enough to be attributable, vary linked parameter groups, and let the listener stop early. Avoid jumping between family identities during a personalization run.
6. **Measure usefulness separately from liking.** Record pairwise preference and a short state-identification task. Analyze whether a candidate is liked, whether listeners read vehicle state correctly, and whether any trade-off appears.
7. **Refine from results.** Use participant feedback and candidate-level audio metrics to revise family recipes and bounds. Only then decide whether to add another family or more controls.

## Limits and cautions

- No fixed pitch, Hz range, or oscillator combination guarantees enjoyment for all drivers.
- Many cited experiments use small listener groups, recorded vehicles, laboratory playback, or exterior warning sounds; results may not transfer directly to this simulator's synthesized in-cabin sound.
- ISO/ECMA metrics characterize sound properties. They do not certify comfort, usefulness, or individual preference.
- Current Comfort, Sport, and Deep presets are prototype sound palettes, not validated industry standards or OEM reproductions.
- OEM publications describe goals and inputs, but rarely disclose exact synthesis algorithms or numeric mappings. Reverse engineering can characterize audible spectra, pitch trajectories, modulation, envelopes, and their relationship to known vehicle states; it cannot recover proprietary settings uniquely from audio alone.

## Signal analysis of reference clips

### Scope and method

This is an exploratory baseline for the 22 MP3 files in the sibling `ev-sound-example/` folder (about 447 seconds total). Qt Multimedia's FFmpeg decoder read all 22 files at 44.1 or 48 kHz. Frame features use a 8192-sample window and 2048-sample hop. Stereo channel power is averaged before calculating spectral features to avoid phase cancellation from a simple mono mix.

This initial pass used the project's installed NumPy/SciPy stack; its reported measurements are not librosa pitch-tracking or source-separation results. It does not include librosa's pYIN pitch tracking, MFCCs, or harmonic-percussive separation. Per-clip frame data and summary are in ignored `artifacts/audio-analysis/`.

The analyzed recordings are mixtures as published: possible narration, road/wind/rain, music, compression, and edits remain in the signal. Measurements characterize each complete clip, not a purified vehicle layer. Filenames provide tentative labels only. Early/middle/late means thirds of the file timeline; it does not mean launch/coast/maximum speed, 0–100, or any known vehicle input. A cut can create an apparent feature change. Missing regeneration audio is absent evidence, not a regeneration response.

### Measured trends

Across the 22 clips:

- Median spectral centroid was **143 Hz** across clips (middle half: about **115–215 Hz**). Median strongest spectral peak in the 40–1500 Hz analysis band was about **104 Hz** (middle half: **74–127 Hz**).
- Median energy share in 20–200 Hz was high: **91% / 82% / 84%** in the early, middle, and late thirds of clips. This confirms a strong low-frequency bed in these recordings, but does not prove the synthesized source itself has a 100 Hz fundamental; recording playback and noise can dominate.
- Within-file spectral shifts vary, but may reflect edits or narration: BMW i7 measures **164 / 224 / 225 Hz**; BMW M/Hans Zimmer **117 / 142 / 174 Hz**; one Hyundai Ignition/Evolution/Supersonic clip **169 / 454 / 488 Hz**. Other clips shift down: Hyundai Lightspeed **281 / 231 / 224 Hz**, Kia Stylish/Dynamic/Cyber **183 / 146 / 143 Hz**, and `hyndia-enhanced.mp3` **671 / 395 / 198 Hz**. These are not speed-response curves.
- Mercedes Vivid is low-centred in this recording: **79 / 85 / 121 Hz**, with about **97–98%** of measured energy below 200 Hz. That does not match a simple “crystalline/high” assumption; the clip mix, voiceover, capture chain, or label may explain the difference. Listen to the isolated segment before using it as a tonal target.
- The road/wind-labeled MG clip has centroid rising **201 / 322 / 355 Hz** and more energy in 200–1000 Hz. The rain-labeled MG clip has the highest median spectral flatness (**0.018**), consistent with a more noise-like mix. These are clues, not source separation or confirmed rain/wind detection.

These measurements support several candidate character recipes, not conclusions about driving response: a stable low bed, a low bed with a stronger mid layer, and a texture whose spectral balance changes between segments. The files cannot tell us whether a change came from speed, throttle, regeneration, an edit, or another source.

### Candidate character groups

| Group | Signal pattern | Character hypothesis | Candidate controls |
| --- | --- | --- | --- |
| **Low foundation** | Energy concentrated below 200 Hz; centroid and peak remain low | Warm, deep, restrained | `electric_pitch_offset`, low-layer gain, restrained `electric_cutoff`/`richness` |
| **Low + mid layer** | Strong low foundation with a meaningful 200–1000 Hz component | Fuller, more present, potentially more expressive | Keep foundation fixed; move linked partial/layer blend and `richness`/`electric_growl` together |
| **Textured / broadband** | Higher flatness or spectral flux; energy spread beyond the low band | Rough, airy, or noisy | Texture/noise blend and transient density; first verify it is not road, rain, or speech |
| **Segment-changing** | Large centroid or band-share shift within a clip | Unknown; could be designed evolution, edit, mode switch, or another source | Do not expose as a recipe until the segment is isolated and identified |

The current clips do not establish a reliable ICE/order character from harmonics alone. Engine-like naming is a label clue, not a measured engine-order track.

### Kia: three candidate sound segments

I treated the profile order in each filename as a tentative label and divided both recordings into three excerpts. The second file has clearer transitions; the first has no silent gaps, so its boundaries are lower-confidence estimates based on the three-part sequence and feature changes.

| Tentative profile | `kia-cyber-dynamic-stylish.mp3` segment | `kia-stylish-dynamic-cyber.mp3` segment | Measured character across the two excerpts |
| --- | --- | --- | --- |
| **Cyber** | 0.00–4.95s | 14.10–20.18s | Low foundation. Second excerpt adds a gradual mid-band lift near its end. |
| **Dynamic** | 4.95–9.50s | 6.95–13.35s | Most repeatable pattern: low foundation remains while mid-band share grows (about 11→35% and 6→23%). Best first candidate for a linked low-plus-mid probe. |
| **Stylish** | 9.50–14.93s | 1.40–6.95s | Less consistent: first excerpt has a strong late mid-band increase; second has a more balanced low/mid mix throughout. Needs listening confirmation before recipe tuning. |

The second file contains a low-level transition around 13.35–14.10s; I left that gap out of its third excerpt. These are audio-feature boundaries, not verified video edit points or exact mode labels. The excerpt times and findings are retained here; temporary trimmed WAV copies are not maintained.

### Smooth-reference candidates from frame data

These are candidates for human listening, ranked by measured continuity only:

- **Ford Mustang Mach-E (`Ford Mustang Mach-e-70-183.mp3`)**: steadiest candidate for a sustained low character. Centroid stays around **86–96 Hz**, low-band share around **86–95%**, and level stays close to **−16 dBFS** in 2-second windows. No large frame-to-frame jumps crossed the screening thresholds. It offers little measured evolution.
- **Porsche Taycan low-speed (`Porsche-taycan-low_speed.mp3`)**: simplest low-frequency bed. Centroid moves gradually from about **68 Hz** in the first 2 seconds to roughly **108–114 Hz** later; about **98–100%** of energy remains below 200 Hz. The first fraction of a second has an onset transient. The clip is explicitly low-speed, so it is not a full driving-range reference.
- **Kia Cyber/Dynamic/Stylish (`kia-cyber-dynamic-stylish.mp3`)**: possible richer reference with a modest mid layer; centroid thirds are **115 / 152 / 142 Hz** and low-band share is **91 / 82 / 85%**. It has no large detected jumps, but the file label may combine several profiles; segment identity needs listening confirmation.

BMW i7 has a clear low-to-mid expansion in its broad timeline bins, but a sharp centroid transition near **3.7 seconds** makes the full clip less suitable as a clean continuous target. Hyundai Lightspeed also has multiple sharp spectral shifts. Those changes could be edits or intended transitions; measurements cannot decide which.

This direction also fits BMW's published design aim of reducing basic notes while adding perceived depth, color, and precision. That supports exploring a few coordinated layers; it does not disclose BMW's DSP or parameter values ([BMW HypersonX](https://www.bmwgroup.com/en/news/allgemein/2025/hypersonx.html)).

### Feature-to-engine mapping

| Measured feature | What it describes | Relevant current control group | Confidence / caution |
| --- | --- | --- | --- |
| `candidate_peak_40_1500_hz` | Largest spectral bin in selected band; not necessarily a fundamental | `electric_pitch_offset`, `electric_pitch_scale`, `order_rpm_scale` | Low as a parameter estimate; use only as a candidate register clue |
| `spectral_centroid_hz`, band shares, rolloff | Where spectral energy sits; perceived brightness/weight | `electric_cutoff`, `richness`, `electric_growl`, `electric_depth`, partial/layer mix | Medium for describing the recording; low for separating vehicle sound from ambience |
| `rms_dbfs` | Recorded level over time | `drive_cruise_gain`, `gain`, response envelopes | Low as an OEM loudness target; video normalization and mic gain are unknown |
| `spectral_flux` | How quickly spectral content changes between frames | `acceleration_richness`, attack/release timing, transient accents | Low for linking a change to throttle without synchronized vehicle data |
| `spectral_flatness` | Tonal concentration versus noise-like energy | `richness`/texture mix; possible noise layer | Useful as a broad descriptor, not a rain/speech classifier |

In current code, the search-facing controls group these as **register**, **tone**, and **response**. The C++ renderer maps vehicle motion/load to sound controls, but the reference clips have no synchronized speed/pedal trace. Therefore audio alone cannot recover the transfer curve from speed or throttle to pitch, level, or filtering. It also cannot uniquely recover oscillator type, harmonic recipe, or proprietary signal flow.

### Baseline recipe proposal

Use this as an original experimental direction, not an OEM copy:

1. Keep a stable low foundation.
2. Offer a separate linked mid-harmonic layer that can stay restrained, grow, or recede. Treat its connection to propulsion as a design hypothesis to validate, not as a mapping measured from these clips.
3. Keep state response smooth and controlled; compare tone candidates under the same vehicle-input mapping.
4. Tune `electric_pitch_offset`/`electric_pitch_scale` for register, `electric_cutoff`/`richness`/`electric_growl` for spectral color, and `drive_cruise_gain`/`acceleration_richness`/attack-release for intensity and response.
5. Do not add rain, road noise, speech, birds, welcome cues, or other environmental recordings to the synthesized drive sound based on these videos. Treat those as contamination or separate events unless a later study specifically tests them.

No single clean reference segment is selected yet. The clips lack labels and synchronized vehicle states, and these measurements do not replace listening. The clips can be auditioned in the app; mark clean segment boundaries before using any one as a target.

### Re-running the analysis

```sh
.venv/bin/python tools/analyze_audio.py ../ev-sound-example --output artifacts/audio-analysis
```

`summary.csv` holds clip-level statistics. Each clip-named CSV holds frame-level features at about 46 ms spacing. Read peak/centroid tracks as spectral descriptors, not recovered source-oscillator settings.


## Source material and renderer evidence

### Question

Public descriptions support testing source material and vehicle mapping as separable design decisions. They do not prove that a single fixed source or granular synthesis is the best method. Performance, sound quality, listener preference, and CPU headroom still need evaluation.

Keep three decisions distinct:

1. **Source material:** what is recorded or composed (motor, mechanical, synthetic, or layered material).
2. **Renderer:** how that material becomes continuous sound (granular playback, crossfaded layers, pitch-shifted sample, or another method).
3. **Vehicle mapping:** which input changes which renderer control (speed, pedal, motor load, or regeneration).

These parts can be isolated for controlled experiments, but real sound design is iterative: source, rendering, and mapping may need joint adjustment. The proposed project method is documented separately in [Source-first sound approach](../design/source_first_sound_approach.md).

### Evidence and limits

- Hyundai Motor Group describes GV60 e-ASD as granular synthesis that breaks sound into small units and recombines them, with vehicle speed and acceleration informing the sound. Its public article does not disclose exact grain settings or transfer functions. ([Hyundai Motor Group](https://www.hyundaimotorgroup.com/en/story/CONT0000000000009992))
- Audi describes a synthetic e-tron GT sound built from 32 individual sounds and based on motor speed, accelerator position, vehicle speed, and other parameters. This supports a source-library-plus-mapping architecture; Audi does not identify the system as granular synthesis. ([Audi](https://www.audi.com/en/emotive-design-and-revolutionary-technologythe-audi-e-tron-gt-quattro-and-the-audi-rs-e-tron-gt-2021-13655/e-tron-sport-sound-13782))
- BMW's public HypersonX material describes a designed, situation-responsive soundscape and a large sound-design exploration, but does not establish granular synthesis as its implementation. Treat the BMW clip used here as an authored source audition, not evidence of BMW's renderer. ([BMW Group](https://www.bmwgroup.com/en/news/allgemein/2025/hypersonx.html))
- A 2025 SAE paper proposes granular sound generation for EV sci-fi sound, including adaptive principal-frequency grains and overlap-add; this is evidence of a research approach, not proof of OEM deployment. ([SAE 2025-01-0253](https://saemobilus.sae.org/papers/sound-granular-synthesis-method-sci-fi-sound-quality-electric-vehicles-2025-01-0253))
- Granular systems expose controls such as grain duration, density, playback position, pitch, envelope, and amplitude. These are renderer controls, not universally accepted automotive mappings. ([Audio Weaver granular synthesis guide](https://dochub.dspconcepts.com/latest/example-systems/SNDExamples/granular-synthesis-module/))

The evidence does **not** establish low CPU use on target hardware, a suitable source library, an effective mapping, or preference-learning compatibility. The supplied BMW clip audition was removed after listening exposed pitch fluctuation and unrelated source dropouts. The separate organ preview is not mapped. Neither trial validates a source-first renderer.


## Deferred sound-design idea: slow organic drift

Unimplemented ideas for future listening experiments. These are not part of the current sound behavior contract.

### Slow LFO / organic drift

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

