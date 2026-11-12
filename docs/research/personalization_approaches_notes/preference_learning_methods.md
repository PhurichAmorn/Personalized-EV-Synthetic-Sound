# Preference learning methods for personalizing high-dimensional sound (alternatives to classic IEC)

Scope note: notes collected 2026-11-12 from web searches and a limited number of full-text fetches (about 17 tool calls). Items marked "[not verified in this session]" are recalled from well-known literature. Their bibliographic details and URLs are likely correct, but the report writer should confirm them before citing. "Inferences" are project interpretation for EV Sound Lab, not published findings.

## 1. Latent-space and Bayesian-optimization approaches (search a low-dimensional space, not raw synth parameters)

### Takeaway
The best-supported alternative to IEC is human-in-the-loop Bayesian optimization (BO), and preferential BO in particular, run on a low-dimensional search space. That space is either a learned latent space (VAE/GAN/flow) or a random or line/plane subspace of the parameter space. Published studies report convergence in roughly 10–60 judgments. Koyama-style line and plane searches let a user handle 6–20+ dimensions with one slider or one gallery click per iteration.

### Cited Findings
- **Sequential Line Search (Koyama, Sato, Sakamoto, Igarashi, SIGGRAPH 2017 / ACM TOG 36(4)).** Each iteration the user moves one slider along a 1-D line chosen by BO in the n-D space. The slider output feeds a Bradley–Terry-style preference GP. Demonstrated on photo color enhancement and similar tasks. [not verified in this session] — [project page](https://koyama.xyz/project/sequential_line_search/)
- **Sequential Gallery (Koyama, Sato, Goto, ACM TOG 39(4):88, SIGGRAPH 2020, DOI 10.1145/3386569.3392444).** "Sequential plane search" splits an n-dimensional slider space into a sequence of 2-D plane-search subtasks. The user picks the best cell in a 2-D grid gallery, and the method is a variant of preferential BO. — [project page](https://koyama.xyz/project/sequential_gallery); [author PDF](https://www.koyama.xyz/project/sequential_gallery/download/author-version.pdf)
- PBO with a Sequential-Gallery interface "still requires 10 to 15 iterations to converge" (as characterized by Li, Liao, Holz 2025, citing Koyama 2020). — [arXiv 2507.15355](https://arxiv.org/abs/2507.15355)
- **BO as Assistant (Koyama & Goto, UIST 2022).** A follow-up in which BO suggestions sit alongside free manual slider editing rather than replacing it. — [project page](https://www.koyama.xyz/project/bo-as-assistant/); [PDF](https://staff.aist.go.jp/m.goto/PAPER/UIST2022koyama.pdf)
- **Preferential Bayesian Optimization (González, Dai, Damianou, Lawrence, ICML 2017).** BO driven only by duels (pairwise comparisons), modelled with a GP over a preference function. [not verified in this session] — [PMLR](http://proceedings.mlr.press/v70/gonzalez17a.html)
- **Active preference learning with discrete choice data (Brochu, de Freitas, Ghosh, NIPS 2007)**, plus Brochu et al. 2010 on procedural animation. These are the earliest human-preference BO for design. Both are cited as prior work by Marcos et al. 2025. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12637961/)
- **REMBO (Wang, Hutter, Zoghi, Matheson, de Freitas, IJCAI 2013 / JAIR 2016).** Optimizes in a random low-dimensional linear embedding of a high-dimensional space. It works when the objective has low "effective dimensionality". [not verified in this session] — [arXiv 1301.1942](https://arxiv.org/abs/1301.1942)
- **ROMBO (Marcos, Mur-Labadia, Martinez-Cantin, PLoS One 20(11): e0335853, 2025).** Random *rotational* embeddings keep the Gaussian structure of a generative model's latent space.
  - **Setup:** PowGAN symbolic music generator with a 256-D latent space, searched through a d=10 embedding. Matérn-5/2 ARD kernel, Expected Improvement, Sobol initialization.
  - **Feedback:** 0–10 ratings on about 10-second clips.
  - **Human study:** 16 participants (8 BO, 8 random), 22 Sobol samples + 42 optimized samples = 64 clips per person in about 30 minutes.
  - **Simulation result:** beat REMBO and random search (final loss 0.44 vs 0.57 REMBO vs 1.00 random).
  - **Human result:** the BO group found new favourites about 40% more often, about 16% faster, and spent about 18% less time on disliked pieces.
  - **Prior work:** the authors call it only "the second" BO-with-human-feedback music generation work.
  - [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12637961/)
- **Generative Melody Composition with Human-in-the-Loop BO (MuMe 2020; Zhou, Koyama, Goto, Igarashi [authors not verified in this session]).** Human-in-the-loop BO over a 4-D latent space of MusicVAE, with user preference as the objective. — [arXiv 2010.03190](https://arxiv.org/pdf/2010.03190)
- **Synthesizer sound design via BO in a VAE latent space (DRS 2022 conference paper, "Listening tests for sound design: faster optimization through lower-dimensional parameter spaces").** Pairs BO with a VAE that compresses synth parameters to a 2-D latent space. Reports that optimizing in the compressed space can reduce the number of human listening trials. The full text could not be fetched (403), so effect sizes were not verified. — [DRS](https://dl.designresearchsociety.org/cgi/viewcontent.cgi?article=3072&context=drs-conference-papers); [ResearchGate](https://www.researchgate.net/publication/366433301_Listening_tests_for_sound_design_faster_optimization_through_lower-dimensional_parameter_spaces)
- **Sequential subspace search over a generative image model's latent space with GP preference model and content-based guidance (arXiv 1906.09840, Chiu, Koyama et al. [authors not verified in this session]).** Shows the Koyama approach transfers to GAN latents. — [arXiv 1906.09840](https://arxiv.org/pdf/1906.09840)
- **User-driven voice generation via latent-space navigation (arXiv 2408.17068, 2024).** Frames voice design as black-box optimization of perceptual preference in a generator's latent space and draws an explicit parallel to sound designers tuning synth parameters. — [arXiv 2408.17068](https://arxiv.org/html/2408.17068v4)
- **Perceptually regularized synth VAE (Roche et al., "Make that sound more metallic").** Uses listener perceptual ratings to shape a synth-sound VAE latent so that its axes align with timbre perception. — [ResearchGate](https://www.researchgate.net/publication/351676393_Make_That_Sound_More_Metallic_Towards_a_Perceptually_Relevant_Control_of_the_Timbre_of_Synthesizer_Sounds_Using_a_Variational_Autoencoder)
- **RAVE latents for interaction.** RAVE encodes 2048-sample buffers into a 128-D latent space (NIME 2024). NIME user studies report that RAVE latent dimensions are not explicitly tied to semantic attributes (NIME 2026), and that a single input often cannot be mapped to one sonic feature (Stacco, NIME 2024). — [NIME 2024 #49](https://nime.org/proceedings/2024/nime2024_49.pdf); [Stacco NIME 2024](https://nime.org/proceedings/2024/nime2024_62.pdf); [NIME 2026 #58](https://nime.org/proceedings/2026/nime2026_58.pdf)
- **Comparator outside audio.** In GAN level design, participants slightly preferred a latent *exploration* interface over pure interactive evolution. — [arXiv 2004.00151](https://arxiv.org/pdf/2004.00151)
- **Feasibility-aware latent spaces for preference exploration (arXiv 2609.00527).** Applied to procedural automotive wheel designs. It is a design-domain analogue of keeping latent samples in the valid region. — [arXiv 2609.00527](https://arxiv.org/pdf/2609.00527)

### Inferences
- **Scaling with dimensionality.**
  - GP-based BO degrades beyond about 10–20 dimensions.
  - Line and plane search keeps per-iteration user effort constant (1 slider or 1 grid) however large n is. Convergence still slows with n, and the published demos are roughly 6–20 dimensions.
  - Random or rotated embeddings (REMBO/ROMBO) or a learned latent of about 2–16 dimensions are the standard way to make 50+ synth parameters tractable.
- **Implication for EV Sound Lab.** The current preset-blend design is effectively a hand-made low-dimensional embedding, which explains the low diversity.
  - A VAE or flow trained on *many* random but valid procedural-engine parameter sets, regularized to be perceptually smooth, would give a continuous space of, say, 8–16 dimensions that is not limited to preset convex hulls.
  - BO, Sequential Line Search, or Sequential Gallery can then search that space.
- **Driving context.** EV sound depends on vehicle state, so a "candidate" is a *mapping* (sound × speed/load), not a static clip. Line search with a real-time slider while driving or replaying a scripted drive is plausible because the native engine already renders in real time. This is project interpretation; no published EV study does this.

### Gaps
- No published study found that applies PBO or Sequential Gallery specifically to *dynamic*, state-dependent vehicle sound.
- Quantitative effect sizes for the DRS 2022 synth-BO paper could not be retrieved.
- No direct head-to-head study of IEC versus PBO on synth timbre was found in this session.

## 2. Alternative feedback modalities

### Takeaway
Feedback that is richer than a 1–7 rating carries more information per interaction:
- continuous slider positions (line search),
- a choice from a gallery,
- semantic descriptors,
- natural-language text.

The best-validated audio examples are:
- learned semantic knobs (Huang et al. 2014; SAFE; FlowSynth),
- CLAP-based text-to-parameter optimization (Text2FX, CTAG).

Implicit and physiological signals are mostly unvalidated for sound-design personalization.

### Cited Findings
- **AdaptiveKnobs (Huang, Duvenaud, Arnold, Partridge, Oberholtzer, Gajos, IUI 2014, pp.115–124).**
  - Gaussian processes learn the mapping from synth parameters to a user's perceived level of a high-level quality such as "scratchy" or "bright". The system then builds a single knob that raises or lowers that quality.
  - Active learning queries the sounds expected to be most informative.
  - In simulation it learned knobs faster than several baselines, including for non-linear concepts.
  - [Harvard page](https://www.eecs.harvard.edu/~kgajos/papers/2014/huang14active.shtml); [PDF](https://kgajos.seas.harvard.edu/papers/huang14knobs.pdf)
- **FlowSynth / Flow synthesizer (Esling, Masuda, Bardet, Despres, Chemla-Romeu-Santos).**
  - Published at DAFx 2019, Applied Sciences 10(1):302 (2020), and as an IJCAI 2020 demo.
  - A VAE latent audio space is mapped to synth parameters (Diva) through normalizing flows, with "regression flows" organizing latent dimensions. Disentangled latent dimensions act as *semantic macro-controls*.
  - Supports parameter inference from audio and preset interpolation, and runs in real time in Ableton Live.
  - [DAFx](https://dafx.de/paper-archive/details/cur8Axp8MOYa1QzdZW_Nug); [arXiv 1907.00971](https://arxiv.org/abs/1907.00971v1); [IJCAI 2020](https://www.ijcai.org/proceedings/2020/767); [IRCAM page](https://acids.ircam.fr/flowsynth)
- **SAFE, Semantic Audio Feature Extraction (Stables, Enderby, De Man, Fazekas, Reiss, ISMIR 2014).** DAW plugins that crowdsource descriptor-to-parameter pairs (for example "warm" and "bright" for EQ and compression) so that semantic presets can be recalled. [not verified in this session; search did not return the paper]
- **Text2FX (Chu, O'Reilly, Barnett, Pardo, ICASSP 2025).**
  - Combines CLAP embeddings with differentiable DSP so an open-vocabulary prompt steers EQ and reverb parameters. Optimization is per instance, with no retraining.
  - Listener study: at least one CLAP optimization improved ratings in 67–75% of cases. The directional variant beat the cosine variant.
  - [arXiv 2409.18847](https://arxiv.org/abs/2409.18847)
- **CTAG (Cherep, Singh, Shand, ICML 2024).**
  - Text-to-audio built by optimizing the 78 parameters of a virtual modular synthesizer against a text prompt (CLAP scoring per secondary summaries).
  - Outputs are "distinctive and artistic" yet identifiable as matching the prompt, comparable to neural text-to-audio. The parameters stay interpretable and editable.
  - [arXiv 2406.00294](https://arxiv.org/abs/2406.00294); [MIT Media Lab](https://www.media.mit.edu/projects/ctag/overview/)
- **SynthScribe (NeurIPS 2023 ML4CD workshop).** Multimodal (text and audio) synth sound retrieval and exploration using deep embeddings. — [arXiv 2312.04690](https://arxiv.org/pdf/2312.04690)
- **Implicit and engagement feedback in IEC.** One 2025 workshop paper adjusts mutation rates based on tracked user engagement to reduce fatigue, but it was tested with only 5 volunteers. — [CEUR Vol-4158](https://ceur-ws.org/Vol-4158/Short02.pdf)
- **IEC fatigue is well documented.**
  - Takagi notes that IEC is limited to small populations and about 10–20 generations because of human fatigue.
  - McDermott, O'Neill and Griffith (2010) proposed interfaces for faster evaluation of large timbre populations.
  - Fukumoto and Hanada (2020) split IEC sound evaluation over several days (42 subjects).
  - [Galway](https://research.universityofgalway.ie/en/publications/interactive-ec-control-of-synthesized-timbre-3/); [SMC 2024 paper](https://smcnetwork.org/smc2024/papers/SMC2024_paper_id158.pdf); [Kaliakatsos et al.](https://www.epitropakis.co.uk/sites/default/files/pubs/KaliakatsosEFVevoSIrev.pdf)

### Inferences
- **What each modality needs from the user:**
  - Slider (line search): 1 continuous adjustment per iteration.
  - Gallery (plane search): 1 click among about 9–25 items. This is costly for audio because sounds must be auditioned serially, so a gallery of 4–6 short clips is more realistic than a 5×5 grid.
  - Semantic descriptors: a vocabulary agreed in advance, plus some calibration data.
  - Text: no training, but it depends on CLAP's understanding, which is weak for niche concepts such as "EV whine".
- **Most promising hybrid for EV Sound Lab:**
  - Learn about 4–8 semantic macro-knobs from pilot data (AdaptiveKnobs/SAFE style).
  - Let the user drive directly with those knobs.
  - Have BO propose the next slider line, combining direct manipulation with PBO (BO-as-Assistant style).
- **Audio-specific constraint:** galleries are much less efficient for audio than for images because listening is serial.

### Gaps
- No peer-reviewed study found that uses dwell, replay, or skip signals or physiological signals (EDA, HR) to personalize *synthesized sound design*. Music-recommender implicit-feedback literature exists but was not searched in depth here.
- No CLAP-style text model was found that is validated on vehicle or EV sound vocabulary.

## 3. LLM- and AI-assisted personalization (text-to-audio, RLHF/DPO, aesthetic reward models)

### Takeaway
Preference fine-tuning of generative audio models (RLHF and DPO) works at population scale (MusicRL used about 300k pairwise preferences; Tango 2 used synthetic preferences). It is not a per-user, single-session method. For individual personalization within a session, the practical AI tools are:
- LLMs or CLAP that translate language into parameters (LLM2Fx, Text2FX, CTAG),
- few-shot concept personalization (DreamBooth for audio),
- pretrained aesthetic predictors (Audiobox Aesthetics) used as priors or filters.

### Cited Findings
- **MusicRL (Cideron et al., Google DeepMind, ICML 2024, PMLR 235:8968–8984).** The first music generator fine-tuned from human feedback. MusicLM was RL-fine-tuned on text-adherence and quality rewards (MusicRL-R) and on a user-preference reward model built from about 300,000 pairwise preferences of deployed users (MusicRL-U). The combined RU version was best with raters. Ablations show that text adherence and quality explain only part of human preference. — [PMLR](https://proceedings.mlr.press/v235/cideron24a.html); [arXiv 2402.04229](https://arxiv.org/abs/2402.04229)
- **Tango 2 (Majumder, Hung, Ghosal, Hsu, Mihalcea, Poria, ACM MM 2024).** Diffusion-DPO fine-tuning of the Tango text-to-audio model on Audio-alpaca, a synthetic preference set built from LLM-perturbed prompts and CLAP re-ranking. Beats Tango and AudioLDM2 on objective and subjective metrics. — [arXiv 2404.09956](https://arxiv.org/abs/2404.09956)
- **Survey: "Aligning Generative Music AI with Human Preferences: Methods and Challenges" (arXiv 2511.15038, 2025).** — [arXiv](https://arxiv.org/html/2511.15038v1)
- **Meta Audiobox Aesthetics (FAIR/Reality Labs, arXiv 2502.05139, Feb 2025).**
  - A no-reference predictor of four axes: Production Quality, Production Complexity, Content Enjoyment, and Content Usefulness. Secondary summaries disagree on the fourth axis's name.
  - Covers speech, music, and sound. The model and code are open (facebookresearch/audiobox-aesthetics).
  - Competitive with or better than DNSMOS, SQUIM, and UTMOSv2 on some axes.
  - [arXiv 2502.05139](https://arxiv.org/abs/2502.05139); [Meta page](https://ai.meta.com/research/publications/meta-audiobox-aesthetics-unified-automatic-quality-assessment-for-speech-music-and-sound/)
- **Personalization of text-to-music (Plitsis et al., ICASSP 2024).** DreamBooth and Textual Inversion on AudioLDM learn a new concept from a few audio clips. Rhythm is learned more easily than melody. DreamBooth fails to keep extreme dynamics because it normalizes audio. Similarity metrics agreed with user preferences. — [arXiv 2309.11140](https://arxiv.org/abs/2309.11140); [code](https://github.com/zelaki/DreamSound)
- **PAGURI (ISMIR 2024).** A user-experience study of creative interaction with AudioLDM2, including DreamBooth personalization from users' own uploaded samples. — [arXiv 2407.04333](https://arxiv.org/pdf/2407.04333)
- **LLM2Fx (arXiv 2505.20770, 2025).** Zero-shot LLMs (for example GPT-4o) map natural language directly to EQ and reverb parameters as JSON. For EQ, the MMD was 0.22 against 0.55 for a CLAP-optimization baseline. Adding DSP features, DSP code, and few-shot examples helped further. — [demo](https://seungheondoh.github.io/llm2fx-demo/); [summary](https://pith.science/paper/2505.20770)
- **AutoSynth (arXiv 2610.10774, 2026).** Generates editable synthesizer programs (parameters plus modulation routing) from audio and text. The authors say joint generation from natural language is still open. — [arXiv](https://arxiv.org/html/2610.10774v1)
- **Text-steerable procedural soundscape instrument via LLMs (arXiv 2607.00309, 2026).** An LLM steers procedural audio parameters. — [arXiv](https://arxiv.org/html/2607.00309)
- **Commercial text-to-preset tools (for example "PresetLab" for Serum 2/Diva).** These exist, but the claims come from blogs and gists and are unverified. — [Substack](https://substack.aicentral.blog/p/drop-the-sample-get-the-sound); [gist](https://gist.github.com/0xdevalias/5a06349b376d01b2a76ad27a86b08c1b)

### Inferences
- **RLHF and DPO are out of scope per participant.** They need thousands to hundreds of thousands of comparisons and a neural generator, while EV Sound Lab uses a procedural C++ engine. They could make sense only *across* participants, for example to train a population reward model.
- **LLM as conversational sound designer.** This is feasible with the current procedural engine, following the LLM2Fx/CTAG pattern:
  - The user says "more aggressive, less whine at high speed".
  - The LLM, given the parameter schema and documentation, proposes parameter deltas.
  - Optionally, CLAP or BO refines the result.
  - The procedural engine stays interpretable, which fits the project rule to keep the baseline method.
- **Audiobox Aesthetics is a general-quality prior, not personal taste.** It was trained on speech, music, and sound, not cabin or vehicle sound, so it is best used to filter out low-quality candidates before human evaluation. That use is unvalidated for EV sound.
- **Text-to-audio is a poor fit for the driving loop.** Neural text-to-audio models (Tango, AudioLDM, MusicGen) produce fixed clips. They are not real-time, state-driven engines, so they would mainly serve as source-material generators, consistent with the separate "source-first" direction.

### Gaps
- No study found on LLM-mediated *per-user* iterative refinement of synth sound with measured user satisfaction against IEC or BO.
- No per-user (single-session) DPO or RLHF personalization of audio generators was found. Existing work is population-level alignment.

## 4. Music recommender cold-start and preference elicitation

### Takeaway
Recommender research offers questionnaire- and personality-based priors. Examples are the MUSIC five-factor model (Mellow, Unpretentious, Sophisticated, Intense, Contemporary) and Big Five links. These help cold-start modestly, but they model taste in *content* (genres and songs), not timbre or synthesized sound parameters. Transfer to EV sound is speculative.

### Cited Findings
- **MUSIC model (Rentfrow, Goldberg, Levitin, 2011, JPSP).** Five factors derived from affective reactions to music excerpts across genres. A replication is "The Song Remains the Same". — [Stanford GSB](https://www.gsb.stanford.edu/index%2Ephp/node/428616)
- **Soleymani, Aljanaki, Wiering, Veltkamp (ICME 2015).** Mapped songs onto the MUSIC attributes and used them for cold-start. Results were better than genre, artist, or acoustic-similarity baselines. — [PDF](https://webspace.science.uu.nl/~veltk101/publications/art/SMART2015.pdf); [IEEE](https://doi.ieeecomputersociety.org/10.1109/ICME.2015.7177504)
- **MUSIC profiles for new-user cold-start (Intelligent Decision Technologies, 2021).** Reported to help. — [IOS Press](https://content.iospress.com/articles/intelligent-decision-technologies/idt210196)
- **Laplante (ISMIR 2014).** Reviews new-user cold-start and genre-questionnaire elicitation. — [PDF](https://archives.ismir.net/ismir2014/paper/000339.pdf)

### Inferences
- **A cheap 1–2 minute pre-session elicitation could initialize the search.**
  - Contents: a short semantic questionnaire ("prefer quiet/futuristic/engine-like/sporty") or a few "pick favourite of 4" archetype clips.
  - Purpose: set a BO prior mean or starting region.
  - Cost: low. Benefit: unproven.
- **Personality questionnaires are probably not worth the session time** given weak evidence of transfer to timbre preference.

### Gaps
- No validated link was found between personality or MUSIC factors and preference for synthetic vehicle or timbre sounds.
- Implicit-feedback (skip/dwell) cold-start literature in music recommenders was not reviewed in depth.

## 5. Population priors and warm-starting new users

### Takeaway
Recent HCI work shows that preference models from earlier users can cut the iterations a new user needs. Meta-PO (UIST 2025) is the closest analogue: Sequential-Gallery PBO plus a transfer acquisition function over prior users' models, reported to take about 6–8 interactions versus 10–15. This fits a lab study in which each participant adds to the pool.

### Cited Findings
- **Meta-PO (Li, Liao, Holz, ETH Zürich, UIST 2025, arXiv 2507.15355).**
  - Combines PBO with meta-learning. Prior users' preferences are stored as GP models, and a TAF-R variant weights them by similarity to the current user's observations. Their influence fades as the user's own data accumulates.
  - Builds on the Sequential Gallery 2-D plane interface.
  - Reported about 5.86 interactions on average under similar objectives and convergence within 8 under diverse objectives, against 10–15 for standard PBO. These figures are from secondary summaries plus the abstract, so verify them in the paper.
  - [arXiv 2507.15355](https://arxiv.org/abs/2507.15355)
- **HOMI (arXiv 2510.07754, 2025).** Priors learned from user models for human-in-the-loop optimization. Targets cold start and compares against standard BO and TAF. — [arXiv](https://arxiv.org/pdf/2510.07754)
- **Multi-task PBO for human-in-the-loop MPC tuning (Control Engineering Practice, 2026).** Reuses preference data from earlier tasks or users and adds a batch-initialization strategy. Validated on 4 real tasks. — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0967066126002169)
- **CoExBO (Adachi et al., AISTATS 2024, PMLR 238).** Elicits the user's belief about the optimum through preference learning and adds it to the acquisition function as a soft constraint, making the BO collaborative and explainable. — [PMLR](https://proceedings.mlr.press/v238/adachi24a/adachi24a.pdf)
- **RGPE (Feurer, Letham, Bakshy, AutoML 2018).** A ranking-weighted GP ensemble for warm-starting BO from past runs. A standard non-preferential baseline. — [PDF](https://ml.informatik.uni-freiburg.de/wp-content/uploads/papers/18-AUTOML-RGPE.pdf)

### Inferences
- **Concrete EV Sound Lab design:**
  - Store each participant's final preferred point and their preference GP. Session records already exist, but `experiment_data/` must stay local.
  - Cluster the final points into about 3–6 "archetypes" and use them as the initial gallery and candidates for a new participant.
  - Optionally use Meta-PO/TAF weighting for later participants.
  - This addresses both cold start and diversity, since archetypes come from real preferences rather than hand-made presets.
- **Caveat:** warm-starting biases later participants toward earlier ones. For research validity, counterbalance it or keep a no-prior condition.

### Gaps
- No audio- or sound-domain study of population-prior PBO was found. All evidence is visual design, control tuning, or simulation.
- The minimum number of prior users needed for a useful prior in a 20–40 participant study is unknown.

## 6. Practicality for a small lab study (about 20–40 minute sessions)

### Takeaway
Evidence-weighted, the most practical stack is:
- a low-dimensional (about 6–12 dimensions) learned or random-embedded control space over the existing procedural engine, searched with Sequential Line Search or PBO with a small audio gallery;
- semantic or text input to jump-start the search;
- population priors from earlier participants.

Published human-in-the-loop BO studies with 8–16 participants and 30-minute sessions are the closest feasibility evidence. RLHF/DPO and diffusion fine-tuning are not feasible per session.

### Cited Findings
- **ROMBO human study.** 64 clips in about 30 minutes per participant, 16 participants, 0–10 ratings. Measurable benefit over random sampling. — [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12637961/)
- **PBO with a gallery interface.** About 10–15 iterations to converge, falling to about 6–8 with prior-user meta-learning (Meta-PO). — [arXiv 2507.15355](https://arxiv.org/abs/2507.15355)
- **Text2FX and CTAG.** No per-user training. Per-instance optimization runs from a prompt. — [Text2FX](https://arxiv.org/abs/2409.18847); [CTAG](https://arxiv.org/abs/2406.00294)
- **MusicRL.** Needed about 300k preferences, so population scale only. — [arXiv 2402.04229](https://arxiv.org/abs/2402.04229)
- **IEC.** Practically limited to about 10–20 generations by fatigue. — [Galway/McDermott](https://research.universityofgalway.ie/en/publications/interactive-ec-control-of-synthesized-timbre-3/)

### Inferences
Rough ranking by fit for a 20–40 minute session. All rankings are project interpretation.
1. **Sequential Line Search (or BO-as-Assistant) on about 6–12 dimensions.** The dimensions come from a perceptually regularized VAE or flow trained offline on random valid engine parameters, or from a REMBO/ROMBO random embedding as a no-training fallback. One slider per iteration while a scripted drive loops. Expect about 15–30 iterations. Highest evidence and lowest fatigue.
2. **Semantic macro-knobs, AdaptiveKnobs/FlowSynth style.** Learned from pilot participants' descriptor ratings ("bright", "aggressive", "futuristic", "smooth"). The user tunes them directly for free exploration, then BO refines.
3. **LLM conversational front end.** Maps free-text feedback to parameter deltas (LLM2Fx pattern). Useful for satisfaction and agency. The evidence is from effects (EQ and reverb), not synth timbre, so treat it as exploratory.
4. **Archetype or population warm start.** Meta-PO style, accumulating across participants.
5. **Aesthetic or quality filter.** Audiobox Aesthetics or simple headroom and roughness checks to prune bad candidates before the listener hears them. Not validated for EV sound.
6. **Not recommended per session:** RLHF/DPO, DreamBooth/LoRA training, and physiological sensing. Each is too slow, too data-hungry, or unvalidated.

**Diversity fix:** sample the training set for the latent model from the *full* parameter space, not preset blends. This directly targets the "only presets" complaint.

### Gaps
- No published comparison exists of these methods on time-varying, vehicle-state-dependent sound.
- No direct evidence was found on whether users are *more satisfied* (as opposed to converging faster) with PBO than with IEC for sound. Satisfaction should be an explicit outcome measure in the study.
