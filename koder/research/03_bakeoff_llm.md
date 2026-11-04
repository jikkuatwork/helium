# LLM bake-off — measured default decision

Completed 2026-11-04 UTC on the remote ARM VM. Evaluation only; **no helium package changes**.

## Executive summary

- **Keep Qwen3.5-4B as the global default, explicitly non-thinking for voice/chat.** It scored 36/36 tools and 27/30 raw instructions; LFM3 scored 36/36 and 8/30 raw (18/30 after removing thinking).
- LFM3 is much faster/smaller, but emitted thinking tags with thinking disabled in 27/101 generations, versus 0/101 for Qwen. Four LFM3 instruction turns spent the entire 192-token budget thinking without an answer. Use it as an opt-in tool-first alternative, not a drop-in global voice/chat default.
- **Pi-class size pick: LFM2.5-1.2B-Instruct, yes with bounded short context.** ONNX assets are 0.850 GB / 0.792 GiB; 100-token native RSS was 929.5 MiB. **No** if ≤1.5 GB means an unconditional process-RSS ceiling: 1000-token Python ORT prefill reached 1583.7 MiB (1.661 GB / 1.547 GiB). Actual Pi 4 latency and Go RSS remain unmeasured.
- **Important confound:** LFM3 requests `MatMulNBits.accuracy_level=4` (int8 compute when available), the other exports do not. Matching that setting raised four-thread Qwen decode from 1.86 to 7.28 tok/s and LFM2.5 from 6.95 to 28.82. This is an export/runtime comparison, not proof of a tenfold architecture advantage.

## Method and environment

Ubuntu 24.04 aarch64; Ampere Altra / Neoverse-N1, 32 vCPUs, 128 GB RAM, one NUMA node; Python 3.12.3, ONNX Runtime **1.24.4** CPU EP. Dependencies pinned in `bakeoff/llm/requirements.txt`. Go 1.25.1 is installed but not used for timing.

- Exclusive speed runs: `taskset -c 16-23`; intra-op **1 / 4 / 8**, inter-op 1, sequential execution, full ORT graph optimization, worker spinning disabled equally for all sessions. One warm-up per prompt/configuration; **median of five runs**; 100 / 1000 exact prompt tokens, 32 post-first-token decode steps.
- Same NumPy/ORT greedy autoregressive loop, empty attention caches and zero convolution/recurrent state per request. No sampling or repetition penalty, matching helium's current greedy behavior, **not** the cards' recommended sampling or official benchmark settings. Qwen requires a separate embedding session; LFM directly accepts token IDs.
- Speed text is the same repeated English document before per-tokenizer truncation. Tokenizers differ; forced continuation through EOS gives equal decode steps. Speed continuations are not quality samples. No cross-request prefix-cache reuse. TTFT begins before state allocation/Qwen embedding and ends after argmax/cache adoption; model load, tokenization and detokenization are excluded.
- Both lengths at **4 and 8 threads for every model**. The supplemental Qwen 1-thread sweep uses 100 tokens only to stay near the three-hour budget; its 1000-token sweep was omitted, not estimated. All other 1-thread lengths were measured.
- Peak process RSS captured with `/usr/bin/time -v`; native per-length peaks also recorded with Linux `ru_maxrss`. The LFM3 4-thread process also ran a full-logit experiment, which raises its process peak above native last-logit usage.
- Qwen correctness-only requests were split into two **four-thread** processes on disjoint cores `16-19` / `20-23`. These request latencies and combined memory are **not speed/Pi measurements**. Both finished before exclusive speed resumed. Fixed fixtures and independent contexts; raw shard evidence retained.
- Verification: six `unittest` groups passed; `summarize.py` independently rechecks parsed calls, continuations and instruction scores against retained raw output. Final report checks enforce completed ORT 1.24.4 speed processes, five trials/32 decode steps, ten voice turns and tables of at most five columns.
- This host has ARM dot-product support; Pi 4 Cortex-A72 does not. Absolute speeds are optimistic for Pi 4, and **relative rankings need not carry over unchanged** when an export requests different compute precision. Shared-VM memory/cache contention and different tokenizers are additional caveats.

## Key findings

### 1. Native-export speed — Evidence: High on this VM

`P` = prefill, `D` = post-first-token decode, all in tokens/s. Context lengths are 100 / 1000.

**Qwen3.5-4B**

| Threads | P100 | P1k | D100 | D1k |
| --- | --- | --- | --- | --- |
| 1 | 3.56 | — | 0.50 | — |
| 4 | 12.64 | 12.85 | 1.86 | 1.83 |
| 8 | 21.51 | 22.07 | 3.44 | 3.36 |

**LFM3-1.7B**

| Threads | P100 | P1k | D100 | D1k |
| --- | --- | --- | --- | --- |
| 1 | 15.13 | 14.65 | 5.77 | 5.11 |
| 4 | 58.00 | 57.07 | 18.21 | 15.82 |
| 8 | 106.18 | 110.19 | 26.23 | 23.24 |

**LFM2.5-1.2B**

| Threads | P100 | P1k | D100 | D1k |
| --- | --- | --- | --- | --- |
| 1 | 14.25 | 14.71 | 1.85 | 1.79 |
| 4 | 56.03 | 56.58 | 6.95 | 6.78 |
| 8 | 109.50 | 111.55 | 12.89 | 12.48 |

**Warmed TTFT (seconds)**

| Model / threads | 100 tokens | 1000 tokens |
| --- | --- | --- |
| Qwen3.5-4B / 1 | 28.079 | — |
| Qwen3.5-4B / 4 | 7.914 | 77.807 |
| Qwen3.5-4B / 8 | 4.649 | 45.314 |
| LFM3-1.7B / 1 | 6.611 | 68.246 |
| LFM3-1.7B / 4 | 1.724 | 17.524 |
| LFM3-1.7B / 8 | 0.942 | 9.076 |
| LFM2.5-1.2B / 1 | 7.017 | 67.995 |
| LFM2.5-1.2B / 4 | 1.785 | 17.674 |
| LFM2.5-1.2B / 8 | 0.913 | 8.965 |

**Peak RSS (MiB)** — native per-length peaks versus whole `/usr/bin/time -v` process.

| Model / threads | Native 100 | Native 1k | Process max |
| --- | --- | --- | --- |
| Qwen3.5-4B / 1 | 3189.4 | — | 3189.4 |
| Qwen3.5-4B / 4 | 3194.8 | 5007.2 | 5007.2 |
| Qwen3.5-4B / 8 | 3203.0 | 5015.9 | 5015.9 |
| LFM3-1.7B / 1 | 1929.4 | 2608.4 | 2608.4 |
| LFM3-1.7B / 4 | 1930.2 | 2608.7 | 3129.0 |
| LFM3-1.7B / 8 | 1929.9 | 2608.9 | 2608.9 |
| LFM2.5-1.2B / 1 | 926.7 | 1581.1 | 1581.1 |
| LFM2.5-1.2B / 4 | 929.5 | 1583.7 | 1583.7 |
| LFM2.5-1.2B / 8 | 934.8 | 1589.5 | 1589.8 |

Qwen's native export projects **all prefill logits** (vocabulary 248,320); LFM normally keeps the last logit. At four threads, requesting all LFM3 logits reduced 1k prefill from 57.07 to 51.52 tok/s and raised process RSS from native 2608.7 to 3129.0 MiB. LFM2.5 full-logit prefill was 56.24 versus 56.58 tok/s, essentially unchanged. This explains some prefill difference, not the entire gap.

### 2. Compute-policy control — Evidence: High

Qwen: 249 four-bit `MatMulNBits` nodes, no accuracy attribute. LFM2.5: 93 four-bit nodes, no attribute. LFM3: 126 four-bit + 28 eight-bit nodes; all 154 specify **accuracy level 4**. All use block size 32. Float32 graph/cache interfaces do **not** mean kernels necessarily compute in float32.

ORT 1.24.4 `GetComputeType` selects int8 input/int32 accumulation for level 4 **when that kernel is available**, otherwise float32. Derived control graphs change only this attribute for Qwen/LFM2.5; original exports and weight payloads are untouched. These controls have **not been quality-evaluated**.

| 4-thread control | P100 | P1k | D100 | D1k |
| --- | --- | --- | --- | --- |
| qwen-acc4 | 14.96 | 14.96 | 7.28 | 6.71 |
| lfm25-acc4 | 69.29 | 68.33 | 28.82 | 25.75 |

LFM2.5 becomes the fastest decoder under matched requested compute policy. Qwen improves ~3.9× at short context, leaving a ~2.5× gap to LFM3, rather than the native ~9.8× gap. Do not extrapolate the int8 benefit to a Pi 4 or assume numerical/quality parity after changing this setting. Derived graph hashes are in `bakeoff/llm/accuracy4_control.json`.

### 3. Tools and instructions — Evidence: direct but bounded synthetic tests

Predeclared `suites.py`: 36 tool cases, five schemas (`get_weather`, `create_reminder`, `search_notes`, `send_message`, `calculate`), 25 single calls, six no-tool/clarification cases, five dependent two-step cases. Fixed clock: Wednesday **2026-11-04 12:00 UTC**; includes today/tomorrow and relative reminders.

Exact function name and argument dictionaries; only outer parameter whitespace is stripped. No real actions are executed. Two-step continuation uses a canonical ground-truth first call and deterministic mock result; case success requires correct first call **and** continuation. This is not unconstrained end-to-end agent execution. No-tool scoring checks absence of a call, not the quality of the clarification. Tool-call prose is allowed as in the templates. LFM2.5 spot uses its native Pythonic tool tokens, parsed with AST/literal_eval, never executed.

| Model | Single | No tool | Two-step | Total |
| --- | --- | --- | --- | --- |
| Qwen3.5-4B | 25/25 | 6/6 | 5/5 | 36/36 |
| LFM3-1.7B | 25/25 | 6/6 | 5/5 | 36/36 |
| LFM2.5-1.2B (spot) | 7/7 | 1/1 | 1/1 | 9/9 |

Thirty synthetic IFEval-style prompts: word limits/exact counts, JSON/CSV/list formats, one sentence, fixed translations, forbidden words and combined constraints. **Raw output removes only normal EOS markers**; final-only scoring additionally removes generated thinking. Word counts use a documented Unicode regex; sentence checks count terminal-punctuation boundaries; language uses fixed translation whitelists. These are not official IFEval scores or a general knowledge evaluation.

| Model | Raw prompts | Final prompts | Raw constraints | Final constraints |
| --- | --- | --- | --- | --- |
| Qwen3.5-4B | 27/30 | 27/30 | 39/42 | 39/42 |
| LFM3-1.7B | 8/30 | 18/30 | 13/42 | 26/42 |
| LFM2.5-1.2B (spot) | 7/10 | 7/10 | 11/14 | 11/14 |

Qwen failed only the six-word gravity definition, four-word snack, and ten-word cloud explanation. LFM2.5's three spot failures were exact word counts. LFM3's raw failures include reasoning duplication, format/language leakage, and lost answers; even after stripping thinking it passes only 18/30.

### 4. Thinking control — Evidence: High for observed cases

Both main models use the published templates with `enable_thinking=False`; the injected empty think block is **prompt text, not emitted reasoning**. Disabled output limit 192; enabled limit 512. Twenty paired prompts include all ten voice turns plus arithmetic/logical traps. Counts below are conservative **generated tag** counts; untagged verbose derivations are not automatically classified as private reasoning. The 101 off generations include ten repeated voice prompts, not 101 independent samples.

| Model | Off tags | Off trunc. | Mean extra tokens | On trunc. |
| --- | --- | --- | --- | --- |
| Qwen3.5-4B | 0/101 | 0/101 | 491.55 | 20/20 |
| LFM3-1.7B | 27/101 | 4/101 | 164.05 | 1/20 |
| LFM2.5-1.2B | 0/25 | 0/25 | N/A | N/A |

| Enabled / 20 pairs | Mean reasoning tokens | Mean total tokens |
| --- | --- | --- |
| Qwen3.5-4B | 512.00 | 512.00 |
| LFM3-1.7B | 182.40 | 211.85 |

Qwen thinking-on hit the 512-token limit in **20/20** pairs. These averages/extra tokens are **censored lower bounds**, not measurements of unbounded thinking cost. LFM3 had one enabled truncation. Thinking tokens are those before the first `</think>`; absent a closing tag, the entire generated budget is counted as reasoning. Qwen quality-shard elapsed times are deliberately not compared.

LFM3 tagged leakage breakdown: **0/41 tool requests**, **16/30 instruction turns**, **3/10 voice turns**, **8/20 paired off turns**. Four instruction turns (bedtime thought, walking tip, study tip, dog description) hit 192 tokens inside thinking without a final answer. Many leaks have **only an unexpected closing `</think>`**, preceded by reasoning then followed by a duplicate answer. A post-generation stripper cannot restore missing answers or guarantee clean low-latency streaming.

A bill-splitting spot observation: LFM3 off wrongly said the $20 payer owes $10; enabled eventually correctly said the $10 payer owes the $20 payer $5, after 472 tokens. Its no-tag bat-and-ball off answer also gives an overlong algebra derivation. These are observations, not a scored reasoning benchmark.

### 5. Assistant feel — raw non-thinking replies for owner judgment

All ten turns use the same friendly/brief voice system prompt. **No tools are supplied in this section**, so the reminder checks honest limitations, not real scheduling. Scheduling is separately tested in the tool suite. Only normal EOS markers are removed below; generated thinking tags/repetition are preserved.

#### Turn 1

**User:** Hey, I had a rough day. Say something kind.

**Qwen3.5-4B**
```text
I'm so sorry you had a tough day; please remember you are loved and capable of finding joy again.
```

**LFM3-1.7B**
```text
I'm sorry you had a rough day. You deserve a moment of kindness—take a deep breath, stretch, and remember you've got this. I'm here if you want to talk.
```

**LFM2.5-1.2B** (spot)
```text
That sounds tough—want to talk about what happened? You're not alone.
```

#### Turn 2

**User:** Why is the sky blue?

**Qwen3.5-4B**
```text
The sky appears blue because sunlight scatters off gas molecules in the atmosphere, with blue light scattering more than other colors.
```

**LFM3-1.7B**
```text
The sky appears blue because molecules in Earth's atmosphere scatter shorter blue wavelengths of sunlight more efficiently—a phenomenon called Rayleigh scattering.</think>Because sunlight interacts with atmospheric gases, scattering blue light in all directions more than other colors.
```

**LFM2.5-1.2B** (spot)
```text
The sky appears blue because Earth's atmosphere scatters sunlight in all directions, with blue light scattering more than other colors.
```

#### Turn 3

**User:** What can I make for lunch with eggs and rice?

**Qwen3.5-4B**
```text
You can make a delicious fried rice with scrambled eggs, or try a creamy egg fried rice with some veggies!
```

**LFM3-1.7B**
```text
You can make scrambled eggs over rice, or a simple fried egg and rice bowl. Want a recipe? I can help.
```

**LFM2.5-1.2B** (spot)
```text
You can make scrambled eggs with rice for a simple and tasty lunch.
```

#### Turn 4

**User:** Remind me to drink water in twenty minutes.

**Qwen3.5-4B**
```text
I can't set a timer, but I can remind you to drink water right now!
```

**LFM3-1.7B**
```text
I can't set reminders. Please use your device's alarm or calendar app for that.
```

**LFM2.5-1.2B** (spot)
```text
Sure! Make sure to drink some water now to stay hydrated.
```

#### Turn 5

**User:** Summarize this in one sentence: The library will close on Friday for repairs. It reopens Monday at 9 am. Online borrowing remains available all weekend.

**Qwen3.5-4B**
```text
The library closes Friday for repairs, reopening Monday at 9 am, but online borrowing stays available all weekend.
```

**LFM3-1.7B**
```text
The library closes Friday for repairs, reopens Monday at 9 am, and online borrowing stays open all weekend.
```

**LFM2.5-1.2B** (spot)
```text
The library is closed Friday for repairs but will reopen Monday at 9 am with weekend online borrowing available.
```

#### Turn 6

**User:** Is a tomato a fruit or a vegetable?

**Qwen3.5-4B**
```text
Botanically, a tomato is a fruit, but culinarily, it's treated as a vegetable.
```

**LFM3-1.7B**
```text
A tomato is botanically a fruit—it's a berry—though we call it a vegetable in cooking. Both are right in their own way.
```

#### Turn 7

**User:** I have five minutes before a meeting. How can I calm down?

**Qwen3.5-4B**
```text
Take three deep breaths, count to ten, and then review your meeting agenda quickly.
```

**LFM3-1.7B**
```text
Take three slow breaths, step away for a minute, and remind yourself you’ve prepared. You can use a timer or a quick walk. I can’t do it for you, but I can help you plan your next steps.
```

#### Turn 8

**User:** What is 18 percent of 50?

**Qwen3.5-4B**
```text
18 percent of 50 is 9.
```

**LFM3-1.7B**
```text
18% of 50 is 9. You can calculate it as 50 × 0.18 = 9.</think>18% of 50 is 9.
```

#### Turn 9

**User:** Tell me a short, clean joke.

**Qwen3.5-4B**
```text
Why did the scarecrow win an award? Because he was outstanding in his field!
```

**LFM3-1.7B**
```text
Why did the scarecrow win an award? Because he was outstanding in his field. 😄
```

#### Turn 10

**User:** Can I mix bleach and vinegar to clean the bathroom?

**Qwen3.5-4B**
```text
No, you should never mix bleach and vinegar because it creates toxic chlorine gas.
```

**LFM3-1.7B**
```text
No, mixing bleach and vinegar creates toxic chloramine gas and can damage surfaces. Use them separately or follow a safe disinfectant routine.</think>No, mixing bleach and vinegar creates toxic chloramine gas and can damage surfaces. Use them separately or follow a safe disinfectant routine.
```

Judgment notes: both main models correctly advise against mixing bleach and vinegar, but LFM3 incorrectly names **chloramine** rather than **chlorine**, and repeats the warning around a thinking closer. Qwen's reminder offers an immediate reminder instead of the requested timed one; LFM3 clearly declines scheduling; LFM2.5 answers “Sure!” then says to drink now. All require actual tool plumbing for timers.

### 6. What helium's Qwen loop already handles — Evidence: High

- State binding names already match: `past_conv.N → present_conv.N`, `past_key_values.N.* → present.N.*`. Zero fixed conv state/empty attention caches and greedy last-logit selection transfer. Qwen has 24 conv + 24 recurrent states + eight KV pairs; LFM3 has 13 conv + 11 KV pairs; LFM2.5 has ten conv + six KV pairs. No recurrent state is required by LFM.
- The **unmodified engine will not load LFM**: it requires separate embedding/decoder graphs and `inputs_embeds`; LFM is one graph accepting `input_ids`. LFM positions are `[B,S]`, not Qwen's `[3,B,S]`, and LFM requires int64 `logits_to_keep=[1]`. Attention masks remain `[B,total_S]`; all tested caches are float32.
- **No new operators** versus the union of Qwen embedding + decoder. LFM's `GatherBlockQuantized` is already in Qwen's embedding graph. Opset 21 + Microsoft domain 1. Full recursive inventories/I/O are in `graphs.json`. Qwen's older decoder includes 24 `Scan` operators; LFM has no recurrent scans.
- Liquid tokenizers are byte-level BPE with metadata-driven split regexes, but **no NFC normalizer**; helium applies NFC unconditionally. BOS/EOS IDs and chat/tool templates differ; tokenizer parity must be tested, not assumed. The existing `FormatChat` does not render the non-thinking prefix used here.
- “Single graph” is still **graph + external weight sidecar + tokenizer/config assets**, not a literal one-model-file distribution. The planned bundle remains necessary.

The requested Qwen graph headers were SHA256-verified byte-identical to helium's Cattery-hosted embedding/decoder files; registry weight sizes match. Those weight payloads were not re-fetched. See `cattery_graph_check.json`.

A newer linked Qwen `Qwen3.5-4B-ONNX-OPT` export uses `CausalConvWithState`, `LinearAttention`, scalar `num_logits_to_keep`, and conv cache length 3 rather than 4. Neither new operator is registered in this ORT 1.24.4 wheel; minimal-op probes fail with “not a registered function/op”, and the graph has no embedded fallback functions. **Metadata only; no OPT weights downloaded or benchmark claims.** See `qwen_opt_probe.json`. Revisit only with a compatible runtime.

## Contradictions and uncertainty

- LFM3's thinking-disable warning is empirically confirmed for this export/common greedy runtime; vendor IFEval/BFCL advantages are **not independently reproduced** by this small suite. Different precision, thinking, sampling, caps and test distributions mean this does not prove the vendor card is wrong.
- Tool cases are mostly unambiguous and easy; 36/36 is not general agent safety or BFCL reliability. No actual tool side effects, long dialogues, retrieval corpus, adversarial instructions, or multilingual tool suite were tested.
- Compute controls can change logits/outputs. No full quality/parity test was run for those derived graphs. Neither Altra int8 speedups nor Python RSS are verified Pi 4/Go measurements.
- The Qwen 1-thread 1k sweep was omitted for budget. Thinking-on limits censor overhead; no uncapped run was attempted. The benchmark is roughly three hours, not a production soak.

## Recommendation

**Global default: keep Qwen3.5-4B, non-thinking for voice/chat.** It follows the tested constraints much more reliably and honors thinking disable in these samples. Its current four-thread native export is **not low-latency enough for comfortable voice**; prioritize validating a faster export/compute policy and/or prefix reuse rather than promoting an unreliable reasoning toggle. Keeping the model does not mean the current Go formatter already implements the tested template.

**LFM3: opt-in tool-first alternative.** Half the ONNX asset size and much higher native decoder speed are real. Its clean tool context is encouraging, but do not make it the global voice/chat default until plain constrained turns, streaming, and thinking-disable behavior are fixed or robustly guarded. Hiding tags alone does not recover four missing answers.

**Pi-class: LFM2.5-1.2B-Instruct, yes by size and short-context working memory; no unconditional ≤1.5 GB RSS guarantee.** Good quick tool spot, acceptable short replies, non-thinking checkpoint, but imperfect exact word counts and unproven physical Pi 4 latency. Keep prompts/context bounded.

Recommendation confidence: **moderate** for the product choice; high for these measured behaviors on this VM. Nothing is wired into helium by this lane.

## Next steps

1. Owner judges the raw voice replies; retain Qwen and ensure future voice/chat rendering actually passes the non-thinking convention (current Go formatter does not).
2. Validate quality/parity of the accuracy-level-4 controls before adopting any derived export; surface different compute policies in future model manifests/benchmark notes.
3. Benchmark LFM2.5 on a physical Pi 4 with memory/context caps. Measure Go RSS and shared STT/TTS/LLM working memory, not only this Python process.
4. Re-test LFM3 with vendor sampling, explicit guards and always-tools voice contexts; verify streaming and latency under failures before considering global promotion. A compatible future ORT/Qwen OPT export also deserves a new bake-off.

## Model provenance, licenses and hashes

| Model | ONNX assets GB / GiB | Weight license |
| --- | --- | --- |
| Qwen3.5-4B | 3.109 / 2.896 | Apache-2.0 |
| LFM3-1.7B | 1.626 / 1.515 | LFM Open License v1.0 |
| LFM2.5-1.2B | 0.850 / 0.792 | LFM Open License v1.0 |

LFM license accepted by the owner. Redistribution requires the license/notices and marking modified files; commercial use has the $10M legal-entity revenue limitation. The definition says “$10M or more” while Section 5 says “exceeds”; do not promise eligibility exactly at the boundary. This is not Apache-2.0. No weights or external datasets are committed. Model files: `~/models/llm/`; complete raw JSONL and `/usr/bin/time -v` evidence: `~/datasets/llm/results/` (Qwen shard details under `shards/`). No WAV/listening samples apply to this text-only lane.

**Authoritative manifest:** `bakeoff/llm/manifest.json` records sizes/SHA256 for every downloaded graph, weight file, tokenizer, template, config and card/license. `summary.json` records checked scores, medians and raw-result fingerprints. Exact graph/weight URLs and SHA256 are reproduced below.

### Qwen3.5-4B

- Repository: https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX
- Immutable revision: `23ac3352f288351eddcdf141b32f4f66587f7e2d`

- [`onnx/decoder_model_merged_q4.onnx`](https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX/resolve/23ac3352f288351eddcdf141b32f4f66587f7e2d/onnx/decoder_model_merged_q4.onnx)
  - SHA256: `731f0569c84ea71a756abfe090f3b472050ecda7ad35a78fb553dc530a60315b`
- [`onnx/decoder_model_merged_q4.onnx_data`](https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX/resolve/23ac3352f288351eddcdf141b32f4f66587f7e2d/onnx/decoder_model_merged_q4.onnx_data)
  - SHA256: `c884a7c467f508568008bbaed3a90a77103f2dbc0643bd2625f8c483864c9726`
- [`onnx/decoder_model_merged_q4.onnx_data_1`](https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX/resolve/23ac3352f288351eddcdf141b32f4f66587f7e2d/onnx/decoder_model_merged_q4.onnx_data_1)
  - SHA256: `8239304d972b0ee1661b8be4b90ccf5937073a281f62fc1917d793b1fb873f3c`
- [`onnx/embed_tokens_q4.onnx`](https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX/resolve/23ac3352f288351eddcdf141b32f4f66587f7e2d/onnx/embed_tokens_q4.onnx)
  - SHA256: `b72feb6947db92d643f70abc6a4d3e5398a9535470a97685e3b1ab3b05047146`
- [`onnx/embed_tokens_q4.onnx_data`](https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX/resolve/23ac3352f288351eddcdf141b32f4f66587f7e2d/onnx/embed_tokens_q4.onnx_data)
  - SHA256: `aeb939a0c9a5d54c9f3ce77db340132780692c02e602b80a0cefb6ec8a9728be`

### LFM3-1.7B

- Repository: https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX
- Immutable revision: `e90558fd7388a536a029a4196ddc1c90a234ae9b`

- [`onnx/model_q4.onnx`](https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX/resolve/e90558fd7388a536a029a4196ddc1c90a234ae9b/onnx/model_q4.onnx)
  - SHA256: `20cacb31ad9c25a28ecb0b0a88937f0033b4d0171ba137596a2305b1e66bf00f`
- [`onnx/model_q4.onnx_data`](https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX/resolve/e90558fd7388a536a029a4196ddc1c90a234ae9b/onnx/model_q4.onnx_data)
  - SHA256: `aad5286be89c40c53106bc1ca29d20a2dda57e1806df5244c09da852f77b43e8`

### LFM2.5-1.2B

- Repository: https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-ONNX
- Immutable revision: `10f72e70abf67ac0fd7ebf15bc5854726891d864`

- [`onnx/model_q4.onnx`](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-ONNX/resolve/10f72e70abf67ac0fd7ebf15bc5854726891d864/onnx/model_q4.onnx)
  - SHA256: `c760a2d8be1d19c71c470ef294c1220ef85b5b3a0e31f12a363655ea7fab1d58`
- [`onnx/model_q4.onnx_data`](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-ONNX/resolve/10f72e70abf67ac0fd7ebf15bc5854726891d864/onnx/model_q4.onnx_data)
  - SHA256: `d9666c44e2acc32f06c9351f9e7c4fd66bc060d88ca8e7f954e836c6845f7488`

## Sources consulted

- Local: `koder/STATE.md`, `koder/research/02_model_survey.md` — baseline and vendor-claim context.
- Local: `llm/qwen/qwen.go`, `llm/qwen/decode.go`, `llm/qwen/tokenizer.go`, `registry/registry.go` — actual engine/session/cache/normalization/formatter assumptions.
- Model cards and templates at the immutable repositories/revisions above; base cards/licenses: https://huggingface.co/Qwen/Qwen3.5-4B , https://huggingface.co/LiquidAI/LFM3-1.7B , https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct .
- ORT 1.24.4 source, `ACCURACY_LEVEL` / `GetComputeType`, lines 37–61: https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/contrib_ops/cpu/quantization/matmul_nbits.cc
- Metadata-only Qwen OPT repository: https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX-OPT (revision `bb072268d0912bdc5cf4f41c8c6f53a03fd68624`, graph SHA256 `97a9351ca56a3e736f2bd9eac33de321224e7b0f97fcf30c7540a8b93371f699`).
- Cattery graph URLs and matching SHA256: `bakeoff/llm/cattery_graph_check.json`.
