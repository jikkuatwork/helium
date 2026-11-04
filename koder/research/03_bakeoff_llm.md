# LLM bake-off — Qwen3.5-4B / LFM3-1.7B / LFM2.5-1.2B

Status: **running**. Evaluation only; no integration changes.

## Executive summary

- Goal: choose helium's short-reply/tool-calling default from measured CPU performance and checkable local quality tests, not vendor benchmark claims.
- Qwen3.5-4B is the integrated baseline. LFM3-1.7B is the default challenger; LFM2.5-1.2B-Instruct gets speed and a smaller quality spot check.
- Results pending acquisition/inference. No verdict yet.

## Method and environment

2026-11-04, Ubuntu 24.04 aarch64, Python 3.12.3, Ampere Altra / ARM
Neoverse-N1, 32 vCPUs, 128 GB RAM. All inference pinned to `taskset -c 16-23`;
ORT CPU EP, sequential execution, intra-op 1 / 4 / 8, inter-op 1.
ORT 1.24.x resolved version recorded in `bakeoff/llm/requirements.txt`.
Python runner will use identical greedy decode/cache handling, except Qwen's
required separate embedding graph versus LFM's direct token input. Model loading
and tokenization excluded from warmed TTFT; peak process RSS includes them.
Warm-up once, at least five measured runs per speed configuration, medians.

The N1 has ARM dot-product instructions; Pi 4 Cortex-A72 does not. **These are
not Pi 4 latency measurements.** Q4 is not uniform: LFM3's official `q4` retains
embedding, LM head and 27/153 projections in int8; its `q4f32` is a different
and larger variant, not tested here. All CPU q4 variants use float32 activations.

## Research plan

- Speed / memory: immutable official/community exports, common ORT loop, measured medians (high confidence on this VM).
- Tool calls: ≥30 exact schema/name/argument cases including no-tool and dependent calls (bounded synthetic evidence).
- Thinking: published template flag, count generated reasoning and paired enabled-token overhead.
- Instructions: ~30 deterministic, checkable format/length/language constraints (not official IFEval).
- Voice feel: 10 full raw short turns per default candidate for owner judgment.
- Portability: graph I/O and operators compared with `llm/qwen/` (direct evidence).

## Key findings

Pending.

## Contradictions and uncertainty

- Vendor IFEval/BFCL numbers are not independently verified or necessarily comparable; this small task-specific suite is not those benchmarks.
- LFM3 ONNX card currently lists CPU q4 as 1.63 GB (decimal), not the survey's lowest 1.21 GiB size. Exact downloaded sizes/hashes will settle this.
- Thinking-disable inconsistency remains to measure; injected empty think blocks are prompt tokens, not emitted reasoning.

## Recommendation

Pending measurements.

## Next steps

1. Acquire pinned q4 artefacts; record SHA256, licenses and rendered templates.
2. Run speed and quality suites, inspect failures and preserve raw output.
3. Recommend default and Pi-class choice, with caveats and integration deltas.

## Sources consulted

- `koder/STATE.md`, `koder/research/02_model_survey.md`: current baseline and prior claims.
- `llm/qwen/qwen.go`, `llm/qwen/decode.go`: existing graph/state/input assumptions.
- https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX — export and template.
- https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX — official export, quantization and input contract.
- https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-ONNX — official low-end export and template.
