# Psychoacoustic comfort, annoyance and unpleasantness constraints for synthetic EV cabin sound

Scope: what makes synthetic EV cabin sounds harsh, rough, dissonant, piercing or tiring, and how to turn that into checks a search algorithm can compute (filters, penalties, constraints).
Status note: findings below are from literature and tool documentation. Nothing here is implemented in the EV Sound Lab code. Several primary sources (ISO/DIN/ECMA standards, Fastl & Zwicker book, SAE papers) are paywalled and were not read in full. Where a constant or threshold comes from a secondary source, these notes say so.

## 1. Psychoacoustic metrics and their links to annoyance and pleasantness

### Takeaway
Loudness and sharpness are the most reliable predictors of annoyance. Roughness, fluctuation strength and tonality add to it depending on context. Zwicker's psychoacoustic annoyance (PA) combines all four into one number you can compute. Aures' sensory pleasantness model points in the right directions but correlated poorly with ratings of artificial sounds. No published EV cabin target ranges were found for these metrics.

### Cited Findings
- Zwicker/Fastl psychoacoustic annoyance (as reproduced by secondary sources): PA = N5 · [1 + sqrt(wS² + wFR²)], with N5 = the loudness (sone) exceeded 5% of the time. Sharpness term wS = 0.25·(S − 1.75)·log10(N5 + 10), applied only when S > 1.75 acum, otherwise 0. Modulation term wFR = (2.18 / N5^0.4)·(0.4·F + 0.6·R), with F in vacil and R in asper. The N5^−0.4 factor means modulation weighs relatively more in quiet sounds. — [MetricGate PA doc](https://metricgate.com/docs/psychoacoustic-annoyance/); [John D. Cook blog](https://www.johndcook.com/blog/2016/07/28/quantifying-how-annoying-a-sound-is/). Caveat: the patent extractions of this formula are partly garbled, and the log argument differs between sources. Check coefficients against Fastl & Zwicker, *Psychoacoustics: Facts and Models* ([Springer chapter](https://link.springer.com/chapter/10.1007/978-3-662-09562-1_9)) before relying on them.
- Worked example: at 80 dB, a leaf blower gives PA ≈ 56 and a kettledrum PA ≈ 19. This shows PA separates broadband, sharp and modulated sounds from tonal, dull ones. — [John D. Cook](https://www.johndcook.com/blog/2016/07/28/quantifying-how-annoying-a-sound-is/)
- A 2025 EV tutorial uses a variant, PA = N·(1 + sqrt(((S−S0)² + (R−R0)² + (F−F0)²)/3)), with unspecified reference thresholds S0, R0, F0. It claims that annoyance "correlates well with customer satisfaction studies in automotive NVH" but gives no data for this. — [Goswami 2025, arXiv:2509.16901](https://arxiv.org/html/2509.16901)
- Definitions from the same tutorial:
  - Loudness: N = ∫ N′(z) dz over 0–24 Bark (ISO 532-1/2).
  - Sharpness: S = ∫ g(z)·N′(z)·z dz / ∫ N′(z) dz (acum), where g(z) emphasizes content above about 1 kHz (von Bismarck 1974).
  - Roughness (Daniel–Weber): built from modulation depth^0.6 for modulation in 15–300 Hz (asper).
  - Fluctuation strength: peaks near 4 Hz modulation, for variations below about 20 Hz (vacil).
  - Tonality (DIN 45681): tone level minus masking level.
  - Source: [arXiv:2509.16901](https://arxiv.org/html/2509.16901)
- Inverter and gear-mesh tones sit in roughly the 1–10 kHz range. EV interiors lack combustion masking, so these tones raise sharpness and tonality. — [arXiv:2509.16901](https://arxiv.org/html/2509.16901)
- Aures sensory pleasantness (Acustica 1985) predicts that pleasantness falls with roughness, sharpness and loudness and rises with tonality. Aures tonality = tonal specific loudness / total specific loudness. — [Salford sound quality metrics](https://acoustics.salford.ac.uk/psychoacoustics/sound-quality-making-products-sound-better/an-introduction-to-sound-quality-testing/sound-quality-metrics/); [MetricGate Aures tonality](https://metricgate.com/docs/tonality-aures/)
- Validity limit: in a JAIST paired-comparison study on artificial sounds, the Aures model correlated with measured pleasantness at only r ≈ 0.23. The model rated bandpass noise as unpleasant, but listeners did not. — [JAIST paper](https://dspace.jaist.ac.jp/dspace/bitstream/10119/18909/4/paper.pdf)
- In an annoyance (not pleasantness) study, loudness was the main predictor and sharpness the next strongest (r² = 0.72). Roughness (r² = 0.04) and tonality (r² = 0.08) did not contribute significantly. — reported via [Salford/publisso summary](https://journals.publisso.de/de/journals/zaud/volume7/zaud000073) (secondary; original study not read)
- Fluctuation strength peaks near 4 Hz modulation. At higher modulation rates the sensation turns into roughness. — [MetricGate PA doc](https://metricgate.com/docs/psychoacoustic-annoyance/); [arXiv:2509.16901](https://arxiv.org/html/2509.16901)
- Comparison of the two tonality standards: Lennström & Nykänen measured 13 electrified cars. Prominence ratio (PR) and tone-to-noise ratio (TNR, ECMA-74/418-1) sometimes disagreed significantly, and the paper gives guidance on which to use. — [SAE 2015-01-2367](https://saemobilus.sae.org/content/2015-01-2367)

### Inferences
- PA is a cheap scalar penalty a search can use. The sharpness term switches on above 1.75 acum, so it works as a natural "piercing" threshold. Most of the benefit probably comes from limiting loudness and sharpness. Roughness and fluctuation matter mainly for our layered and modulated sounds, where the synthesis itself creates them.
- Do not use Aures pleasantness as a reward: it rewards tonality, and its validity on synthetic sounds is weak. Tonality is the very feature that becomes annoying in EVs (see section 3).

### Gaps
- I did not obtain the original Fastl & Zwicker coefficients, the full Aures equations, or the ECMA-418-2 (Sottek) tonality and roughness definitions.
- I found no published target ranges (for example "cabin ASD should stay below X acum") for EV interior sound.
- The textbook roughness peak (about 70 Hz modulation for a 1 kHz carrier, in Fastl & Zwicker) was not verified from a fetched source.

## 2. Dissonance and consonance between simultaneous partials and layers

### Takeaway
Two partials closer than a critical band beat or sound rough, with the worst dissonance at roughly a quarter of a critical band apart. The total dissonance of a mix is the sum over all pairs of partials, so mixing layers whose partials do not line up causes roughness and inharmonic clashes. Sethares' model makes this computable for any set of partials.

### Cited Findings
- Plomp & Levelt (1965, JASA 38(4), "Tonal Consonance and Critical Bandwidth") had listeners rate pairs of sine tones. Dissonance rises quickly to a peak and then decays. The peak lies at about 1/4 of a critical bandwidth. — [AudioLabs Erlangen ISMIR 2025 resource](https://audiolabs-erlangen.de/resources/MIR/2025-ISMIR-SD); [Sethares page](https://sethares.engr.wisc.edu/consemi.html)
- Sethares models the Plomp–Levelt curve as a difference of exponentials, d(x) = e^(−a·x) − e^(−b·x), scaled by the critical bandwidth at the lower frequency and weighted by the partials' amplitudes. Total dissonance = the sum over all pairs of partials. — [Sethares, HelmTTSS.pdf](https://sethares.engr.wisc.edu/paperspdf/HelmTTSS.pdf); [Sethares 1993 JASA 94(3) via author page](https://sethares.engr.wisc.edu/papers/consance.html). The constants commonly used with this model (a = 3.5, b = 5.75, d* = 0.24, s = d*/(0.021·f_min + 19)) are from my recollection of Sethares 1993/1998 and were not verified from a fetched page. Confirm them in the paper.
- Harmonic spectra: dissonance minima fall at simple ratios (1:1, 2:1, 3:2, 4:3, 5:4, 5:3). Inharmonic spectra (for example bells and bars) have unevenly spaced minima. Stretched spectra have a "pseudo-octave". Shallow minima disappear as the number of partials grows. — [Sethares, Relating Tuning and Timbre](https://sethares.engr.wisc.edu/consemi.html)
- Different pure-tone dissonance models use different parameters and give somewhat different curve shapes. Sensory dissonance has been computed for multi-track recordings. — [AudioLabs ISMIR 2025](https://audiolabs-erlangen.de/resources/MIR/2025-ISMIR-SD)

### Inferences (project interpretation, not published EV findings)
- Combining layers: when two pitch-mapped layers follow speed with different mapping slopes, their frequency ratio drifts continuously. This sweeps through the dissonance peaks and produces beating that comes and goes. Rule: give every tonal layer the same pitch-vs-speed law, multiplied by a fixed ratio. That ratio should be a small-integer ratio or an engine-order-style multiple of a shared fundamental (for example orders 1, 2, 3, 4, 6). This keeps the ratio constant at every speed.
- Detuned unison or chorus: two partials a few Hz apart beat. Beats near 4 Hz register as fluctuation and beats around 15–300 Hz as roughness (section 1 ranges). Penalize detuning so that |Δf| does not land in the roughness band relative to the critical band, unless the effect is intentional.
- Granular or noise layers with no clear partials add little to pairwise dissonance but add sharpness and loudness. Measure them with section 1 metrics, not with Sethares.
- Cheap guard: for each candidate, take a sample of speeds, list the top N partials of every layer (from the synthesis parameters directly, with no audio needed), compute Sethares dissonance, and penalize the maximum over speeds. This costs microseconds per candidate.

### Gaps
- I found no published study that applies Plomp–Levelt or Sethares dissonance specifically to EV ASD layering. The rules above are interpretation.

## 3. EV-specific findings

### Takeaway
In EVs, the main sources of discomfort are prominent tones from motors, inverters and gears that nothing masks. Clearly audible tonal components strongly reduce pleasantness. Standard tonality metrics (PR, TNR) only partly predict this. One thesis reports that annoyance was similar across frequency ranges when PR was below about 3 dB. No consensus number exists for an acceptable cabin ASD level.

### Cited Findings
- Lennström et al. (INTER-NOISE 2019) ran a listening test on EV interior sound with tones at 200–900 Hz. They compared pleasantness with PR, DIN 45681 tonality and ECMA-74. Existing tonality metrics did not explain how tonal events affect pleasantness. Tone detectability was linked to pleasantness. — [INCE 2019 art00070](https://ince.publisher.ingentaconnect.com/content/ince/incecp/2019/00000259/00000006/art00070?format=bib)
- A dissertation (Logos Verlag, ISBN 9783832555900) on audibility of tonal components and a pleasantness model for interior sound states that separately audible tonal components severely affect pleasantness in EVs and hybrids. Its chapters cover critical masking ratios. — [Logos ToC](https://www.logos-verlag.de/tocs/9783832555900toc.pdf); [Logos landing](https://www.logos-verlag.de/lp/9783832555900lp.pdf)
- A thesis on electric powertrain noise reported that at prominence ratios below 3 dB, perceived annoyance was similar regardless of frequency range. — [Methods for motor noise evaluation and control in EVs](https://www.dissertations.se/dissertation/6ed30dbdcb/) (search-snippet level; full text not read)
- Pietila et al. (SAE 2019-01-1467) built a frequency-dependent tonal annoyance weighting curve to apply on top of existing tonality metrics. It was tested against a listening study of 8 EV sounds. — [SAE 2019-01-1467](https://saemobilus.sae.org/content/2019-01-1467)
- Li & Parizet (INSA Lyon, Forum Acusticum 2026) ran two listening experiments on dynamometer recordings of electric, hybrid and combustion cars. Tonality metrics remain useful inputs to annoyance models, but tone-prominence metrics alone may not capture perceived tonality. — [FA2026 000797](https://dael.euracoustics.org/confs/fa2026/data/articles/000797.pdf)
- A Forum Acusticum 2026 paper studies whether perceived tonal magnitude in artificial EV cabin sounds depends on overall level. It notes that PR and TNR as standardized ignore level. — [FA2026 000242](https://dael.euracoustics.org/confs/fa2026/data/articles/000242.pdf) (PDF text could not be extracted; numbers not obtained)
- A 2024 INTER-NOISE paper notes that without engine masking, whine and whistle become noticeable and unpleasant. It proposes using designed sound to mask such defects. — [INCE 2024 art00047](https://ince.publisher.ingentaconnect.com/content/ince/incecp/2024/00000270/00000006/art00047?format=bib)
- A Korean simulator study varied acceleration-sound level in 3 dB steps and rated annoyance and sportiness. Passengers were less sensitive to annoyance than drivers, and the authors suggest separate ASD levels for each. — [KoreaScience JAKO202105360045766](https://koreascience.kr/article/JAKO202105360045766.pdf) (via search summary; fetch failed, exact dB values not obtained)
- A Bamberg dissertation (BMW-affiliated) covers annoyance, perceived quality and preference for e-powertrain noise and ASD, including continuous in-drive evaluation. — [Uni Bamberg](https://fis.uni-bamberg.de/bitstreams/a7626733-d7b9-493d-a3a9-c36fe8a38f1c/download)
- An EAA 2025 study tested whether artificial engine sound reduces motion sickness in EVs (15 participants, public road). — [FA2025 000569](https://dael.euracoustics.org/confs/fa2025/data/articles/000569.pdf)
- For exterior synthetic EV sounds (VR study), psychoacoustic metrics predicted annoyance better than conventional level metrics. — [TU Delft repository](https://repository.tudelft.nl/record/uuid:9c885aa0-5933-4a86-93dc-4fca2ddadb35); [arXiv 2510.25593](https://arxiv.org/abs/2510.25593v1)

### Inferences
- Penalize high-frequency pure tones (above about 1–2 kHz) that stand out clearly, using PR/TNR per tone, for example a soft penalty above about 3 dB PR and a hard cap at a larger margin. This targets the "piercing whine" failure mode. The 3 dB figure comes from one thesis snippet, so treat it as a starting point to tune.
- Because perceived tonality depends on level, compute tonality at the actual playback level, not on normalized audio.
- Long-drive fatigue: no direct cabin-ASD fatigue study was found. Psychoacoustic annoyance theory predicts that sharp, rough or strongly tonal sounds get worse with exposure. Prefer candidates with lower PA, not merely ones below a hard limit.

### Gaps
- Specific acceptable ASD levels (dB(A) or sone vs speed) were not found in accessible text.
- I found no controlled long-exposure fatigue study for cabin ASD.
- Numeric results of the FA2026 papers and the Lennström thesis were not obtained.

## 4. Safety and health limits, peaks and headroom

### Takeaway
Hearing-safety limits sit far above normal cabin listening levels. They matter only as an outer guard. The practical risk in a prototype is sudden peaks and clipping, which a limiter and loudness cap prevent.

### Cited Findings
- NIOSH recommended exposure limit: 85 dBA as an 8-hour TWA, with a 3 dB exchange rate (allowed time halves for each +3 dB). — [CDC/NIOSH Understand Noise Exposure](https://www.cdc.gov/niosh/noise/prevent/understand.html)
- WHO safe-listening guidance: 80 dB(A) for up to 40 h/week. With equal energy, the example durations are 8 h at 80 dBA, 4 h at 83 dBA and 2 h at 86 dBA. — [WHO/Neitzel safe listening review 2017](https://www.recordere.dk/wp-content/uploads/2024/03/WHO-Neitzel-Safe-Listening-Review-032017.pdf)
- OSHA uses 90 dBA with a 5 dB exchange rate. Do not mix it with NIOSH or WHO figures. — [OSHA standards archive](https://webarchive.library.unt.edu/eot2008/20081104074915/http:/www.osha.gov/dts/osta/otm/noise/standards.html)
- ITU-R BS.1770 (LUFS) is a standard way to normalize program loudness, implemented in Python as pyloudnorm. — [arXiv:2509.16901](https://arxiv.org/html/2509.16901)

### Inferences
- Guards:
  - A fixed master limiter with a true-peak ceiling of a few dB below 0 dBFS.
  - A per-candidate LUFS or sone cap relative to a calibrated reference level.
  - A max slew limit on gain changes when switching candidates, which also avoids startle.
  - A participant-session dose cap, for example keeping headphone Leq below 80 dBA, at the WHO limit.
- Keep the existing project rule: preserve headroom and smoothing.

### Gaps
- I found no specific standard for the maximum ASD level allowed inside a cabin.

## 5. Open-source tools, compute cost and suitability

### Takeaway
MoSQITo (Python) covers ISO 532-1 loudness, DIN 45692 sharpness, Daniel–Weber and ECMA-418-2 roughness, and ECMA-418-1 PR/TNR. It is suitable for offline pre-screening of short rendered clips, not for per-block real-time use. MATLAB's Audio Toolbox and SQAT have equivalents. Cheap proxies (spectral centroid, LUFS, envelope modulation spectrum) work as real-time stand-ins.

### Cited Findings
- MoSQITo `sq_metrics` includes:
  - Loudness: ISO 532-1:2017 (stationary and time-varying) and ECMA loudness.
  - Sharpness: DIN 45692.
  - Roughness: Daniel & Weber, and ECMA-418-2.
  - Tonality: prominence ratio and tone-to-noise ratio (ECMA-418-1).
  - Speech Intelligibility Index (ANSI S3.5).
  - The docs give no performance or validation notes.
  - Source: [MoSQITo docs](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.html); [changelog](https://pyup.io/changelogs/mosqito/)
- Implementing ECMA-418-2 roughness in MoSQITo exposed ambiguities and missing details in the standard. — [Wanty et al., INTER-NOISE 2024](https://ai.updf.com/paper-detail/ECMA-418-2-roughness,-a-challenging-implementation-wanty-glesser-2424c69489717508c43912aad89dbf4bc3c2a32f)
- The `sottek-hearing-model` package on PyPI implements ECMA-418-2 loudness, tonality and roughness, translated from MATLAB. — [PyPI](https://pypi.org/project/sottek-hearing-model/0.1.8/) (page details could not be loaded)
- MATLAB Audio Toolbox provides acousticLoudness, sharpnessDIN, roughnessDW, fluctuationStrength and tonalityDIN. On the Python side, pyloudnorm and librosa (spectral centroid) serve as proxies. — [arXiv:2509.16901](https://arxiv.org/html/2509.16901)

### Inferences
- Rough cost (unmeasured, from the algorithms' structure): ISO 532-1 time-varying loudness and Daniel–Weber roughness run filterbanks or Bark-band envelopes. They likely take on the order of 0.1–1 s per few-second clip in Python. ECMA-418-2 is heavier. This is fine for screening tens to hundreds of candidates offline, but too slow for the audio thread. Benchmark on this project's renders before relying on it.
- Two-tier plan:
  - Tier 1, microseconds, no audio: parameter-space rules and Sethares dissonance from partial lists.
  - Tier 2, offline: render a speed sweep with `tools/`, then compute N5, S, R, F, PR/TNR and PA with MoSQITo.
  - Cache results per candidate.

### Gaps
- No published timing benchmarks for MoSQITo were found.
- SQAT (MATLAB) was not looked up in this pass.

## 6. Using these metrics in the search: constraints, penalties, feasibility models

### Takeaway
Established methods exist: constrained BO (EI × probability of feasibility), safe BO (SafeOpt and its variants) that never evaluates points predicted to be unsafe, and preference-based optimization with unknown constraints (C-GLISp, CrashPBO, safety-aware preference learning). For listener comfort, the simplest robust design has two parts. First, filter out candidates that fail the computed psychoacoustic checks before anyone hears them. Second, learn a "too unpleasant" classifier from listener reject flags and use it as a probability-of-feasibility term.

### Cited Findings
- Gardner et al. (ICML 2014): constrained BO with GP priors on both the objective and the constraints. EIC = expected improvement × probability that constraints are satisfied. — [PMLR v32 gardner14](https://proceedings.mlr.press/v32/gardner14)
- Gelbart, Snoek & Adams (UAI 2014): BO with unknown, noisy constraints that can be evaluated separately from the objective. — [arXiv 1403.5607 / PDF](https://lips.cs.princeton.edu/pdfs/gelbart2014constraints.pdf); summary of EIC lineage in [Hernández-Lobato et al. arXiv 1502.05312](https://arxiv.org/pdf/1502.05312v2.pdf)
- SafeOpt (Sui, Gotovos, Burdick, Krause, ICML 2015):
  - Only evaluates parameters whose GP lower bound keeps performance above a threshold.
  - Expands the safe set from a known safe seed, using a Lipschitz assumption.
  - Motivated in part by patient-comfort settings in biomedical applications.
  - Source: [Berkenkamp et al. summary arXiv 1602.04450](https://arxiv.org/pdf/1602.04450)
- Follow-ups: SafeOpt-MC handles multiple constraints, StageOpt splits safe expansion from optimization ([arXiv 1806.07555](https://arxiv.org/pdf/1806.07555)), and StageOpt also covers preference-only utility feedback. Fiedler et al. (TMLR 2024) argue that SafeOpt's guarantees rest on hard-to-justify assumptions and propose LoSBO. — [arXiv 2403.12948](https://arxiv.org/pdf/2403.12948)
- C-GLISp (Zhu, Piga, Bemporad): active preference learning from pairwise "better/worse/similar" queries with unknown constraints, designed for safe exploration. — [arXiv 2106.05639](https://pdf.arxiv.org/pdf/2106.05639)
- CrashPBO (Menn et al., IEEE RA-L 2026): preferential BO plus binary "crash" feedback for unsafe trials. — [arXiv 2604.01776](https://arxiv.org/html/2604.01776v1)
- Safety-aware preference-based learning (Cosner et al., L4DC 2022): LineCoSpar extended with safety. — [PMLR v168](https://proceedings.mlr.press/v168/cosner22a/cosner22a.pdf)
- Lindner et al.: interactively learning unknown preference constraints (for example, comfortable driving) in linear bandits. — [arXiv 2206.05255](https://pdf.arxiv.org/pdf/2206.05255)

### Inferences (proposed design for EV Sound Lab, not implemented)
1. Hard filters before listening (cheap, deterministic):
   - Tier-1 parameter rules: shared pitch law, ratio-locked layers, and detune limits.
   - Tier-2 metric caps on a rendered speed sweep: N5 cap, a sharpness cap (start near the 1.75 acum PA knee and tune), a roughness cap, and a max per-tone PR/TNR above about 2 kHz.
   - Candidates failing any cap are never played.
2. Soft penalty: add −λ·PA (or −λ·max(0, S−S_ref) − μ·R − ν·dissonance) to the acquisition or utility prior, so that two otherwise equal candidates resolve toward the more comfortable one. Keep λ small so that listener preference still dominates. The metrics are only partly valid (r ≈ 0.23 for Aures on artificial sounds).
3. Learned feasibility: log a per-candidate "uncomfortable/reject" button. Fit a GP or logistic classifier on parameters plus metrics. Multiply the acquisition by P(feasible), as in Gardner/Gelbart, or limit queries to a SafeOpt-style safe set grown from the current baseline presets.
4. Pre-screening also protects experiment integrity: record why a candidate was filtered, so that the search history shows constraint rejections apart from listener choices.

### Gaps
- I found no published work that applies constrained or safe BO specifically to sound-design comfort. The mapping above is interpretation.
- I found no data on how well PA or MoSQITo metrics predict rejection of synthetic EV sounds. This would need a small calibration study in this project.
