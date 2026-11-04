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

## Important export caveat (graph inspection)

The sherpa 110M export is opset 17 with a **fixed `[1,9999,512]` relative
position table**, not an unbounded position generator. This suggests an
export limit of roughly 5,000 downsampled frames (~400 s), distinct from the
original NeMo model's advertised 20-minute limit. Five-minute single-pass
and 12/20-minute failure probes are queued; do not promise 20-minute single
passes from this export. Bounded chunking remains available.

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

Pending: fp32 control, noise tables, isolated repeated short/long timing and
RSS, larger model accuracy/timing, exact feature validation, hashes appendix,
and final verdict.
