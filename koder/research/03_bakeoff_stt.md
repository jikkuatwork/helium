# STT bake-off — work in progress

## Scope and environment

Evaluation only; no helium package changes. Ubuntu 24.04 aarch64, Ampere
Altra / Neoverse-N1, 32 logical cores; assigned affinity `taskset -c 8-15`.
Python 3.12.3, Go 1.25.1, ONNX Runtime **1.24.4**, CPU EP. Timed model
sessions will explicitly use intra-op 4 or 1, inter-op 1, sequential execution.
ARM dot-product exists here but not on Raspberry Pi 4: absolute quantized
speeds are optimistic for Pi 4, and no Pi 4 speed claim is made.

## Candidate provenance (verified setup)

- Moonshine: helium's unchanged `encoder_model_quantized.onnx` (7,937,661
  bytes) and `decoder_model_merged_quantized.onnx` (20,243,286 bytes), plus
  tokenizer JSON. Weights MIT (English original; confirm exact upstream card
  before final). Runtime assets downloaded by `/tmp/helium`.
- Parakeet 110M CTC fp32: <https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000>
  revision `3af92f152d32c836acabf38f4c993bc96b80eb2d`, `model.onnx`,
  458,161,021 bytes. Graph metadata explicitly says **Only the CTC branch is
  exported**, 80 features, subsampling 8, vocabulary 1024 + blank.
- Parakeet 110M CTC int8: <https://huggingface.co/VocaHQ/sherpa-onnx-nemo-parakeet-tdt-ctc-110m-en-int8>
  revision `43869f73831659dd8b0ccee617ee42474b7aa974`, `model.int8.onnx`,
  131,652,171 bytes. Dynamic QUInt8 quantization of that fp32 export;
  upstream quantizer used ORT 1.30.0, **inference here is 1.24.4**. Both
  graphs successfully load in ORT 1.24.4 CPU EP. NVIDIA source and this
  int8 model card state **CC-BY-4.0**.
- Canonical sherpa int8 HF repository is empty, not a usable download.

Models live in `~/models/stt/`; LibriSpeech OpenSLR 12 test-clean/test-other
archives and extracted FLAC live in `~/datasets/stt/`; no weights or audio
are committed.

## Method and completed accuracy (interim)

OpenSLR 12 test-clean/test-other, uniformly shuffled utterances with Python
`random.Random` seeds 20261104/20261105; 320 per split. Exclude clips longer
than 29.5 s so every short clip is one graph call for both candidates.
References contain 6,509 clean / 5,813 other words; audio is 2,407.62 /
2,085.52 s. WER is corpus-micro `(S+D+I)/reference_words`, lowercase,
punctuation deleted, whitespace collapsed. No number expansion, spelling
repair, language model, beam search, VAD, or post-hoc transcript correction.
See per-clip JSONL under `bakeoff/stt/results/`.

| Build | Clean WER | Other WER |
|---|---:|---:|
| Moonshine quantized | 5.21% | 12.23% |
| Parakeet 110M int8 CTC | 3.40% | 5.92% |
| Parakeet 110M fp32 CTC | 3.44% | 5.54% |
| Parakeet 0.6B v2 int8 TDT | 1.97% | 3.04% |

That is **34.8% / 51.6% fewer errors** on these two samples. Do not compare
these directly to the cross-corpus model-card 7.49/12.66 figures; NVIDIA's
default decoder is TDT, whereas this evaluation deliberately uses CTC.
Four-thread corpus RTF was approximately 0.036 vs 0.023, **diagnostic only**;
final speed ranking will use isolated median-of-five repetitions, including
a balanced 60-clip batch and explicit one-thread runs.

Noise uses the same first 50 selected clean clips, deterministic Gaussian
white noise seeded from SHA-256(utterance ID), scaled from whole-clip mean
signal/noise power at 10 and 0 dB. No clipping/renormalization; float samples
are fed directly. This tests white-noise robustness, not real-world room,
traffic, microphone, or competing-speaker noise.

Long files concatenate whole selected clean utterances (no added gap,
no cropped words), just over 5, 12, and 20 min. Tests distinguish the actual
helium silence-aware 30 s chunker/stitcher, controlled fixed 30 s blocks,
and Parakeet single-pass inference. The Go helper is built with a **temporary
Go build overlay changing only session thread options**; product files are
unchanged. It uses helium's actual WAV reader, chunk planner, decoder,
tokenizer, and overlap stitching. Python Moonshine greedy output has matched
the CLI on the initial 9.19 s parity clip; further parity checks are pending.

## Noise robustness (completed, 50 clean clips)

All three columns use the **same 50 clips / 1,266 reference words**.

| Build | Original WER | 10 dB WER | 0 dB WER |
|---|---:|---:|---:|
| Moonshine quantized | 5.61% | 12.80% | 52.05% |
| Parakeet 110M int8 CTC | 3.16% | 5.77% | 21.80% |
| Parakeet 110M fp32 CTC | 3.32% | 5.21% | 18.17% |
| Parakeet 0.6B v2 int8 TDT | 1.74% | 2.61% | 7.19% |

Int8 is the practical small tier, but it is not accuracy-free: test-other
costs +0.38 WER points vs fp32 and 0 dB white noise costs +3.63 points.
Both remain substantially better than Moonshine. The paired utterance
bootstrap 95% CI for Parakeet-int8 minus Moonshine WER is -2.50 to -1.11
points (clean), -7.53 to -5.08 (other), 2,000 draws, seed 20261104. This is
utterance—not speaker—resampling, not a deployment-wide confidence claim.

## Important export caveat (graph inspection and first long result)

The sherpa 110M export is opset 17 with a **fixed `[1,9999,512]` relative
position table**, not an unbounded position generator. This suggests an
export limit of roughly 5,000 downsampled frames (~400 s), distinct from the
original NeMo model's advertised 20-minute limit. **Both 12- and 20-minute
single passes now failed**, at `/layers.0/self_attn/Add_2`, with relative
position broadcast mismatches (4012 vs 9012, and 9999 vs 15016). These are
export shape errors, not unavailable ORT operators. Bounded chunking works.

**The 301.735 s single-pass test completed** at 4 threads: median **22.12 s**
(RTF 0.0733), WER 4.86%, **5,468,464 KiB peak RSS (5.22 GiB)**. That already
exceeds a 4 GB Pi 4. The fixed-30-s Python Moonshine control took 13.20 s
(RTF 0.0438), WER 9.13%, 403,300 KiB RSS. These fixed cuts are not helium's
silence-aware cuts. The actual helium Go engine (thread-only evaluation
overlay) scores **16.37% WER / 12.91 s** on the 5-minute file and **10.78% /
32.80 s** on the 12-minute file at 4 threads. Its chunk boundaries, overlap,
and stitching differ from fixed cuts; do not attribute that gap solely to
the model. The surprising long-file degradation merits separate chunker
regression work, not a product fix in this lane.

On the **same 12-minute file and same fixed 30 s cuts**, Python Moonshine
scores 7.50% WER / 29.77 s, versus Parakeet int8 4.82% / 17.44 s, at 4
threads. Parakeet's peak RSS is 723,376 KiB (**0.69 GiB**), rather than the
5.22 GiB of its five-minute single pass. This strongly favors **bounded
Parakeet chunking**, even if a future export removes the position-table cap.

## Representative speed and the optional large tier (interim)

Sixty clips, 30 per split, 442.57 s total, loaded before timing; one full
batch warm-up followed by five whole-batch repetitions. Same CPU EP,
ORT 1.24.4, assigned cores, explicit thread counts. Main comparison uses
Python for both candidates, avoiding mixed-runner speed claims.

| Build | RTF, 4 threads | RTF, 1 thread | RSS, 4 threads |
|---|---:|---:|---:|
| Moonshine quantized | 0.03994 | 0.07653 | 397.6 MiB |
| Parakeet 110M int8 CTC | 0.02330 | 0.04416 | 724.6 MiB |

Parakeet is **1.7× faster** here despite its larger weights. The large tier
is **0.6B v2 English**, not v3: 652,184,014-byte encoder plus 8,998,286-byte
merged decoder/joint graph, CC-BY-4.0, from the fixed istupakov v2 revision.
It achieves 1.97% / 3.04% WER and 7.19% at 0 dB noise, making it a credible
optional high-quality desktop tier. Its representative batch timing is
still running. A five-minute file takes 21.58 s in fixed 30 s blocks
(WER 3.56%, 1.52 GiB peak), versus 50.65 s single pass (WER 3.08%, 5.34 GiB).

## Current caveats / next measurements

Helium creates Moonshine sessions with nil session options, exposing no
thread control. The main fair comparison uses identical graphs and helium's
greedy settings in Python ORT; the evaluation-only overlay gives its real
Go engine explicit 4/1 threads for separate parity and long-audio measures.

Initial short smoke (a two-word clip) genuinely produced an empty Moonshine
transcript; a normal 9.19 s clip produced matching Python/Go/CLI output.
Helium's CLI timing stderr is suppressed: in `ort.Init`, deferred close of
the duplicated stderr descriptor executes before deferred restore. The
probe uses direct ORT initialization to avoid that unrelated issue; **no
product fix is included**.

Pending: large representative batch timing, actual 20-minute helium result,
exact graph-length boundary, full actual-Go short/noise parity, hashes appendix,
and final verdict. The independent feature frontend already matches collapsed
CTC tokens on 10/10 clips (max feature error 1.10e-4, RMS <=3.41e-6); frame
argmax alignment is not bit-identical under dynamic quantization.
