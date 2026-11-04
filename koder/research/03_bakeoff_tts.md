# TTS bake-off — Phonon 31m-en vs Kokoro-82M

Completed 2026-11-04 on the remote ARM VM. **Evaluation only: no helium
package changes.** Scripts and auditable text results: [`bakeoff/tts/`](../../bakeoff/tts/README.md).

## Executive summary

- **Verdict: conditional replacement, not an immediate default switch.**
  Phonon int8 removes espeak-ng and has a decisive CPU throughput advantage:
  **10.55–11.14× real time at four threads**, **3.55–3.76× at one thread**.
  Kokoro reaches **0.66–0.67× / 0.50–0.51×**, respectively.
- **Quality superiority is not established.** On 45 pre-expanded sentences,
  WER is Kokoro **1.39%**, Phonon int8 **2.43%**, Phonon fp32 **2.08%**.
  On a separate 20-sentence raw numbers/acronyms audit, the order reverses:
  **2.43% / 0.97% / 1.46%**. Phonon needs its own preprocessing contract;
  blindly applying Kokoro's full number/initialism expansion is a mistake.
- Int8 is operationally viable, but **not waveform-equivalent to fp32**:
  isolated int8 Mimi decoding has median **18.81 dB SNR**, **1.96 dB log
  spectral distance** at temperature 0.3. Listen before accepting its voice
  fidelity. All tested graphs load; all corpus utterances produce finite PCM
  without reaching the generation cap.
- The community README is **materially stale**. The measured revision uses
  an eight-frame flow graph and **stateless full-sequence Mimi**, IR 10 /
  opset 21, not the documented stateful opset-18 streaming graphs.

## Key findings

### 1. Method and environment — evidence: High

Ubuntu 24.04 aarch64, Ampere/Neoverse-N1, 32 physical vCPUs, 128 GB RAM;
Linux `7.0.0-1017-azure`, Python **3.12.3**, Go **1.25.1**. CPU advertises
`asimddp` (ARM dot-product); **Pi 4/Cortex-A72 does not**. Absolute int8 speed
on this VM is optimistic for Pi 4. No claim here is a measured Pi 4 result.

Every TTS timed process uses `taskset -c 0-7`, ORT **1.24.4** CPU EP,
intra-op **4 or 1**, inter-op **1**, sequential execution, BLAS threads 1.
Inference jobs run serially within the lane. One warm-up of each input,
then **median of five runs**; separate process and `/usr/bin/time -v` for
**each model × thread count × input**. All 18 cells exit zero. The first two
Kokoro cells were repeated with the final shared imports for RSS fairness.

**RT× = audio seconds / synthesis wall seconds; higher is better.** Timings
include normalization/tokenization or phonemization, RNG, state allocation,
ORT calls and PCM assembly. They exclude downloads, session construction,
WAV file writes and ASR. TTFA is availability of the **first complete PCM
text chunk**, not first latent, file close, or device playback latency.

The fixed speed inputs contain **10 / 76 / 275 words**. Full text is authored
in `bakeoff/tts/corpus.py`; generated corpus files and audio are outside git
in `~/datasets/tts/`. Session construction observed across cells was about
1.0s for Kokoro, 1.8–1.9s for Phonon int8, 2.2–2.4s for fp32; these are not
cold-cache startup medians and must be added for a fresh CLI process.

Kokoro uses helium's actual `model_quantized.onnx`, Bella, speed 1.0, the
exact existing Go `normalize/` and `phonemize/` through a small evaluation
bridge, its vocabulary, 480-token phoneme chunks and 75ms inter-chunk gaps.
`/tmp/helium` was built and successfully synthesized Bella. **Controlled
speed numbers are Python ORT, not CLI medians**: the existing CLI creates a
session with default options and exposes no intra-op thread control.

Phonon uses Easton, SentencePiece/Unigram via the exported tokenizer JSON,
**`ptts==0.6.0`'s Rust-backed Python `normalize(text, lang='en')`**, sentence /
clause / word packing into at most ~50 tokens, one Euler flow step,
Gaussian noise scaled by **sqrt(0.3)**, seed **1234**, EOS logit >4, one
extra frame (three for ≤4 words), 24 kHz. Each text chunk resets flow/Mimi
and recomputes the voice prompt. No trailing-silence processor or gain
normalization is added. Flow output is cumulative; Mimi decodes the entire
accumulated latent input, rather than exposing the old stateful decoder API.

### 2. Speed and memory — evidence: High on this VM

Tables use the same short / paragraph / long inputs. RSS is the maximum
process RSS including model load, warm-up and five runs; it is **not**
weight size or a forecast of a pure-Go application's RSS.

**Four intra-op threads**

| Model / input | Audio s | RT× ↑ | TTFA s ↓ | RSS MiB ↓ |
|---|---:|---:|---:|---:|
| Kokoro / short | 3.725 | 0.670 | 5.560 | 282.0 |
| Kokoro / paragraph | 29.925 | 0.664 | 33.863 | 1199.7 |
| Kokoro / long | 98.625 | 0.661 | 35.640 | 1163.7 |
| Phonon int8 / short | 2.960 | 10.552 | 0.280 | 323.5 |
| Phonon int8 / paragraph | 25.120 | 10.729 | 0.380 | 592.5 |
| Phonon int8 / long | 83.840 | 11.143 | 0.434 | 665.7 |
| Phonon fp32 / short | 2.960 | 7.734 | 0.383 | 417.2 |
| Phonon fp32 / paragraph | 25.040 | 8.008 | 0.508 | 685.4 |
| Phonon fp32 / long | 83.360 | 8.116 | 0.597 | 750.7 |

**One intra-op thread**

| Model / input | Audio s | RT× ↑ | TTFA s ↓ | RSS MiB ↓ |
|---|---:|---:|---:|---:|
| Kokoro / short | 3.725 | 0.507 | 7.346 | 283.3 |
| Kokoro / paragraph | 29.925 | 0.505 | 44.623 | 1202.8 |
| Kokoro / long | 98.625 | 0.498 | 46.466 | 1162.5 |
| Phonon int8 / short | 2.960 | 3.584 | 0.826 | 323.7 |
| Phonon int8 / paragraph | 25.120 | 3.545 | 1.120 | 592.8 |
| Phonon int8 / long | 83.840 | 3.759 | 1.281 | 665.7 |
| Phonon fp32 / short | 2.960 | 2.307 | 1.283 | 417.8 |
| Phonon fp32 / paragraph | 25.040 | 2.405 | 1.670 | 685.7 |
| Phonon fp32 / long | 83.360 | 2.438 | 1.993 | 751.1 |

Phonon int8 has roughly **16–17× the normalized throughput** of the current
Kokoro int8 export at four threads. Its shorter audio reflects faster voice
delivery; RT× accounts for the duration difference. Int8 is ~1.3–1.6× faster
than Phonon fp32. **Short-input RSS is higher than Kokoro**, whereas the
stock long-input chunk policy uses substantially less memory.

Chunking is a confounder for TTFA/RSS, not a hidden speed trick: Kokoro's
paragraph packs 377 + 127 phoneme tokens; its long input packs 418 / 377 /
476 / 434. Phonon uses 5 / 15 sentence chunks. Smaller Kokoro chunks could
improve latency and memory; these tables describe its current policy, not
an intrinsic 1.2 GiB minimum. No speed input hit Phonon's generation cap.

### 3. Intelligibility — evidence: Medium, ASR proxy only

**195 TTS → STT round trips**: each variant gets 45 controlled sentences
(10 prose, 10 structured numbers/dates/currency, 10 names, 10 acronyms,
5 long sentences), plus a separate 20 raw structured/acronym inputs. The
controlled input spells out intended speech for both models; the raw audit
uses each engine's actual normalizer. Primary voices are **Bella vs Easton**,
not a multi-voice population benchmark.

Recognizer: **Whisper small.en**, pinned Systran conversion, CTranslate2
4.8.5 CPU int8, four threads, beam 5, temperature 0, English forced, no VAD,
no reference prompts, no previous-text conditioning. This recognizer is
**not ORT**; all TTS ORT sessions and the Python ORT installation are 1.24.4.
Soundfile + scipy resampling avoids faster-whisper/PyAV's API mismatch.
All long evaluation sentences fit within Whisper's 30s window.

WER is micro-averaged after OpenAI-style English number/currency
normalization and explicit initialism/orthographic equivalences. A post-hoc
**symmetric formatting audit** removes false errors such as `202-555-0198`
versus ten individually spaced digits, `6.05 p.m.` versus spoken six oh five,
`March 15` versus `March fifteenth`, written domains, JSON and kg. It never
repairs a wrong digit, name or content word. Immutable transcripts,
pre-audit edit counts and literal edit counts are retained in
[`transcripts.json`](../../bakeoff/tts/results/transcripts.json). Literal
controlled WER is 17.64% / 19.09% / 18.77%, mostly written-vs-spoken formatting;
it is not the intelligibility headline. This is **not vendor LLM-assisted WER**.

**Controlled, 45 sentences, 577 canonical reference words**

| Category | Words | Kokoro WER | Phonon int8 | Phonon fp32 |
|---|---:|---:|---:|---:|
| Prose | 96 | 0.00% | 0.00% | 0.00% |
| Structured | 90 | 0.00% | 2.22% | 2.22% |
| Names | 87 | 8.05% | 8.05% | 5.75% |
| Acronyms | 116 | 0.86% | 3.45% | 3.45% |
| Long | 188 | 0.00% | 0.53% | 0.53% |
| **All** | **577** | **1.39% (8 errors)** | **2.43% (14)** | **2.08% (12)** |

**Raw normalizer audit, 20 sentences, 206 canonical reference words**

| Category | Words | Kokoro WER | Phonon int8 | Phonon fp32 |
|---|---:|---:|---:|---:|
| Structured | 90 | 4.44% | 1.11% | 2.22% |
| Acronyms | 116 | 0.86% | 0.86% | 0.86% |
| **All** | **206** | **2.43% (5 errors)** | **0.97% (2)** | **1.46% (3)** |

Examples worth listening to, rather than overinterpreting ASR:

- Phonon on expanded `a m` ends up transcribed **AMIA/AMIOS**; expanded
  `b b c` becomes **BB Key**. Native `AM` / `BBC` inputs fare better. Do not
  reuse Kokoro's acronym expansion unchanged.
- Kokoro raw phone digits become **2002505198**, rather than **2025550198**;
  the raw temperature loses **minus**; the email ends with **calm** instead
  of **dot com**. Phonon's normalizer handles those examples better.
- Phonon reads the raw numeric date as **3 15 2026**, rather than March 15;
  dates/times rewriting is opt-in in the reference normalizer. This is a
  spoken-form policy gap, not proof that the date's numeric content is wrong.
- Rare names/place names remain problematic. Phonon int8's Worcester /
  Gloucester is transcribed **Warsaw / Glusister**; Kokoro also has name errors.
  Whisper spelling uncertainty means these need human review.

A paired **5,000-resample sentence bootstrap** gives Phonon int8 minus
Kokoro WER difference **+1.04 percentage points**, 95% interval
**−0.60 to +2.94** on controlled inputs, and **−1.46 pp**, interval
**−4.19 to +1.06** on raw inputs. Neither establishes a quality winner.
No cap was hit across all 195 corpus utterances; Phonon used 70 chunks per
65 utterances, Kokoro 65. No human MOS/Elo or broad seed/voice study was done.

### 4. Int8/fp32 signal correctness — evidence: High numerically, not perceptually

Five identical texts (prose, currency, names, acronym, long sentence),
Easton, seed 1234, tested at temperatures 0.3 and 0. Waveform SNR compares
the common-length prefix without time alignment. Spectral distance is RMS
log-magnitude STFT difference, FFT 512 / hop 128, common −80 dB magnitude
floor. Full records: [`signal.json`](../../bakeoff/tts/results/signal.json).

| Comparison | Temp | Median SNR dB | Median LSD dB |
|---|---:|---:|---:|
| Full int8 vs full fp32 | 0.3 | −2.18 | 9.10 |
| Int8 Mimi on identical fp32 latents | 0.3 | 18.81 | 1.96 |
| Full int8 vs full fp32 | 0 | −1.90 | 6.14 |
| Int8 Mimi on identical fp32 latents | 0 | 16.82 | 2.06 |

At temperature 0.3, isolated decoder SNR ranges **14.88–19.86 dB**, LSD
**1.87–2.81 dB**. Full AR runs change timing/pitch and sometimes frame count;
their negative sample SNR is **not** proof of a broken codec or unintelligible
speech. Temperature zero does not prevent quantization-induced AR drift.
The decoder-only test separates codec quantization from that drift.

**Does int8 hold up?** It loads, remains finite, and its WER is close to fp32
(only two extra controlled edit errors, one fewer raw error). It is not a
high-SNR replacement for fp32 audio. The old card's >70 dB fp32/reference
claim does not validate this new int8 export; independent numerical parity
against the original Rust/PyTorch fp32 runtime was not tested here.

### 5. ONNX/Go practical work — evidence: High for inspected interfaces

Actual community revision: `f0f522a750bf515227cb478abb97b2ffca7e6d8c`.

- **Four weight files, two graphs**, not one deployable model file: flow
  `.onnx` + external data, Mimi `.onnx` + external data, plus tokenizer and
  voice. Int8 graph/data total **63,979,899 bytes**; fp32 **165,762,741**.
  Kokoro's one ONNX is **92,361,116 bytes**. A bundle is still required.
- Actual producer is `huggingface` / `onnx.quantize`, **IR 10, opset 21**,
  Microsoft domain opset 1. Flow uses GroupQueryAttention, RotaryEmbedding,
  SkipLayerNormalization, QuickGelu; Mimi uses MultiHeadAttention,
  RotaryEmbedding and Gelu. **All run on ORT 1.24.4 CPU EP on aarch64**;
  no missing-op or export blocker occurred. Do not assume standard-ONNX-only
  portability to other runtimes/EPs.
- Flow inputs: IDs `[B,T]`, voice `[B,V,512]`, mask, positions, normalized
  past audio latents, noise `[B,8,32]`, six KV pairs `[B,8,P,64]`. It returns
  eight EOS logits, cumulative denormalized latents, normalized present
  latents and present KV pairs. Voice files are `[1,512,125]` float32;
  transpose them to `[1,125,512]` for this graph.
- Position/mask inputs must cover **all seven future unrolled positions**,
  not only the first prefill position. A first prototype failed with
  `RotaryEmbedding ... position_ids ... got 0`; supplying the complete
  block positions/mask resolves it. The old README loop is incompatible.
- Go needs a **4k Unigram Viterbi tokenizer with UTF-8 byte fallback**, the
  tokenizer's normalization rules, Gaussian sampling, EOS/tail/cap logic,
  six past→present KV pairs, cumulative latent handling, and both sessions
  with explicit thread settings. No phonemizer or speaker encoder is needed.
- Extend/selectively reuse existing pure-Go normalization: currency, numbers,
  dates, titles and units exist. Reference Rust additionally handles email /
  URL separators, phone/digit grouping, Unicode/quotes, temperature/minus,
  Greek/math/subscripts/superscripts, and elongated words. Crucially, preserve
  **native digits and uppercase initialisms where Phonon expects them**;
  full Go expansion is not an interchangeable front end. Python normalization
  is a Rust wheel wrapper, not a pure-Python algorithm to copy.
- **Streaming gap:** current Mimi accepts only `audio_latents` and
  `num_frames`, returns PCM/lengths, and exposes **no state**. This evaluation
  decodes complete text chunks. Frame/stateful streaming needs a validated
  re-export or a separately validated prefix-decoding approach; the latter
  was not benchmarked. Eight flow frames mean a 640ms audio block per call,
  not eight flow integration steps. Existing chunk-streaming can still start
  far sooner than Kokoro, but do not promise the vendor's 68ms first-frame TTFA.

## Contradictions and uncertainty

- **Survey/card streaming/opset/filenames vs actual graphs:** resolved by
  loading and inspecting pinned files. The stale card describes `flow_lm`,
  stateful Mimi and opset 18; the actual revision has `model`, stateless Mimi,
  opset 21. Graph hashes and I/O, not card prose, are the integration contract.
- **Vendor quality win vs this test:** unresolved/generalization unproven.
  Raw-input direction agrees with the vendor, but the samples, normalizer,
  voices, ASR and scoring differ, and confidence intervals include zero.
- **Pi 4 performance, multi-voice quality, human preference, frame streaming,
  and fresh-process CLI latency:** not established. Short-input RSS is worse
  than Kokoro; long-input memory/TTFA partly reflect different chunk policies.
- **Pocket 7m/18m:** not benchmarked; no speed, RSS or quality comparison is
  claimed. Its stated CC-BY-4.0 license is from the task/survey, not a new
  weight-download audit in this lane.

## Recommendation

**Preferred next candidate: Phonon 31m-en int8, conditionally.** Its speed,
smaller artifact set and removal of espeak-ng solve real helium constraints.
Do not announce that it sounds better or remove Kokoro based on this WER
proxy. Keep Kokoro available while validating the following gates:

1. Engine-specific Go preprocessing reproduces the **raw** path, with explicit
   date/time and acronym expectations; no blind reuse of full Kokoro expansion.
2. Listen to int8 vs fp32, especially rare names, acronym/datetime stress and
   codec fidelity. If int8 sounds worse, fp32 remains 7.7–8.1× RT at four
   threads on this VM, at the cost of ~166 MB weights and ~750 MiB peak RSS.
3. Validate actual Pi 4 CPU EP, targeting **≥1.3× RT at four threads**,
   acceptable TTFA/RSS, and the intended chunk/streaming behavior.
4. Pin/review the export and package graph/data/tokenizer/voice together.

**Pocket TTS lower-end option:** do not prioritize another exporter solely
for this VM: Phonon int8's **3.55–3.76× RT at one thread** is already useful,
and fp32's **2.31–2.44×** gives additional evidence beyond dot-product kernels.
However, those are not Pi 4 measurements and Phonon has not clearly won
quality. **Retain Pocket 7m/18m as a contingency**, only promote it if Phonon
fails the actual Pi 4 throughput/memory gate or substantially smaller devices
are required. This test does not justify deleting that low-end path forever.

## Next steps

1. Owner/orchestrator listen to the files below; a small blinded, loudness-matched
   A/B would be stronger than labelled samples. This lane did not listen.
2. Run the same harness on Pi 4, then plan a bundle/Unigram/normalizer adapter
   only if replacement gates pass. No new model was wired into helium here.
3. Obtain or build a pinned stateful Mimi export before claiming true frame
   streaming; separately revalidate fp32 reference parity and quantization.

### Listening index

Root: **`~/bakeoff-samples/tts/`**, mono 24 kHz PCM16, no gain matching.
The requested set is **six fixed texts × two voices × three variants = 36 WAVs**.
For each prefix below: `NN-kokoro-{bella,heart}.wav`,
`NN-phonon-int8-{easton,zoey}.wav`, `NN-phonon-fp32-{easton,zoey}.wav`.
Exact text/file/voice map: [`sample_index.json`](../../bakeoff/tts/results/sample_index.json).

| Prefix | Corpus ID | Text/topic |
|---|---|---|
| 01 | prose-01 | Quick brown fox |
| 02 | structured-11 | Twenty-three dollars / forty-five cents |
| 03 | structured-12 | March fifteenth / meeting time |
| 04 | names-21 | Maya Thompson / Daniel Brooks |
| 05 | acronyms-31 | NASA satellite |
| 06 | long-41 | Volunteers repairing and planting in the park |

Also **12 explicitly post-hoc diagnostics** in `diagnostics/`: raw date,
expanded/native BBC, Worcester/Gloucester, each with Bella/Easton across
three variants. These were not used to select the WER corpus. See
[`diagnostic_index.json`](../../bakeoff/tts/results/diagnostic_index.json).
Two `setup-*.wav` smoke-test files are not part of the indexed comparison.

## Sources consulted

### Licenses and exact model locations

| Artifact | Weight license | Source |
|---|---|---|
| Phonon 31m-en | Apache-2.0 | Original + community HF cards |
| Phonon voices | Apache-2.0 | Phonon/voice catalogue cards |
| Kokoro-82M | Apache-2.0 | hexgrad HF card |
| Whisper small.en | MIT | Systran HF metadata / OpenAI base |

Runtime normalization: `xn-ptts` / `ptts` **MIT OR Apache-2.0**. Kokoro still
requires the separately bundled espeak-ng executable/data; eliminating it
is a packaging benefit, not a change to Kokoro's weight license.

- Phonon original: https://huggingface.co/gradium/phonon-31m-en
- Measured community repo: https://huggingface.co/onnx-community/phonon-31m-en-ONNX
- **Immutable Phonon download base:**
  `https://huggingface.co/onnx-community/phonon-31m-en-ONNX/resolve/f0f522a750bf515227cb478abb97b2ffca7e6d8c/`
- Reference normalization/source inspected:
  https://github.com/gradium-ai/xn-ptts/tree/ee395caac058950cbcabfa3785c63630942f31ed
- Voices/catalogue: https://huggingface.co/gradium/phonon-voices
- Kokoro original card: https://huggingface.co/hexgrad/Kokoro-82M
- **Actual Kokoro model URL:**
  `https://github.com/jikkuatwork/cattery-artefacts/raw/main/models/kokoro-82m-v1.0/model_quantized.onnx`
  Voice files use the same base plus `voices/af_bella.bin` / `voices/af_heart.bin`.
- **Immutable ASR download base:**
  `https://huggingface.co/Systran/faster-whisper-small.en/resolve/d1d751a5f8271d482d14ca55d9e2deeebbae577f/`

Local sources: `koder/STATE.md`, survey's TTS section, `tts/kokoro/{kokoro,chunk}.go`,
`normalize/`, `phonemize/espeak.go`, `registry/registry.go`, `ort/ort.go`.
They establish the actual weights, vocabulary, normalizer, chunking and
lack of CLI thread control. Reference `preprocess.rs` and rewrite modules
establish its normalization policies and opt-in date/time rules.

### SHA256s of measured weight files

Phonon paths are relative to the immutable base above. **All exact URLs,
byte sizes and hashes**, including tokenizer, config, voices and ASR files,
are in [`artifacts.json`](../../bakeoff/tts/results/artifacts.json).

```text
onnx/model_int8.onnx
58b6cdf0b79a10ad426d960258ef8017083f2eaa0a430985bdf0297070566d66
onnx/model_int8.onnx_data
35582f56a6e78e49e03bd21f5adc5581a0ea9b111caf5f691ae3e5d3618cf91b
onnx/mimi_decoder_int8.onnx
3594e7fce7b57d561b7e81816e2eb2b7fe7b3561cafcf58678f713065d1981b6
onnx/mimi_decoder_int8.onnx_data
89a98f731f14acf6d17874dfdf706f90cfa5d44279e7249986aeb643147831e5
onnx/model.onnx
4374b2f3bf69f2dcc0bcecfc91742f46d3b0934c9c4fa2f52126d02fb2de6c94
onnx/model.onnx_data
404bd74fa953816404a5be303f3362bf7afebd4f9b752b4e5c80f86589a50138
onnx/mimi_decoder.onnx
3a33403772d285ac77279b61902e836c1ef031568548f83831f04da889a457f8
onnx/mimi_decoder.onnx_data
35c735bfde62100182ee84747135515612c960f9b54e74233d44a9b509e4128e
Kokoro model_quantized.onnx
fbae9257e1e05ffc727e951ef9b9c98418e6d79f1c9b6b13bd59f5c9028a1478
Whisper model.bin
62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a
```

Corpus JSON SHA256:
`c6eb863cbc444ac3b6ed02d2400ef7dc0007949f5345afbd95220d53d76a323b`.
Pinned Python dependencies: `bakeoff/tts/requirements.txt`. Five regression
tests pass, including token-budget/content preservation and formatting
aliases that keep incorrect phone digits distinguishable. No weights,
WAVs, or audio datasets are committed.
