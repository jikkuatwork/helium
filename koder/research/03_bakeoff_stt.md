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

## Current caveats / next measurements

Helium creates Moonshine sessions with nil session options, exposing no
thread control. Main fair comparison will run the **same downloaded
Moonshine graphs and helium greedy decoder settings** in Python ORT with
explicit thread control, with CLI parity checked separately. Initial helium
CLI smoke exits 0 but writes no transcript or timing; investigate before
calling this path validated. Do not conflate published cross-corpus WER
7.49/12.66 with our CTC-head LibriSpeech result.

Pending: stratified >=300 utterances per split, white-noise 10/0 dB on 50
clean clips, repeated short and long timing/RSS, long-input attention memory,
exact feature parameters, file SHA-256s, and final verdict.
