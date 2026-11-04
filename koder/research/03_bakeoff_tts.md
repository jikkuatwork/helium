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
- Reference normalization is Rust (`ptts/src/preprocess.rs`), but discovery
  found an exposed Python entry point: **`ptts.normalize(text, lang='en')`**
  in `ptts==0.6.0`, which needs no model loaded. The runner uses it. Primary
  controlled WER uses already-normalized spoken text for both models; a
  separate 20-sentence raw structured/acronym audit tests each normalizer.

## Sources / licenses

- Phonon original: https://huggingface.co/gradium/phonon-31m-en — Apache-2.0.
- Community ONNX: https://huggingface.co/onnx-community/phonon-31m-en-ONNX —
  Apache-2.0 model-card metadata.
- Reference: https://github.com/gradium-ai/xn-ptts — MIT OR Apache-2.0 runtime.
- Kokoro original: https://huggingface.co/hexgrad/Kokoro-82M — license to be
  verified and file hashes to be recorded with measurements.

## Interim measurements (4 threads)

Median of five warm runs; Python ORT CPU EP, includes Kokoro's Go
normalizer/espeak bridge, excludes model load and WAV file writes. TTFA is
first complete PCM chunk. All runs use `taskset -c 0-7`.

| Kokoro input | RT× ↑ | TTFA s ↓ | Peak MiB ↓ |
|---|---:|---:|---:|
| 10 words | 0.677 | 5.501 | 278.2 |
| 76 words | 0.667 | 33.670 | 1198.1 |
| 275 words | 0.661 | 35.640 | 1163.7 |

At 1 thread Kokoro reaches 0.507 / 0.505 / 0.498× RT for short /
paragraph / long, respectively.

| Phonon int8 input | RT× ↑ | TTFA s ↓ | Peak MiB ↓ |
|---|---:|---:|---:|
| 10 words, 4 threads | 10.552 | 0.280 | 323.5 |
| 76 words, 4 threads | 10.729 | 0.380 | 592.5 |
| 275 words, 4 threads | 11.143 | 0.434 | 665.7 |
| 10 words, 1 thread | 3.584 | 0.826 | 323.7 |
| 76 words, 1 thread | 3.545 | 1.120 | 592.8 |

Phonon uses more RSS on the short input, less on the default-chunked long
inputs. Its faster delivery also produces shorter audio (2.96 / 25.12 /
83.84s vs Kokoro 3.725 / 29.925 / 98.625s); RT× accounts for this.
Neither speed input hit Phonon's generation cap.

The paragraph packs into 377 + 127 phoneme tokens, matching helium's
480-token chunk policy; memory is dominated by inference, not weights.
Full matrix and quality measurements are running serially.

## Next measurements

Complete ≥5 warm runs at 4 and 1 threads, peak RSS, fp32/int8 signal
comparisons, 45-sentence/model STT round trip plus separate raw-input audit,
and 36 listening samples. Final verdict pending measurements.
