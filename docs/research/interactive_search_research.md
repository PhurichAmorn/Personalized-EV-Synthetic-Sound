# Interactive preference research and proposed direction

## Scope

This note compares methods that use listener feedback to generate or select the next sound or music candidate. It focuses on interactive evolutionary computation (IEC/IGA), pairwise Gaussian-process preference learning, preferential Bayesian optimization (PBO), and related hybrids. Character vocabulary may describe candidates, but preference feedback guides search.

## Method comparison

| Method | Listener input | Search mechanism | Strength | Main risk here |
| --- | --- | --- | --- | --- |
| IEC / interactive GA | Rates or selects several generated candidates, often once per generation | Select, mutate, recombine, and retain high-fitness candidates | Supports broad candidate diversity and recombination where quality is hard to encode | Repeated rating causes fatigue; strong selection can converge early or lose alternate character families |
| Pairwise GP preference learning | Chooses preferred sound from a pair; may allow equal/neither | Infers latent preference over candidate features from pairwise comparisons | Natural, low-burden choice; can generalize to untested candidates when features/kernel are useful | Poor features or kernel mislead predictions; model alone does not ensure broad exploration |
| Preferential Bayesian optimization | Compares pairs selected by an acquisition rule | Uses GP uncertainty and predicted preference to choose informative or promising comparisons | Spends limited feedback strategically | Standard optimization may focus on one predicted best region too soon for character discovery |
| Multi-attribute preference BO / menu methods | Compares candidates represented by several outcome attributes | Models uncertainty in attribute trade-offs and returns a diverse menu | Retains several plausible choices instead of assuming one estimate identifies the only winner | Needs trustworthy candidate attributes and more complex modeling |
| Surrogate-assisted / continuous IEC | Rates or selects candidates; may split work across sessions | Adds constraints, surrogate predictions, or staged evaluation to reduce direct human scoring | Keeps evolutionary search while reducing fatigue or enabling longer runs | Added machinery; gains depend on surrogate/fitness matching listener preference |
| RL-based co-exploration | Works with agent while exploring sound controls | Learns useful exploration actions or parameter moves | Can help skilled sound designers explore high-dimensional interfaces | Not the simplest fit for a short, bounded preference session; reward and interaction design are substantial |

**Terms:** GA (genetic algorithm) is an optimization family. IEC means a human supplies evaluation used by evolutionary computation; IGA is an interactive genetic algorithm. GP preference learning models choices. PBO adds a rule for choosing subsequent comparisons. Recipe awareness describes candidate constraints/proposal rules; by itself, it is not a distinct preference-learning model.

## Evidence from music and sound studies

- **Music composition with IGA:** Unehara, Ebihara, and Onisawa encode melody properties in chromosomes, generate 200 chromosomes, filter these to 20 candidates with musical-rule fitness, then ask the user to evaluate them. Their paper reports that objective fitness filtering reduced human evaluation fatigue. Useful for this project: screen candidates before asking listeners, instead of exposing arbitrary parameter combinations.
- **Sound synthesis with interactive evolution:** Dahlstedt describes repeatedly selecting preferred synthesized sound objects from genetically bred populations to explore large synthesis spaces. Listener guides aesthetic search without programming every sound-engine parameter.
- **IEC across multiple days:** Fukumoto and Hanada's CEIEC study explicitly targets evaluation fatigue. Sixteen participants selected bright sign sounds over two days of 15 generations each, then rated sounds from generations 0, 14, and 29 on day three. The highest-rated tested sound came from generation 29. This shows many evolutionary rounds can be spread over time; it does not establish that one 15–20-pair session is enough or necessary.
- **Pairwise GP for music preference:** Jensen, Saez Gallego, and Larsen model pairwise music choices with GP priors. Their small dataset had 10 participants evaluate 30 tracks in three genres; reported leave-one-out pairwise prediction accuracy was 74% versus 50% random. Evidence for modeling comparisons over audio features, not proof of a good online sound-generation policy.
- **PBO:** González et al. formulate search where objective values are unavailable and only pairwise duels can be queried. A GP models latent preference; acquisition functions choose later duels. Their experiments show assumed correlations between candidates strongly affect how many comparisons search needs. This is general PBO research, not an EV or music listener trial.
- **Multi-attribute preference BO:** Astudillo and Frazier model pairwise preferences over attribute vectors and account for utility uncertainty. Their method returns a menu of designs instead of treating one estimated utility function as certain. This matches the goal of preserving multiple character options during exploration.
- **Music generation with BO:** A 2025 human-in-the-loop music-generation pilot tested ROMBO with 16 participants and compared BO-selected samples with random samples. The protocol capped sessions at 30 minutes and rated 64 generated samples, including initial and later optimization samples. The authors report that optimization helped users find/refine favorites and reduced time spent on uninteresting queries. This differs from our analytic synthesizer and pairwise interface; 64 samples is not a recommended EV session length.
- **Sound-design co-exploration:** Scurto et al.'s Co-Explorer studies investigate agents helping professional sound designers navigate high-dimensional parameter interfaces. This is a creative co-design workflow, not evidence that deep RL is best for a listener's bounded EV-character search.

## Implications for this EV sound study

The goal is **find a preferred sound character first, then optionally tune it**. “Good search” therefore means more than maximizing one predicted score: preserve coherent, distinct sound families, expose underexplored alternatives, compose compatible traits after evidence of interest, and begin local optimization only after the listener marks a direction as promising.

The current method names need careful interpretation:

1. **Evolutionary search** is IEC-inspired: it scores candidates and mutates/recombines their traits. It is a textbook GA only if it uses a population, explicit selection, crossover/mutation operators, and generation semantics. Current per-candidate 1–7 ratings provide more information than a pairwise winner.
2. **GP preference + BO** learns from pairwise choices and selects group-step comparisons. This is the most principled current option for sample-efficient preference learning, but its feature representation and query policy must preserve broad character coverage.
3. **Recipe-aware pairwise** encodes domain constraints and rules for changing/composing linked groups. It is currently a structured heuristic comparator, not a third learned model. It could instead become a candidate generator shared by IEC and PBO.

### Fair comparison

To claim **which search policy learns preference better**, methods need the same feedback type, candidate pool, starting distribution, guardrails, and comparison budget. Otherwise, results compare complete interaction packages (policy plus feedback UI), not algorithms alone. Current Evolutionary asks for two 1–7 ratings; GP and recipe-aware methods ask for pairwise preference. Two defensible designs:

- **Algorithm-focused:** use same pairwise response for all policies. Evolutionary selection maps Prefer A/B to relative fitness; Equal adds no selection pressure; Neither rejects both. Test the value of two separate ratings in a later interface study.
- **Interaction-package-focused:** keep Evolutionary's two-score UI and pairwise GP/recipe UIs, but state that feedback and search policy both differ. Compare completion, satisfaction, character diversity, choice confidence, and listener effort. Do not name a pure algorithm winner.

Recommend **interaction-package comparison first**, since user's two-score Evolutionary feedback is deliberate and central outcome is personalization experience. Keep candidate constraints, initial sound set, and budget common; log policy, feedback type, candidate signature, history, and proposal reason. If later claiming algorithm superiority, run follow-up with matched feedback.

### Recommended framing

Treat the three options as **interaction approaches**, not three equally mature algorithms:

- **IEC / evolutionary:** broad structured population or lineage search with listener scores, diversity preservation, and practical fatigue controls.
- **GP preference + active comparison selection:** model relative preference over linked character-group features; balance informative comparisons with exploration of underexposed styles.
- **Recipe-aware structured search:** explainable constrained baseline using same group compatibility rules and budget; do not present it as a separate machine-learning method.

Keep 15–20 as a prototype usability budget, not a literature-derived optimum. Let listeners stop early, continue, or refine only after identifying promising character. Evaluate whether methods reveal distinct preferred styles and satisfying final choices, not only whether they predict next vote.

## References

- Unehara, M., Ebihara, T., & Onisawa, T. (2001). [The Composition System Reflecting User's Feeling](https://doi.org/10.5057/jjske2001.1.2_66). *Journal of Japan Society of Kansei Engineering*, 1(2), 66–72.
- Dahlstedt, P. (2001). [Creating and Exploring Huge Parameter Spaces: Interactive Evolution as a Tool for Sound Generation](https://research.chalmers.se/en/publication/59128). *Proceedings of the International Computer Music Conference*, 235–242.
- Fukumoto, M., & Hanada, Y. (2017). [A Proposal for Continuous Evaluation-based Interactive Evolutionary Computation](https://doi.org/10.5687/sss.2017.211). *ISCIE Symposium on Stochastic Systems Theory and Its Applications*, 211–215.
- Jensen, B. S., Saez Gallego, J., & Larsen, J. (2012). [A Predictive Model of Music Preference Using Pairwise Comparisons](https://dihana.cps.unizar.es/proceedings/ICASSP/2012/pdfs/0001977.pdf). *ICASSP*, 1977–1980.
- González, J., Dai, Z., Damianou, A., & Lawrence, N. D. (2017). [Preferential Bayesian Optimization](https://proceedings.mlr.press/v70/gonzalez17a.html). *ICML / Proceedings of Machine Learning Research*, 70, 1282–1291.
- Astudillo, R., & Frazier, P. (2020). [Multi-attribute Bayesian optimization with interactive preference learning](https://proceedings.mlr.press/v108/astudillo20a.html). *AISTATS / Proceedings of Machine Learning Research*, 108, 4496–4507.
- Scurto, H., Van Kerrebroeck, B., Caramiaux, B., & Bevilacqua, F. (2021). [Designing Deep Reinforcement Learning for Human Parameter Exploration](https://doi.org/10.1145/3414472). *ACM Transactions on Computer-Human Interaction*, 28(1).
- Marcos Gil, M., Mur Labadía, L., & Martínez-Cantín, R. (2025). [Random rotational embedding Bayesian optimization for human-in-the-loop personalized music generation](https://pmc.ncbi.nlm.nih.gov/articles/PMC12637961/). *Peer-reviewed pilot study*. See methods and limitations before comparing its results to this project.

## Proposed character-first design (not implemented)


### Research goal

Find a vehicle-linked EV ambience character that fits a driver: smooth, warm, bright, forceful, ICE-inspired, orchestral, or a coherent blend. The experiment should discover promising styles first. Fine adjustment of exact parameter values begins only after the listener marks a sound as a promising direction.

The search does not seek one objectively correct sound or parameter set. It explores listener preference while preserving readable speed, acceleration/load, and regeneration cues.

### Design decisions

- Keep Comfort, Sport, and Deep as session modes. A mode sets sound-design and technical guardrails; it does not select or lock the final sound.
- Keep Evolutionary, GP preference + BO, and recipe-aware pairwise as selectable research methods. All use the same feasible candidate space and exploration budget, while retaining their feedback formats and proposal policies.
- Treat recipes as sound-building structures and starting hypotheses, not final presets. Candidate profiles may combine compatible traits from different structures.
- Keep several candidate families alive while preference is uncertain. One A/B response must not eliminate another family. `Equal` records no direction; `Neither` rejects that pair only.
- Target 15–20 comparisons. Explore character first, compose compatible traits second, and offer local tuning only when the listener asks to refine a promising sound. Allow early satisfaction and continuation.
- Preserve legacy session IDs, profiles, and exact replay. New mappings use new algorithm/mapping versions; do not rewrite participant records.

### Sound-character representation

Build each candidate from a **style signature**: a sound structure plus a small set of linked perceptual groups. Each group changes related DSP fields together; listeners compare the resulting character rather than editing raw Hz or envelope values.

| Group | Perceptual direction | Linked sound behavior |
| --- | --- | --- |
| Structure | Continuous electric, RPM/order-based, traction-like, orchestral, or compatible blend | Chooses which synthesis sources/layers are active and how they relate to vehicle state |
| Register | Light/airy to warm/full | Pitch foundation and speed-linked pitch travel |
| Harmonic body | Clean/smooth to rich/bright | Harmonic richness, cutoff, depth, and related tonal controls |
| State response | Subtle/gradual to assertive/quick | Load presence, acceleration emphasis, and attack/release timing |
| Regeneration | Restrained to more distinct | Regen level, harmonic character, and timing where supported |

The style signature is not a fixed preset. It is a coherent combination proposed from the listener's comparison history and a compatibility table. Randomness may select among valid combinations, but cannot bypass bounds, layer compatibility, headroom checks, or sound-quality screening. Use broad, clearly audible contrasts during discovery; do not present numeric low/high labels to listeners.

Mode-level physical and audio guardrails apply across candidates. Recipe-specific group support still matters: Sport ICE currently has effective order-register and response controls, but no independent tone/regen controls in its current profile. Do not expose inactive controls as if they changed the sound. Existing physical windows in [sound design research notes](sound_design_research.md) remain provisional until in-app listening review.

### Search stages

#### Explore character — pairs 1–8

Use eight planned comparisons of broad candidates, not a fixed four-pair checklist or a tournament that permanently crowns one recipe. The first Sport comparison can contrast Electric Sport and ICE Inspired as whole sound structures. Later pairs should expose meaningful variants within both branches and test other style signatures assembled from compatible group directions.

Each new pair uses preference history and exposure history. Prefer novel candidates from underexplored families or group combinations when evidence is weak. A clear preference shifts future sampling toward that direction but keeps viable alternatives available for later comparisons. An equal response means “no direction learned yet”; offer a different contrast. Neither removes both candidates from future proposals but does not consume a comparison.

For Sport, this means the listener can hear Electric and ICE-inspired structures, then see how each develops under its supported group changes. A first preference for Electric does not prevent a later ICE candidate from being varied or combined. Comfort and Deep follow the same principle with their own supported structures.

#### Compose character — pairs 9–14

Test whether liked traits work well together. **Cross-family composition** means taking compatible group-level traits from different explored candidates and generating a new coherent candidate. For example, compare an EV-style continuous pitch rise with an EV/ICE hybrid that adds a bounded, vehicle-linked order response. In Deep, compare a traction foundation with a candidate that adds a restrained orchestral layer.

These comparisons ask, “Do these characteristics sound good together?” They do not claim that one parameter caused preference. Keep the original candidates in an archive, compare each composition against a relevant parent or current favorite, and retain multiple branches while evidence remains uncertain. Do not combine arbitrary endpoints or incompatible fields.

The current engine constraint must shape the Sport plan: `order_mix` currently crossfades the electric sound out when order synthesis is active. A true Electric + ICE-order hybrid therefore needs an audio-engine blend path, controlled blend bounds, level/headroom checks, and transition tests before the app offers that composition. Deep already has traction and orchestral profile layers that can be composed through supported mix controls.

#### Refine a promising sound — optional pairs 15–20

Fine adjustment means smaller changes to linked groups around one chosen sound, rather than another broad style comparison. Only enter it after the listener marks a candidate as a promising direction, such as **Refine this sound**. Preserve that candidate's structure and other liked traits.

If the listener has not found a promising sound, keep exploring new style signatures or allow continuation. Do not spend the remaining budget optimizing exact values for a character they do not like. **I'm satisfied** remains the separate action for saving a final favorite.

### Algorithms and feedback

All methods receive the same candidate generator, group compatibility rules, guardrails, and initial exploration budget. Their differences concern how they use feedback to choose the next valid candidate:

- **Evolutionary:** listener scores A and B separately from 1–7. Proposals retain and recombine useful style/group traits, while preserving diversity during Explore.
- **GP preference + BO:** listener chooses Prefer A, Equal, or Prefer B. The model can guide comparisons toward informative or promising style signatures, but should not collapse exploration to a single branch before a promising direction is selected.
- **Recipe-aware pairwise:** same pairwise feedback; candidate proposals use explicit group compatibility and composition rules. It is a research comparator, not assumed to be better.

The listener can stop at any time. A saved favorite is the listener's explicit final choice, not automatically the highest score or model prediction.

### Elicit preference and character separately

Preference remains the comparison decision: Evolutionary scores A and B separately; GP and recipe-aware methods use Prefer A, Equal, or Prefer B, with Neither rejecting that pair. Character is descriptive context, not another hidden preference score. At a few checkpoints (after an early broad comparison and at the final choice), ask which plain-language qualities stood out, with optional free text. Candidate prompts can use provisional pairs such as smooth–rough, light–full, subtle–assertive, electric–engine-like, and calm–dramatic. Do not show parameter values or require a participant to know sound-design vocabulary.

This follows listening-study practice that combines open descriptions, semantic ratings, and preference measures. It also avoids interpreting a whole-candidate win as evidence that any one group caused the preference. Character words may guide later composition hypotheses, but they must not override pairwise preference or eliminate untried families.

### Guardrails and qualification

Guardrails screen candidates for clipping, excessive tonal prominence, unstable/distracting modulation, masking of vehicle-state cues, and invalid linked combinations. They define the feasible search space, not a universal comfort or safety guarantee. Do not set a single maximum-frequency rule from unrelated listening studies. Use spectral balance, tonal prominence, level matching, and human listening review together; see [sound design research notes](sound_design_research.md).

Qualify candidate families over the same startup, steady-speed, acceleration, lift-off, and regeneration scenarios. Match practical loudness where possible, inspect rendered output, and audition in the app before admitting a family or blend to participant sessions. Keep listener playback level under their control.

### What current prototype needs to change

The current probe mapping opens with four comparisons, tunes linked groups against the first recipe in pairs 5–14, then compares combined settings and challenges the alternate recipe. It stores mode-level bounds, but numeric freedom within one structure does not provide broad character exploration. The proposed redesign would replace that schedule with adaptive multi-family exploration, trait composition, and listener-triggered refinement. Existing v2 and older sessions continue to replay with stored profiles.

### Related research and evidence

See [method evidence above](#evidence-from-music-and-sound-studies) for method evidence, the limits of 15–20 as a literature claim, and comparing interaction packages versus isolated algorithms. See [sound design research notes](sound_design_research.md) for EV sound-quality dimensions, tone-perception findings, preference and character elicitation methods, loudness/tonality screening, and limits of published frequency results as universal thresholds. Literature informs guardrails and candidate hypotheses; it does not decide which character a participant should prefer.

## Implementation-plan summary

The retired task checklist proposed six pieces of future work: define style signatures and compatible linked groups; add a controlled electric/order-synthesis blend before offering Sport hybrids; keep multiple character branches available during exploration; compose only compatible traits; make fine refinement listener-triggered; and expose stage, changed groups, candidate ancestry, and query reason in the trace. These remain design proposals. Current app behavior is documented separately in [Interactive search](../system/interactive_algorithm.md).

## Final ranking by pairwise comparison

Source discovery now ends with a round-robin of four finalists ordered by Bradley-Terry, instead of ranking by mean 1–7 rating. Published findings and limits:

- Absolute scores separate perceptually close stimuli poorly; ranking-by-elimination and pairwise tests were proposed for this case in TTS evaluation ([Lakshminarayana et al. 2023](https://audiolabs-erlangen.de/resources/2023-SSW-MOSVSRANK); [Rethinking MUSHRA](https://arxiv.org/html/2411.12719v2)). Listening-test results are better treated as relative ([AES e-lib 14393](https://www.aes.org/e-lib/browse.cfm?elib=14393)). These are speech-quality studies, not EV sound preference.
- Paired comparison lowers fatigue in interactive evolutionary computation; tournament selection converges slowly for lack of information ([Takagi & Pallez](https://arxiv.org/pdf/0909.2091)). Simulated-user results.
- Bradley-Terry aggregation of pairwise labels is standard; a full round-robin is one "standard trial" ([Hybrid-MST](https://arxiv.org/pdf/1810.08851); [ASAP](https://discovery.ucl.ac.uk/id/eprint/10095672/)). Active pair selection is not used: at four items the full round-robin is only six pairs.
- Preference-GP and preferential Bayesian optimization also learn from pairwise choices ([Brochu et al. 2007](https://proceedings.nips.cc/paper_files/paper/2007/file/b6a1085a27ab7bff7550f8a3bd017df8-Paper.pdf); [Koyama et al. 2017](https://koyama.xyz/project/sequential_line_search/)).
- Best-worst scaling was more reliable than rating scales at small budgets ([Kiritchenko & Mohammad 2017](https://arxiv.org/pdf/1712.01765)), in sentiment annotation. Considered, not adopted.

Project interpretation: six choices from one listener give a coarse order. Whether the final round improves agreement with later listening needs a pilot.

