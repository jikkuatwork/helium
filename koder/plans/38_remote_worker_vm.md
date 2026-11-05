# Plan 38 — Remote Worker VMs (on-demand cloud lanes)

Status: Phase 1 — first real run done 2026-11-05: three plan-39 lanes ran ~2–3 h, fetched, landed; VM deallocated · First consumer: helium · The
process evolves here (owner, 2026-11-04: "we will learn here by evolving the
process here"); once it is good, it moves into the **koder-pattern** skill.
Phase 1 tooling: `scripts/hvm` + `scripts/hvm-host-init.sh` (this repo).

## One capability

**Spin up a cloud VM with the full Pi/harnex toolchain on demand, run
GPT-backed workers on it unattended, steer them from a local orchestrator
(human or Claude), and pull their work back as a local git worktree.**

## Why

- Local dev box is a small headless VM; bake-offs and model exports need
  bandwidth (multi-GB Hugging Face pulls), RAM (fp32 parity checks of a 4B
  LLM), many cores, and hours of unattended runtime.
- Sponsored Azure capacity exists (see `~/Projects/cloma`), and Pi already
  reaches sponsored GPT models through the Foundry gateway.
- The pattern recurs across projects, so it should become a tool, not a
  one-off runbook.

## Architecture: four layers, each with an eventual home

```
 local machine (orchestrator: you or Claude)        cloud VM (worker host)
 ───────────────────────────────────────────        ──────────────────────
 1 PROVISION   cloma vm up/stop/destroy  ──az──▶   VM + NSG + disk (tagged RG)
 2 BOOTSTRAP   host init (over ssh)      ──ssh──▶   mise: ruby/node/go, tmux,
                                                    pi@<local ver>, harnex@<local ver>,
                                                    pi-config sync, capped key
 3 DISPATCH    harnex … (Phase 1: ssh;   ──ssh──▶   harnex delegate → Pi workers
               Phase 2: --on HOST/MCP)              in tmux, worktree harnex/NAME
 4 RETURN      git fetch HOST harnex/NAME ◀─git/ssh─ lane branch
               → .harnex/worktrees/NAME (review, test) → land onto main
```

| Layer | Phase 1 home (helium) | Eventual home | Cloud-specific? |
|---|---|---|---|
| Provision | `scripts/hvm up/stop/destroy` | koder-pattern / `cloma vm` | yes (Azure) |
| Bootstrap | `scripts/hvm-host-init.sh` | koder-pattern / `harnex host init` | no |
| Dispatch | `scripts/hvm delegate/run` | harnex `--on HOST` (harnex #97) | no |
| Return | `scripts/hvm fetch/land` | `harnex fetch` / `land --on` (#97) | no |

Project-specific setup stays in the project: `.harnex/host-init.sh`
(optional hook run after bootstrap; e.g. helium: Python venv for ONNX exports).

## Lifecycle

```
scripts/hvm up helium                      # guard → RG/VM/NSG → ssh alias hvm-helium
scripts/hvm init helium                    # toolchain parity (pi, harnex, ruby/node/go)
scripts/hvm key helium                     # owner pastes the capped fnd_… key (stdin)
scripts/hvm push helium                    # base = exact local main (incl. unpushed)
scripts/hvm delegate helium tts-bake brief.md   # copy brief, start a worktree lane
  … check-ins: scripts/hvm run helium harnex lanes|result|reply (or Claude on a loop) …
scripts/hvm fetch helium tts-bake          # → .harnex/worktrees/tts-bake on harnex/tts-bake
scripts/hvm land helium tts-bake           # merge locally, clean host, re-push main
scripts/hvm stop helium                    # deallocate (disk kept)
scripts/hvm destroy helium                 # RG deleted; then revoke the key
```

## Provision (Azure, cloma)

- **Guard first:** `ruby bin/cloma verify-sponsored --json --no-cache` (after
  `time-sync --check`); any failure aborts. Image must report `plan: null`
  (no Marketplace meter).
- **Resources:** one resource group per host `rg-hvm-<name>`, tagged
  `cloma-approved=true`, `purpose=remote-worker`, `project=<name>`,
  `created=<date>`. Destroy = delete the RG.
- **Region: westus2.** In eastus2 every ARM size (Dpsv5/v6, Epsv5/v6) is
  `NotAvailableForSubscription` despite 65 vCPU quota (checked 2026-11-04);
  westus2 offers them (65 regional / 65 DPSv5 vCPUs). x64 v7 sizes work in
  eastus2.
- **Image:** Canonical Ubuntu 24.04 LTS, arm64 or x64 to match the size.
- **Disk:** 256 GB Premium SSD OS disk (model caches, Go/npm caches).
- **Network:** `--nsg-rule NONE` + one SSH rule from the operator's egress IP;
  `vm allow-me` refreshes it when the IP changes. No other inbound ports.
- **SSH:** dedicated key `~/.ssh/hvm_ed25519`; script writes a `Host
  hvm-<name>` block with `ServerAliveInterval 30`, `ControlMaster auto`,
  `ControlPersist 10m` (check-ins reuse one connection).
- **Optional:** `--auto-shutdown HH:MM` backstop (off by default — it would
  kill unattended work; rely on lane caps instead, harnex #95).
- **Private details** (resource names, IPs, spend) go to `~/.cloma/`, never into
  the cloma repo (pre-commit privacy hook).

### Sizing (helium)

- **Default: `Standard_D32ps_v5`** — 32 Ampere Altra vCPUs (aarch64), 128 GB,
  ~$1.23/hr list (~$30/day). aarch64 matches helium's targets; 128 GB holds
  fp32 parity checks; 32 cores allow several *pinned* benchmarks
  (`taskset`, 4 threads each) side by side plus a dozen Pi workers.
- **Not D64ps_v5:** workers mostly wait on the GPT API and benchmarks must run
  on a few quiet cores to mean anything, so 64 cores add little. It would also
  take the whole Dpsv5 quota (65 vCPU, eastus2) and cross cloma's ~$50/day
  burn flag. Available via `--size` when a job really is CPU-parallel.
- **GPU:** `Standard_NC24ads_A100_v4` (quota: 2× A100, eastus2) only for GPU
  execution-provider work; start, use, deallocate.
- **Caveat:** Neoverse-N1 has dotprod; a Pi 4 (Cortex-A72) does not. Relative
  model comparisons hold; absolute Pi 4 numbers need a real Pi.

## Bootstrap (cloud-agnostic)

- Wait for cloud-init's apt lock, then base packages (`build-essential git
  tmux jq curl unzip python3-venv`).
- **Toolchain parity** with the local machine: copy local `~/.tool-versions`
  and `~/.config/mise/config.toml`, `mise install` (ruby 3.3.0, node 24.8.0,
  go 1.25.1 today).
- **Pi:** `npm i -g @earendil-works/pi-coding-agent@<local pi --version>`, then
  rsync `~/Projects/pi-config` and run `install.sh --sync` (models.json uses
  `$FOUNDRY_API_KEY`).
- **harnex:** `gem install harnex -v <local version>` (harnex publishes every
  release immediately; init re-checks parity, `doctor` flags drift).
- **Secret:** a **dedicated Foundry gateway key** (foundry-operator skill,
  Foundry MCP). Foundry keys are **prepaid balances, not rate caps**, so the
  owner's "$100/day" is: fund $100, top up at most $100 per day (each top-up
  is an owner-approved money call). The token is handed to the owner once
  and never stored by the orchestrator; the owner installs it with
  `scripts/hvm key NAME` (read from stdin, sent over ssh stdin) into
  `~/.config/hvm/env` (mode 600), sourced at the top of `~/.bashrc` so
  non-interactive `ssh CMD` sees it. Destroy → revoke.
- **Repos:** pushed from local over ssh, not cloned from GitHub —
  `ssh host git init ~/work/<repo>` + `git config receive.denyCurrentBranch
  updateInstead`, then local `git remote add hvm-<name> hvm-<name>:work/<repo>`
  and `git push`. **The VM never holds GitHub credentials.**
- Project hook: run `.harnex/host-init.sh` if present.

## Dispatch and check-ins

**Phase 1 (works with harnex 0.30.1 today):** everything over ssh.

- `ssh hvm-x 'cd ~/work/<repo> && harnex delegate --no-wait --worktree NAME --file BRIEF'`
- `ssh hvm-x harnex lanes --json` · `harnex result NAME --json` ·
  `harnex reply NAME "…"` · `harnex pane NAME` (screen snapshot)
- Workers keep running if ssh drops (tmux on the VM).
- Live view: `ssh -t hvm-x tmux attach`.

**Claude as orchestrator:** this session drives the same commands through
Bash; check-ins run on `/loop` (or ScheduleWakeup) every 30–60 min — read
`lanes --json`, the lane's `tmp/TICK.md`, `git log`; summarize; steer with
`reply`; fetch finished lanes for review. Constraint: check-ins stop when
the local session ends; the VM keeps working, bounded by lane caps.

**Phase 2 (harnex #97):** lane verbs gain `--on HOST` (MCP `host` arg, gpt
agent `host:` header), so the Agent tool / harnex MCP orchestrate remote lanes
natively, with progress notifications, local shadow lane records, and
`land`/`fetch` doing the git round-trip.

## Return: pull back as a worktree

```
git fetch hvm-x harnex/NAME
git worktree add .harnex/worktrees/NAME -b harnex/NAME FETCH_HEAD
# review + run tests locally (local machine is the source of truth)
git merge --no-edit harnex/NAME            # onto main
git worktree remove .harnex/worktrees/NAME && git branch -d harnex/NAME
ssh hvm-x 'cd ~/work/<repo> && harnex discard NAME'
```

Remote work arrives as a worktree for review, then lands on main. (Local
harnex work in helium still goes straight onto main.)

## Security model

- VM credentials: only the capped, revocable Foundry key. No GitHub token, no
  Azure credentials, no personal keys.
- Inbound: SSH from the operator IP only. Outbound: open (HF downloads etc.).
- Artefact publishing (e.g. `cattery-artefacts` LFS pushes) stays local and
  manual.
- Teardown always: deallocate when idle; destroy deletes the RG and revokes
  the key.

## Phases and acceptance criteria

**Phase 1 — scripts + manual flow (helium bake-off as the proving run)**
- [ ] `vm up` aborts on a failed sponsored guard; creates only tagged RG resources.
- [ ] `vm up` + `vm init` → host ready (pi, harnex, go versions = local) in < 15 min.
- [x] A Pi lane runs on the VM with the capped key; `lanes --json` readable over ssh. (2026-11-05)
- [x] `vm fetch` materializes the lane branch as a local worktree; tests pass locally. (2026-11-05, 3 lanes)
- [ ] `vm destroy` leaves no RG and the key revoked; `vm stop` deallocates.
- [ ] Friction log kept below → feeds harnex #97 and koder-pattern.

### Friction log (Phase 1)

- 2026-11-04 · eastus2 refuses every ARM size (`NotAvailableForSubscription`)
  despite quota → default region westus2. `vm up` should check
  `az vm list-skus` restrictions for the size before creating the RG.
- 2026-11-04 · `cloma verify-sponsored --no-cache` takes ~2.5 min; run it in
  the background from an agent (tool calls time out at 2 min).
- 2026-11-04 · first `up` failed before touching Azure: ssh_config written
  before `~/.config/hvm/` existed (fixed).
- 2026-11-04 · `init` took < 1 min: mise installs a prebuilt Ruby on arm64,
  so no source compile; versions matched local (pi 1.4.0, harnex 0.30.1).
- 2026-11-04 · return path verified with a smoke commit: VM worktree →
  `hvm fetch` → local `.harnex/worktrees/smoke`; cleaned without landing.
- 2026-11-04 · Foundry MCP not connected in the orchestrating session; key
  creation needs the owner (console) or an MCP connect + explicit go.
- 2026-11-05 · Foundry MCP connected; `keys_create` from Claude worked on the
  owner's go (key `4rn4pmnn53rx`, $100). The token passed through the
  orchestrator once (piped to `hvm key` over stdin); rotate if that bothers.
- 2026-11-05 · smoke `harnex ask` on the VM answered in 5 s (gpt-6.1-sol):
  key, pi-config and tmux-over-ssh all work for a single lane.
- 2026-11-05 · **harnex 0.30.1 bug for remote hosts:** `run.rb` picks
  `tmux new-window` only when `$TMUX` is set, else `new-session -s harnex`.
  Over non-interactive ssh `$TMUX` is unset, so the second lane fails with
  `duplicate session: harnex`. Workaround in `hvm run/delegate`: export
  `TMUX` from `tmux display -p -t =harnex` before calling harnex. Filed as
  harnex #98 (prerequisite for #97): reuse `=harnex` via `has-session`, not `$TMUX`.
- 2026-11-05 · `harnex delegate` warned "1 uncommitted change" because the
  copied brief under `.harnex/briefs/` is untracked on the host; `hvm push`
  now adds `.harnex/` to the host repo's `info/exclude`.
- 2026-11-05 · `hvm start` returns before ssh is reachable (~5 s later);
  callers must poll. Fine for now.
- 2026-11-05 · run totals: tts 2h03m, stt 2h02m, llm 3h12m (brief said ~3 h);
  VM up ~3h15m. Foundry ledger: **$26.03**, 423 requests, 51.4 M tokens for the
  key; harnex footers summed to only $11.16 (2.90 + 4.13 + 4.13), so harnex's
  lane cost under-reports by >2x against the gateway. Trust the ledger.
- 2026-11-05 · a Claude usage-limit pause skipped two 30-min check-ins; the
  lanes did not care. Unattended lanes + infrequent check-ins worked.
- 2026-11-05 · land needs a clean local tree (`--untracked-files=no`), so
  orchestrator edits must be committed before the first `hvm land`.
- 2026-11-05 · second host `do6` (Standard_D2s_v3, x64) for the small-VPS
  test (`koder/research/04_small_vps.md`). **`hvm up` had never worked for
  x64:** the image line's `$([ arm64 ] && echo -arm64)` returns 1 under
  `set -e` and killed the script silently. Fixed with `|| true`.
- 2026-11-05 · shaping a VM into a smaller box works with kernel args
  (`mem=… nr_cpus=…`, `bakeoff/vps/limit.sh`). Azure puts RAM below 1 GiB
  and above 4 GiB, so "1 GB" needs `mem=4170M`. Candidate `hvm shape` verb.

**Phase 2 — harnex remote lanes** (harnex #97, with #95 caps) — see that issue.

**Phase 3 — extract:** `cloma vm` subcommand (generic, privacy-clean);
`harnex host init` + guide; this plan shrinks to a pointer.

## Deferred

- Other clouds (GCP, Hetzner, DigitalOcean) — provision layer only.
- Custom VM image / snapshot to cut bootstrap time.
- Self-reaping VM (managed identity deallocates itself when idle).
- Several hosts per project; host pools; autoscaling.
- Tailscale/VPN instead of an IP-restricted NSG.
- Claude Code running on the VM (owner direction: workers are Pi + GPT).
- Remote GPU lanes beyond "pick a GPU size".

## File changes (Phase 1)

- `scripts/hvm` (new) — up/init/key/push/delegate/run/fetch/land/ssh/
  status/allow-me/stop/start/destroy. Guard via `~/Projects/cloma`.
- `scripts/hvm-host-init.sh` (new) — runs on the host; idempotent.
- `~/.config/hvm/` — private host registry, ssh config (`Include`d from
  `~/.ssh/config`), known_hosts. `~/.cloma/CHANGELOG.md` gets an entry per
  up/stop/start/destroy.
- `.harnex/host-init.sh` (optional project hook, not yet needed).
- `~/Projects/harnex/koder/issues/97_remote_host_lanes.md` — filed.

## Decisions (2026-11-04)

- Foundry key: $100 balance, topped up ≤ $100/day (prepaid, not a rate cap).
- Scripts live in helium; evolve here, then fold into koder-pattern.
- Size: D32ps_v5 (owner: cost no object; bigger adds nothing — see Sizing).

## Open questions

- Check-in owner: Claude on a loop, the owner, or both?
- Keep hosts long-lived per project (stop/start) or destroy after each run?
