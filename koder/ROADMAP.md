# Helium — Roadmap

Direction and open questions. The next concrete steps live in [STATE.md](STATE.md).

## Design parameters (owner, 2026-11-05)

These replace the 2026-11-04 vision. New work is judged against them.
Evidence: [research/04_small_vps.md](research/04_small_vps.md).

**Vision: an elegant monolith.** One pure-Go binary that runs practically
any model type on low-spec machines: LLM, TTS, STT, text-to-image,
image-to-video, omni models, and anything in between, all inside a hard
250 MiB memory ceiling and behind one API.

**Why: skate to where the puck will be.** Model memory needs fall every
year. Helium fixes the ceiling and the API now. Each model type joins as
soon as a good-enough model fits, with no change to the API.

**Priorities, in order, when they conflict:** a clear and stable API,
reliability, the lowest memory and compute, then speed. Speed improves
release by release behind the same API. SDKs come later, as thin clients
of the HTTP contract.

### The parameters

1. **One binary + one model file per model.**
2. **Reference machine: a ~1 GB VPS.** One shared x86-64 vCPU (AVX2,
   Broadwell-class), ~960 MiB RAM, no swap, ~25 GB disk: DigitalOcean's $6
   Basic droplet. `bakeoff/vps/` reproduces it on Azure. "Effortless" means
   default settings work there, with no swapfile and no tuning. Pi 4 is
   dropped for now; linux/arm64 stays a build target.
3. **Hard 250 MiB RSS ceiling, for every model type.** This is absolute, not
   a target: the whole helium process never exceeds it. Helium stays under
   it by chunking, tiling and streaming, and refuses up front any job it
   cannot fit, instead of attempting it. A model is supported once its
   working set fits; until then it waits for a smaller model. The ceiling
   may be configured lower, never higher. Weights are memory-mapped, and
   idle RSS returns near zero after eviction.
4. **No cgo.** `CGO_ENABLED=0`, one static binary that cross-compiles
   anywhere and can be imported by cgo-free Go programs. Inference runs in
   pure Go; Go assembly for SIMD kernels is allowed, since it is not cgo.
5. **Nothing downloaded except model files.** No shared libraries, no helper
   binaries, no system packages: ONNX Runtime and espeak-ng leave. Model
   files come only from `cattery-artefacts` or its mirrors. Go modules
   compiled into the binary are not runtime dependencies; keep them few.
6. **One engine core, shared by every model.** A small set of reusable
   blocks: quantized matmul and convolution, attention with a KV cache,
   recurrent cells, FFT/STFT, and two generation loops (autoregressive
   tokens; diffusion/flow steps). A model family is wiring of those blocks,
   not a new engine. It is not a general ONNX runtime.
7. **Adaptive chunking, tiling and streaming are shared layers.** Each
   model's manifest declares its hard input limit and its memory cost per
   unit. The scheduler sizes every piece as the smallest of that limit, the
   memory ceiling and a latency target: small first pieces for fast first
   output, larger after. Text splits at sentence, clause, then word
   boundaries. Audio splits at silences with overlap and stitching. Images
   split into tiles, video into frame windows. Kokoro ignoring chunk size
   today is what kills it on 1 GB.
8. **Input and output stages are configurable per model.** Input stages
   make data model-ready: text normalization (numbers, dates, currency into
   words), tokenizers (SentencePiece, BPE), G2P, audio features (log-mel),
   image preprocessing. Output stages turn model output back into media:
   detokenizers, vocoders and ISTFT, image and video decoders. Each stage
   is a named, versioned component the model's manifest selects; its data
   (lexicons, tokenizer files) lives inside the model file. A new model is
   a manifest, plus at most one new stage.
9. **One extensible API for every model type.**
   - **Models describe themselves:** capabilities as input → output
     modalities (text → audio, audio → text, text + image → text,
     text → image, image → video, any → any for omni), limits, an options
     schema, memory need and license. Callers choose by capability, not by
     name.
   - **Inputs and outputs are lists of typed parts:** text, audio, image,
     video, tool call, embedding. A new modality is a new part type, never
     a new request shape.
   - **One run primitive; every request is a job** with the same lifecycle:
     queued, running, streaming parts, then done, failed or cancelled.
     Output streams as typed events for every modality: text tokens, audio
     chunks, image previews, video frames. Long jobs can be detached and
     polled.
   - **Large media goes by reference:** upload once, refer by id. Nothing
     big travels inline in JSON.
   - **Familiar endpoints are thin adapters** over the same core: the
     OpenAI-compatible speech, transcription, chat, image and embedding
     paths.
   - **Evolution is additive only.** New fields are optional; unknown
     fields are ignored; model-specific knobs live only in `options`,
     validated against the manifest. A versioned path exists for a breaking
     change; the aim is never to need it.
10. **Works like Ollama.** `helium serve` is the primary interface: a program
    connects to a local port. Model management is part of the API: list,
    pull with progress, show, delete, and list loaded models with their
    memory. Importing helium as a Go package stays possible but is
    secondary.
11. **Admission, rejection and resumability: helium provides the
    mechanism, the caller sets policy.** Requests that cannot be served will
    arrive: too long, too many at once, or unable to finish by a deadline.
    Helium keeps its own queue short and answers clearly, so the calling
    program (over HTTP, or a Go program importing helium) can run the deep
    queue, retries and priorities itself.
    - **Decide at submit time.** Every request is either accepted with a job
      id or rejected before any work starts. Admission checks model limits,
      the memory ceiling, queue space, rate limits, and whether the
      estimated finish meets the job's deadline.
    - **Rejections are typed and actionable.** A stable `code` (`too_large`,
      `queue_full`, `deadline`, `rate_limited`, `shutting_down`, `invalid`,
      `unsupported`, …), a `retryable` flag, `retry_after_ms` when it is
      retryable, and the limit that was hit with its maximum, so a caller
      can split the input and resubmit. The HTTP status mirrors the code
      (400, 413, 429, 503 with `Retry-After`); the body is the contract. Go
      importers get the same codes as a typed error.
    - **Ask before sending.** Model manifests publish their static limits,
      so callers can split input without a round trip. A dry run returns
      the admission answer, ETA and memory estimate without queuing. A load
      endpoint reports queue depth, ETA and headroom against the ceiling.
    - **Submission is idempotent.** A caller-chosen key makes a retry after
      a timeout or a dropped connection return the existing job, never
      start a second one.
    - **Jobs outlive connections.** Status, event stream and cancel are
      addressed by job id. Every event carries a sequence number;
      reconnecting with the last one seen replays the rest. Output is
      spooled to disk, not held in memory, and kept for a bounded time. An
      attached job waits a short reconnect window before it is cancelled; a
      detached job runs to the end.
    - **Work resumes at chunk boundaries.** Chunked jobs record each
      finished chunk. After an interruption, a retry with the same key
      skips finished chunks: a 20-minute transcript resumes rather than
      restarting. The API does not change for this; the retry just
      finishes sooner.
12. **Reliability: helium never falls over.**
    - **The kernel never kills it.** Memory is accounted for and admitted
      against the ceiling up front, never discovered by the OOM killer.
    - **Everything is bounded:** queue length, input and upload size, run
      time per job (a watchdog), spool disk and result lifetime.
    - **Crash-only.** Killing helium at any moment is safe. A small on-disk
      journal brings back finished results and queued jobs on restart. A
      job that was running resumes from its last finished chunk, or is
      reported `interrupted` and retryable.
    - **A bad request fails its own job, never the process.** Inputs are
      validated at admission, decoders and parsers are fuzzed, and a panic
      inside a job is contained to that job.
    - **Clean drain.** On SIGTERM helium stops admitting (`shutting_down`,
      retryable), finishes or checkpoints the running job, then exits.
      Health reports ready, busy or draining.
    - **Proven on the reference machine.** A release passes a long soak of
      mixed jobs (no OOM, RSS under the ceiling throughout), a kill and
      restart in the middle of a job, and an overload test in which every
      excess request gets a typed rejection.

Illustrative shape only; the draft spec is
[plans/40_api_v1.md](plans/40_api_v1.md):

```
POST /v1/run
Idempotency-Key: reply-8812
{"model": "phonon-31m",
 "input": [{"type": "text", "text": "Hi there"}],
 "output": ["audio"], "options": {"voice": "easton"},
 "stream": true, "deadline_ms": 5000}

→ event: queued  {"job": "j_42", "seq": 1, "position": 0, "eta_ms": 900}
→ event: part    {"seq": 2, "type": "audio", "format": "pcm16", "rate": 24000, ...}
→ event: done    {"seq": 3, "usage": {"audio_ms": 1100, "peak_rss_mib": 142}}

GET /v1/jobs/j_42/events?after=2        (reconnect: replays from seq 3)

← 413 {"error": {"code": "too_large", "retryable": false,
         "limit": {"name": "input_chars", "max": 4000, "got": 9100}}}
← 503 Retry-After: 12
      {"error": {"code": "queue_full", "retryable": true, "retry_after_ms": 12000}}
```

### Decided and proposed

- **LLMs live under the same ceiling (decided 2026-11-05).** An LLM keeps all
  its weights resident while it generates, so today that means about 300M
  parameters at 4-bit (~150–200 MB of weights): good for short replies,
  intent and tool calls, weaker at open chat. Larger LLMs join as smaller
  ones get good. Needs a survey of that size class; the 2026-11-04 survey
  stops at 0.8B.
- **Proposed, to confirm — speed on the reference machine:** STT at least
  5x realtime; TTS at least 1x realtime (2x preferred) with first audio
  within 1.5 s. Kokoro measured 0.33x there and fails; Phonon measured
  3.2x and passes.
- **To prove — streaming weights from disk.** Paging a model's layers in
  from the memory-mapped file and releasing them after use could run
  models whose weights exceed the ceiling, at a speed cost. Unproven; a
  spike decides whether it is worth it.

### What the parameters change

- **Today's binary meets none of 3–5:** it peaks at 525–720 MiB on the
  reference machine, uses cgo, and loads ONNX Runtime and espeak-ng.
- **The largest piece of work is the pure-Go engine core** (parameter 6).
  Prove it first on the smallest model (Moonshine-tiny, 27M) against ONNX
  Runtime's speed on the reference machine.
- **What fits today:** speech models of roughly 100M parameters or fewer
  at int8, and LLMs around 300M at 4-bit. Phonon 31M needs no phonemizer,
  so it fits parameters 5 and 8 better than Kokoro, which needs espeak-ng.
  Moonshine-tiny fits the ceiling better than Parakeet 110M. Most current
  image and video generators exceed 250 MiB; they join as smaller ones
  appear.
- **Today's server already sheds load,** but crudely: a bounded queue
  returns 503 with a fixed `Retry-After` (2 or 30 s) and a free-text
  message. Typed codes, estimates, idempotency keys, job ids, replayable
  events and the journal (parameters 11–12) are all new.
- **GPU is deferred:** the ONNX Runtime execution-provider path needed cgo.

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
  2. ~~ORT embedded in release binaries~~ — superseded 2026-11-05 by no cgo and a pure-Go inference core.
  3. espeak-ng removal — now required (design parameter 5); likely solved by switching to Phonon, else a pure-Go G2P with lexicon data in the model file.
  4. Library API: no `ort` lifecycle for importers; inconsistent constructors (`kokoro.New(path, dataDir)`, `moonshine.New(dir, meta)`, `qwen.New(dir, *registry.Model)`); no `context.Context` on TTS/STT; no LLM token streaming/chat/image input; spike cmds + plumbing pkgs not `internal/`.
  5. Linux-only build: `ort/ort.go` uses glibc `malloc_trim` + `x/sys/unix` with no build tags (absorbs #05).
  6. ~~GPU via ORT execution providers~~ — deferred 2026-11-05; that path needs cgo.
- **Shared Go building blocks** that unlock most picks: SentencePiece tokenizer, log-mel/STFT, generic `past_*`→`present_*` stateful decode loop.

## Open decisions

- Sequencing under the 2026-11-05 parameters. Bake-off done (plan 39). Proposed: API spec plan → pure-Go engine spike on Moonshine-tiny → shared chunking and stage layers → Phonon in pure Go → model-file format → daemon on the new API → tiny-LLM survey and first LLM → more model types as they fit.
- English-only TTS default OK? (multilingual = Pocket TTS 100M, desktop-only)
- ~~Low-end reference: Pi 4 for TTS/STT/VAD?~~ — decided 2026-11-05: a ~1 GB VPS; Pi 4 dropped for now.
- Bundle container: custom aligned format (GGUF-like) vs store-only zip. Must support mmap (parameter 3).
- Design parameters, remaining assumptions: a pure-Go core rather than cgo-free loading of ONNX Runtime (parameter 5 rules out shipping a native library); the Go package API stays supported but secondary.
- API spec: drafted 2026-11-05 as [plan 40](plans/40_api_v1.md) (parameters 9–12: run primitive, parts, jobs and events, manifest, rejection codes, idempotency, replay, journal, Go `Runner`); in review. Its job core needs no engine, so it can be built in parallel with the engine spike (owner's call).
- Fate of #12 (LLM proxy) and #23 (remote engines) — off-mission for a local-inference runtime; propose drop.

## Open items

- **#12 LLM proxy** — unified AI backend (`helium think`); may merge with #13's server endpoint
- **#07** License compliance follow-through (now includes Qwen3.5 Apache-2.0)
- **#33** Enable GH Actions PR permission (one-time repo setting, P3)
- **#36** Serve `--memory` semantics — decide if co-residency hint is the right abstraction (P3)
- **LLM `<think>` tag stripping** — Qwen3.5 emits `<think>…</think>` reasoning tokens; currently shown raw in CLI and API output
- ~~**#34** Trim espeak-ng-data to English-only~~ — dropped; keeping all 117 languages
- ~~**#23 OpenAI remote engines**~~ — deferred (pure local focus)
- **Tracker drift**: 15 issue files still say `Status: open` though done here (01–04, 08–10, 16–20, 24, 25); `download/download.go:5` comment still says ORT comes from Microsoft; Key Decisions "Remote models are just models" / "Dual-mode operation" describe deferred #23

