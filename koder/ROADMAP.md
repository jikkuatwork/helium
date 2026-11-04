# Helium — Roadmap

Direction and open questions. The next concrete steps live in [STATE.md](STATE.md).

## Vision (owner, 2026-11-04)

Standalone Go runtime for tiny models — TTS, STT, LLM, VLM and other useful
types. Goals:
- **Exactly one binary + one model file** per model (today: binary + ORT .so +
  many model/voice/tokenizer files + espeak-ng binary/data).
- CPU-first on any machine; use a GPU when present (ORT execution providers).
- Importable Go module for larger projects (first consumer: Go assistant bot).

## Model survey and architecture gaps (2026-11-04)

- **Model survey done** → [research/02_model_survey.md](research/02_model_survey.md).
  Candidate picks (unverified on our hardware):
  - TTS: **Phonon 31m-en** (Apache, no phonemizer → drops espeak-ng); Pocket TTS 7m/18m low-end
  - STT: **Parakeet TDT-CTC 110M** (CC-BY, ~40% fewer errors than Moonshine-tiny); Parakeet 0.6B large tier
  - LLM: **Qwen3.5-4B vs LFM3-1.7B** (contest); **LFM2.5-1.2B** for Pi-class
  - VLM: Qwen3.5 vision encoder vs LFM3-VL-2B; LFM2.5-VL-450M Pi-class
  - New: Silero VAD v6.2, Granite-97M / EmbeddingGemma 2 embeddings, GTCRN denoise, PP-OCRv6
- **License policy decided** (see Key Decisions): revenue caps like LFM's $10M are OK.
- **Architecture gaps identified** (not yet filed as issues):
  1. Single-file model bundle (manifest + aligned blobs, mmap) — needed by nearly every pick (multi-graph). Spike: >2GB external weights from inside one file (onnxruntime_go lacks the in-memory external-initializer API; fallback = extract to cache).
  2. ORT embedded in release binaries (`go:embed` per platform, extract by hash, dlopen); slim build for `go install`/library.
  3. espeak-ng removal — likely solved by switching to Phonon (else espeak→WASM via wazero inside the bundle).
  4. Library API: no `ort` lifecycle for importers; inconsistent constructors (`kokoro.New(path, dataDir)`, `moonshine.New(dir, meta)`, `qwen.New(dir, *registry.Model)`); no `context.Context` on TTS/STT; no LLM token streaming/chat/image input; spike cmds + plumbing pkgs not `internal/`.
  5. Linux-only build: `ort/ort.go` uses glibc `malloc_trim` + `x/sys/unix` with no build tags (absorbs #05).
  6. GPU: all 5 session-creation sites pass nil options; onnxruntime_go v1.27 already wraps CUDA/CoreML/DirectML/OpenVINO. Add one session choke point first.
- **Shared Go building blocks** that unlock most picks: SentencePiece tokenizer, log-mel/STFT, generic `past_*`→`present_*` stateful decode loop.

## Open decisions

- How to proceed: owner wants to rethink sequencing. Proposed: bake-off on this VM (Phonon vs Kokoro, Parakeet 110M vs Moonshine-tiny, Qwen3.5-4B vs LFM3-1.7B) → bundle format → ORT embed → library API → new model types → GPU.
- English-only TTS default OK? (multilingual = Pocket TTS 100M, desktop-only)
- Low-end reference: Pi 4 for TTS/STT/VAD; Pi 5 for LLM (A72 lacks dotprod → slow q4 prefill)?
- Bundle container: custom aligned format (GGUF-like) vs store-only zip.
- Fate of #12 (LLM proxy) and #23 (remote engines) — off-mission for a standalone runtime; propose drop.

## Open items

- **#12 LLM proxy** — unified AI backend (`helium think`); may merge with #13's server endpoint
- **#07** License compliance follow-through (now includes Qwen3.5 Apache-2.0)
- **#33** Enable GH Actions PR permission (one-time repo setting, P3)
- **#36** Serve `--memory` semantics — decide if co-residency hint is the right abstraction (P3)
- **LLM `<think>` tag stripping** — Qwen3.5 emits `<think>…</think>` reasoning tokens; currently shown raw in CLI and API output
- ~~**#34** Trim espeak-ng-data to English-only~~ — dropped; keeping all 117 languages
- ~~**#23 OpenAI remote engines**~~ — deferred (pure local focus)
- **Tracker drift**: 15 issue files still say `Status: open` though done here (01–04, 08–10, 16–20, 24, 25); `download/download.go:5` comment still says ORT comes from Microsoft; Key Decisions "Remote models are just models" / "Dual-mode operation" describe deferred #23

