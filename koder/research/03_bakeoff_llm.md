# LLM bake-off — Qwen3.5-4B / LFM3-1.7B / LFM2.5-1.2B

Status: **running**. Evaluation only; no integration changes.

## Executive summary

- Goal: choose helium's short-reply/tool-calling default from measured CPU performance and checkable local quality tests, not vendor benchmark claims.
- Qwen3.5-4B is the integrated baseline. LFM3-1.7B is the default challenger; LFM2.5-1.2B-Instruct gets speed and a smaller quality spot check.
- Acquisition completed; immutable revisions and every downloaded file's SHA256 are in `bakeoff/llm/manifest.json`. All three q4 graphs run on ORT 1.24.4 CPU EP.
- Core quality is complete: Qwen **36/36 tools, 27/30 raw instructions**, versus LFM3 **36/36, 8/30 raw (18/30 final-only)**. Keep Qwen as the global default with the tested non-thinking template; LFM3 is a fast tool-first alternative, not a safe drop-in voice/chat default.
- Supplemental Qwen thinking-on and 8/1-thread sweeps still running. Final censored thinking averages, full voice transcripts and consolidated tables pending.

## Method and environment

2026-11-04, Ubuntu 24.04 aarch64, Python 3.12.3, Ampere Altra / ARM
Neoverse-N1, 32 vCPUs, 128 GB RAM. All inference pinned within cores **16–23**;
exclusive speed processes use `taskset -c 16-23`.
ORT CPU EP, sequential execution, intra-op 1 / 4 / 8, inter-op 1.
Qwen correctness-only requests are sharded into two four-thread processes,
`taskset -c 16-19` and `20-23`, to fit the wall-time budget. Their request
latencies/combined RSS are **not** speed/Pi measurements; both processes
finish before the next exclusive speed run. Quality uses greedy decode,
fixed fixtures and independent empty contexts, so no shared request state.
ORT **1.24.4**, pinned with dependencies in `bakeoff/llm/requirements.txt`.
Python runner will use identical greedy decode/cache handling, except Qwen's
required separate embedding graph versus LFM's direct token input. Model loading
and tokenization excluded from warmed TTFT; peak process RSS includes them.
Warm-up once per speed prompt/configuration, at least five measured runs,
medians. Both 100/1000-token lengths at 4 and 8 threads; supplemental Qwen
1-thread sweep is 100 tokens only because its long prefill exceeds the
remaining wall-time budget. Other candidates include both lengths at 1 thread.

The N1 has ARM dot-product instructions; Pi 4 Cortex-A72 does not. **These are
not Pi 4 latency measurements.** Q4 is not uniform: LFM3's official `q4` retains
embedding, LM head and 27/153 projections in int8; its `q4f32` is a different
and larger variant, not tested here. All CPU q4 variants have float32 graph tensor/cache interfaces; LFM3's
matmul kernels can quantize activations internally (see compute-policy note).
Worker spinning is disabled identically for every measured model/session.

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
inventories are recorded in `bakeoff/llm/graphs.json`. Both Liquid tokenizers
are byte-level BPE with metadata-driven split regexes compatible in shape
with helium's tokenizer loader, but unlike Qwen they have **no NFC normalizer**;
helium currently applies NFC unconditionally. BOS/EOS IDs and published chat
rendering also differ. Tokenizer parity must be tested, not assumed.

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
Parser unit-tested including malformed calls. Two small Cattery-hosted Qwen
graph files were fetched and their SHA256 verified **byte-identical** to the
HF baseline (`bakeoff/llm/cattery_graph_check.json`); registry weight sizes also
match. Cattery weight payloads were not downloaded again. This anchors the
baseline's graph/compute policy to helium's current self-hosted model.
LFM2.5 uses its native
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

### Completed LFM2.5 speed + quick spot check

Median of five warmed runs; decode uses 32 steps after the first token.

| Threads | Prefill 100 tok/s | Prefill 1000 tok/s | Decode 100 / 1000 tok/s |
|---|---:|---:|---:|
| 1 | 14.25 | 14.71 | 1.85 / 1.79 |
| 4 | 56.03 | 56.58 | 6.95 / 6.78 |
| 8 | 109.50 | 111.55 | 12.89 / 12.48 |

| Threads | TTFT 100 (s) | TTFT 1000 (s) | Peak RSS (MiB) |
|---|---:|---:|---:|
| 1 | 7.017 | 67.995 | 1581.1 |
| 4 | 1.785 | 17.674 | 1583.7 |
| 8 | 0.913 | 8.965 | 1589.8 |

Four-thread RSS after 100-token warm/trials was 929.5 MiB; 1000-token prefill
raises it above **1.5 GB / 1.5 GiB**, even though the model files fit comfortably.
Pi-class recommendation must distinguish weight size from working memory and
restrict context. Additional full-logits 1000-token prefill: 56.24 tok/s at
4 threads / 111.67 at 8, essentially unchanged for this model.

LFM2.5 spot: **9/9 tools**, including one canonical dependent continuation;
**7/10 instructions** (same raw/final score), 0 reasoning traces or truncated
outputs in 25 off generations. The three failures were exact word counts.
Replies are short and generally usable, but without tools the reminder turn
answered "Sure! Make sure to drink some water now to stay hydrated." rather
than setting a twenty-minute reminder or clearly declining. This is not a
proof of general agent reliability.

### Completed LFM3 quality (Qwen baseline pending)

**36/36 tools**: 25/25 single, 6/6 no-tool/clarification, 5/5 dependent paired
calls. However, only **8/30 instruction prompts pass on raw visible output**;
**18/30** after stripping generated reasoning. Sixteen of the 30 instructions
emitted `<think>`/`</think>` while the published template was explicitly
called with `enable_thinking=False`; four hit the 192-token limit, all in
reasoning, without an answer. This is not just an empty-tag cosmetic issue.
One short sky-blue voice turn also emitted a reasoning answer followed by
`</think>` and then a second answer. Across the full suite: **27/101 off
outputs contain generated thinking tags**: 0/41 tool requests (including
continuations), 16/30 instructions, 3/10 voice turns, 8/20 paired off turns.
The 101 generations include ten repeated voice prompts; these are not 101
independent samples. An untagged, overlong bat-and-ball algebra derivation
also appears; it is not included in the conservative tagged-leak count.

Thinking enabled adds **164.05 tokens on average** across 20 pairs (mean
211.85 total output tokens, 182.4 reasoning tokens). One enabled response
hit 512 tokens, so the unbounded overhead is underestimated. Simple bill
splitting was wrong with thinking off (said the $20 payer owes $10), but
correct with thinking on after 472 tokens ($10 payer owes $20 payer $5).
The bleach/vinegar voice reply correctly says not to mix them, but wrongly
names the gas as chloramine instead of chlorine. These are spot observations,
not a scored knowledge benchmark; see full voice transcripts below at completion.
Qwen baseline results pending.

Raw example for "Give a calming bedtime thought in at most 10 words":

> `<think>We need to generate a calming bedtime thought, at most 10 words...`
> [192 generated tokens, truncated before final answer]

Tool scoring checks calls/arguments, allowing pre-call prose as the templates
do. Instruction results report **both raw output and extracted final content**,
not silently granting credit by hiding unwanted reasoning. Raw scoring strips
only normal EOS markers. Headline constraint accuracy will use raw output;
think-prefix prompt tokens are never counted as emitted reasoning.

### New optimized Qwen export caveat — Evidence: High

The requested Qwen repository's card links a newer
https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX-OPT . Metadata-only inspection
found fused `com.microsoft::CausalConvWithState` and `LinearAttention`, scalar
`num_logits_to_keep`, and convolution state length 3 instead of 4.
**Neither new operator is registered in this ORT 1.24.4 wheel**: minimal-op
session probes fail with "not a registered function/op". Recorded in
`bakeoff/llm/qwen_opt_probe.json`; no OPT weights downloaded or speed claims
made. Thus the requested older export remains the usable 1.24.x baseline,
but do not interpret the forthcoming speed gap as intrinsic to every Qwen
runtime/export.

### Compute-policy confound — Evidence: High

Graph inspection found Qwen's 249 and LFM2.5's 93 `MatMulNBits` nodes use 4-bit
weights, block size 32, **no `accuracy_level` attribute**. LFM3 has 126 4-bit
and 28 8-bit matmuls; **all 154 set `accuracy_level=4`**. ORT 1.24.4 source
`GetComputeType` selects int8 input/int32 accumulation only for level 4 when
that kernel is available; otherwise float32 compute. This VM's dot-product
hardware can therefore benefit LFM3 disproportionately. Same q4 labels do
not mean equal compute precision, even with identical sessions/loops.

Requested native-export results remain unchanged. A supplemental four-thread
control sets only Qwen/LFM2.5 `MatMulNBits.accuracy_level=4` in derived graphs
outside the repo; weights and I/O are untouched. This is **not** a silently
optimized baseline and may change numerical outputs; do not infer quality
parity without separately evaluating those derived graphs. Control medians so far: LFM2.5 decode improves from **6.95 to 28.82 tok/s**
at 100-token context, and from 6.78 to 25.75 at 1000. Prefill improves only
from 56.03/56.58 to 69.29/68.33 tok/s. Qwen control still running. LFM2.5
therefore becomes faster than LFM3 for decode under matched requested compute
policy. This reverses the naive native-export size/speed interpretation.
On a Pi 4 without the required kernels, ORT falls back to fp32; the
relative Altra speed ranking need not carry over unchanged.

Source read: https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/contrib_ops/cpu/quantization/matmul_nbits.cc
(`ACCURACY_LEVEL` / `GetComputeType`, lines 37–61).

### Completed four-thread native comparison (Qwen quality pending)

| Model | Prefill 100 / 1000 tok/s | Decode 100 / 1000 tok/s | TTFT 100 / 1000 (s) | Native peak RSS (MiB) |
|---|---:|---:|---:|---:|
| Qwen3.5-4B | 12.64 / 12.85 | 1.86 / 1.83 | 7.914 / 77.807 | 5007.2 |
| LFM3-1.7B | 58.00 / 57.07 | 18.21 / 15.82 | 1.724 / 17.524 | 2608.7 |
| LFM2.5-1.2B | 56.03 / 56.58 | 6.95 / 6.78 | 1.785 / 17.674 | 1583.7 |

RSS column is native 1000-token peak before supplemental full-logit trials.
The `/usr/bin/time -v` LFM3 process peak is 3129.0 MiB because that process
also ran a full-logit control; Qwen already computes full logits natively.
Qwen's four-thread native decode is nearly ten times slower than LFM3 at
100-token context, but matched-compute Qwen is **7.28 / 6.71 tok/s**, with
prefill 14.96 / 14.96 and TTFT 6.687 / 66.863 seconds. Control peak RSS
5011.0 MiB. Most of the native decoder gap is therefore export compute-policy
plus size/architecture, not evidence of a tenfold intrinsic model advantage.
Modified control graph quality has not been evaluated.

### Core Qwen quality complete; thinking-on / extra threads pending

Qwen: **36/36 tools**, including every dependent continuation; **27/30 raw
instruction prompts** and 27/30 extracted-final prompts. Its three failures
are word counts (six-word gravity definition, four-word snack, ten-word cloud
explanation). No thinking tags in the 81 non-thinking tool/instruction/voice
requests, before the paired thinking tests. All ten voice turns are recorded.
The bleach/vinegar reply correctly warns about chlorine. The no-tool reminder
reply is unhelpful (offers a reminder now instead of scheduling twenty minutes).

All first nine measured Qwen thinking-on turns hit the **512-token limit**
inside lengthy "Thinking Process" analysis, with no final answer. The eventual
mean will be a **censored lower bound**, not an estimate of unbounded thinking
cost. Non-thinking is essential for voice here. The Go `FormatChat` currently
emits only the assistant header, not the empty think block used in this test;
keeping the model does not mean the existing CLI already applies this policy.

Remaining Qwen thinking and 8/1-thread speed results pending.

## Contradictions and uncertainty

- Vendor IFEval/BFCL numbers are not independently verified or necessarily comparable; this small task-specific suite is not those benchmarks.
- LFM3 ONNX card currently lists CPU q4 as 1.63 GB (decimal), not the survey's lowest 1.21 GiB size. Exact downloaded sizes/hashes will settle this.
- Thinking-disable inconsistency remains to measure; injected empty think blocks are prompt tokens, not emitted reasoning.

**Keep Qwen3.5-4B as the global default, with thinking explicitly disabled
for voice/chat.** LFM3 is dramatically faster/smaller and passes this easy tool
suite, but its disable flag is not dependable, and it loses constrained replies
entirely to reasoning loops. A post-generation think stripper cannot restore
answers that never arrived or guarantee low-latency streaming of unframed
reasoning. Do not promote it on vendor IF/BFCL claims alone.

**Pi-class size pick: LFM2.5-1.2B-Instruct, yes for short bounded contexts.**
Its q4 ONNX assets are 0.850 GB / 0.792 GiB, but the measured Python ORT
1000-token peak is 1.661 GB / 1.547 GiB. If ≤1.5 GB means a strict process-RSS
ceiling for every context length, it does not meet that measured budget at
1000 tokens. Actual Pi 4 latency and Go RSS still need measurement.

Quality parity for accuracy-level-4 control graphs is untested. Treat them as
performance research, not already-approved replacement exports.

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
