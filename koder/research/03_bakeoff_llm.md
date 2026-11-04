# LLM bake-off — Qwen3.5-4B / LFM3-1.7B / LFM2.5-1.2B

Status: **running**. Evaluation only; no integration changes.

## Executive summary

- Goal: choose helium's short-reply/tool-calling default from measured CPU performance and checkable local quality tests, not vendor benchmark claims.
- Qwen3.5-4B is the integrated baseline. LFM3-1.7B is the default challenger; LFM2.5-1.2B-Instruct gets speed and a smaller quality spot check.
- Acquisition completed; immutable revisions and every downloaded file's SHA256 are in `bakeoff/llm/manifest.json`. All three q4 graphs run on ORT 1.24.4 CPU EP.
- Warmed speed/quality batches are running sequentially; no verdict yet.

## Method and environment

2026-11-04, Ubuntu 24.04 aarch64, Python 3.12.3, Ampere Altra / ARM
Neoverse-N1, 32 vCPUs, 128 GB RAM. All inference pinned to `taskset -c 16-23`;
ORT CPU EP, sequential execution, intra-op 1 / 4 / 8, inter-op 1.
ORT **1.24.4**, pinned with dependencies in `bakeoff/llm/requirements.txt`.
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

### Export/input compatibility — Evidence: High

LFM3 has 13 fixed float32 convolution caches + 11 attention KV pairs; LFM2.5
has 10 + 6, versus Qwen's 24 convolution + 24 recurrent + 8 KV pairs.
`past_conv.N → present_conv.N` and `past_key_values.N.* → present.N.*` already
match helium's state naming/zero initialization. The **unmodified** Qwen engine
still cannot load LFM: it requires two graphs and `inputs_embeds`, builds
`position_ids` as `[3,1,S]`, and does not accept `logits_to_keep`. Both LFM graphs
are single-graph, direct `input_ids`, `[1,S]` positions, and int64
`logits_to_keep=[1]`. No recurrent state is needed. Cache outputs must be
fed back just like Qwen's. All tested caches use float32.

No new operator compared with the **union** of Qwen's embedding and decoder
operators: LFM's `GatherBlockQuantized` is already in Qwen's embed graph.
All export opsets are 21 plus Microsoft domain 1. Full graph I/O/operator
inventories are recorded in `bakeoff/llm/graphs.json`.

LFM3's `logits_to_keep=1` avoids projecting all prefill tokens into vocabulary;
Qwen's export always returns full prefill logits (248,320-vocabulary). This is a
real export/runtime advantage, not an equal-kernel architecture experiment.
Additional LFM full-logits prefill trials will expose the contribution.

### Test scope — Evidence: High for fixtures; bounded for model conclusions

Predeclared `suites.py`: 36 tool cases (25 single, 6 no-tool/clarification,
5 dependent two-step), 5 schemas, 30 instruction prompts, 10 voice turns,
and 20 paired thinking-off/on prompts including reasoning traps. Greedy
argmax without repetition penalty/sampling for all models. Output limits are
192 tokens off / 512 on; truncations will be reported rather than silently
counted as completed answers. Exact string argument matching, no fuzzy judge;
XML parser unit-tested including malformed calls. LFM2.5 uses its native
Pythonic `<|tool_call_start|>` protocol for the spot check, **not** LFM3 XML.

Two-step continuation is tested with a ground-truth first call/result. Strict
end-to-end score is first-call correctness AND continuation correctness;
continuation is separately observable even if the first call failed. No real
messages/reminders are executed. Instructions are synthetic IFEval-style,
not the official IFEval dataset. Language checks are fixed translations.

### Licenses — Evidence: High

Qwen: Apache-2.0 (base model card/license). Both Liquid checkpoints: **LFM Open
License v1.0** (`LICENSE` in each ONNX repository), accepted by owner. Include
the license/notices on redistribution and surface the $10M revenue commercial
license threshold to downstream users. This is not Apache-2.0. The actual
license defines threshold as $10M or more but Section 5 says "exceeds"; avoid
promising eligibility exactly at the boundary. No license gate was added to
the evaluation.

Speed and quality results pending.

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
