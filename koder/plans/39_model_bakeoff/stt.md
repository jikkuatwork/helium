# Bake-off: STT — Parakeet TDT-CTC 110M vs Moonshine-tiny

Area name: `stt`. Your cores: `taskset -c 8-15` (use 4 threads inside that).

## Question

Should helium replace **Moonshine-tiny** (UsefulSensors, ~27 MB quantized
ONNX, raw 16 kHz PCM in, English) with **Parakeet TDT-CTC 110M** (NVIDIA,
CC-BY-4.0, English, punctuation) using its CTC head (one graph, greedy
argmax)? Model-card WER: 7.49 vs 12.66 — we need our own numbers on this CPU.

## Candidates

- **Moonshine-tiny** — helium's current STT: `/tmp/helium stt file.wav`
  (first run downloads the model). Helium chunks audio at ~30 s.
- **Parakeet TDT-CTC 110M** — `https://huggingface.co/nvidia/parakeet-tdt_ctc-110m`.
  Find or make an ONNX export of the **CTC head** (sherpa-onnx and the
  `onnx-asr` / istupakov exports are good places to look; NeMo export is the
  fallback). Use int8 if available, else fp32 (and say which). Feature
  extraction is 80-bin log-mel — note the exact parameters (window, hop,
  normalization) because helium would reimplement them in Go.
- **Optional, if time allows:** Parakeet TDT 0.6B v2 int8 as the
  "large tier" reference (`https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx`
  or a v2 export).

## Measure

1. **Accuracy:** WER (normalized: lowercase, no punctuation) on ≥ 300
   utterances of LibriSpeech test-clean and ≥ 300 of test-other (OpenSLR 12),
   plus a few long files (5–20 min: concatenate utterances or use a public
   long-form talk) to test long-audio handling.
2. **Speed:** real-time factor at 4 threads and 1 thread; also total time on
   the long files.
3. **Memory:** peak RSS (short and long audio).
4. **Robustness:** a handful of noisy clips (add noise at 10 dB and 0 dB SNR
   to 50 test-clean utterances) — WER for each model.
5. **Practical notes:** what Go needs (log-mel parameters, tokenizer /
   vocabulary format, CTC decode, max audio length per graph call, chunking),
   punctuation and casing quality, any ORT op problems.

## Verdict wanted

Replace Moonshine-tiny with Parakeet 110M: yes / no / conditional — with the
numbers, and whether the 0.6B is worth offering as a "large" option.
