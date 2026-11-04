# Bake-off: TTS — Phonon 31m-en vs Kokoro-82M

Area name: `tts`. Your cores: `taskset -c 0-7` (use 4 threads inside that).

## Question

Should helium replace Kokoro-82M (int8 ONNX, needs the espeak-ng
phonemizer) with **Phonon 31m-en** (Gradium, Apache-2.0, no phonemizer,
released 2026-10-20)? Phonon's quality claims are vendor-only and its ONNX
export is community-made, so we need our own numbers.

## Candidates

- **Kokoro-82M int8** — helium's current TTS: `/tmp/helium tts --voice bella
  -o out.wav "text"` (first run downloads the model, voices and espeak-ng).
  For a fair speed comparison also time Kokoro's ONNX through Python ORT if
  practical (the model lives under `~/.helium/artefacts/models/`).
- **Phonon 31m-en** — `https://huggingface.co/onnx-community/phonon-31m-en-ONNX`
  (two graphs: flow LM with past→present state, and the Mimi decoder; int8
  and fp32). Reference implementation: `https://github.com/gradium-ai/xn-ptts`
  and the HF model card `https://huggingface.co/gradium/phonon-31m-en`
  (SentencePiece Unigram tokenizer, 1-step flow head, Gaussian noise temp
  0.3, end-of-speech threshold, 24 kHz). Use the card's / repo's text
  normalization if it has a Python one; otherwise feed already-normalized
  text and say so.

## Measure

1. **Correctness of the ONNX path:** Phonon int8 vs fp32 ONNX on the same
   input and seed: SNR of the waveforms (or a spectral distance) — does int8
   hold up?
2. **Speed:** real-time factor (audio seconds / wall seconds; higher is
   better) and time-to-first-audio, at 4 threads and 1 thread, for: a short
   sentence (~10 words), a paragraph (~80 words), and ~300 words.
3. **Memory:** peak RSS for each.
4. **Intelligibility:** TTS → STT round trip. Synthesize a fixed set of ≥ 40
   sentences (mix: plain prose, numbers/dates/currency, names, acronyms,
   a few long sentences) with each model, transcribe with a strong STT
   (e.g. Whisper small or Parakeet via Python, CPU is fine), and report WER
   per model and per category.
5. **Samples to listen to:** 6 sentences × each model (2–3 voices each) into
   `~/bakeoff-samples/tts/`.
6. **Practical notes:** what the Go side would need (tokenizer, normalizer
   gaps vs helium's existing `normalize/` package, streaming), and any ORT
   op/export problems.

## Verdict wanted

Replace Kokoro with Phonon 31m-en: yes / no / conditional — with the numbers.
If Phonon is clearly better, also say whether Pocket TTS 7m/18m (Kyutai,
CC-BY-4.0) is still needed as a lower-end option, based on Phonon's speed at
1 thread.
