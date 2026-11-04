# TTS bake-off — Phonon 31m-en vs Kokoro-82M

Status: in progress, 2026-11-04. Evaluation only; no runtime integration.

## Early verified findings

- Python ONNX Runtime **1.24.4** CPU EP loads Phonon fp32/int8 flow and
  decoder graphs successfully on aarch64.
- Pinned community revision: `f0f522a750bf515227cb478abb97b2ffca7e6d8c`.
  **Its README is stale**: it describes `flow_lm` and a stateful Mimi decoder,
  but actual files are `model*.onnx`, with **8 autoregressive frames per call**,
  and a **stateless full-sequence Mimi decoder**. Do not implement the card's
  streaming snippet against this revision.
- Actual flow inputs: text IDs, voice `[B,V,512]`, attention mask, position IDs,
  normalized past audio latents, noise `[B,8,32]`, six KV pairs. Outputs include
  cumulative denormalized audio latents, normalized present latents, EOS logits
  for eight frames, and six present KV pairs. Decoder takes audio latents and
  num_frames, returns PCM and lengths. No decoder past/present inputs.
- Flow graph already contains Microsoft fused ops (GroupQueryAttention,
  RotaryEmbedding, SkipLayerNormalization, QuickGelu), not just the standard
  opset-18 ops advertised by the stale card.
- Reference runtime normalization is Rust (`ptts/src/preprocess.rs`), not an
  independent Python implementation. Plan: explicit already-normalized spoken
  text for the primary controlled comparison; report normalization coverage
  separately.

## Sources / licenses

- Phonon original: https://huggingface.co/gradium/phonon-31m-en — Apache-2.0.
- Community ONNX: https://huggingface.co/onnx-community/phonon-31m-en-ONNX —
  Apache-2.0 model-card metadata.
- Reference: https://github.com/gradium-ai/xn-ptts — MIT OR Apache-2.0 runtime.
- Kokoro original: https://huggingface.co/hexgrad/Kokoro-82M — license to be
  verified and file hashes to be recorded with measurements.

## Next measurements

Validate the current eight-frame loop, then ≥5 warm runs at 4 and 1 threads,
peak RSS, fp32/int8 signal comparisons, ≥40-sentence STT round trip, listening
samples. Final verdict pending measurements.
