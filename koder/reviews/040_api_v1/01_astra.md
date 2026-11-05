# Plan Review — 40 API v1 (astra)

Reviewer: GPT-6 Astra (`foundry-zyt/gpt-6-astra`, effort high, read-only),
2026-11-05. Saved verbatim.

## Summary

The plan is not ready to implement as a stable contract: duplicate submissions can undo cancellation, retention can silently release idempotency keys, and resumed output can invalidate bytes already downloaded. The memory guard explicitly permits crossing the owner's absolute RSS ceiling, while the proposed HTTP test path still imports cgo and downloads native-runtime dependencies. File-based durability is feasible, but the plan specifies files and fsync intervals rather than a recoverable commit protocol. Keep the closed status set and fake-first approach, but settle the state machine, resource bounds and durable-output semantics before Phase B freezes their types.

## Findings

1. **P1** — The memory guard detects the forbidden breach after it happens.

   *Admission and memory* says a job fails when "RSS [passes] the ceiling despite its estimate." That directly contradicts ROADMAP parameter 3: the process must **never** exceed 250 MiB. `GOMEMLIMIT` is soft and does not account for mmapped weights. Reservations also omit explicit budgets for the runtime, loaded models, concurrent admission, decoders, uploads, event readers and response construction. "A stalled client never holds memory" is false: its goroutine, stack and buffers remain allocated.

   **Fix:** Require conservative, pre-allocation budgets for the whole process, including touched mmap pages and bounded HTTP/admission concurrency. Bound total JSON size, nesting, part count, decoded media dimensions and response size—not just individual inline media. Separate queued jobs' feasibility estimates from reservations for executing work; reserving every queued working set would unnecessarily exhaust a one-worker scheduler. Reject ceiling configurations above 250 MiB. An underestimated allocation must be refused **before allocation**, not detected after RSS crosses the ceiling. Specify the limitations for an embedded runtime whose host also allocates memory.

2. **P1** — The fake HTTP path is not engine-independent or cgo-free.

   Phase D adds routes to the existing `server` package, and the file list changes initialization only to register routes. But `server.New` calls `download.Ensure` for TTS, STT and LLM before returning (`server/server.go:259–273`). The package imports `ort`, whose source contains `import "C"` (`ort/ort.go:7`). Merely hiding fake models behind an environment variable does not remove those compile-time dependencies or startup downloads. Leaving legacy routes active also lets their unaccounted allocations violate the new scheduler's process-wide ceiling.

   **Fix:** Put the v1 HTTP handler in an independent package and run conformance through a minimal fake-only executable with no legacy engine imports or downloads. Explicitly scope the no-cgo proof to that executable and the new packages until the daemon migrates. Do not claim whole-daemon ceiling compliance while legacy routes remain usable. Clarify "standard library only" as "standard library plus helium's own dependency-free packages."

3. **P1** — Retrying a submission can undo cancellation or advance an unintended attempt.

   *Keys across failures* automatically restarts a cancelled or retryably failed job. A delayed duplicate of the original POST can therefore resurrect a job after the caller deliberately cancelled it. Concurrent duplicates can also advance through several quickly failing attempts. This contradicts admission step 2, which returns an existing job "as it is," and makes `done` terminal only temporarily.

   **Fix:** Write a transition table covering submission, cancellation, recovery and retry. Ordinary duplicate submissions should return the existing state; intentional retry should carry a compare-and-set condition such as `retry_of_attempt`, still using the same job and key. Explicit cancellation should not be reversed by an indistinguishable retransmission. State whether `done` terminates an attempt or the job, include attempt identity in terminal events, and make the caller loop handle historical terminal events correctly. Keep the closed status set; a cancellation-requested field can represent pending cancellation without inventing another status.

4. **P1** — "Same request" has no defined equivalence rule.

   The key contract says different requests produce `key_conflict`, but never defines the fingerprint. JSON ordering, omitted defaults, output shorthand, ignored fields, metadata, `stream`, `detach` and deadlines all create ambiguities. Retrying after a default model or option changes is particularly dangerous: normalization against current defaults can turn the same submitted body into different work.

   **Fix:** Specify canonicalization and exactly which fields constitute execution identity. Persist the resolved model revision, effective options and fingerprint at initial acceptance; do not resolve defaults again on duplicate lookup. Define whether presentation mode can change without conflict and whether lifetime policy can change at all. Add fixtures for reordered JSON, omitted versus explicit defaults, unknown fields, changed options and concurrent lookup/create. Define duplicate or malformed `Idempotency-Key` header handling as well.

5. **P1** — Quota eviction silently weakens the idempotency window.

   *Retention* promises results for `result_ttl` "within a spool quota," removes oldest jobs first, and immediately frees their keys. Under disk pressure, a completed job can disappear well before the advertised hour. A retry after an uncertain response can then run the work again. No response tells the caller the actual deduplication horizon.

   **Fix:** Separate bulky result retention from a guaranteed idempotency-record lifetime. Retain a small durable tombstone containing the fingerprint, job identity and terminal outcome after output eviction; return an explicit expired-result response rather than silently rerunning. Publish expiration times and define when their clocks start and whether attempts reset them. Bound tombstone storage and reject new admission rather than breaking an existing guarantee. Explicitly document that retries after the deduplication horizon require caller reconciliation.

6. **P1** — The journal layout lacks an atomic commit and recovery protocol.

   *Durability and resume* lists `job.json`, `events.log`, output files and chunk markers, but not their ordering or authoritative state. Rename alone does not durably commit a directory entry. A crash can leave a chunk marker without durable output, a durable event ahead of the job snapshot, or a successful snapshot without its terminal event. Trimming a torn last line does not resolve these cases.

   **Fix:** Define one authoritative commit boundary and recovery algorithm. Specify file and directory fsync ordering, durable output offsets, chunk/checkpoint publication, event sequence allocation, terminal-state publication and reconstruction of key bindings. Distinguish incomplete tails from corruption of previously committed records. Require exclusive ownership of a data directory. The acceptance claim must be "no **durably committed** chunk is recomputed"; a chunk whose computation finished just before its commit marker can legitimately execute again after a crash.

7. **P1** — Output rollback is incompatible with the promised live byte-range resume.

   *Events* voids earlier-attempt parts from `resumed_from` onward, while `/output/{n}` streams a growing file and promises byte-identical Range resumption. A client can download an uncommitted prefix, crash, then append bytes from a different attempt. WAV finalization can also rewrite earlier header bytes. Meanwhile, a growing or replaceable output cannot already have its final content-hash file ID. "Final output files are always consistent" does not make previously downloaded bytes consistent.

   **Fix:** Prefer immutable, durably committed chunk objects and a committed-output frontier. Assign content hashes only to finalized objects. Expose completed files through ordinary Range semantics initially. If live mutable downloads remain, specify generation/ETag and `If-Range` behavior that forces clients to discard invalid prefixes. Distinguish provisional SSE pieces from committed output and expose commitment explicitly; an audio consumer cannot undo playback merely because a later `started` event voids it.

8. **P1** — Disk exhaustion after acceptance has no defined outcome.

   Admission checks disk once, but outputs, events, chunk markers and uploads continue growing afterward. `storage_full` exists only as a rejection, not as a job failure. Concurrent uploads or unrelated filesystem use can exhaust space after acceptance, including the space needed to record failure. The spool quota also lacks an accounting definition for temporary files, duplicate media in SSE and output files, active jobs and filesystem metadata.

   **Fix:** Bound and reserve output/event growth, account for all spool consumers, and retain emergency metadata capacity. Specify write, short-write, fsync, rename, ENOSPC and EIO behavior at every commit boundary. Define the accepted-job storage failure and its retry/resume behavior. When durability becomes unavailable, stop admission and report unhealthy rather than acknowledging undurable transitions. State which storage failures are outside the durability guarantee. Ensure quota collection cannot delete data still needed by active or resumable jobs.

9. **P1** — Resume depends on resources whose identity, lifetime and authorization are unspecified.

   A persisted chunk plan is insufficient if an input file expires, another caller deletes a deduplicated file, a model is replaced, or preprocessing/chunk-stitching state changes. *Parts* permits deleting files but supplies no pinning rules. *Auth* scopes jobs to keys, not their hash-addressed input/output files; authentication alone does not make a globally predictable content hash an authorization boundary. A `resumable: true` manifest flag also does not specify the state required to continue a recurrent or overlapping chunk pipeline.

   **Fix:** Pin immutable inputs, model/stage revisions and required checkpoints for the resumable lifetime. Define a model execution contract for independently resumable chunks or explicit checkpoint state, including randomness and stitching. Reject deletion of pinned resources or defer physical deletion. Apply per-principal authorization to file GET/HEAD/DELETE and output references; deduplication must not grant access or permit another principal to remove needed bytes. Define expiry for uploads never attached to a job.

10. **P1** — Permanent-first admission contradicts both the numbered order and unchanged auth.

    Admission checks `rate_limited` and `storage_full` before permanent `too_slow`. Thus a request known to miss its deadline even on an idle machine can still be told to retry. The unchanged middleware is a larger contradiction: it rate-limits before entering the handler and returns untyped errors, including a 403 absent from the proposed code table (`server/auth.go:253–282`). It also does not attach the authenticated principal to the request for ownership checks.

    **Fix:** Authenticate first, then run bounded permanent validation—including idle deadline feasibility—before admission rate/capacity checks. Split authentication from rate limiting for v1, pass principal identity into the core, and translate every auth failure into the v1 error contract. Define whether existing-job lookup and control/replay operations consume admission quota. Preserve the old middleware for legacy routes if necessary, but remove "auth changes" from the deferral list for the new surface.

11. **P1** — A watchdog cannot forcibly stop arbitrary in-process Go work.

    *Durability and resume* promises timeout failure, cancellation at the next boundary, panic containment and drain within 30 seconds. There is no execution interface requiring bounded boundaries or cancellation cooperation. A stalled goroutine cannot safely be killed; a parent's `recover` does not catch a panic in an engine-owned child goroutine. Marking the job failed while its execution continues would let another job start against memory still in use.

    **Fix:** Define a cooperative executor contract with bounded steps, context checks, managed goroutine ownership and reservation release only after execution actually stops. Specify daemon fail-stop behavior when an engine violates that contract, and the different limits of embedded operation. Do not claim recovery from runtime-fatal OOM or arbitrary engine corruption. Test a cooperative stall separately from an intentionally non-cooperative executor; they cannot have the same promised outcome.

12. **P2** — Reply modes and attachment ownership are underspecified and unnecessarily coupled.

    *The run request* has conflicting booleans: `stream: true` promises SSE, while `detach: true` promises immediate JSON. Their combination is undefined. A default `Run` waits for completion, yet the Go example calls `Events` after `Run`, suggesting submission returns immediately. Reconnect grace does not define whether polling, output downloads or multiple clients count as attachments, or whether one client disconnecting can cancel another client's job. `Runner` also lacks a stated route for uploading the referenced media it consumes.

    **Fix:** Simplify submission to returning a job promptly, with waiting and streaming performed through the existing job methods. Treat attachment lifetime as a separate policy. If all three reply modes remain, provide a truth table and exact Go signatures. Define attachment reference counting, normal long-poll completion, grace timing across restart, and Go context cancellation. Include file operations in the transport-neutral API or explicitly limit `Runner` parity to already-uploaded inputs.

13. **P2** — Dry-run equivalence is promised where it cannot hold.

    Dry runs "never use a key" but return an error "exactly what the real request would get." Real submission may instead return an existing job or `key_conflict`. Capacity can change immediately after the preview. "Dry runs that parse return 200" also leaves valid JSON with invalid fields, auth failures and malformed media ambiguously classified. The Go API example only shows a job return value, not an admission-result variant.

    **Fix:** Define dry run as an advisory preview of a **new** submission, explicitly excluding idempotency lookup and capacity reservation. It must not evict models, pin resources, consume admission quota or mutate measurements. Specify which transport/auth/decoding failures use non-200 responses and how admission failures appear inside 200. Give Go callers a typed admission result and define interactions with stream/detach flags. Return an estimate snapshot, not a promise that subsequent submission will be accepted.

14. **P2** — Deadline and retry guidance conflates permanent invalidity with scheduling estimates.

    The plan never fixes the origin of `deadline_ms`: receipt, acceptance or execution start. It also omits restart and retry behavior, clock jumps and time spent loading or committing output. `too_slow` is permanently non-retryable despite being based on measurements that can change on a shared vCPU; `timeout` similarly locks the key after an estimated watchdog expires. Finally, `retry_after_ms` cannot always come from inference ETA: rate limits use window reset time, while shutdown and disk recovery may have no known completion time.

    **Fix:** Define the deadline budget and its persistence rules explicitly, using monotonic timing within a process and documented wall-clock/restart handling. Separate "automatic retry is recommended" from "this request can never succeed." Review `too_slow`, `timeout`, `model_missing` and memory `too_large` against that definition; not every `too_large` error can be fixed by splitting. Give retry hints code-specific sources and documented fallback backoff when recovery time is unknown. Remove the unconditional "within 2x of real wait" guarantee: a rejection reserves no future slot.

15. **P2** — The additive contract still contains unresolved schema and default choices.

    `unsupported` includes an option the model lacks, while *Evolution* says unknown options succeed with warnings. Omitting both model and output is ambiguous for text input that could mean TTS or LLM, and the manifest does not publish an explicit default output. Part accumulation is also not defined: whether `index` identifies a logical output or a streamed piece, how deltas become final parts, and which fields are required for each variant. "Ignore unknown events and parts" needs a distinction between optional additions and output a caller must understand.

    **Fix:** Freeze one canonical output-request representation rather than both strings and objects. Define deterministic model selection or require a capability/output when selection is ambiguous. Publish defaults and required part fields, bound recursive message content, and distinguish unknown options from known-but-unsupported values. Add complete request/event/final-job fixtures for text, audio and tool calls. Preserve old endpoint response shapes when calling `/v1/status` an alias; changing its body would not be additive.

16. **P2** — The acceptance suite needs fault boundaries and measurable resource gates.

    Random `kill -9` tests do not establish the multi-file ordering, fsync-error behavior or stable Range semantics above. They also do not simulate loss of unsynced filesystem state. "No finished chunk runs twice," "slow reader does not raise RSS," and retry hints within 2x are not achievable as written. The 20 ms group-commit interval has no stated behavior under slow fsync or bounded pending-event storage. The reference-machine research measures inference and disk reads, not journal fsync latency; its stock STT result of 267 MiB already exceeds the new ceiling.

    **Fix:** Add deterministic crash/fault injection around every persistence boundary, plus disk-full, directory-sync failure, corrupt log, restart-during-GC and second-writer tests. Exercise retries after cancel/expiry, fast repeated failures, cross-key file access, historical `done` replay, future cursors, and the replay-to-live handoff. Measure peak RSS with real touched allocations/mappings and bounded concurrent readers/uploads, not only declared fake memory. Benchmark fsync latency and throughput on the reference machine; treat 20 ms as a batching target, not a completion guarantee. Replace zero-memory assertions with explicit per-client bounds and define recovery-time, spool and CPU acceptance thresholds.

## Codebase Accuracy

Static inspection only; no builds or tests were executed.

| Claim | Verified? | Evidence (file:line) |
|---|---|---|
| Five routes | Five API routes; also pprof | `server/server.go:378–391` |
| OpenAI-compatible chat | Partial; history is collapsed | `server/llm.go:260–284` |
| Models list contains IDs only | No; standard fields too | `server/server.go:128–134,529–534` |
| Status has per-modality stats | Yes | `server/server.go:543–580` |
| Shared `QueueMax` capacity | Yes; shared waiter semaphore | `server/pool.go:200–235` |
| All modalities share it | Yes | `server/server.go:726–740` |
| 500-character TTS budget | Default 500; actually bytes | `server/server.go:203–207,467` |
| Every rejection is 503 | No; validation/auth differ | `server/server.go:434`; `server/auth.go:253–278` |
| Fixed 2/3/30-second shedding | Yes for those branches | `server/server.go:470–497` |
| All errors use OpenAI envelope | No; chat/auth use plain error | `server/llm.go:98`; `server/auth.go:278` |
| TTS/STT use type and null code | Yes | `server/server.go:848–855`; `server/stt.go:47` |
| No job IDs or idempotency | Yes; request-bound execution | `server/server.go:481`; `server/llm.go:114–144` |
| Nothing survives disconnect | Too broad; TTS/STT lack context | `server/server.go:665`; `server/stt.go:63` |
| TTS buffers the complete WAV | Yes | `server/server.go:663–690` |
| STT uses 32 MiB threshold | Yes; not a total upload limit | `server/stt.go:85` |
| Chat streams a finished reply | Yes | `server/llm.go:114–144,202` |
| Speech rejects unknown fields | Yes; chat does too | `server/server.go:432`; `server/llm.go:76` |
| Existing mux can be fake-only | Not with stated initialization | `server/server.go:259–273`; `ort/ort.go:7` |
| Auth can remain unchanged | Not for v1 ordering/envelopes | `server/auth.go:253–282` |

The absence of jobs/idempotency is supported by the inspected handlers and a search of `server/`; chat completion response IDs are not durable job IDs. The plan's `server/llm.go:202` citation is accurate. Its load-shedding citations describe TTS correctly but do not justify generalizing that envelope to chat and auth.

## Scope Discipline

This is a broad API design plus several implementation projects, not yet a thin implementation layer. Phase C alone includes admission, scheduling, accounting, durable storage, replay, resume, garbage collection, cancellation, watchdogs, draining and estimation. Phase D adds uploads, downloads, long polling, ownership and an HTTP client.

Keep the broad document as a draft design, but make the first implementation slice:

- One immutable run identity, one worker and a short queue.
- Immediate job submission, status, cancel and sequence-numbered events.
- A minimal durable commit protocol.
- One chunked fake executor and one non-resumable fake executor.
- The same black-box tests through in-process and isolated HTTP implementations.

Defer live mutable Range downloads, adaptive chunk sizing, learned ETA, model management, output shorthand and multiple response modes from that proof. Do not defer idempotency lifetime, ownership, memory bounds or crash ordering: those shape the core and cannot safely be bolted on later.

## Thin-Layer Checklist

- **One capability in a sentence — PASS.** The document states one overarching capability, although its implementation expands substantially.
- **Deferral list longer than in-scope — FAIL.** The deferred bullets are outnumbered by substantive mechanisms and surfaces being built.
- **POC testable before dependencies — FAIL.** The core can be, but the proposed HTTP path still requires legacy initialization and cgo.
- **Structural decisions explicit — PASS.** Transport, storage layout, queue and status choices are named; commit and transition protocols remain blockers.
- **Acceptance criteria concrete — FAIL.** Several are measurable, but key guarantees are impossible or lack a defined fault/resource model.
- **File change list present — PASS.** Present, but must include isolated HTTP bootstrapping and v1 auth integration.

## Verdict

FAIL (11 P1, 5 P2, 0 P3)
