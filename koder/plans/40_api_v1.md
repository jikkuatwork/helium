# Plan 40 — Helium API v1: one contract for every model

Status: draft for review, 2026-11-05 · Implements [ROADMAP](../ROADMAP.md)
design parameters 9–12 · Needs no inference engine

## One capability

**Define one stable contract for running any model on helium (submit, admit
or reject, stream, resume, cancel) and prove it with an engine-independent
job core and a conformance suite run against fake models.**

## Why now

- The owner's priorities put the API first and reliability second. Every
  model built after this is built against it.
- Requests that cannot be served will arrive: too long, too many at once,
  past a deadline. A caller can only run its own queue on top of helium if
  every answer is clear and every submission is safe to repeat.
- None of this needs an inference engine. The job core can be built and
  hardened with fake models while the pure-Go engine spike runs in parallel.

## What exists today (v0.9.1)

- **Five routes:** OpenAI-compatible speech, transcription and chat;
  `GET /v1/models` (OpenAI list, ids only); `GET /v1/status` (pool stats per
  modality).
- **Load shedding:** one shared queue of `QueueMax` slots and a 500-character
  TTS budget. Every rejection is a 503 with a fixed `Retry-After` (2, 3 or
  30 s) and a free-text message in OpenAI's envelope, typed
  `invalid_request_error` with `code: null`, even when the server is just
  busy (`server/server.go:466-497`, `server/pool.go:200`).
- **No job ids, no idempotency.** Nothing survives a disconnect or a restart.
- **Memory:** TTS buffers the whole WAV before replying; STT parses
  multipart with a 32 MiB in-memory threshold; chat "streaming" splits a
  finished reply into deltas (`server/llm.go:202`).
- **Strict decoding:** `handleAudioSpeech` rejects unknown fields
  (`DisallowUnknownFields`), the opposite of the additive rule.

## Principles

1. **One way to do each thing.** One run primitive, one job resource, one
   error shape, one event stream.
2. **Decide early, decide once.** Accept or reject before any work.
   Permanent checks run before transient ones, so a request that can never
   succeed is never told to retry.
3. **If helium said "accepted", it remembers.** A job is acknowledged only
   after its record is on disk, and an event is on disk before any client
   sees it.
4. **Disk, not memory.** Inputs, outputs and events are spooled to disk. A
   queued job costs kilobytes of RAM; a slow reader costs none.
5. **Mechanism here, policy with the caller.** Helium's queue is short and
   FIFO. Priorities, deep queues and retry budgets live in the caller.
6. **Additive forever** once frozen (see *Evolution*).

## Endpoints

| Route | Purpose |
|---|---|
| `POST /v1/run` | Create a job, or a dry run |
| `GET /v1/jobs/{id}` | Status and output; `?wait_ms=` long-polls |
| `GET /v1/jobs/{id}/events` | Event stream; `?after=N` replays |
| `GET /v1/jobs/{id}/output/{n}` | Raw bytes of output part n; `Range` |
| `DELETE /v1/jobs/{id}` | Cancel; idempotent |
| `GET /v1/jobs` | Newest first; `?status=&after=&limit=` |
| `POST /v1/files` | Upload media as the raw body |
| `GET/HEAD/DELETE /v1/files/{id}` | Fetch, check, remove |
| `GET /v1/models` | All models with manifests |
| `GET /v1/models/{id}` | One manifest |
| `POST /v1/models/pull` | Pull a model; it runs as a job |
| `DELETE /v1/models/{id}` | Remove a model's files |
| `GET /v1/load` | Queue, ETA, memory, loaded models |
| `GET /v1/health` | ready, busy or draining; no auth |
| OpenAI paths | Thin adapters over `/v1/run` |

- `GET /v1/models` keeps OpenAI's list shape (`object: list`, `data[].id`)
  and adds helium's manifest fields to each entry. OpenAI clients ignore
  extra fields, so one route serves both.
- `GET /v1/status` stays as a deprecated alias until 1.0.
- Every response carries `X-Request-Id`; a job's id is also in `Location`.

## The run request

```
POST /v1/run
Idempotency-Key: reply-8812
{
  "model": "phonon-31m",
  "input": [{"type": "text", "text": "Hi there"}],
  "output": [{"type": "audio", "format": "wav"}],
  "options": {"voice": "easton", "speed": 1.0},
  "stream": true,
  "deadline_ms": 5000,
  "if_busy": "queue",
  "metadata": {"chat": "c_77"}
}
```

| Field | Default | Meaning |
|---|---|---|
| `model` | by capability | Omitted: default model for input → output |
| `input` | required | List of typed parts |
| `output` | model's default | Wanted parts; `"audio"` = `{"type":"audio"}` |
| `options` | `{}` | Model knobs, checked against the manifest |
| `stream` | false | true: the reply is the event stream |
| `detach` | false | true: 202 at once; the job runs to the end |
| `deadline_ms` | none | Reject if the ETA misses it; stop if run misses it |
| `if_busy` | `queue` | `reject`: answer `busy` unless it can start now |
| `dry_run` | false | Admission answer only; never queues |
| `metadata` | none | Up to 4 KiB, echoed on the job |

- **Three reply modes.** `stream: true` gives `200 text/event-stream`.
  `detach: true` gives `202` with the job. Otherwise helium holds the
  request until the job ends and returns the job as JSON.
- **Dry runs** that parse return `200 {"admit": true|false, "model": …,
  "eta_ms": …, "memory_mib": …, "error": …}`, where `error` is exactly what
  the real request would get. A dry run never queues and never uses a key.
- **Idempotency key** goes in the `Idempotency-Key` header (IETF draft
  standard), or `Run.Key` in Go: up to 255 printable ASCII characters,
  scoped to the auth key (global when auth is off).

## Parts

Every input and every output is a list of typed parts. A new modality is a
new part type, never a new request shape.

| Type | Fields |
|---|---|
| `text` | `text`; streamed as `delta` |
| `audio` | `file` or `data`; `format`, `rate`, `channels`, `duration_ms` |
| `image` | `file` or `data`; `format`, `width`, `height` |
| `video` | `file`; `format`, `fps`, `frames`, `duration_ms` |
| `embedding` | `vector`, `dims` |
| `message` | `role` (system, user, assistant, tool), `content: [parts]` |
| `tool_call` | `id`, `name`, `arguments` (JSON) |
| `tool_result` | `id`, `content: [parts]` |

- A TTS call is one `text` part. A chat is a list of `message` parts. An
  omni model takes messages whose content mixes text, audio and images.
- **Media by reference.** `file` is an id from `/v1/files` or an earlier
  job's output. Inline `data` (base64) is allowed up to `inline_max_bytes`
  (default 256 KiB); beyond that the answer is `too_large` with
  `limit.name: inline_bytes`.
- **File ids are content hashes** (`file_` + 32 hex characters of
  SHA-256). Uploading the same bytes twice returns the same id, and
  `HEAD /v1/files/{id}` lets a caller skip an upload it already made.
  Uploads stream to disk; `max_upload_bytes` defaults to 512 MiB. Files
  follow job retention, counted from their last use.
- **Media formats in v1:** audio as WAV (PCM16 or float32) or raw `pcm16`
  and `f32` with `rate`; images as PNG and JPEG. More decoders are additive
  (see *Deferred*).

## The job

```
{"id": "job_7k2m…", "status": "running", "model": "phonon-31m",
 "key": "reply-8812", "attempt": 1,
 "created_at": "2026-11-05T10:00:00Z",
 "position": 0, "eta_ms": 900,
 "progress": {"done": 2, "total": 5, "unit": "chunk"},
 "output": [{"type": "audio", "file": "file_…", "format": "wav",
             "duration_ms": 1100}],
 "usage": null, "error": null, "warnings": [],
 "last_seq": 4, "metadata": {"chat": "c_77"}}
```

- **Status is a closed set:** `queued`, `running`, `succeeded`, `failed`,
  `cancelled`. The reason for a failure is in `error.code`. Clients switch
  on status, so this set never grows; detail lives in codes.
- **Retention.** A finished job, its events and its output stay for
  `result_ttl` (default 1 h) within a spool quota (default 2 GiB), oldest
  removed first. After that the job is gone and its key is free: helium runs
  each key at most once *within the retention window*.
- **Usage** is measured per job: amounts in each model's units
  (`input_chars`, `input_audio_ms`, `output_tokens`, …), plus `queue_ms`,
  `load_ms`, `run_ms` and `peak_rss_mib`.
- **Auth.** With auth on, a job is visible only to the key that made it;
  other keys get `not_found`.

## Events

Server-Sent Events. Every event has `id: <seq>`. Seq starts at 1, rises by
one, never repeats and continues across attempts.

```
id: 2
event: part
data: {"index": 0, "chunk": 0, "attempt": 1, "type": "audio",
       "format": "pcm16", "rate": 24000, "data": "…"}
```

| Event | Data |
|---|---|
| `queued` | `position`, `eta_ms`; sent again when they change |
| `loading` | `model`, `eta_ms` |
| `started` | `attempt`, `resumed_from` (a chunk index or null) |
| `progress` | `done`, `total`, `unit`, `eta_ms` |
| `part` | One output piece: a text delta, audio chunk, image preview, frames |
| `warning` | `code`, `message`, `field` |
| `done` | `status`, `usage`, `error` |

- **Replay.** `GET /v1/jobs/{id}/events?after=N` (or `Last-Event-ID: N`)
  replays every event after N from disk, then follows live. Replay is
  byte-identical to what was sent.
- **Attempts.** A `started` event for attempt n with `resumed_from: k`
  means parts of chunks before k stand, and earlier attempts' parts from
  chunk k on are void. With `resumed_from: null`, all earlier parts are
  void. Final output files are always consistent.
- **Streamed media is bounded:** at most 64 KiB of data per event. Whole
  media comes raw from `/v1/jobs/{id}/output/{n}`, which streams while the
  job runs and honours `Range`, so a media download resumes too.
- **Keep-alive:** a comment line every 15 s keeps proxies open and detects
  dead clients.
- **Disconnects.** A streaming or waiting client that drops has
  `reconnect_grace` (default 30 s) to reattach; otherwise its job is
  cancelled. `detach: true` jobs are never cancelled this way.
- **Slow readers cost nothing.** Senders read from the on-disk log, so a
  stalled client never holds memory.

## Errors and rejections

One shape for rejections, job failures and `done` events:

```
{"error": {
  "code": "too_large",
  "message": "input is 9100 characters; this model takes at most 4000",
  "retryable": false,
  "limit": {"name": "input_chars", "max": 4000, "got": 9100},
  "field": "input[0].text",
  "request_id": "req_3f9…"}}
```

- **`retryable: true` means the same request may succeed later,
  unchanged.** Then `retry_after_ms` is set, together with the
  `Retry-After` header in seconds, computed from the measured ETA rather
  than a constant.
- `message` is for people. Programs read `code`, `retryable`, `limit` and
  `field`.

Rejections (no job is created):

| Code | HTTP | Retry | When |
|---|---|---|---|
| `invalid` | 400 | no | Malformed JSON or a bad value; `field` set |
| `unauthorized` | 401 | no | Missing or bad auth key |
| `not_found` | 404 | no | Unknown model, job or file |
| `key_conflict` | 409 | no | Same key, different request |
| `model_missing` | 409 | no | Model known but not pulled |
| `too_large` | 413 | no | Past a model limit, an upload limit or the ceiling |
| `unsupported` | 422 | no | Modality, format or option the model lacks |
| `bad_media` | 422 | no | Input media cannot be decoded |
| `too_slow` | 422 | no | Even idle, the run would miss `deadline_ms` |
| `rate_limited` | 429 | yes | Per-key rate limit |
| `queue_full` | 503 | yes | Helium's queue is full |
| `busy` | 503 | yes | `if_busy: reject` and no free slot now |
| `deadline` | 503 | yes | Waiting in the queue would miss `deadline_ms` |
| `shutting_down` | 503 | yes | Helium is draining |
| `storage_full` | 507 | yes | Spool quota or disk is full |
| `internal` | 500 | no | A bug; `request_id` finds it in the log |

Job failures (in `job.error` and the `done` event):

| Code | Retry | When |
|---|---|---|
| `timeout` | no | The run passed `deadline_ms` or its run-time cap |
| `interrupted` | yes | A crash cut the run and it could not resume |
| `too_large` | no | RSS passed the ceiling despite the estimate |
| `bad_media` | no | Media failed to decode partway through |
| `internal` | no | A bug, including a recovered panic |

### Admission order

Permanent checks come first, so a hopeless request never hears "retry".

1. Parse and authenticate: `invalid`, `unauthorized`.
2. Idempotency: an existing job with this key is returned as it is; a
   different request under the same key gets `key_conflict`.
3. Resolve the model: `not_found`, `model_missing`, `unsupported`.
4. Static limits, media headers and the memory ceiling: `too_large`,
   `bad_media`.
5. Rate limit: `rate_limited`.
6. Draining and disk: `shutting_down`, `storage_full`.
7. Deadline against an idle run: `too_slow`.
8. Capacity: `busy` (with `if_busy: reject`), `queue_full`, or `deadline`
   when the queue wait would miss it.
9. Write the job record, fsync, then accept.

### Keys across failures

- **A rejection does not use the key.** No job is created, so resending
  the same request with the same key is simply a new submission.
- **Same key while queued, running or succeeded:** returns that job.
- **Same key after a retryable failure or a cancel:** starts the next
  attempt on the same job id, skipping finished chunks.
- **Same key after a non-retryable failure:** returns that failure. The
  caller must change the request and use a new key.

### The caller's loop

The whole retry contract. An SDK wraps exactly this.

```
key = a stable id for this unit of work
loop:
  r = POST /v1/run with Idempotency-Key: key
  if accepted:
    follow events; on a dropped connection, GET events?after=<last seq>
    if done.error is retryable: wait, then loop
    else: finished (succeeded, or failed for good)
  elif r.error.retryable:            wait retry_after_ms, then loop
  elif r.error.code == "too_large":  split by r.error.limit, new keys
  else:                              fix the request or give up
```

A new error code never breaks a caller, because `retryable` alone decides
what to do with a code it has not seen.

## Load and health

```
GET /v1/load
{"state": "busy", "ceiling_mib": 250, "rss_mib": 171, "headroom_mib": 79,
 "queue": {"depth": 2, "max": 4, "eta_ms": 8200},
 "running": [{"job": "job_…", "model": "moonshine-tiny", "eta_ms": 1200}],
 "loaded": [{"model": "moonshine-tiny", "rss_mib": 88, "idle_ms": 0}]}
```

- `GET /v1/load?wait=slot&timeout_ms=30000` returns as soon as a job could
  start at once, or at the timeout, so a caller's queue sleeps instead of
  polling.
- `GET /v1/health` returns `200 {"state": "ready"}` or `"busy"`, and
  `503 {"state": "draining"}`.

## Model manifest

Each model describes itself. The same manifest drives validation,
admission and ETA.

```
{"id": "phonon-31m", "object": "model", "owned_by": "helium",
 "family": "phonon", "version": "1.0.0", "state": "loaded",
 "capabilities": [{"input": ["text"], "output": ["audio"]}],
 "limits": {"input_chars": 20000, "output_audio_ms": 1800000},
 "options": {"voice": {"type": "string", "enum": ["easton", "…"]},
             "speed": {"type": "number", "minimum": 0.5, "maximum": 2,
                       "default": 1}},
 "memory": {"resident_mib": 64, "per_unit_mib": 0.05,
            "unit": "phoneme"},
 "speed": {"unit": "char", "per_s": 210, "measured": true},
 "chunking": {"unit": "sentence", "resumable": true},
 "license": {"spdx": "Apache-2.0", "notes": null},
 "size_bytes": 33554432}
```

- `memory` and `chunking` let admission work out a job's need and refuse up
  front.
- `speed` starts from the manifest's reference value and is replaced by
  measurement on this host, kept across restarts.
- `options` uses a small JSON Schema subset (type, enum, minimum, maximum,
  default): enough to validate knobs and to generate a form.

## Admission and memory

- **Reservations.** Each job reserves its model's resident size (if not
  loaded) plus the working set for its chunk size. Reservations never sum
  past the ceiling; idle models are evicted to make room before a job waits.
- **Chunk plans.** Chunk sizes are chosen at admission from the model's
  limit, the memory headroom and a latency target (a small first chunk).
  The plan is written to the journal, so a resumed job splits the same way
  even if headroom has changed.
- **Guard.** Go's soft memory limit (`GOMEMLIMIT`) sits below the ceiling,
  and RSS is sampled at every chunk boundary. A job that pushes RSS past
  the ceiling despite its estimate fails with `too_large`
  (`limit.name: memory_mib`); the bad estimate is logged as a bug.
- **Defaults** on the reference machine: one running job, a queue of 4.

## Durability and resume

- **Journal.** One directory per job under the data dir: `job.json`
  (request, chunk plan, status; written by temp file and rename),
  `events.log` (append-only), `out/` (output files) and `chunks/` (one
  marker per finished chunk). No database.
- **Fsync points.** On accept, before the reply. Events are
  group-committed at least every 20 ms, before they are sent, so nothing a
  client has seen can be lost. On every finished chunk and at the end. The
  cost is measured on the reference machine in Phase E.
- **Recovery on start.** Queued jobs return to the queue in order. A
  running job on a resumable model re-queues as the next attempt from its
  last finished chunk. Any other running job fails with `interrupted`,
  which is retryable. Expired jobs are deleted. A torn last line in
  `events.log` is cut off.
- **Drain on SIGTERM.** Stop admitting (`shutting_down`); let the running
  job finish its current chunk and checkpoint; leave queued jobs in the
  journal for the next start; exit within `drain_timeout` (default 30 s).
- **Watchdog.** Each job's run-time cap is three times its estimate, or its
  deadline if that is sooner; passing it fails the job with `timeout`.
- **Isolation.** A panic inside a job is recovered, the job fails with
  `internal`, and that engine instance is discarded and reloaded.
- **Cancel** stops a running job at its next chunk or token boundary.

## Go API

One `api` package serves the daemon, the embedded runtime and the client.

```go
rt, err := jobs.Open(jobs.Config{DataDir: dir, CeilingMiB: 250})
job, err := rt.Run(ctx, api.Run{Key: "reply-8812", Model: "phonon-31m",
    Input: []api.Part{api.Text("Hi there")}})
var e *api.Error
if errors.As(err, &e) && e.Retryable {
    time.Sleep(e.RetryAfter)
}
for ev, err := range rt.Events(ctx, job.ID, 0) { … }
```

- **One interface, two implementations.** `api.Runner` (Run, Job, Events,
  Cancel, Load, Models) is implemented in-process by `jobs` and over HTTP
  by `client`. Switching between embedded and daemon is one line.
- **The Go client is the first SDK** and comes nearly free. Other languages
  wait for demand; their OpenAPI document would then be generated from the
  `api` package, not written by hand.

## Evolution

`v1-draft` until the first pure-Go model ships on it; frozen after that.

- **Allowed:** new optional request fields (absent means the old
  behaviour), new response fields, part types, event types, error codes,
  endpoints and manifest fields.
- **Never:** remove or rename a field; change a type, meaning or default;
  change a code's HTTP status or `retryable` meaning; add a job status.
- **Clients must** ignore unknown fields, events and parts, and handle
  unknown error codes by `retryable` alone.
- **Helium** ignores unknown request fields and options and lists each in
  `warnings` (`code: unknown_field`), so typos show up without breaking
  newer clients.
- **Conventions:** units in field names (`_ms`, `_bytes`, `_mib`);
  snake_case JSON; prefixed ids (`job_`, `file_`, `req_`); times in RFC 3339
  UTC.
- A breaking change would need `/v2/`; the aim is never to need it.

## OpenAI-compatible adapters

- Speech, transcription and chat keep their request and response shapes
  and become thin translations into `/v1/run`, sharing admission, the
  ceiling, the journal and the codes.
- Their errors keep OpenAI's envelope, with helium's code in `code` and
  `retryable` and `retry_after_ms` as extra fields. `Idempotency-Key` works
  on them too.
- They are rewired when the first v1 engine lands (see *Deferred*); until
  then they run as today.

## Phases

No phase needs an inference engine, ONNX Runtime or a model download, so
B–E can run in parallel with the pure-Go engine spike.

- **A. Review.** Owner review, plus an optional second opinion from a GPT
  worker on the owner's go. Exit: `CONVERGED` in
  `koder/reviews/040_api_v1/`.
- **B. `api/` package.** Wire types (Run, Part, Job, Event, Error, Model,
  Load), the code table (code → HTTP status, retryable), validation,
  golden JSON fixtures and the `Runner` interface. Standard library only.
  `docs/api.md` is written from this plan.
- **C. `jobs/` core.** Admission in the order above, FIFO queue,
  idempotency, memory reservations, event log with group commit and
  replay, spool and quota, journal and recovery, chunk plans and resume,
  cancel, reconnect grace, watchdog, drain, and ETA from measured speed.
  Fake models in `jobs/fake`: TTS, STT and LLM stand-ins that emit chunks
  with set delays and declared memory, and can be told to panic, stall,
  overrun memory or fail to decode.
- **D. HTTP surface.** v1 routes on the existing server mux, with fake
  models visible only under `HELIUM_FAKE_MODELS=1`; old routes unchanged.
  `client/` is the HTTP `Runner`.
- **E. Conformance, chaos and overload.** `conformance/` runs the same
  black-box tests against both `Runner`s, locally and on the reference
  machine (`hvm-do6` booted as 1 vCPU / 959 MiB).

## Acceptance criteria

- [ ] Every rejection and failure code is produced by at least one
      conformance test with its documented HTTP status, `retryable` and
      `retry_after_ms`.
- [ ] Permanent before transient: a request that is invalid and arrives
      during overload gets `invalid`, not `queue_full`.
- [ ] Idempotency: 100 concurrent submissions with one key create one job;
      a different body under that key gets `key_conflict`; resending a key
      whose job failed retryably starts attempt 2 on the same job id.
- [ ] Replay: from random reconnect points, `events?after=N` returns
      events N+1 onward byte-identical to the live stream, with no gaps or
      repeats in seq.
- [ ] Media resume: downloading `/output/{n}` with `Range` while the job
      runs yields a byte-identical final file.
- [ ] Crash: `kill -9` at 200 random points during fake TTS and STT jobs.
      After each restart, every acknowledged job finishes or fails
      `interrupted`, none is lost, and no finished chunk runs twice.
- [ ] Overload: 200 concurrent requests on the reference machine with a
      queue of 4. Every response is an accepted job or a typed rejection;
      no 500, no hang, no OOM; `retry_after_ms` within 2x of the real wait.
- [ ] Drain: SIGTERM mid-job turns new requests away with
      `shutting_down`, exits within `drain_timeout`, and the queued jobs
      run after restart.
- [ ] Cancel takes effect within one chunk of a running fake job.
- [ ] The core is small: idle daemon RSS ≤ 20 MiB; ≤ 64 KiB of RSS per
      queued job; 1,000 retained finished jobs add ≤ 2 MiB.
- [ ] A client reading events at 1 byte/s through a long job does not
      raise RSS.
- [ ] Forward compatibility: requests with unknown fields and options
      succeed with `unknown_field` warnings; a client built on the fixtures
      ignores an injected unknown event type and part type.
- [ ] Fuzzing: the request decoder and the journal reader each survive
      10 minutes of `go test -fuzz`.
- [ ] Builds with `CGO_ENABLED=0`; `api/`, `jobs/` and `client/` import
      only the standard library.
- [ ] Soak: 4 hours of mixed fake jobs with random disconnects and cancels
      on the reference machine; RSS flat, spool within quota, no failures
      other than injected ones.

## Structural decisions

| Decision | Choice | Why |
|---|---|---|
| Run primitive | `POST /v1/run` | Reads as "run this model"; jobs are the resource |
| Idempotency | `Idempotency-Key` header | IETF draft; works on adapters, uploads |
| Streaming | SSE | Standard; `Last-Event-ID` resume; no deps |
| State | Files per job | Pure Go; crash-safe with rename and fsync |
| Media ids | Content hash | Free dedup; callers skip repeat uploads |
| Missing model | `model_missing` | No surprise downloads mid-request |
| Unknown fields | Ignore with a warning | Additive, yet typos are visible |
| Job status | Closed set | Clients switch on it; codes carry detail |
| Retry signal | `retryable`, `retry_after_ms` | Unknown codes stay safe |
| Queue | Short FIFO | The caller owns policy |

## File change list

New:
- `api/`: types, codes, validation, `Runner`, fixtures
- `jobs/`: admission, queue, journal, spool, events, recovery
- `jobs/fake/`: fake models
- `client/`: the HTTP `Runner`
- `conformance/`: black-box suite for both `Runner`s
- `server/v1.go` and tests: v1 routes on the existing mux
- `docs/api.md`: the reference, written from this plan in Phase B

Changed:
- `server/server.go`: register v1 routes; `/v1/models` gains manifest fields
- `cmd/helium`: `serve` flags `--ceiling`, `--queue`, `--result-ttl`,
  `--spool-quota`
- `koder/ROADMAP.md`, `koder/DECISIONS.md`: record the converged contract

Unchanged: every engine package, `ort/` and today's OpenAI routes.

## Deferred

- Real models on v1; they arrive with the engine spike (plan 41)
- Rewiring the OpenAI adapters onto jobs
- Building model pull and delete as jobs (specified here; built with the
  model-file format)
- Input decoders beyond WAV, raw PCM, PNG and JPEG (OGG/Opus, MP3, FLAC)
- Output encoders beyond WAV and raw PCM
- Priorities, fairness between keys, several queues
- Webhooks: outbound calls clash with the network rule; long-polls cover it
- NDJSON and WebSocket transports
- LLM resume mid-generation (re-prefill the prompt and emitted tokens)
- Non-Go SDKs and the generated OpenAPI document
- A metrics endpoint (Prometheus text format)
- Auth changes: today's opt-in Bearer keys and rate limits apply as they are
- GPU, and more than one running job per model

## Open questions for the owner

1. **Defaults:** result retention 1 h, spool quota 2 GiB, queue of 4,
   reconnect grace 30 s, inline media 256 KiB. Good starting points?
2. **Sequencing:** build phases B–E now, in parallel with the engine
   spike, or after it?
3. **Auto-pull:** Ollama pulls a missing model on first use. Proposed here:
   never inside a run; `model_missing` tells the caller to pull first.

## Thin-layer checklist

- [x] One capability in a sentence
- [x] Deferral list longer than the in-scope list
- [x] Testable before dependencies: fake models, no engine
- [x] Structural decisions explicit
- [x] Acceptance criteria concrete
- [x] File change list present
