# Helium — Project Reference

Stable facts about what Helium is. The hand-off lives in [STATE.md](STATE.md).

## Overview

Local TTS, STT and LLM in Go. No Python. Tiny binary (~8MB). ONNX Runtime, models, voices and espeak-ng auto-download from `cattery-artefacts` on first run (espeak falls back to a system `espeak-ng` on PATH).

```
go install github.com/jikkuatwork/helium/cmd/helium@latest
helium "Hello, world."
```

## Stack

- **Language**: Go (small cgo shim for `malloc_trim` during ORT teardown)
- **Inference**: ONNX Runtime 1.24.1+ via `yalue/onnxruntime_go` v1.27.0 (dlopen)
- **Model**: Kokoro-82M int8 quantized (92MB ONNX)
- **Phonemization**: espeak-ng via `os/exec` (downloaded binary; system fallback)
- **Audio**: WAV (pure Go streaming writer)

## Architecture

```
helium/
├── cmd/
│   ├── helium/       # CLI
│   └── spike/         # Original spike (reference, has timing)
├── tts/               # TTS engine interface + Kokoro implementation
├── stt/               # STT engine interface + Moonshine implementation
├── llm/               # LLM engine interface + Qwen implementation
├── phonemize/         # espeak-ng IPA phonemizer
├── audio/             # Pure Go WAV writer
├── download/          # Auto-download with progress bars and checksum verification
├── server/            # REST API server with lazy engine pool
├── preflight/         # System readiness checks (RAM, deps)
├── registry/          # Model/voice metadata registry
├── paths/             # Data directory resolution (~/.helium/)
├── scripts/           # Helper scripts, benchmarks
└── koder/             # Project tracking
```

## CLI Commands

```
helium "Hello, world."          # TTS with random voice
helium tts --voice bella "Hi"   # pick voice by name
helium tts --female "Hello"     # random female voice
helium tts --speed 1.5 -o out.wav
helium stt recording.wav        # transcribe audio
helium llm "What is the capital of France?"  # local LLM
helium llm --system "You are helpful" "Hi"
helium status                   # platform, models, disk usage
helium download                 # pre-fetch model + all voices
helium serve                    # REST API on :7100
helium serve --port 8080 -w 2   # custom TTS workers
helium serve --stt-workers 2    # custom STT workers
helium serve --auth             # require API keys
helium help --advanced          # full flag/command reference
```

## Downloads (no auth, stable URLs)

| Asset | Source | Size |
|---|---|---|
| TTS model + voices | `jikkuatwork/cattery-artefacts` (Git LFS) | 88MB + 13MB |
| STT model | `jikkuatwork/cattery-artefacts` (Git LFS) | 28MB |
| LLM model (Qwen3.5-4B q4) | `jikkuatwork/cattery-artefacts` (Git LFS) | ~2.91 GiB |
| ORT runtime | `cattery-artefacts` (mirror of MS release) | 18MB |

Registry currently includes 27 voices. Downloaded artefacts (incl. espeak-ng) are cached in `~/.helium/`; nothing is embedded in the binary yet.

## Performance (aarch64 VM, 6-core)

| Metric | Value |
|---|---|
| RTF | 0.70x (faster than real-time) |
| Idle RSS (lazy) | 8 MB (no engine loaded) |
| Idle RSS (post-evict) | ~50 MB (after malloc_trim) |
| Peak RSS (short text) | ~180 MB |
| Peak RSS (long text) | ~360 MB |
| Cold start | ~1.4s (ORT reload + model) |
| Binary | 8.3MB |
| First-run download | ~120MB total |

## Research

- [01_initial.md](research/01_initial.md) — KittenTTS benchmarks, size analysis, library survey, phonemizer options
- [02_model_survey.md](research/02_model_survey.md) — 2026-11 survey of tiny TTS/STT/VAD/LLM/VLM/embedding/utility models vs the one-binary-one-file vision; picks, licenses, disqualifications
