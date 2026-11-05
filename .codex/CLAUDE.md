# Helium — Project Instructions

## Project Tracking

- `koder/STATE.md` — source of truth for status, open issues and next steps (<100 lines)
- `koder/PROJECT.md`, `koder/DECISIONS.md`, `koder/ROADMAP.md` — stack, decisions, direction
- `koder/issues/README.md` — index of every issue
- `koder/issues/NN_slug.md` — individual issue specs
- `koder/plans/` — technical plans
- `koder/reviews/` — turn-based review conversations

Always read `koder/STATE.md` at session start.

## Confidential Context

Important: Refer: `koder/scratch/01_dependencies.md` ; NOTE: ignored folder, info not to leak to repo.

- Never copy names, paths or details from that file into tracked files, commit messages, issues, plans, PR text, or briefs for remote workers.
- If the file is missing (fresh clone, worktree, remote VM), carry on without it.

## Design Parameters

New work is judged against the design parameters in `koder/ROADMAP.md` (2026-11-05): one pure-Go monolith for any model type behind one additive-only API, a ~1 GB VPS as the reference machine, a hard 250 MiB RSS ceiling, no cgo, and nothing downloaded except model files. When goals conflict: API first, then reliability, then memory and compute, then speed.

## Non-Negotiable: Zero External Dependencies

The entire system lives in two repos: `helium` and `cattery-artefacts`. No download, fetch, or network call may target any host outside these two repos. CDN mirrors are allowed only if they serve copies of assets already in `cattery-artefacts`, and the GitHub raw URL must always remain a working fallback. Never introduce a third-party download dependency.

## Multi-Agent Dispatch (Harnex)

Use the global `harnex` skill for dispatch. No local docs — the skill is the single source of truth.

## Scratch State

- `tmp/TICK.md` — orchestration scratch file (current issue, phase, notes)
- `tmp/` is gitignored; cleared during `/close`
