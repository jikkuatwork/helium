# Model Survey — Tiny Models for Helium (2026-11-04)

Survey of current (2025–2026) models against helium's north-star: a Go runtime
for tiny models where **one binary + one model file** runs a model, CPU-first
(Pi 4 reference low end), optional GPU, importable as a Go module.

Method: four parallel web-research passes (TTS; STT/VAD/wake word; LLM/VLM;
embeddings + utility), checked against HF model cards, the HF file API,
GitHub repos and papers. The LLM pass also inspected downloaded ONNX graph
headers (I/O names, ops). Tags: **V** verified in a primary source,
**VC** vendor claim, **3P** single third-party report, **?** unknown.

## Filters

1. Runs on ONNX Runtime (CPU EP); pre/post-processing doable in pure Go.
2. Weights redistributable (we self-host in `cattery-artefacts`):
   Apache-2.0 / MIT / BSD / CC-BY-4.0 OK. **Revenue-cap licenses OK** when
   they carry no other use restrictions (owner decision 2026-11-04, prompted
   by LFM's $10M cap: "99% of users will be able to use it freely").
   NC, gated-with-terms, OpenRAIL/AUP use restrictions, competing-use bans,
   AGPL → out.
3. Small enough for CPU; Pi 4 (Cortex-A72, 4 GB) as the low end.
4. TTS: no external phonemizer (espeak-ng is the main blocker for one-file TTS).

## Picks at a Glance

| Modality | Default | Low-end / alt | License |
|---|---|---|---|
| TTS | Phonon 31m-en | Pocket TTS 7m/18m | Apache / CC-BY |
| STT | Parakeet TDT-CTC 110M | Parakeet TDT 0.6B (large) | CC-BY-4.0 |
| VAD | Silero VAD v6.2 | — | MIT |
| LLM | Qwen3.5-4B vs LFM3-1.7B | LFM2.5-1.2B | Apache / LFM |
| VLM | Qwen3.5-4B vis. vs LFM3-VL-2B | LFM2.5-VL-450M | Apache / LFM |
| Embed | Granite-97M-multi-r2 | EmbeddingGemma 2 (qual.) | Apache |
| Denoise | GTCRN | DPDFNet (quality) | MIT / Apache |
| OCR | PP-OCRv6 small | PP-OCRv6 tiny | Apache |

## TTS

**Default: Phonon 31m-en** (Gradium, ex-Kyutai team; released 2026-10-20)
- **No phonemizer** — SentencePiece Unigram (4k vocab, byte fallback) on raw
  text (V). Eliminates espeak-ng.
- Arch: 6-layer causal transformer (d=512) → 1-step flow head → 32-dim latent
  per 80 ms → 10.3M Mimi decoder; 24 kHz, streaming (V).
- Weights, tokenizer, 102 voice embeddings (256 KB each), `phonon-mimi`:
  **Apache-2.0, ungated** (V). English only.
- ONNX: community `onnx-community/phonon-31m-en-ONNX` — 2 graphs (flow LM with
  past→present state, Mimi decoder), opset 18; int8 ≈ 38 + 25 = 63 MB (V).
  fp32 parity >70 dB SNR (claim); re-verify int8 ourselves.
- Go work: Unigram tokenizer; text normalization (Gradium's is ~170 KB Rust;
  we already have pure-Go `normalize/` from #25 to extend); ≤~50-token
  sentence chunks; AR loop with Gaussian noise (temp 0.3) + EOS threshold;
  streaming decoder state.
- Speed (Gradium runtime, not ORT): Pi 5 1-core 2.3× RT, 68 ms TTFA (VC).
  Pi 4 / ORT: **?**
- Quality (Gradium-run, no independent eval yet): Elo 2098 vs Kokoro 2043;
  hard-set WER 1.5–1.7% vs Kokoro 3.5% (VC).
- No local voice cloning (no speaker encoder in open weights) (V).
- **Trap:** all Phonon **40m** checkpoints (incl. multilingual, 5 langs) are
  **CC BY-NC 4.0 + gated** (V) — unusable.

**Low-end: Pocket TTS english 7m / 18m** (Kyutai, 2026-10-20) — same pipeline
as Phonon, so one Go loop serves both families. CC-BY-4.0, ungated repo (V).
No ONNX yet — adapt the Pocket exporter. Only needed if Phonon int8 is too
slow on Pi 4 (target ≥ ~1.3× RT on 4 threads).

**Multilingual / cloning tier: Pocket TTS 100M** — 7 languages, WAV cloning,
CC-BY-4.0 weights (use the ungated `pocket-tts-without-voice-cloning` repo or
vet cloning terms); some bundled voices NC/unlicensed → vet each. Community
ONNX (sherpa-onnx int8, ~173 MB bundles). Desktop/server only (Pi CM4 demo
~10 s for 2 s audio, 3P).

**Watch:** Phonon 40m if relicensed; Supertonic 3 (raw codepoints, 31 langs,
official Go+onnxruntime_go example, but OpenRAIL-M + repo archived 2026-09);
Soprano 1.1-80M (Apache, BPE, no phonemizer, 1 voice, en).

**Disqualified:** Kokoro-82M and Kitten TTS 0.8 (need espeak-ng); Piper
(GPL, embeds espeak); NeuTTS Air/Nano (espeak + GGUF, custom license);
Chatterbox Turbo (~490 MB q4); Kitten TTS 2 (1.7B, custom revenue-cap
license); MOSS-TTS-Nano (not licensed for redistribution, Python normalizer).

## STT, VAD, Wake Word

**Default STT: Parakeet TDT-CTC 110M** (NVIDIA, English) — WER 7.49 vs
Moonshine-tiny 12.66 (~40% fewer errors) (VC). Use the CTC head: one graph,
greedy argmax. Punctuation, 20 min single pass. int8 ≈ 100 MB. 80-bin log-mel
in Go. CM5 RTF 0.12 (3P). CC-BY-4.0. Pi 4 speed **?** — benchmark.

**Large tier: Parakeet TDT 0.6B v2 (en) / v3 (25 EU langs)** — WER 6.05 /
6.34 (v3 independently reproduced 6.32). int8 ≈ 670 MB, 3 graphs, TDT decode
loop, 128-bin mel, ~1.8 GB RAM. 24 min single pass (no 30 s chunking).
CC-BY-4.0. Community ONNX (istupakov, sherpa-onnx).

**Streaming tier: Moonshine v2 Streaming** (Tiny 34M / Small 123M; MIT) —
raw PCM, AR decoder, 80 ms lookahead, word timestamps; WER 12.0 / 7.84;
official ONNX is int8 `.ort` split into 5–6 graphs (~45 / 142 MB).

**VAD: Silero VAD v6.2** — MIT, 1.2–2.3 MB ONNX, 8/16 kHz, <1 ms per 32 ms
chunk (VC); v6 noise accuracy 0.61→0.87. Offline `*_sequence.onnx` variant
for batch files; `If`-free variant exists.

**Turn detection (later):** Smart Turn v3.2 (BSD-2, 8.7 MB ONNX).

**Wake word (later):** sherpa-onnx KWS Zipformer (open-vocab, no training;
needs transducer keyword search in Go); LiveKit WakeWord (Apache repo,
weights license **?**).

**Watch:** Nemotron 3.5 ASR Streaming 0.6B (OpenMDW, no ONNX yet); FUTO
asr4all (28M CTC, Pi 4 2.4× RT, but custom restricted license); Qwen3-ASR-0.6B;
Meta Omnilingual CTC 300M (Apache, 1600+ langs).

**Disqualified:** TEN VAD (Agora terms forbid enabling third parties — can't
ship in a library); openWakeWord pretrained models (CC BY-NC-SA); Moonshine
legacy non-English (NC community license); SenseVoice (custom license, weak
English); Kyutai STT (no ONNX, 1B+ codec decoder); Whisper (30 s window,
hallucinates, worse than Parakeet per byte); LLM-decoder ASR (Voxtral, Granite
Speech, Canary-Qwen) — GPU-sized.

## LLM and VLM

**Default LLM: keep Qwen3.5-4B** — no Apache ≤4B model beats it on IF/tool
benchmarks (IFEval 89.8, BFCL-V4 50.3, TAU2 79.9; VC). Already integrated.
Default to non-thinking (`enable_thinking=false`) for voice turns; enable per
request. Arch (V, from graph): 24 Gated-DeltaNet layers with fixed-size
`past_conv`/`past_recurrent` state + 8 attention layers with KV cache;
`position_ids` is [3,B,S] MRoPE. Qwen3.6/3.8 open weights start at 27B — nothing
newer and small.

**Low-end:** Qwen3.5-0.8B (0.60 GiB q4; weak tools, BFCL 25.3) or 2B
(1.43 GiB; card warns of thinking loops). Same decode loop.

**VLM: Qwen3.5's own vision encoder** — same onnx-community repos ship it:
+65 / 208 / 209 MiB q4 for 0.8B / 2B / 4B (V). One family = one decode loop for
text and vision. Go preprocessing: bicubic resize to multiples of 32 px,
/255, mean/std 0.5, 16-px patches, frame duplication, 2×2 merge order;
tokens = (H/32)(W/32) → 448² = 196 tokens. Splice features into
`inputs_embeds`, build 3-D MRoPE ids. Cap images ~448² on CPU.

**Pi 4 caveat (V, ORT 1.24.1 source):** Cortex-A72 lacks dotprod, so 4-bit
MatMulNBits uses fp32-compute kernels with weight dequant on prefill → slow
prefill for long prompts/images. Realistic Pi 4 LLM: 0.8B. Pi 5 has dotprod.

**Generic decode loop:** binding each `past_*` input to its `present_*` output
(empty initial caches) covers Qwen3.5, LFM, Granite-H and Gemma 4 — so one Go
loop driven by the bundle manifest can serve many families.

**LFM family (Liquid AI) — accepted after license review (2026-11-04):**
- **LFM3-1.7B** (2026-10-27): challenger for the default LLM. IFEval 96.7,
  BFCL-V4 71.4, τ³ 68.0 vs Qwen3.5-4B 89.8 / 50.3 — at ~half the size
  (1.21–1.51 GiB q4); weaker on GPQA (63.4 vs 75.8). All VC, 8 days old, no
  independent evals. Official (Liquid-published) single-graph ONNX: 13
  `past_conv` + 11 KV pairs, only ops the Qwen3.5 graphs already use (V).
  Tool-call XML matches Qwen3.5's `qwen3_coder` format → parser reuse.
  Risk: thinking on by default; card says disabling it "can be inconsistent"
  — matters for low-latency voice turns.
- **LFM2.5-1.2B-Instruct** (2026-01): **Pi-class pick**, replaces
  Qwen3.5-0.8B. 0.79 GiB q4; IFEval 86.2, BFCLv3 49.1 (VC) vs 0.8B's 52.1 /
  25.3. Non-thinking by design (reasoning is a separate checkpoint). Pi 5
  Ollama 15.5 tok/s @ 967 MB RSS (3P). 32K ctx, 8 languages.
- **LFM3-VL-2B**: VLM challenger — avg 71.4 over 62 benchmarks vs Qwen3.5-2B
  64.0 / 4B 73.4 (VC); CPU bundle 1.69 GB; decoder takes `image_features`
  directly (no Go-side splicing); Qwen-style preprocessing (patch 16,
  merge 2, mean/std 0.5). Separate checkpoint from LFM3-1.7B (unlike Qwen,
  text + vision are two model files).
- **LFM2.5-VL-450M**: Pi-class VLM. SigLIP2 NaFlex, 512-px tiles +
  thumbnail, 64–256 tokens; OCRBench 684 vs SmolVLM2-500M 609 (VC); 0.75 GiB.
- **License (LFM Open License 1.0, read 2026-11-04):** Apache-2.0-derived.
  Commercial use unlicensed for a Legal Entity (incl. ≥50% affiliates) with
  ≥ $10M annual revenue; qualified non-profits exempt for non-commercial or
  research use. No AUP, no field-of-use limits. Redistribution: include
  license copy, mark modified files, keep notices + NOTICE file. Auto-terminates
  on non-compliance (no cure period). Each downstream importer is its own
  licensee → helium must surface the cap (bundle manifest license field,
  `helium list`, `THIRD_PARTY_NOTICES.md`).

**Watch:**
- Gemma 4 E2B (Apache since Apr 2026; text+image+audio; 3.38 GiB q4 with PLE).
- Granite 4.1-3B (Apache; needs our own q4 export).

**Disqualified:** FastVLM (Apple research-only); Moondream 3.x (custom
license, GPU runtime, no ONNX); Gemma 3n (Gemma terms; superseded by Apache
Gemma 4); Llama 3.2 (dated, community license); SmolLM3-3B / Phi-4-mini
(same size, weaker, no vision); EXAONE 4.0 (NC); SmolVLM2 (weak language side,
IFEval 30).

## Embeddings and Utility Models

Priority by value-per-Go-effort: **embeddings → denoising → OCR**; rerankers
nearly free after embeddings but low value at personal-corpus scale.

**Embeddings:**
- Start: **granite-embedding-97m-multilingual-r2** (IBM, 2026-04, Apache) —
  384-d, 32k ctx, CLS pooling, no prompts; official int8 ONNX 98 MB (named
  `quint8_avx2` → aarch64 speed **?**). Byte-level BPE → reuses existing
  `llm/qwen/tokenizer.go`. Multilingual retrieval 60.3 (VC); English weaker.
- Quality upgrade: **EmbeddingGemma 2** (Google, 2026-10, Apache, ungated) —
  270M text tower, 768-d Matryoshka (512/256/128), 8k ctx; MTEB multi 61.36,
  eng 68.46 (VC); onnx-community int8 314 MB / q4 174 MB. Needs a Gemma
  SentencePiece-BPE tokenizer (262k vocab).
- Desktop: Qwen3-Embedding-0.6B (Apache, reuses Qwen tokenizer, 614 MB int8).

**Rerank:** Qwen3-Reranker-0.6B (Apache; yes/no logits; reuses Qwen
tokenizer + template) or gte-reranker-modernbert-base (Apache, 151 MB int8).

**Denoise:** **GTCRN** (MIT, 48K params, 0.54 MB ONNX, 16 kHz — matches STT
input; RTF 0.07 streaming, VC). Go: FFT/STFT/iSTFT only. Quality alt:
DPDFNet (Ceva, Apache, 8.8–14.6 MB).

**OCR:** **PP-OCRv6** (Apache, official ONNX, 2026-06) — small: det 9.9 MB +
rec 21.2 MB; tiny: 1.8 + 4.5 MB. Go: resize/normalize, DB post-process
(threshold, contours, min-area rect, unclip), perspective crop, CTC decode.

**Speaker ID / diarization:** 3D-Speaker CAM++ (Apache, ~29 MB);
pyannote segmentation-3.0 (MIT, gated but redistributable). Needs Kaldi fbank.

**Translation:** Qwen3.5 already translates (zero new model). OPUS-MT/Marian
(CC-BY-4.0, ~106 MB int8 per pair) if dedicated MT is needed.

**Detection:** RF-DETR Nano/Small (Apache for N–L sizes; no NMS) or D-FINE-N
(Apache, 4M; COCO-only checkpoints).

**Disqualified:** jina v5 / reranker v3 (CC-BY-NC); EmbeddingGemma-300M v1
(Gemma terms; superseded); harrier-oss-v1 (MIT label on Gemma3 base —
unclear); NLLB-distilled (NC); TranslateGemma (Gemma terms); HY-MT1.5 (region
exclusions); Indra/Chandra OCR (OpenRAIL-M + revenue caps); DEIMv2 (no
commercial); RF-DETR Atto/Femto/Pico/XL (PML 1.0); Ultralytics YOLO (AGPL);
ms-marco MiniLM cross-encoders (MS MARCO NC data).

## Cross-Cutting Findings

1. **Nearly every pick is multi-graph** (Phonon 2, Parakeet-0.6B 3,
   Moonshine v2 5–6, Qwen3.5 embed+decoder+vision, PP-OCR 2) — confirms the
   single-file bundle format is the foundation, not a nice-to-have.
2. **Shared Go building blocks** that unlock many models at once:
   - SentencePiece (Unigram + BPE w/ byte fallback): Phonon, Pocket, Parakeet,
     EmbeddingGemma 2, Gemma 4, OPUS-MT.
   - Byte-level BPE (exists): Qwen3.5, Granite embed, Qwen3 embed/rerank.
   - Log-mel / fbank + STFT/iSTFT: Parakeet, GTCRN, speaker models.
   - Generic stateful session runner (`past_*` → `present_*`): Qwen3.5, LFM,
     Phonon flow LM, Moonshine v2.
   - Text normalizer (exists, #25): Phonon/Pocket.
3. **Licensing traps are everywhere** — Phonon 40m, TEN VAD, openWakeWord
   models, Gemma 3n, Supertonic all fail. (LFM passes under the revenue-cap
   policy, but its cap must be surfaced to importers.) CC-BY-4.0 picks (Parakeet,
   Pocket) need attribution in `THIRD_PARTY_NOTICES.md` (#07).
4. **Evidence is thin on our hardware** — Phonon quality is vendor-only and
   two weeks old; community ONNX exports unverified; Pi 4 ORT speeds unknown
   for most picks. Bake-off before committing.
5. **Pi 4 limits:** TTS/STT/VAD/embeddings fine; LLM realistically ≤1.2B
   (no dotprod → slow q4 prefill). LFM2.5-1.2B is the best fit. Consider
   whether Pi 5 should be the LLM reference.

## Sources (primary)

TTS
- https://gradium.ai/blog/gradium-releases-phonon
- https://gradium.ai/blog/release-phonon-open-weight
- https://huggingface.co/gradium/phonon-31m-en
- https://huggingface.co/gradium/phonon-40m-multilingual
- https://huggingface.co/gradium/phonon-mimi
- https://huggingface.co/gradium/phonon-voices
- https://github.com/gradium-ai/xn-ptts
- https://huggingface.co/onnx-community/phonon-31m-en-ONNX
- https://github.com/kyutai-labs/pocket-tts
- https://huggingface.co/kyutai/pocket-tts-without-voice-cloning
- https://k2-fsa.github.io/sherpa/onnx/tts/pocket.html
- https://huggingface.co/Supertone/supertonic-3
- https://huggingface.co/ekwek/Soprano-1.1-80M
- https://github.com/hexgrad/misaki
- https://huggingface.co/KittenML/kitten-tts-mini-0.8

STT / VAD / wake word
- https://huggingface.co/nvidia/parakeet-tdt_ctc-110m
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx
- https://arxiv.org/html/2604.14493v2
- https://arxiv.org/abs/2602.12241
- https://github.com/moonshine-ai/moonshine/blob/main/docs/models/available-models.md
- https://github.com/snakers4/silero-vad/releases
- https://github.com/snakers4/silero-vad/wiki/Quality-Metrics
- https://github.com/TEN-framework/ten-vad/blob/main/LICENSE
- https://huggingface.co/pipecat-ai/smart-turn-v3
- https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models
- https://github.com/dscripka/openWakeWord

LLM / VLM
- https://huggingface.co/Qwen/Qwen3.5-4B
- https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX
- https://huggingface.co/onnx-community/Qwen3.5-0.8B-ONNX
- https://huggingface.co/LiquidAI/LFM3-1.7B
- https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX
- https://www.liquid.ai/lfm-license
- https://huggingface.co/google/gemma-4-E2B-it
- https://huggingface.co/onnx-community/gemma-4-E2B-it-ONNX
- https://huggingface.co/ibm-granite/granite-4.1-3b
- https://huggingface.co/HuggingFaceTB/SmolVLM2-500M-Video-Instruct
- https://huggingface.co/apple/FastVLM-0.5B
- https://github.com/microsoft/onnxruntime/blob/v1.24.1/onnxruntime/core/mlas/lib/qnbitgemm_kernel_neon.cpp
- https://simeononsecurity.com/articles/ai-models-raspberry-pi-4-5/

Embeddings / utility
- https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2
- https://huggingface.co/google/embeddinggemma-2
- https://huggingface.co/onnx-community/embeddinggemma-2-ONNX
- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- https://github.com/Xiaobin-Rong/gtcrn
- https://huggingface.co/Ceva-IP/DPDFNet
- https://huggingface.co/PaddlePaddle/PP-OCRv6_tiny_det_onnx
- https://huggingface.co/papers/2606.13108
- https://github.com/roboflow/rf-detr
- https://huggingface.co/Xenova/opus-mt-en-de
