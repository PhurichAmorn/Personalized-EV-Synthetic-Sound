# Interactive sound search

## Research references

- [Wang and Pei (2024), “A comprehensive survey on interactive evolutionary computation in the first two decades of the 21st century,” *Applied Soft Computing*, 164, 111950](https://doi.org/10.1016/j.asoc.2024.111950): broad IEC review covering algorithms, preference elicitation, user fatigue, perception, and applications.
- [Takagi (2001), “Interactive Evolutionary Computation: Fusion of the Capabilities of EC Optimization and Human Evaluation”](https://doi.org/10.1109/5.949485): foundational IEC survey and background on human evaluation in evolutionary search.
- [Takagi and Pallez (2009), “Paired comparison-based Interactive Differential Evolution”](https://doi.org/10.1109/NABIC.2009.5393359): paired-comparison evolutionary method designed to reduce evaluation burden. Our Evolutionary option is a simpler mutation/retention method, not their differential-evolution algorithm.
- [Broukhim et al. (2025), “Preference-Based Learning in Audio Applications: A Systematic Analysis”](https://arxiv.org/abs/2511.13936): recent audio-domain review; currently an arXiv preprint. Provides context for the limited and varied use of preference learning in audio research.
- [Chu and Ghahramani (2005), “Preference Learning with Gaussian Processes”](https://doi.org/10.1145/1102351.1102369): GP model for learning preferences from pairwise comparisons.
- [González et al. (2017), “Preferential Bayesian Optimization”](https://proceedings.mlr.press/v70/gonzalez17a.html): GP-based Bayesian optimization when feedback is pairwise preference rather than direct objective values.
- [Astudillo and Frazier (2020), “Multi-attribute Bayesian optimization with interactive preference learning”](https://proceedings.mlr.press/v108/astudillo20a.html): learns utility over multiple attributes from pairwise judgments and selects experiments while accounting for preference uncertainty. This project uses a smaller pairwise GP baseline over sound-control parameters; it is not a reproduction of their full method.

## Use

1. Choose **Personalize sound**, enter a participant name/alias, and select a starting mode.
2. Choose **New session**. The car powers on automatically; the existing startup sweep completes before READY and driving input unlocks. Sound A is selected.
3. Select A and B in turn and drive with the keyboard or controller. For GP preference + BO, choose **Prefer A**, **Like both equally**, or **Prefer B**. Choose **Neither · new pair** if both sounds are disliked; the app rejects both and generates a fresh pair at the same comparison number. Evolutionary takes a separate 1–7 liking score for each sound; give both low scores when both are disliked.
4. Choose **Next pair** to save feedback and prepare another pair with Sound A selected. Pair 10 is a checkpoint; pair 20 completes the current block. Listen to A and B. If satisfied, choose a favorite; otherwise grade the pair and choose **Continue search**. The listener can stop earlier. If a saved session is resumed at a checkpoint, **Continue search** generates the next pair then. A returning Evolutionary sound keeps its most recent score, shown with its source pair; the listener can change it without auditioning again. New sounds must be auditioned before scoring. Advancing does not stop/reset a running car; if stopped, it powers on automatically.
5. Choose **Like both equally** when neither sound has an advantage, including when they are hard to distinguish. Choose **Neither · new pair** when you dislike both. Neither rejects both sounds and generates two fresh candidates without using a comparison. Earlier saved sessions can still contain a **Too similar** skip, which kept one sound and replaced its challenger.
6. After hearing both sounds, choose **I'm satisfied**. The app asks which sound you prefer; choose **Save Sound A** or **Save Sound B**. That explicit choice becomes the participant's favorite, even if another sound was playing or scored higher. **Pause search** saves progress without marking satisfaction.

On returning, enter the same alias and select **Continue search**, **Use saved sound**, or **New session**. Continuing restores search state, not a moving vehicle. New sessions preserve previous records. Aliases are matched without case sensitivity; they are identifiers for a local demo, not authenticated accounts. Use different aliases for different people. The current baseline selector can replace a loaded saved sound.

The **TRACE** page lists local experiment sessions by date, mode, participant, and comparison count. Select a comparison and A or B to inspect its search controls, full DSP profile, preference, and saved audition summary. **Replay** restores that candidate profile and plays it with the simulator's current driving inputs. It does not record or replay the original audio waveform or exact pedal/speed trajectory. The delete button removes the whole saved session after confirmation; active sessions must be paused or finished first.

Closing the app during an active search offers **Cancel**, **Save & Exit**, and **Exit Without Saving**. Cancel returns to the session. Save & Exit pauses it and keeps its record. Exit Without Saving deletes the current session record, including comparisons already saved during that session; other sessions remain available.

## Learning methods and comparison

Choose a learning method when starting a session. **GP preference + BO** uses feature-guided comparisons; **Evolutionary** preserves the earlier mutation-based method as a research comparator. Comfort, Sport, and Deep sessions keep separate baselines and records; observations are never pooled across modes.

### Current character search

New Comfort, Sport, and Deep sessions use the **same ten normalized controls and physical mapping**. The selected mode supplies an opening seed and a separate experiment label; Deep also uses a more grounded motor sound in place of the extreme whirling first challenger. It does not fence off a timbre or force aggression, quietness, or oscillation. The on-dashboard baseline selector still plays the original three profiles outside the search. A candidate profile is stored in full, so future mapping changes do not alter saved playback.

| Control | Low to high audible range |
| --- | --- |
| `register` | 70–180 Hz starting carrier |
| `motion` | Small to large compressed speed-pitch excursion |
| `tone` | Nearly pure/warm to harmonically rich/bright motor tone |
| `whirl` | Stable tone to smoothly moving upper partial and detuning |
| `pulse` | Sustained tone to motor-like rhythmic modulation; no combustion sample |
| `shimmer` | Little to more clean, high-register tonal energy |
| `ensemble` | Motor tone to sustained chordal blend |
| `phrase` | Continuous speed stages to more repeating, crossfaded acceleration phrase |
| `response` | Gentle/slow to stronger/faster drive and acceleration response |
| `regen` | Quiet/smooth to more present regen harmonics |

New GP sessions start with six separate feature comparisons: register; speed-pitch motion; tone and whirr; pulse and shimmer; ensemble and phrase; and response and regen. Each pair changes only its named control group, so a preference supplies clearer evidence than choosing between unrelated sounds. The twelve opening candidates share the selected mode's seed values outside their contrasted group. Evolutionary retains its six opening candidates: the mode seed plus five deliberately separated sounds. Deep replaces the extreme whirr with a moderate motor tone. Neither method restricts later search to opening candidates. Compare candidates under similar driving actions and system volume. Candidate gain is fixed at 0.32, but perceptual loudness is **not** calibrated equal across timbres.

GP uses three graded pairwise choices: **Prefer A**, **Like both equally**, and **Prefer B**. Responses are stored as `A`, `equal`, or `B`; GP models them as −1, 0, or +1. **Neither** skips the pair and removes both candidates from later proposals. Evolutionary instead scores each sound from **1** low to **7** high; the higher score survives. A tie retains the existing parent after the three opening pairs and chooses one opening survivor at random during those first three pairs. A/B position is randomized. Ten pairs offer a break; twenty end a block, after which the listener can continue. Satisfaction can end the search after both sounds in the current pair have been heard.

**GP preference + BO:** Pairs 1–6 test the six feature groups. A preferred opening candidate is retained as evidence for that group; ties leave it unresolved. Pairs 7–17 use a small GP regression of three-choice pairwise judgments and select a challenger by expected latent-utility improvement. Its kernel averages six RBF similarities, one per feature group, so evidence about pitch can transfer across different textures; this assumes group effects are approximately additive. Up to 24 proposals per round mix mutations near prior preferred sounds with uniform exploration; local proposal probability starts at 55% and becomes 70% after ten pairs. Pairs 18–20 test three combinations of preferred groups against the current incumbent, with ordinary GP proposals when no distinct combination can be made. Each group uses RBF length 0.65, and mutation width narrows after comparisons 8 and 14. The finite-pool model approximates pairwise preference; feature combinations test hypotheses rather than prove the listener likes individual parameters. Existing `gp-character-v1` sessions retain their original full-space kernel and pairing policy when resumed.

**Evolutionary:** Three disjoint opening pairs retain one winner each. Later pairs compare one lineage parent with a child that mutates one or two controls. The parent's last score carries forward, so only the new child needs a fresh score unless the listener wants to revise the parent. Mutation width narrows after comparisons 8 and 14. Every fifth child changes all controls with a broad random draw. Ties retain the parent. There is no crossover or automatic convergence claim.

### Saved-session compatibility

New sessions use schema 3, `gp-feature-v2` or `three-lineage-character-v1`, and categorical pairwise preferences. Existing schema 3 `gp-character-v1` sessions remain resumable with their original policy. Older schema 1–2 sessions with numeric GP preferences are not loaded. All new participant/session records remain local and separate by mode.

## Persistence

`experiment_data/interactive/<session-id>/session.json` is local and gitignored. It contains:

- Participant alias/ID, UUID session ID, timestamps, mode, vehicle name and initial vehicle snapshot.
- Version, DSP source hashes, fixed sound-mapping configuration, seed, baseline, normalized bounds, all candidate profiles/controls/parents/origins.
- Current pair, GP pairwise preference or Evolutionary per-sound ratings, selected sound, survivors, parent/lineage, checkpoints and block budget.
- Neither skips, plus any earlier Too-similar skips, with discarded pairs and replacement candidates; these do not add to the completed comparison count. GP excludes rejected candidates from later proposals.
- Completed comparisons and candidate auditions, with sampled driving duration, speed range/sum, pedal sum and signed-load sum/count.
- Favorite candidate and satisfaction/pause history.

The monitor samples driving at 5 Hz and records aggregates, not a full replay trajectory. Audition aggregates are flushed on switching, Next, finish, and orderly close; force-killing the process can lose the current aggregate. Pairwise preferences and candidate selections are saved as they occur.

Each update writes and fsyncs a temporary snapshot, then atomically replaces the session file before accepting the state change. Write errors leave the current pair and ratings available for retry. Favorite playback loads the exact stored profile. A new search cannot overwrite an earlier session.

## Separate debug windows

- **View → Telemetry** opens the motor torque/RPM graph in its own window. It is unloaded when closed.
- **View → Sound signal** opens waveform, spectrum, and spectrogram together in three equally sized panels:
  - Waveform: recent output samples, time in milliseconds and normalized amplitude.
  - Spectrum: frequency in hertz and level in dBFS.
  - Spectrogram: the last 10 seconds of spectrum snapshots, with time, frequency (0–2000 Hz), and color-coded level in dBFS.

Analysis refreshes at 10 Hz only while the window is visible. The spectrogram stores at most 100 snapshots and reduces the existing spectrum to 96 frequency bins. These are output-signal estimates, not calibrated cabin loudness or a continuous recording.

## Input

Triggers and W/S retain the existing vehicle controls. D-pad/arrows navigate UI controls; confirm/Enter activates them. Preference selection and sound switching do not stop the car. Audio parameter transitions are smoothed with oscillator phases retained; there is no stream restart on A/B switching. Typed W/S in text fields are treated as text.

### A/B directional navigation

On the sound row, left/right moves directly between Sound A and Sound B. Down enters the selected sound's score scale for Evolutionary, or the three shared preference choices for GP; up returns to the sound. Left/right changes the focused score or choice. A new sound's controls stay disabled until it has been auditioned. A returning Evolutionary sound's carried score can be changed immediately.

Directional focus selects the sound or preference immediately; confirm is optional. Idle focus fades and resumes at the previous control. Mouse clicks continue to work normally.

Starting or resuming personalization selects A and focuses its sound button. Continuing after a checkpoint does the same for the next pair. Loading a saved favorite powers on with that favorite rather than replacing it with A. Automatic power-on preserves the existing startup/READY gate and audio-error reporting. Pause search remains available while driving.

### Controller navigation stability

Rear-button learning/bindings are removed. D-pad navigation is tap-based: a direction, A confirm, or B back must be stable for 40 ms; held inputs do not auto-repeat. B closes the current dialog or returns to the dashboard without discarding an active search. Connecting, switching controllers, conflicting button combinations, or losing application focus require 80 ms of neutral input before navigation re-arms. Mapped controllers retain trigger input. Unmapped SDL joysticks use hat 0 for directions and raw buttons 0/1 for A/B; their triggers are unavailable. Accepted navigation actions and raw controller button changes appear in the terminal for troubleshooting.

Controller vibration is benched and excluded from the app and experiment records for now.
