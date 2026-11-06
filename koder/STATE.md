---
updated_at: "06 Nov 2026 | 03:41 PM IST"
---

# Helium — State

Go runtime for tiny local models: TTS (Kokoro-82M), STT (Moonshine-tiny) and LLM
(Qwen3.5-4B) over ONNX Runtime, as a CLI, a REST server and a Go module. v0.9.1.
Direction since 2026-11-05: one pure-Go monolith for any model type, hard 250 MiB
RSS ceiling, no cgo, one additive-only API ([ROADMAP.md](ROADMAP.md) *Design parameters*).

Reference files, read when the task needs them:
- [PROJECT.md](PROJECT.md): overview, stack, architecture, CLI, downloads, performance
- [DECISIONS.md](DECISIONS.md): key decisions; **zero external dependencies** is non-negotiable
- [ROADMAP.md](ROADMAP.md): design parameters 1–12, model survey, gaps, open decisions
- [issues/README.md](issues/README.md): every issue with its status

## Past

- 2026-03: TTS, STT, LLM, REST server with auth, OpenAI-compatible API, streaming
  and bounded memory, artefacts self-hosted in `cattery-artefacts`.
- 2026-10-31: renamed cattery → helium; v0.9.1 is the first release as helium.
- 2026-11-04: model survey and license policy; remote worker VM tooling
  ([plans/38](plans/38_remote_worker_vm.md), `scripts/hvm`).
- 2026-11-05:
  - **Bake-off done** ([plans/39](plans/39_model_bakeoff/README.md)): three Pi
    lanes on `hvm-helium`, landed. TTS: Phonon ~11x faster than Kokoro
    (conditional replace). STT: Parakeet 110M int8 conditional yes. LLM: keep
    Qwen3.5-4B non-thinking. Foundry ledger $26.03 (harnex under-reports 2x).
  - **$6-droplet stress test** ([research/04](research/04_small_vps.md),
    `bakeoff/vps/`): stock helium OOMs on 1 GB; Kokoro's 480-token chunks are
    the cause; Phonon 3.2x realtime at one thread.
  - **Owner's design parameters** recorded (ROADMAP, DECISIONS): monolith, 250
    MiB absolute, LLMs ~300M at 4-bit, priorities API → reliability → memory
    → speed, typed rejection + resumability (params 11–12).
  - **Plan 40 (API v1) drafted**; GPT-6 Astra review **FAIL (11 P1, 5 P2)**,
    saved at `reviews/040_api_v1/01_astra.md`.
  - Fixed `hvm up` for x64; filed harnex Issue 98 (second remote lane).
- 2026-11-06 (this close): **CLA** on `main`: `CLA.md` (contributor keeps
  copyright; Maintainer gets an irrevocable license to use, relicense and
  transfer; Singapore law), `CLA-CORPORATE.md`, `CONTRIBUTING.md`, CLA workflow
  (archived action pinned by SHA). Intent: no contributor can claim ownership.

## Present

- `main` is 2 commits ahead of `origin/main` (the CLA, not pushed). PR #2
  (`chore/cla`) is still open; its head commit is already on `main`.
- VMs `hvm-helium` (ARM, 32 vCPU) and `hvm-do6` (x64 D2s_v3, small-VPS box)
  are **deallocated**, disks kept. Foundry key `4rn4pmnn53rx` (VM lanes) has
  ~$74 left; top-ups only on the owner's go.
- Private notes live in ignored `koder/scratch/` (pointer in project
  instructions; retention ledger `SCRATCH_RETAIN.jsonl`). Never copy them out.
- Today's binary fails parameters 3–5 (525–720 MiB peaks, cgo, ORT/espeak).
- Known bugs: LLM output shows `<think>` tags raw; chat endpoint keeps only the
  last system and user message (`server/llm.go:260-284`), dropping history.

| # | Open issue | Pri |
|---|---|---|
| [05](issues/05_cross_platform_build.md) | Cross-platform build (Linux-only today) | P2 |
| [07](issues/07_license_audit.md) | License audit follow-through | P1 |
| [12](issues/12_llm_proxy.md) | LLM proxy (propose drop) | P2 |
| [14](issues/14_web_ui.md) | Embedded web UI | P3 |
| [23](issues/23_openai_remote_engines.md) | OpenAI remote engines (propose drop) | P2 |
| [33](issues/33_gh_actions_pr_permission.md) | GH Actions PR permission | P3 |
| [36](issues/36_serve_memory_semantics.md) | Serve `--memory` semantics | P3 |

## Future

Waiting on the owner's go: **take the CLA live**. Push `main` (GitHub should
then mark PR #2 merged), delete `chore/cla`, create an unprotected
`cla-signatures` branch for the bot. PR #2 lists four lawyer-review points.

Start here, in order:
1. **Revise plan 40 with fresh eyes** against Astra's review; write the
   response as `reviews/040_api_v1/02_claude.md`. Last session's leanings,
   non-binding: accept nearly all findings; memory enforced by engines
   allocating from a pre-checked budget (RSS check only as last resort);
   watchdog last resort = daemon exits, crash recovery restarts it; run
   returns the job at once, `Prefer: wait=N` for one-call results, `Accept:
   text/event-stream` to stream, opt-in lease instead of detach/grace;
   explicit `POST /v1/jobs/{id}/retry` with attempt CAS; per-job event log
   as the single source of truth; media streamed only in committed chunks;
   key tombstones outlive results; v1 HTTP in its own cgo-free package;
   first build slice narrowed as Astra suggests.
2. Second Astra pass for convergence: a paid Foundry call, owner's go first.
3. Owner decisions in plan 40: defaults, build the job core in parallel with
   the engine spike or after, no auto-pull.
4. Then per ROADMAP: pure-Go engine spike on Moonshine-tiny (plan 41) →
   shared chunking/stage layers → Phonon in pure Go → model-file format →
   daemon on v1 → tiny-LLM survey.

Housekeeping when convenient:
- Destroy or keep the deallocated VM disks (`scripts/hvm destroy do6`).
- Candidate `hvm shape` verb for mem=/nr_cpus= box emulation (plan 38 log).
- Tracker drift: 15 issue files say `Status: open` though done;
  `download/download.go:5` still says ORT comes from Microsoft.
- Optionally `koder-pattern init` for repo-local `open`/`close` copies.
- README (`knowledge-base/README.md`) License links use `../`, which break on
  the GitHub repo home page; `/LICENSE` style works in both places.
