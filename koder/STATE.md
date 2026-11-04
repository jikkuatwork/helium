---
updated_at: "04 Nov 2026 | 11:04 PM IST"
---

# Helium — State

Go runtime for tiny local models: TTS (Kokoro-82M), STT (Moonshine-tiny) and LLM
(Qwen3.5-4B) over ONNX Runtime, as a CLI, a REST server and a Go module. v0.9.1.

Reference files, read when the task needs them:
- [PROJECT.md](PROJECT.md): overview, stack, architecture, CLI, downloads, performance
- [DECISIONS.md](DECISIONS.md): key decisions; **zero external dependencies** is non-negotiable
- [ROADMAP.md](ROADMAP.md): vision, model survey picks, architecture gaps, open decisions
- [issues/README.md](issues/README.md): every issue with its status

## Past

- 2026-03: TTS, STT, LLM, REST server with auth, OpenAI-compatible API, streaming
  and bounded memory, artefacts (models, ORT, espeak-ng) self-hosted in `cattery-artefacts`.
- 2026-10-31: renamed cattery → helium; v0.9.1 is the first release as helium.
- 2026-11-04: owner's vision recorded (one binary + one model file per model,
  CPU-first, optional GPU, importable); model survey and license policy done.
- 2026-11-04: remote worker VM built ([plans/38](plans/38_remote_worker_vm.md),
  `scripts/hvm`); bake-off planned ([plans/39](plans/39_model_bakeoff/README.md)).
- 2026-11-04 (this close): hand-off tooling only, no product code.
  - Removed the old `.codex/skills/{open,close}`.
  - Claude now uses machine-wide `open`/`close` routers from pi-config; in a repo
    without its own copy they run the koder-pattern templates.
  - Added `koder-pattern drift`/`upgrade` in pi-config `79656e9`.
  - Split this file into the reference files above.

## Present

- `main` was 3 commits ahead of `origin/main` before this close (not pushed).
- VM `hvm-helium` (D32ps_v5, 32 ARM vCPU, 128 GB, westus2; eastus2 blocks ARM)
  is **deallocated**; toolchain at parity (pi 1.4.0, harnex 0.30.1, go 1.25.1).
  Tooling: `scripts/hvm` + `scripts/hvm-host-init.sh`. Push and
  fetch-as-worktree verified; no Pi lane run yet (no key).
- No repo-local `open`/`close` and no `koder/AGENTS.md`: Claude's routers follow
  the templates; Pi has no hand-off skills here. `koder-pattern init` would add
  copies plus `CHANGELOG.md` (owner's call).
- LLM output shows Qwen3.5 `<think>…</think>` tags raw (CLI and API).

| # | Open issue | Pri |
|---|---|---|
| [05](issues/05_cross_platform_build.md) | Cross-platform build (Linux-only today) | P2 |
| [07](issues/07_license_audit.md) | License audit follow-through | P1 |
| [12](issues/12_llm_proxy.md) | LLM proxy (propose drop) | P2 |
| [14](issues/14_web_ui.md) | Embedded web UI | P3 |
| [23](issues/23_openai_remote_engines.md) | OpenAI remote engines (deferred; propose drop) | P2 |
| [33](issues/33_gh_actions_pr_permission.md) | GH Actions PR permission | P3 |
| [36](issues/36_serve_memory_semantics.md) | Serve `--memory` semantics | P3 |

## Future

Start here, in order:
1. **Foundry key.** The Foundry MCP was not connected in the 2026-11-04 sessions;
   if it still shows "Needs authentication": `/mcp` → *claude.ai foundry* → sign in.
   Load `foundry-operator`; on the owner's go: `console_me`, then `keys_create`
   label `hvm-helium — remote worker VM (helium plan 38)`, $100 (`100000000`
   µUSD), `allowed_models: []`, idempotency key `hvm-helium-key-2026-11-04`.
   The token goes to the owner once; the owner runs `scripts/hvm key helium` in a
   separate terminal. Budget: $100 balance, top-ups ≤ $100/day, each on the
   owner's go.
2. `scripts/hvm start helium` → `scripts/hvm push helium` → smoke Pi turn on the VM.
3. Bake-off ([plans/39](plans/39_model_bakeoff/README.md)): lanes `tts`, `stt`,
   `llm` in parallel; check in every 30–60 min; fetch → review → land.
4. Log friction in plan 38; later fold the process into koder-pattern; harnex
   Issue 97 (remote host lanes) after Phase 1.
5. `scripts/hvm stop helium` whenever no lane is running.

Then, per [ROADMAP.md](ROADMAP.md): bundle format → ORT embed → library API →
new model types → GPU (sequencing still open with the owner).

Housekeeping when convenient:
- Tracker drift: 15 issue files say `Status: open` though done (see issues/README.md);
  `download/download.go:5` still says ORT comes from Microsoft; DECISIONS
  "Remote models are just models" / "Dual-mode operation" describe deferred #23.
- Optionally `koder-pattern init` for portable `open`/`close` copies.
