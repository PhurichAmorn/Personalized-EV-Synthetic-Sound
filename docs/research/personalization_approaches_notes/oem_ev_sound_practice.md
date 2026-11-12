# OEM EV Driving/Cabin Sound Practice and Evidence on Who Prefers What

Research date: 2026-11-12. Sources were gathered by web search and page fetches. Where a page could not be fetched, the claim is marked "(search snippet)" and should be checked before formal citation. Most OEM material is press or marketing copy. It shows what the OEM *says*, not verified engineering detail.

## OEM examples, synthesis approaches, inputs, and suppliers/tools

### Takeaway
OEMs publicly describe *what* drives their EV sounds (speed, torque/load, pedal, recuperation, drive mode) far more than *how* the audio is synthesized. Only Hyundai (granular synthesis, through its in-house e-ASD) and BMW (algorithmic generation plus some recorded material) give any method detail. Porsche says it uses sources taken from the car itself. Supplier and tool vendors (Siemens, HEAD acoustics, Harman, Crankcase REV) offer both order synthesis and granular synthesis.

### Cited Findings
**BMW (IconicSounds Electric with Hans Zimmer and Renzo Vitale; HypersonX for Neue Klasse)**
- BMW M material says acceleration, load change and recuperation "are reflected acoustically within milliseconds". Each driving mode has a different sound, and M models are tuned to sound more intense — [BMW M: IconicSounds Electric](https://www.bmw-m.com/en/topics/magazine-article-pool/bmw-m-iconicsounds-electric.html) (search summary of the page)
- BMW press: some tonal components are "more traditional" and others come from "completely new sound generation". Zimmer and Vitale turn emotional cues into melodic components — [BMW Group press release, IconicSounds Electric](https://www.press.bmwgroup.com/asia/article/attachment/T0364493EN/517715); [InsideEVs](https://insideevs.com/news/506635/bmw-motorsport-electric-zimmer-sound/) (search snippets)
- Vitale says he translates the car's physical curves (rim, seat, rear body) into sound-generation algorithms, and compares this to Xenakis's use of geometry. This describes his design philosophy, not an engineering specification — [Domus interview, 2021](https://www.domusweb.it/en/news/2021/01/08/designing-the-sound-of-the-electric-car-city.html) (search snippet)
- HypersonX (Neue Klasse, first car the new iX3): BMW's algorithm produced "over nine million sound variations", and the team picked the best ones by hand. A multilingual choir of employees' voices was recorded as source material. Personal and Sport modes contain "43 unique sound signals and special driving effects". HypersonX has "fewer fundamental notes, but they're now sharper, more dynamic". On the Vision Neue Klasse X concept, steering-wheel buttons let the driver change the sound in real time. Production availability of that control is not confirmed — [BMWBlog, Apr 2025](https://www.bmwblog.com/2025/04/14/bmw-hypersonx-neue-klasse-sounds/)
- A 2025 BMW patent application uses existing actuator motors (windows, wipers, tailgate) pulsed through resonators to make tones. This is not granular synthesis — [BMWBlog, Jul 2025](https://www.bmwblog.com/2025/07/29/bmw-ev-noise-motor-patent/); [DexPatent](https://dexpatent.com/insights/2025/08/01/bmw-files-a-patent-application-for-ev-sound-system-using-existing-motors/)

**Porsche Taycan (Porsche Electric Sport Sound)**
- Tobias Hillers' team began work in 2012, and the sound debuted on the Mission E concept (2015). Hillers says the sound should be "authentic", using only sounds that come from the car itself (electric motor, transmission, some tyre noise). He calls himself "an engineer, not a designer or even composer". The sound was developed in the studio, on the road and on track (919 Hybrid), and changes with speed and acceleration — [Porsche Newsroom: Sound pioneer Tobias Hillers](https://newsroom.porsche.com/en/campus/sound-pioneer-tobias-hillers-18780.html) (search summary)
- Porsche's acoustic QA also deals with unmasked auxiliary noises, for example the oil pump becoming relevant in an EV — [Porsche: pursuit of perfect sound, 2024](https://newsroom.porsche.com/it_CH/2024/innovation/porsche-pursuit-of-perfect-sound-36203.html) (search summary)

**Mercedes-EQ (Sound Experience: Silver Waves, Vivid Flux, Roaring Pulse, Serene Breeze)**
- On the EQS and EQE, Burmester audio includes Silver Waves and Vivid Flux. Roaring Pulse ("reminiscent of powerful machines… sonorous and extroverted") can be bought by over-the-air update — [MBUSA: EQS design for all the senses](https://media.mbusa.com/news/the-eqs-design-for-all-the-senses); [MBUSA: EQE](https://media.mbusa.com/news/the-eqe-the-new-business-avant-garde)
- Mercedes says OTA functions are sold in the Mercedes me Store "as a one-off purchase option or also as a subscription model". On the EQA and EQB, Roaring Pulse and Serene Breeze can be activated online as part of the Individualisation Package — [Mercedes UK: EQA/EQB upgrade](https://mercedes-benz-media.co.uk/releases/1545)
- One owner reports an annual "Digital Extras" fee that unlocked Roaring Pulse and Serene Breeze. This is anecdotal — [MBEQClub forum](https://www.mbeqclub.com/threads/2023-eqe-350-suv-4matic-sound-experience-engine-sound-and-dashcam.4151/)

**Hyundai Motor Group (e-ASD; Ioniq 5 N "N Active Sound+" and "N e-shift")**
- Hyundai's Sound Design Research Lab developed "e-Active Sound Design (e-ASD)". It uses a "Granular Synthesis" method that breaks sounds into very small units and recombines them in real time from vehicle signals. Hyundai says the advantage is "harmonically implementing multiple tones", and that the themes range from engine-like to spaceship-like — [Hyundai Motor Group Tech: Adding sound to a quiet EV](https://tech.hyundaimotorgroup.com/article/adding-sound-to-a-quiet-electric-vehicle/) (search snippet only; the page returned HTTP 503 twice)
- Hyundai-affiliated academic work: Lazaro, Kim, Choi, Kim, Park, Moon and Yun, "Design and Evaluation of Electric Vehicle Sound Using Granular Synthesis", JAES 70:294–304 (2022). It varied four parameters (sample source, grain duration, grain envelope, RPM range), each at three levels, to make 27 stimuli. A jury of 32 rated them on refined, sporty and futuristic, plus overall satisfaction. Each parameter affected perceived affect differently — [AES E-Library 21566](https://aes2.org/publications/elibrary-page/?id=21566); [ResearchGate](https://www.researchgate.net/publication/360533091_Design_and_Evaluation_of_Electric_Vehicle_Sound_Using_Granular_Synthesis)
- Ioniq 5 N: N Active Sound+ offers three themes: "Ignition" (an ICE N engine and exhaust sound), "Evolution", and "Supersonic" (inspired by fighter jets). It plays through interior Bose speakers plus exterior speakers. Volume is adjustable, with a legal maximum. N e-shift simulates an 8-speed DCT by controlling motor torque to create a shift jolt — [Hyundai IONIQ 5 N press kit](https://www.hyundai.news/eu/models/performance/ioniq-5-n/press-kit/press-information.html)
- The speaker count conflicts between sources: 8 interior + 2 exterior (most reports), "10 interior" (Yahoo), and "10 internal and eight external" (a trade item) — [Yahoo Tech](https://tech.yahoo.com/audio/articles/hyundai-put-speakers-electric-car-105000257.html); [Hyundai press kit](https://www.hyundai.news/eu/models/performance/ioniq-5-n/press-kit/press-information.html)
- Hyundai says the purpose is "an acoustic reference to gauge the power being utilized". A trade publication says Ignition is tuned to the N four-cylinder engine — [Hyundai: Wards 10 Best](https://www.hyundai.com/worldwide/en/newsroom/detail/0000000827) (search snippet)
- A secondary source says the sound "remixes" continuously with speed and throttle, and that turning on e-shift switches Active Sound+ to Ignition and adds pops and bangs on shifts — [Tarmac n Torque](https://tarmacntorque.com/news/ioniq-5-n-e-shift-active-sound-explained-2026-price-cut) (secondary; not verified against Hyundai)

**Dodge Charger Daytona (Fratzonic Chambered Exhaust)**
- Dodge says it generates sound "through an amplifier and tuning chamber located at the rear of the vehicle". The hardware is dual high-efficiency transducers plus passive chamber-loaded radiators in a custom enclosure, with a dedicated amplifier. Inputs are pedal position, speed and torque. Drive modes change intensity, and a silent "Stealth" mode exists. Dodge claims up to 126 dB, and says the design is patent-pending — [Green Car Reports](https://www.greencarreports.com/news/1145190_odge-charger-daytona-ev-fratzonic-how-it-works); [Autoblog](https://www.autoblog.com/2024/03/05/2024-dodge-charger-fratzonic-chambered-exhaust-what-is-it-explained/); [Motorbiscuit](https://www.motorbiscuit.com/is-the-dodge-charger-evs-fratzonic-chambered-exhaust-system-just-a-speaker-making-engine-noises)
- No synthesis method is disclosed. The press says Dodge "hasn't been forthcoming with more details" — [Motorbiscuit](https://www.motorbiscuit.com/is-the-dodge-charger-evs-fratzonic-chambered-exhaust-system-just-a-speaker-making-engine-noises)

**GMC Hummer EV**
- An industry article reports that an OEM (in the context of the Hummer EV) built its own granular-synthesis sound — [audioXpress, 2021](https://audioxpress.com/article/automotive-audio-solutions-the-changing-automotive-environment-in-2021) (search snippet; the OEM claim is loosely attributed)

**Xiaomi SU7 / SU7 Ultra (supplier: HEAD acoustics)**
- HEAD acoustics designed three "Powertrain Sound Enhancement" (PSE) models for the SU7 Ultra and one for the SU7. They were based on "detailed measurements and analysis of both electric and combustion vehicles". The audio engine is described as "multi-layered, data-driven" and "reacts in real time to key vehicle parameters such as speed, torque, and motor RPM". The models are integrated into the multimedia and drive-mode settings "with instant profile switching". The sounds were checked in "user experience testing" for being "pleasurable over long-term use". The synthesis method is not named — [HEAD acoustics blog](https://www.head-acoustics.com/blog/data/sound-that-moves-you-head-acoustics-sound-design-for-xiaomi/)

**Other OEMs (limited detail)**
- Chevrolet Equinox EV: a 2026 OTA update changed the "Motor Sound" menu, and some owners lost the off option. This shows that interior sound settings are now software-managed and can change after sale — [GM Authority, Mar 2026](https://gmauthority.com/blog/2026/03/chevy-equinox-ev-software-update-glitch-changes-cabin-motor-sound-settings/)

**Suppliers and tools**
- Siemens' Active Sound Design / AVAS webinar lists "Granular synthesis | Order synthesis" as alternative synthesis approaches, along with in-vehicle tuning and production integration (vendor material) — [Siemens webinar PDF](https://www.plm.automation.siemens.com/media/global/en/Webinar-Active-Sound-Design-AVAS_tcm27-81791.pdf)
- Harman HALOsonic: engine-order cancellation (RPM reference) plus electronic sound synthesis (ESS) for interior and exterior sound, first developed with Lotus — [Automotive World](https://www.automotiveworld.com/news-releases/the-sound-of-safety-harman-halosonic/). Harman's ESS has been integrated into the VI-grade NVH driving simulator for "rapid prototyping" (VI-NVHSim 2025.1 SP1) — [Harman/VI-grade 2025 slides](https://www.vi-grade.com/dynatc/attachments-2878-7b28/harman-rapid-prototyping-for-automotive-sound-design-nazps2025.pdf)
- Crankcase Audio REV is a granular vehicle-sound plugin from games audio. A thesis cites it as a granular design tool — [af Malmborg thesis, KTH](https://www.diva-portal.org/smash/get/diva2:1557027/FULLTEXT01.pdf)
- In a games context, a listening test rated granular synthesis the most realistic method for engine sound — [af Malmborg thesis](https://www.diva-portal.org/smash/get/diva2:1557027/FULLTEXT01.pdf)
- More academic granular EV work: "Sound Granular Synthesis Method for Sci-Fi Sound Quality of Electric Vehicles", SAE 2025-01-0253 — [SAE Mobilus](https://saemobilus.sae.org/papers/sound-granular-synthesis-method-sci-fi-sound-quality-electric-vehicles-2025-01-0253); "A method of generating car sounds based on granular synthesis algorithm", Noise Control Eng. J. 70(4), 2022 — [Ingenta](https://ince.publisher.ingentaconnect.com/contentone/ince/ncej/2022/00000070/00000004/art00007)
- A US patent, "Methods and systems for engine sound synthesis", modulates grain pitch from speed, RPM and driver behaviour, and notes that existing methods "may be expensive in terms of processing" — [USPTO 12243510](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12243510) (search snippet; assignee not checked)

### Inferences
- **Is granular synthesis standard?** It is *one* of two mainstream approaches. Hyundai's own technical statements, at least one other US OEM (unconfirmed), academic papers with Hyundai authors, and supplier toolchains (Siemens) document it. The other approach is engine-order or tonal synthesis, offered side by side by Siemens and implied by Harman's RPM-referenced tools. "Granular synthesis is OEM practice" holds for Hyundai. It is not shown for BMW, Porsche, Mercedes, Dodge or Xiaomi, which do not disclose their method.
- Every OEM that describes its control inputs names the same small set: vehicle speed, torque/load (or pedal), motor RPM, recuperation, and drive mode. A prototype driven by speed, torque, pedal and regen therefore matches OEM practice at the input level.
- OEM philosophies fall into three groups. (a) "Authentic" sound built from the car's own sources (Porsche). (b) Composed or brand sound (BMW/Zimmer, Mercedes themes). (c) ICE emulation (Hyundai Ignition, Dodge Fratzonic, Xiaomi PSE). Sample-based granular synthesis can serve all three, depending on the source material.
- BMW's "nine million variations, curated by hand" workflow is a generate-then-select process that resembles an interactive search approach, though BMW does not describe it as preference learning.

### Gaps
- No primary technical source was found for Audi e-tron GT, Renault (Jean-Michel Jarre), Volvo, Kia (EV6 GT / EV9 GT), Polestar, Lucid, BYD, NIO, Tesla Boombox, or VW ID. These were not covered within the search budget. Search results for VW, Kia, Polestar and Lucid returned nothing specific.
- No BMW patent or Vitale interview was found that describes granular synthesis. BMW's synthesis method remains undisclosed.
- Continental, Bose and HEAD acoustics' internal tools, and the use of Wwise/FMOD or other middleware in production vehicles, could not be verified.
- The Hyundai e-ASD article could not be fetched (HTTP 503). Its details come from a search snippet.

## OEM development process (brand DNA, target sound, jury tests, metrics, clinics)

### Takeaway
Public evidence of OEM process is thin. What exists shows iterative design across studio, road, track and simulator; jury listening tests with semantic-differential or affect scales; and long-term "user experience testing". Suppliers increasingly offer driving-simulator prototyping. No OEM publishes its psychoacoustic target values.

### Cited Findings
- Porsche developed its sound in the studio, on the road and on the race track over several years (2012 to 2019) — [Porsche Newsroom](https://newsroom.porsche.com/en/campus/sound-pioneer-tobias-hillers-18780.html)
- BMW: algorithmic generation of millions of variants, followed by expert selection — [BMWBlog](https://www.bmwblog.com/2025/04/14/bmw-hypersonx-neue-klasse-sounds/)
- HEAD acoustics/Xiaomi: measuring and analysing EV and ICE reference vehicles, defining a target performance character per model, then user experience testing for long-term pleasantness — [HEAD acoustics](https://www.head-acoustics.com/blog/data/sound-that-moves-you-head-acoustics-sound-design-for-xiaomi/)
- Hyundai's research used a factorial design (27 stimuli) rated by a 32-person jury on affective adjectives — [JAES 2022](https://aes2.org/publications/elibrary-page/?id=21566)
- Harman/VI-grade let engineers check active sound design in an NVH driving simulator before vehicle tuning — [Harman/VI-grade slides](https://www.vi-grade.com/dynatc/attachments-2878-7b28/harman-rapid-prototyping-for-automotive-sound-design-nazps2025.pdf)
- Methods in the academic literature include paired comparison, rating scales, MUSHRA, semantic differentials, driving simulators, and demonstrator or real vehicles. Fiebig and Schulte-Fortkamp frame the core problem as finding "how the majority assesses sound quality of EVs without any existing frame of reference" — [Mündler and Carbon review, Frontiers in Mech. Eng. 2022](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Siemens presents a workflow of design, then in-vehicle tuning, then production integration (vendor) — [Siemens webinar](https://www.plm.automation.siemens.com/media/global/en/Webinar-Active-Sound-Design-AVAS_tcm27-81791.pdf)

### Inferences
- The typical industry sequence appears to be: reference measurement, target and character definition, synthesis design, jury or simulator evaluation, in-car tuning, and fixed presets per drive mode. Personalization after delivery is limited to choosing presets and setting volume. Adapting the sound to each listener in a loop, as an interactive preference-learning prototype does, goes beyond documented OEM practice. It extends that practice rather than mirroring it.

### Gaps
- No public OEM document gives psychoacoustic targets (loudness, sharpness, roughness, tonality limits) for EV interior sound.
- No source was found on OEM customer clinics run in specific markets (for example, China versus Europe).

## Personalization offered to customers

### Takeaway
Shipping personalization consists of discrete theme selection, usually tied to drive mode; a volume or intensity setting; an off or "stealth" option; and, at Mercedes and Hashtag-type brands, paid or OTA-delivered extra themes. Continuous user-adjustable timbre parameters were found only on a BMW concept.

### Cited Findings
- Mercedes: themes included with Burmester audio, Roaring Pulse sold OTA, and purchase or subscription through the Mercedes me Store — [MBUSA EQS](https://media.mbusa.com/news/the-eqs-design-for-all-the-senses); [Mercedes UK EQA/EQB](https://mercedes-benz-media.co.uk/releases/1545)
- Hyundai Ioniq 5 N: three themes, adjustable volume, and coupling with e-shift — [Hyundai press kit](https://www.hyundai.news/eu/models/performance/ioniq-5-n/press-kit/press-information.html)
- Dodge: drive modes change intensity, and a silent Stealth mode exists — [Green Car Reports](https://www.greencarreports.com/news/1145190_odge-charger-daytona-ev-fratzonic-how-it-works)
- BMW: sound differs by drive mode, and HypersonX has Personal and Sport modes. The concept car allowed real-time sound changes from steering-wheel buttons — [BMW M](https://www.bmw-m.com/en/topics/magazine-article-pool/bmw-m-iconicsounds-electric.html); [BMWBlog](https://www.bmwblog.com/2025/04/14/bmw-hypersonx-neue-klasse-sounds/)
- Xiaomi: PSE profiles in drive-mode settings with instant switching — [HEAD acoustics](https://www.head-acoustics.com/blog/data/sound-that-moves-you-head-acoustics-sound-design-for-xiaomi/)
- Hashtag-type OTA: an update added driving-sound effects, and a later one added equaliser settings — [evilution.co.uk](https://evilution.co.uk/mod/1-over-the-air-updates.htm) (low-quality source)
- Chevrolet Equinox EV: a Motor Sound menu that OTA updates can change — [GM Authority](https://gmauthority.com/blog/2026/03/chevy-equinox-ev-software-update-glitch-changes-cabin-motor-sound-settings/)

### Inferences
- Commercial personalization is preset selection, not preference learning. No OEM was found that adapts sound parameters to an individual driver from feedback.

### Gaps
- Tesla Boombox (an exterior sound feature), NIO and BYD sound options, and current Mercedes subscription prices were not verified.

## Evidence on individual and group differences in EV sound preference

### Takeaway
The strongest and most repeated finding is that preferences split into subgroups rather than meeting at one optimum. Groups include those who want ICE-like augmentation, those who want new non-ICE augmentation, and those who want genuine or quiet EV sound. Almost everyone wants load-dependent feedback. Gender effects are reported in a few small studies. Evidence on age, culture (China, Europe, Korea), personality and driving style is sparse or missing.

### Cited Findings
- Maunder and Munday (2017), N = 30: three groups. The largest wanted conventional (ICE-like) augmentation, a second wanted augmentation without ICE-like sounds, and a third preferred the genuine EV sound — [Mündler and Carbon 2022 review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Valeri and Pietila (2020): paired comparison plus semantic differential found no single sound preferred overall, with preferences varying by subgroup — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Gwak et al. (2014a), N = 27: different customer groups preferred different enhancement strategies, and subharmonic additions increased dynamism — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Küppers (2015): when participants configured the sound freely in a demonstrator car, only 14% chose no added sound, and most chose combustion-like variants. In a simulator, the genuine e-powertrain noise was rated least pleasant and "paradoxically perceived as the most artificial" — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Sontacchi et al. (2015): many participants preferred quiet vehicles but wanted load-dependent loudness. Only men used positive energy-related descriptors, while women used more varied descriptors — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml); [ResearchGate: Acceptance of synthetic driving sounds in EV interiors](https://www.researchgate.net/publication/335459121_Acceptance_of_synthetic_driving_sounds_in_the_interior_of_electric_vehicles) ("preliminary results indicate gender-related differences… differences… depending on gender, age, habit, and cultural background are worth reviewing")
- Lanslots et al. (2020), N = 10: a V8-like sound was most preferred. The sample was 62.5% ICE drivers, a possible bias toward ICE-like sounds, so prior vehicle experience may shape preference — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Allman-Ward et al. (2020): the best modified concept reached about 50% shared preference, while the unmodified interior noise reached 8% for a sporty EV — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Lennström et al. (2019): a more sensitive subgroup found high-frequency tones increasingly unpleasant as level rose — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Fang and Zhang (2017a): ratings were more consistent for ICE sounds than EV sounds, attributed to familiarity — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Mündler and Carbon (2022), N = 65: how clearly e-powertrain noise could be heard correlated negatively with perceived quality (τ = −0.32). The review concludes that a clear EV sound-design recommendation "cannot yet be concluded", and that customers "lack reference points" — [same review](https://www.frontiersin.org/journals/mechanical-engineering/articles/10.3389/fmech.2022.974464/xml)
- Persona study (Sci. Rep. 2026), N = 50 drivers (32 men, 18 women): women mostly favoured comfort-oriented ratings (66.7% scored 1 to 3), and the preference scores were clustered into personas. It cites a US, Germany and Japan study finding two perceptual axes, Luxury and Sportiness, with Germans leaning to Luxury. That cited study was not about EVs and its methods were not verified — [Sci. Rep. 2026](https://www.nature.com/articles/s41598-026-55385-0) (search snippets; paywall redirect blocked the fetch)
- Lazaro et al. (2022): grain parameters (source, duration, envelope, RPM range) shift perceived refined, sporty and futuristic affect differently. This gives a parameter-to-affect map that personalization could act on — [JAES](https://aes2.org/publications/elibrary-page/?id=21566)

### Inferences
- Stable subgroups (ICE-like, novel synthetic, quiet or authentic) plus within-group variation support interactive per-user search over a single target sound. The lack of reference points and low familiarity also suggest that users' preferences may drift as they are exposed to the sounds. A search method should tolerate this non-stationarity.
- Previous vehicle (ICE vs EV ownership), gender, and noise sensitivity are the covariates with at least some support and are worth logging in session records. Age, culture, personality and driving style should be treated as open hypotheses.
- OEM practice of tying themes to drive modes, and the Luxury versus Sportiness axes, suggest that the driving context (comfort versus sport) changes the preferred sound. A per-context preference model may be warranted.

### Gaps
- No study was found that directly compares EV interior sound preference across China, Europe and Korea with matched stimuli.
- No study was found on personality (for example, Big Five or sensation seeking) or measured driving style as predictors of EV interior sound preference.
- Age effects have been proposed but not tested in the sources found.
- Most samples are small (N = 10 to 65) and from Western Europe or Korea. The Sci. Rep. 2026 paper and the Sontacchi et al. full text were not read directly.
