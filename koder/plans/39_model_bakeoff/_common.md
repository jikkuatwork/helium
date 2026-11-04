## Where you are and the rules (common to every bake-off lane)

You are a worker on a remote build VM: Ubuntu 24.04 **aarch64** (Ampere
Altra / Neoverse-N1, 32 vCPUs, 128 GB RAM), in a git worktree of **helium**
(`github.com/jikkuatwork/helium`): a Go runtime for tiny local AI models on
ONNX Runtime (TTS, STT, LLM). Go 1.25.1, Python 3.12 (use a venv), open
internet. Nobody is watching live; an orchestrator checks in every 30–60 min.

Read first: `koder/STATE.md` (What's Next), and in
`koder/research/02_model_survey.md` the section for your area. The project's
north star: one binary + one model file, CPU-first, Pi-4-class low end.

**This is an evaluation, not an integration.** Measure and recommend; do not
wire new models into helium's packages.

- **Where to put things**
  - Code: `bakeoff/<area>/` (Python scripts + `requirements.txt` pinned;
    small Go programs only if you use helium itself). No changes to existing
    packages.
  - Results: `koder/research/03_bakeoff_<area>.md` — method, environment,
    tables (narrow, ≤ 5 columns), verdict, caveats, exact model URLs and
    file hashes.
  - Model files and datasets: `~/models/` and `~/datasets/` (outside the
    repo). **Never commit model weights, audio datasets, or WAVs.**
  - Listening samples: `~/bakeoff-samples/<area>/` (WAV), with an index in
    the results doc.
- **Fair measurement**
  - Use ONNX Runtime **1.24.x** everywhere (`pip install onnxruntime==1.24.*`;
    helium's own binary already uses 1.24.4). Same version for all candidates.
  - Pin every timed run to your assigned cores with `taskset -c <cores>`, and
    set intra-op threads to **4** (a Pi 4 has 4 cores). Also report 1 thread.
  - Warm up once; report median of ≥ 5 runs; record peak RSS
    (`/usr/bin/time -v`).
  - Note: this CPU has the ARM dot-product extension, a Pi 4 does not, so
    absolute int8/int4 speed is optimistic for a Pi 4; comparisons hold.
- **Helium itself:** build with `go build -o /tmp/helium ./cmd/helium`; it
  downloads its own models from `cattery-artefacts` on first use.
- **Progress file:** keep `tmp/TICK.md` (gitignored) in your worktree current:
  phase, last result, next step, blockers. Update it at every milestone.
- **Commits:** small, frequent, clear messages (`bakeoff(<area>): …`). Commit
  the results doc as it grows, not only at the end.
- **Budget:** about 3 hours of work. If one candidate is blocked for 30
  minutes (broken export, missing op), record why and move on.
- **Licenses:** record each model's weight license from its model card.
- When done: reply with the verdict, the key numbers, and anything that
  surprised you.
