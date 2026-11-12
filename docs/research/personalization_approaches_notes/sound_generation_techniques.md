# Sound generation and synthesis techniques for real-time, vehicle-state-driven EV cabin sound

Scope: going beyond a fixed granular setup plus preset blending. Each section is split into findings with sources, project interpretation (Inferences), and open questions (Gaps). Research cut-off: November 2026. Several sources were read only as abstracts, catalog pages or search summaries; this is noted where it applies.

## 1. Granular synthesis done well: avoiding loop artifacts; engine-sound granular literature and products

### Takeaway
Published engine-sound work and commercial tools agree on the main fix for looping. Cut grains that line up with the engine cycle (pitch-synchronous) from recorded speed sweeps, then choose and overlap them according to the control state instead of replaying a fixed loop. Corpus-based concatenative synthesis (CataRT) extends this. Grains are chosen by their distance to a target point in a descriptor space, which suits a system where vehicle state sets that target.

### Cited Findings
- Jagla, Maillard & Martin, "Sample-based engine noise synthesis using an enhanced pitch-synchronous overlap-and-add method," JASA 132(5):3098-3108, 2012 (DOI 10.1121/1.4754663). The method stores one engine cycle as a sample, plus the overlap needed for smooth transitions, and recombines these samples in real time to follow arbitrary speed profiles. — [HAL record](https://hal.archives-ouvertes.fr/hal-00730614); [full text PDF](https://hal.archives-ouvertes.fr/hal-00730614/file/JAGLA_MS12-11754_Final.pdf)
- The same authors' companion ICASSP 2012 paper proposes Harmonic Synchronous Overlap-and-Add (HSOLA), a variant for harmonic engine noise. — [HAL hal-00661228](https://hal.archives-ouvertes.fr/hal-00661228v2)
- Baldan, Lachambre, Delle Monache & Boussard (2015), "Physically informed car engine sound synthesis for virtual and augmented environments." This is a procedural or physically informed model. The authors present it as an efficient, flexible alternative to sample-based and analysis/resynthesis methods, and say cabin engine sound carries cues about vehicle motion. It is reused as the "Baldan model" in the TrafficSoundSim traffic auralization work. — [CORE PDF](https://core.ac.uk/download/53578982.pdf); [SIVE 2015 PDF](https://avanzini.di.unimi.it/downloads/publications/serafin_sive15.pdf) (read only as an abstract or snippet)
- Crankcase Audio REV (a Wwise plug-in) uses granular synthesis "to eliminate looping." Crankcase describes REV as combining spectral analysis and granular synthesis to manipulate recordings of vehicles in motion. A 2014 interview describes it as "spectral analysis of the audio data and the additive interpolated synthesis of grains," as opposed to crossfaded loops. — [Audiokinetic REV page](https://www.audiokinetic.com/products/plug-ins/crankcase-rev/); [Crankcase REV Unity GitHub](https://github.com/CrankcaseAudio/CrankcaseAudioREVUnity); [Designing Sound 2014](https://designingsound.org/2014/08/11/vehicle-engine-design-project-cars-forza-motorsport-5-and-rev/); [Audiokinetic REV2 racing blog](https://blog.audiokinetic.com/make-racing-engine-sound-based-on-rev2/)
- AudioMotors (embedded in FMOD Studio) has a granular engine that "reproduces engine cycle in a pitch-synchronous manner." — [MCV UK](https://mcvuk.com/development-news/how-to-make-racing-car-engines-roar-using-audiomotors-fmod); [Designing Sound review](https://designingsound.org/2013/04/26/audiomotors-review/)
- CataRT (Schwarz, Beller, Verbrugghe & Britton, DAFx 2006) is real-time corpus-based concatenative synthesis. It selects grains from a segmented corpus, analyzed by audio descriptors, according to their distance to a target point in descriptor space. — [DAFx archive](https://dafx.de/paper-archive/details/NJTiiDRZJmF9nDRvdE6qmg); [HAL hal-01161358](https://hal.archives-ouvertes.fr/hal-01161358)
- CataRT measures selection distance as a weighted distance normalized by each descriptor's standard deviation over the corpus. Candidates come from a selection radius or the k nearest units. A live input can be analyzed with the same descriptors and used as the target. — [Einbond, Schwarz & Bresson 2009 (ICMC)](https://openaccess.city.ac.uk/id/eprint/16733/1/Einbond09.pdf)
- Users steer CataRT by moving through a 2-D or higher projection of the corpus descriptor space, which "extends granular synthesis with direct access to specific sound characteristics." CataRT runs in Max/MSP (FTM/Gabor, later MuBu) or as a standalone application. — [Einbond & Schwarz ICMC 2010](https://openaccess.city.ac.uk/id/eprint/16732/1/Einbond10a.pdf); [Schwarz NIME 2012](https://vhosts.eecs.umich.edu/nime2012/Proceedings/papers/120_Final_Manuscript.pdf); [eContact overview](https://econtact.ca/16_2/schwarz_corpus.html)
- EV-specific granular work:
  - Liu et al., SAE 2025-01-0253, propose granular synthesis for "sci-fi" EV powertrain sound, with a grain window optimized by a genetic algorithm to smooth grain joins. — [SAE Mobilus](https://saemobilus.sae.org/papers/sound-granular-synthesis-method-sci-fi-sound-quality-electric-vehicles-2025-01-0253) (abstract only)
  - A Politecnico di Torino thesis customizes granular engine sound from CAN-bus data. — [PoliTo thesis](https://webthesis.biblio.polito.it/16002/1/tesi.pdf)
  - A Padua thesis evaluates granular EV sounds for noticeability and annoyance. — [UniPD thesis](https://thesis.unipd.it/handle/20.500.12608/66614)
- Hyundai's production EV sound uses "data-driven granular synthesis" built in Simcenter Testlab Sound Designer. Grain position, pitch and duration vary with speed, motor speed, powertrain load and throttle. The source material is a recorded or composed sample chosen to suit the intended driving emotion. — [Siemens/Hyundai case study](https://resources.sw.siemens.com/en-US/case-study-hyundai) (vendor case study, not peer-reviewed)

### Inferences
- Interpretation: audible looping usually means grain read positions repeat on a fixed period, or a single source layer is used. The literature's remedies are:
  - Choose grains by state (rpm/load maps to a corpus position), not by a fixed playhead.
  - Randomize read position within a window around that state point (spray/jitter) and randomize the inter-onset interval.
  - Overlap two or more grains with constant-power windows.
  - Run several independent source layers with decorrelated random seeds.
- Interpretation: pitch-synchronous grains (Jagla; AudioMotors) apply mainly to harmonic sources with a clear cycle. An EV project's source material may be tonal (motor whine, synth pads) or noisy (wind, texture). Use pitch-synchronous grains for tonal layers and asynchronous jittered grains for texture layers.
- Interpretation: a CataRT-style unit selector suits this project directly. Analyze each source sample offline into short units with descriptors (pitch, spectral centroid, loudness, roughness). At runtime, map vehicle state (speed, load, pedal) to a target descriptor vector and pick the k nearest units with randomization. This replaces "blend preset A and B" with continuous navigation inside one corpus, and new source files simply enlarge the corpus.

### Gaps
- The full text of the JASA 2012 paper was not read. Its exact grain-boundary, window and smoothing parameters are unverified here.
- No source was found describing Wwise SoundSeed Grain or FMOD's built-in granular features in technical detail. The Audiokinetic engine-modeling article returned HTTP 403.
- REV's internal algorithm is proprietary. Only the vendor descriptions above are available.

## 2. Which granular parameters should be per-sound or per-user rather than fixed

### Takeaway
Little published work isolates individual granular parameters for EV sound. One AES study by Seoul National University and Hyundai found that each parameter it varied (source, grain duration, grain envelope, RPM range) affected drivers' affective response and satisfaction. That supports treating these parameters as per-sound or per-user variables rather than global constants.

### Cited Findings
- "Design and Evaluation of Electric Vehicle Sound Using Granular Synthesis" (AES E-Library 21566; Seoul National University with the Hyundai Motor Sound Design Research Lab) varied four parameters: sample source, grain duration, grain envelope and RPM range. The design produced 27 sound samples. Each parameter affected drivers' affective experience and satisfaction. — [AES E-Library](https://aes2.org/publications/elibrary-page/?id=21566) (from a search summary only; full text paywalled and the page returned 403 on fetch)
- Hyundai's production system varies grain position, pitch and duration with vehicle parameters. It offers three sound concepts per brand (ICE-inspired to futuristic). Customers can personalize low, mid and high frequency balance and the accelerator response. — [Siemens/Hyundai case study](https://resources.sw.siemens.com/en-US/case-study-hyundai)
- Liu et al. treat the grain window shape as a variable to optimize (by genetic algorithm), not a fixed Hann window. — [SAE 2025-01-0253](https://saemobilus.sae.org/papers/sound-granular-synthesis-method-sci-fi-sound-quality-electric-vehicles-2025-01-0253)
- Doerfler & Wyse report that the same RPM sounds different under acceleration and deceleration, so they condition on RPM deltas. — [arXiv 2603.09391](https://arxiv.org/html/2603.09391)

### Inferences
- Interpretation, proposed split for this project:
  - **Per-source (tuned once per sample, stored with the corpus):** grain size range suited to the source's periodicity, window shape, pitch-sync on or off, and usable read region.
  - **Per-user or personalization (exposed to preference search):** source layer mix weights, density, spray/jitter, the pitch-mapping curve (speed or rpm to pitch ratio, including exponent and range), formant or spectral tilt, the load-to-brightness mapping, and the crossfade curve between low and high load layers.
  - **Fixed engineering limits (not exposed):** headroom limits, smoothing time constants and the maximum grain rate.
- Interpretation: the project currently uses one global grain configuration. That plausibly explains why different presets converge in character, because grain size and envelope strongly shape perceived texture (consistent with the AES finding above). Varying them per source should raise diversity without adding new source material.
- Interpretation: the acceleration-versus-deceleration asymmetry found for ICE engines suggests also feeding d(speed)/dt or the sign of pedal and regen into the granular mapping. This would produce different textures under load and on coast.

### Gaps
- No published perceptual study was found that ranks density, spray or pitch-mapping curves for EV cabin sound. Their effect sizes would have to be measured in this project's own experiments.

## 3. Neural audio synthesis that runs in real time and is controllable (DDSP, RAVE, neural granular, neural engine sound)

### Takeaway
Neural engine-sound synthesis conditioned on RPM, torque and pedal is now an active research area (2024-2026). Nearly all of it builds on DDSP-style harmonic-plus-noise or pulse-train models trained on combustion-engine data. These models are compact and controllable, but each trained model reproduces one sound family. RAVE and BRAVE run in real time on a laptop CPU and provide a latent space suited to timbre transfer and morphing, but the latent space is not directly tied to rpm or load. Neural granular synthesis (Bitton et al.) is the closest match to "granular with learned variety" and is not production-ready.

### Cited Findings
- DDSP (Engel, Hantrakul, Gu & Roberts, ICLR 2020) combines classic DSP modules (harmonic oscillator, filtered noise, reverb) with neural networks that predict their parameters from f0 and loudness. — [arXiv 2001.04643](https://arxiv.org/abs/2001.04643); [GitHub magenta/ddsp](https://github.com/magenta/ddsp)
- Real-time DDSP: Ganis et al. (SMC 2021) built a real-time DDSP plug-in (JUCE) with MIDI control and timbre transfer. They report problems with timbre-transfer quality and with plugin distribution. — [arXiv 2103.07220](https://arxiv.org/pdf/2103.07220.pdf); [SMC PDF](https://vbn.aau.dk/files/467128544/SMC_2021_paper_55.pdf)
- Hayes notes that earlier real-time DDSP required big architectural compromises, a GPU or large buffers. His Neural Waveshaping Synthesis runs in real time on CPU at reasonable buffer sizes. — [NEWT project page](https://ben-hayes.github.io/projects/nws)
- DDSP-based tone transfer models "comfortably run in real-time on a CPU" as a VST. — [arXiv 2310.04811](https://arxiv.org/html/2310.04811v1)
- RAVE (Caillon & Esling 2021) generates 48 kHz audio about 20x faster than real time on a standard laptop CPU. Its real-time use requires the "streaming" export (cached convolutions), otherwise it produces clicks, and a "causal" mode to lower latency. It runs in Max/MSP and Pure Data via nn~, including on embedded hardware. — [arXiv 2111.05011](https://arxiv.org/pdf/2111.05011); [acids-rave PyPI docs](https://pypi.org/project/acids-rave/2.2.1/)
- Caspe, Shier, Sandler, Saitis & McPherson, "Designing Neural Synthesizers for Low-Latency Interaction" (accepted to JAES; arXiv March 2025), analyze latency and jitter in neural audio synthesis models, including RAVE. They propose BRAVE, a low-latency variant with better pitch and loudness tracking, plus a plugin proof of concept. — [arXiv 2503.11562](https://arxiv.org/abs/2503.11562) (abstract only; latency figures not retrieved)
- Neural Granular Sound Synthesis (Bitton, Esling & Harada, arXiv 2008.01393, 2020/2021) replaces the descriptor space of classic granular synthesis with a VAE latent grain space. The space is invertible, so decoding along continuous paths synthesizes sound and source grains need not be stored. A higher-level model learns paths through the space. The authors demonstrate conditional sampling and morphing on pitched, drum and environmental libraries. — [arXiv 2008.01393](https://arxiv.org/abs/2008.01393)
- Neural engine and vehicle sound models:
  - Choi, Kim, Nam (KAIST) & Song (Hyundai), "DDSP-based neural vehicle sound synthesis from driving signals," 6th AES International Conference on Automotive Audio, 2026 (Best Student Paper):
    - Conditioning: CAN-bus RPM, gear, accelerator pedal, speed and longitudinal acceleration.
    - f0 choice: crank-based f0 beat firing-based f0.
    - Signal set: richer signal sets generally improved quality.
    - Conditioning type: encoded conditioning was better on objective metrics, while direct conditioning was best perceptually with all signals.
    - Data and runtime: trained on one 4-cylinder ICE vehicle; real-time performance not reported.
    — [Project page](https://dabinkim0.github.io/publications/ddsp-carsound/index.html)
  - Doerfler & Wyse, "Physics-Informed Neural Engine Sound Modeling with Differentiable Pulse-Train Synthesis" (arXiv 2603.09391, 2026):
    - Method: firing-aligned pulse trains pass through differentiable Karplus-Strong exhaust resonators.
    - Conditioning: RPM and torque plus their first and second deltas at 125 Hz.
    - Result: 5.7% lower total loss and about 21% lower harmonic loss than a harmonic-plus-noise baseline.
    - Runtime: latency and compute not reported.
    — [arXiv HTML](https://arxiv.org/html/2603.09391)
  - Procedural Engine Sounds Dataset (Doerfler & Wyse, 2026): engine audio with sample-accurate RPM and torque annotations. — [arXiv 2603.07584](https://arxiv.org/pdf/2603.07584v1)
  - Doerfler's UPF master's thesis (2025) uses time-varying RPM and torque embeddings. — [Zenodo](https://zenodo.org/records/17304643); [Recercat](https://recercat.cat/handle/10230/72480)
  - Motor2Synth (Lobato et al., AES 2025, HEAD acoustics) models arbitrary combustion engine sounds with DDSP, estimates RPM and targets ASD (active sound design) compatibility. — [HEAD acoustics abstract](https://cdn.head-acoustics.com/fileadmin/data/global/Abstracts/Abstract-AES-2025-Motor2Synth-Leveraging-DDSP-for-Generating-ASD-Compatible-Combustion-Engine-Sounds.pdf)
  - Li, Wang & Li (2024, CCIS vol. 2006) present a hybrid sample-plus-procedural engine sound driven by RPM and pedal, with a DNN tuning pulse-frequency amplitudes. — [Duke Scholars](https://scholars.duke.edu/publication/1621668)
  - Lundberg (2020) studied procedural engine sounds with neural audio synthesis (cited in Doerfler & Wyse's related work). — [arXiv 2603.09391 related work](https://arxiv.org/html/2603.09391)

### Inferences
- Interpretation: DDSP-style models are the most "vehicle-controllable" neural option, because their conditioning inputs can be rpm or speed, load and pedal directly, and they are small enough for CPU use. They need paired training data (control signals plus audio). For an EV designer sound, that data could come from the project's own procedural or granular engine rendered across a speed and load grid. The trained model would then be a fast, smooth emulator, which by itself adds no new diversity.
- Interpretation: RAVE suits the project better as a timbre-transfer stage than as a generator. Feed the existing procedural or granular output through a RAVE model trained on a different corpus (for example, mechanical or sci-fi textures). The result keeps the vehicle-driven pitch and loudness contour but gains a new timbre. Its latent offsets, or a mix between two RAVE models, could become personalization dimensions. Latency and jitter must be checked (see Caspe et al.).
- Interpretation: neural granular synthesis fits the team's preference for granular texture most closely. It is a research codebase, though, and adopting it carries integration risk in a native C++ engine. A lower-risk path is classic granular selection inside a learned or descriptor space (CataRT plus VAE or PCA embeddings of grains), keeping synthesis as plain overlap-add.

### Gaps
- None of the 2024-2026 engine papers reports runtime latency or CPU cost. Real-time feasibility for neural engine sound remains unproven in the published sources found.
- No neural model trained on EV-style (non-combustion) cabin sound was found.
- Exact BRAVE and RAVE latency figures (ms) were not retrieved.

## 4. Text-to-audio and generative models as offline generators of new source material

### Takeaway
Text-to-audio models are too slow and too loosely controllable for in-loop synthesis. They are useful offline for generating many new source clips (drones, whines, textures) that then feed the granular or corpus engine, which directly targets the "low diversity" problem. Stable Audio Open stands out on licensing, because it was trained only on Creative Commons data.

### Cited Findings
- Stable Audio Open (Evans et al., 2024) was trained only on Creative Commons audio from Freesound and the Free Music Archive. The authors screened the training set for copyrighted music using the PANNs tagger. — [arXiv 2407.14358](https://arxiv.org/html/2407.14358v2)
- The same paper notes that AudioGen and AudioLDM were trained on mixes of public datasets that include AudioSet, whose audio licenses are not disclosed. — [arXiv 2407.14358](https://arxiv.org/html/2407.14358v2)
- On AudioCaps, Stable Audio Open scored FD_openl3 78.24, against 186.53 for AudioGen-medium and 170.31 for AudioLDM2-large (lower is better). Its CLAP score was 0.29, against 0.45 and 0.41, so its audio is more realistic but follows prompts less closely. The authors caution that AudioCaps comes from AudioSet, so the comparison may favor the other two. — [arXiv 2407.14358](https://arxiv.org/html/2407.14358v2)
- No memorization of training data was detected. Music quality is lower than earlier Stable Audio models, which the authors attribute to the CC-only training data. — [alphaXiv overview](https://alphaxiv.org/overview/2407.14358v2); [arXiv 2407.14358](https://arxiv.org/html/2407.14358v2)

### Inferences
- Interpretation, proposed pipeline:
  1. Prompt-sweep a text-to-audio model offline (for example "low electric motor hum", "turbine whine rising", "metallic resonant drone"), with many seeds per prompt.
  2. Filter outputs automatically (stationarity, tonality, absence of transients or music) and then by ear.
  3. Segment the survivors and add them to the descriptor-analyzed grain corpus.
  The real-time engine stays native C++ with deterministic latency, while generative AI supplies diversity.
- Interpretation: generated clips are typically static or short. The vehicle-responsive behavior must still come from the granular mapping. Generating several clips along a prompt axis ("calm" to "aggressive") could create ordered layers for load-dependent crossfades.
- Interpretation: for an academic prototype, Stable Audio Open's CC training data is the most defensible choice. The model weights' own license terms must still be checked before any commercial follow-on.

### Gaps
- No primary sources were fetched for Make-An-Audio, AudioLDM or AudioGen themselves (only Stable Audio Open's description of them). Their inference speed and license terms are unverified here.
- No study was found that uses text-to-audio output as granular source material for vehicle sound.

## 5. Interpolation and morphing in a learned timbre space instead of discrete presets

### Takeaway
VAE-based "generative timbre spaces" support continuous paths between sounds, and perceptual regularization can align distances in the space with how listeners judge timbre similarity. Combined with RAVE or neural granular latents, or with CataRT descriptor spaces, this lets a small set of continuous coordinates replace preset blending. A compact space like that suits preference search.

### Cited Findings
- Esling, Chemla-Romeu-Santos & Bitton (DAFx 2018 / ISMIR 2018), "Generative timbre spaces":
  - Method: the VAE latent space is regularized with perceptual dissimilarity ratings, so the latent space reflects perceived timbre similarity.
  - Paths: the space can generate any path between instruments.
  - Smoothness: descriptors have a non-linear global topology but evolve smoothly locally.
  - Front end: the NSGT gave the best correlation with timbre and the best synthesis quality.
  - Control: descriptor-based synthesis keeps the timbre structure.
  — [arXiv 1805.08501](https://arxiv.org/abs/1805.08501v2); [DAFx archive](https://dafx.de/paper-archive/details/Hit9Fiegl7IDPYLADR8a3A)
- Later work shows that linear interpolation between two latent series produces audio that moves smoothly from sample A to sample B. — [arXiv 2008.01370](https://arxiv.org/pdf/2008.01370v2.pdf)
- Neural granular synthesis supports morphing and conditional sampling by moving through a continuous latent grain space. — [arXiv 2008.01393](https://arxiv.org/abs/2008.01393)
- CataRT exposes a navigable 2-D or higher projection of a corpus descriptor space as a control surface. — [Einbond & Schwarz 2010](https://openaccess.city.ac.uk/id/eprint/16732/1/Einbond10a.pdf)

### Inferences
- Interpretation: a practical non-neural "timbre space" for this project:
  1. Embed every corpus grain with descriptors, or with a pretrained audio embedding.
  2. Reduce the embeddings to 2-4 dimensions (PCA or UMAP).
  3. Let the preference search choose a region center and radius per user.
  4. Shift the target within that region with vehicle state.
  This gives a compact, continuous search space (around 4-8 parameters, adding the per-user granular parameters from Section 2), which fits the interactive comparison loop better than a categorical preset index.
- Interpretation: global latent-space topology is non-linear (Esling 2018). Keep each user's region local and morph along short paths to avoid abrupt timbre jumps.

### Gaps
- No study was found that applies learned timbre-space morphing to vehicle or EV sound personalization specifically.

## 6. Compute constraints: what runs on a laptop in real time with low latency

### Takeaway
Classic granular and concatenative synthesis (overlap-add, nearest-neighbor lookup over a precomputed corpus) is cheap and deterministic on a laptop. RAVE runs about 20x faster than real time on a laptop CPU, but adds latency and jitter that need explicit engineering (streaming or causal export, BRAVE). DDSP-family models run in real time on CPU as plugins. Text-to-audio diffusion models belong offline.

### Cited Findings
- RAVE runs about 20x faster than real time at 48 kHz on a laptop CPU. A secondary source reports about 985 kHz throughput on CPU and 11.7 MHz on GPU. Real-time use needs the streaming (cached convolution) and causal modes. — [arXiv 2111.05011](https://arxiv.org/pdf/2111.05011); [acids-rave docs](https://pypi.org/project/acids-rave/2.1.3/)
- Latency and jitter in neural audio synthesis models are a distinct design problem, and BRAVE targets low latency. — [arXiv 2503.11562](https://arxiv.org/abs/2503.11562)
- DDSP-based models run in real time on CPU as VST/JUCE plugins. — [arXiv 2310.04811](https://arxiv.org/html/2310.04811v1); [Ganis et al. 2021](https://arxiv.org/pdf/2103.07220.pdf); [NEWT](https://ben-hayes.github.io/projects/nws)
- CataRT's descriptor analysis of a corpus runs faster than real time, and its unit selection runs live in Max/MSP. — [Schwarz NIME 2012](https://vhosts.eecs.umich.edu/nime2012/Proceedings/papers/120_Final_Manuscript.pdf)
- Baldan et al. present their physically informed model as computationally efficient compared with sample-based methods. — [CORE PDF](https://core.ac.uk/download/53578982.pdf)

### Inferences
- Interpretation, tiers for this project:
  - **Tier 1 (in the C++ engine now):** state-driven grain selection with jitter, multiple layers, per-source grain settings, and descriptor-space targeting.
  - **Tier 2 (optional add-on):** an offline-trained DDSP or RAVE model run through ONNX/libtorch in the sidecar or the native engine, applied as a timbre-transfer stage. Measure buffer size against latency first.
  - **Tier 3 (offline only):** text-to-audio generation of source material.
- Interpretation: real-time neural inference inside the existing C++ audio callback needs care, because model inference must not block the audio thread. A separate thread with a lock-free ring buffer is the usual pattern. This is general audio engineering practice, not taken from a cited source.

### Gaps
- No published laptop benchmark was found for running DDSP or RAVE alongside a vehicle simulation and BeamNG concurrently. This needs to be measured on the project's own hardware.
