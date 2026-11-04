#!/usr/bin/env python3
"""Build the decision memo from independently checked, completed evidence."""
import json
from pathlib import Path
from suites import VOICE, assistant_visible_text

LABEL = {'qwen': 'Qwen3.5-4B', 'lfm3': 'LFM3-1.7B', 'lfm25': 'LFM2.5-1.2B'}


def table(headers, rows):
    assert len(headers) <= 5
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def main():
    base = Path('bakeoff/llm')
    s = json.loads((base / 'summary.json').read_text())
    manifest = json.loads((base / 'manifest.json').read_text())
    q = s['quality']
    for name in ['qwen', 'lfm3']:
        assert q[name]['tool_total'] == 36 and q[name]['instruction_total'] == 30
        assert len(q[name]['voice']) == 10 and q[name]['thinking_pairs'] == 20
    for name in LABEL:
        for threads in [1, 4, 8]:
            assert s['speed'][f'{name}-{threads}t']['process_exit_success']

    def med(name, threads, length):
        return next((r for r in s['speed'][f'{name}-{threads}t']['medians'] if r.get('prompt_tokens') == length), None)

    def val(r, key, digits=2):
        return f'{r[key]:.{digits}f}' if r else '—'

    def ratio_count(obj, success, total):
        return f'{obj[success]}/{obj[total]}'

    lines = ['# LLM bake-off — measured default decision', '',
             'Completed 2026-11-04 UTC on the remote ARM VM. Evaluation only; **no helium package changes**.', '',
             '## Executive summary', '',
             '- **Keep Qwen3.5-4B as the global default, explicitly non-thinking for voice/chat.** '
             f'It scored {q["qwen"]["tool_pass"]}/36 tools and {q["qwen"]["instruction_raw_pass"]}/30 raw instructions; '
             f'LFM3 scored {q["lfm3"]["tool_pass"]}/36 and {q["lfm3"]["instruction_raw_pass"]}/30 raw '
             f'({q["lfm3"]["instruction_pass"]}/30 after removing thinking).',
             f'- LFM3 is much faster/smaller, but emitted thinking tags with thinking disabled in '
             f'{q["lfm3"]["off_tag_emissions"]}/{q["lfm3"]["off_generations"]} generations, versus '
             f'{q["qwen"]["off_tag_emissions"]}/{q["qwen"]["off_generations"]} for Qwen. '
             'Four LFM3 instruction turns spent the entire 192-token budget thinking without an answer. '
             'Use it as an opt-in tool-first alternative, not a drop-in global voice/chat default.',
             '- **Pi-class size pick: LFM2.5-1.2B-Instruct, yes with bounded short context.** '
             'ONNX assets are 0.850 GB / 0.792 GiB; 100-token native RSS was 929.5 MiB. '
             '**No** if ≤1.5 GB means an unconditional process-RSS ceiling: 1000-token Python ORT prefill reached 1583.7 MiB '
             '(1.661 GB / 1.547 GiB). Actual Pi 4 latency and Go RSS remain unmeasured.',
             '- **Important confound:** LFM3 requests `MatMulNBits.accuracy_level=4` (int8 compute when available), '
             'the other exports do not. Matching that setting raised four-thread Qwen decode from 1.86 to 7.28 tok/s '
             'and LFM2.5 from 6.95 to 28.82. This is an export/runtime comparison, not proof of a tenfold architecture advantage.', '',
             '## Method and environment', '',
             'Ubuntu 24.04 aarch64; Ampere Altra / Neoverse-N1, 32 vCPUs, 128 GB RAM, one NUMA node; '
             'Python 3.12.3, ONNX Runtime **1.24.4** CPU EP. Dependencies pinned in '
             '`bakeoff/llm/requirements.txt`. Go 1.25.1 is installed but not used for timing.', '',
             '- Exclusive speed runs: `taskset -c 16-23`; intra-op **1 / 4 / 8**, inter-op 1, sequential execution, '
             'full ORT graph optimization, worker spinning disabled equally for all sessions. One warm-up per prompt/configuration; '
             '**median of five runs**; 100 / 1000 exact prompt tokens, 32 post-first-token decode steps.',
             '- Same NumPy/ORT greedy autoregressive loop, empty attention caches and zero convolution/recurrent state per request. '
             'No sampling or repetition penalty, matching helium\'s current greedy behavior, **not** the cards\' recommended sampling '
             'or official benchmark settings. Qwen requires a separate embedding session; LFM directly accepts token IDs.',
             '- Speed text is the same repeated English document before per-tokenizer truncation. Tokenizers differ; '
             'forced continuation through EOS gives equal decode steps. Speed continuations are not quality samples. '
             'No cross-request prefix-cache reuse. TTFT begins before state allocation/Qwen embedding and ends after argmax/cache adoption; '
             'model load, tokenization and detokenization are excluded.',
             '- Both lengths at **4 and 8 threads for every model**. The supplemental Qwen 1-thread sweep uses 100 tokens only '
             'to stay near the three-hour budget; its 1000-token sweep was omitted, not estimated. All other 1-thread lengths were measured.',
             '- Peak process RSS captured with `/usr/bin/time -v`; native per-length peaks also recorded with Linux `ru_maxrss`. '
             'The LFM3 4-thread process also ran a full-logit experiment, which raises its process peak above native last-logit usage.',
             '- Qwen correctness-only requests were split into two **four-thread** processes on disjoint cores '
             '`16-19` / `20-23`. These request latencies and combined memory are **not speed/Pi measurements**. '
             'Both finished before exclusive speed resumed. Fixed fixtures and independent contexts; raw shard evidence retained.',
             '- Verification: six `unittest` groups passed; `summarize.py` independently rechecks parsed calls, '
             'continuations and instruction scores against retained raw output. Final report checks enforce '
             'completed ORT 1.24.4 speed processes, five trials/32 decode steps, ten voice turns and tables of at most five columns.',
             '- This host has ARM dot-product support; Pi 4 Cortex-A72 does not. Absolute speeds are optimistic for Pi 4, '
             'and **relative rankings need not carry over unchanged** when an export requests different compute precision. '
             'Shared-VM memory/cache contention and different tokenizers are additional caveats.', '',
             '## Key findings', '',
             '### 1. Native-export speed — Evidence: High on this VM', '',
             '`P` = prefill, `D` = post-first-token decode, all in tokens/s. Context lengths are 100 / 1000.', '']
    for name in LABEL:
        rows = []
        for t in [1, 4, 8]:
            a, b = med(name, t, 100), med(name, t, 1000)
            rows.append([t, val(a, 'prefill_tps'), val(b, 'prefill_tps'), val(a, 'decode_tps'), val(b, 'decode_tps')])
        lines += [f'**{LABEL[name]}**', '', table(['Threads', 'P100', 'P1k', 'D100', 'D1k'], rows), '']
    rows = []
    for name in LABEL:
        for t in [1, 4, 8]:
            a, b = med(name, t, 100), med(name, t, 1000)
            rows.append([f'{LABEL[name]} / {t}', val(a, 'ttft_s', 3), val(b, 'ttft_s', 3)])
    lines += ['**Warmed TTFT (seconds)**', '', table(['Model / threads', '100 tokens', '1000 tokens'], rows), '']
    rows = []
    for name in LABEL:
        for t in [1, 4, 8]:
            a, b = med(name, t, 100), med(name, t, 1000)
            rows.append([f'{LABEL[name]} / {t}', val(a, 'peak_rss_mib', 1), val(b, 'peak_rss_mib', 1),
                         f'{s["speed"][f"{name}-{t}t"]["process_peak_rss_mib"]:.1f}'])
    lines += ['**Peak RSS (MiB)** — native per-length peaks versus whole `/usr/bin/time -v` process.', '',
              table(['Model / threads', 'Native 100', 'Native 1k', 'Process max'], rows), '',
              'Qwen\'s native export projects **all prefill logits** (vocabulary 248,320); LFM normally keeps the last logit. '
              'At four threads, requesting all LFM3 logits reduced 1k prefill from 57.07 to 51.52 tok/s and raised process RSS '
              'from native 2608.7 to 3129.0 MiB. LFM2.5 full-logit prefill was 56.24 versus 56.58 tok/s, essentially unchanged. '
              'This explains some prefill difference, not the entire gap.', '',
              '### 2. Compute-policy control — Evidence: High', '',
              'Qwen: 249 four-bit `MatMulNBits` nodes, no accuracy attribute. LFM2.5: 93 four-bit nodes, no attribute. '
              'LFM3: 126 four-bit + 28 eight-bit nodes; all 154 specify **accuracy level 4**. All use block size 32. '
              'Float32 graph/cache interfaces do **not** mean kernels necessarily compute in float32.', '',
              'ORT 1.24.4 `GetComputeType` selects int8 input/int32 accumulation for level 4 **when that kernel is available**, '
              'otherwise float32. Derived control graphs change only this attribute for Qwen/LFM2.5; original exports and '
              'weight payloads are untouched. These controls have **not been quality-evaluated**.', '']
    rows = []
    for name in ['qwen-acc4', 'lfm25-acc4']:
        a, b = med(name, 4, 100), med(name, 4, 1000)
        rows.append([name, val(a, 'prefill_tps'), val(b, 'prefill_tps'), val(a, 'decode_tps'), val(b, 'decode_tps')])
    lines += [table(['4-thread control', 'P100', 'P1k', 'D100', 'D1k'], rows), '',
              'LFM2.5 becomes the fastest decoder under matched requested compute policy. Qwen improves ~3.9× at short '
              'context, leaving a ~2.5× gap to LFM3, rather than the native ~9.8× gap. Do not extrapolate the int8 benefit '
              'to a Pi 4 or assume numerical/quality parity after changing this setting. Derived graph hashes are in '
              '`bakeoff/llm/accuracy4_control.json`.', '',
              '### 3. Tools and instructions — Evidence: direct but bounded synthetic tests', '',
              'Predeclared `suites.py`: 36 tool cases, five schemas (`get_weather`, `create_reminder`, `search_notes`, '
              '`send_message`, `calculate`), 25 single calls, six no-tool/clarification cases, five dependent two-step cases. '
              'Fixed clock: Wednesday **2026-11-04 12:00 UTC**; includes today/tomorrow and relative reminders.', '',
              'Exact function name and argument dictionaries; only outer parameter whitespace is stripped. No real actions '
              'are executed. Two-step continuation uses a canonical ground-truth first call and deterministic mock result; '
              'case success requires correct first call **and** continuation. This is not unconstrained end-to-end agent execution. '
              'No-tool scoring checks absence of a call, not the quality of the clarification. Tool-call prose is allowed '
              'as in the templates. LFM2.5 spot uses its native Pythonic tool tokens, parsed with AST/literal_eval, never executed.', '']
    rows = []
    for name in LABEL:
        z = q[name]
        cats = z['tool_categories']
        rows.append([LABEL[name] + (' (spot)' if name == 'lfm25' else ''),
                     *[ratio_count(cats[c], 'pass', 'total') for c in ['single', 'no_tool', 'two_step']],
                     ratio_count(z, 'tool_pass', 'tool_total')])
    lines += [table(['Model', 'Single', 'No tool', 'Two-step', 'Total'], rows), '',
              'Thirty synthetic IFEval-style prompts: word limits/exact counts, JSON/CSV/list formats, one sentence, '
              'fixed translations, forbidden words and combined constraints. **Raw output removes only normal EOS markers**; '
              'final-only scoring additionally removes generated thinking. Word counts use a documented Unicode regex; '
              'sentence checks count terminal-punctuation boundaries; language uses fixed translation whitelists. '
              'These are not official IFEval scores or a general knowledge evaluation.', '']
    rows = []
    for name in LABEL:
        z = q[name]
        rows.append([LABEL[name] + (' (spot)' if name == 'lfm25' else ''), ratio_count(z, 'instruction_raw_pass', 'instruction_total'),
                     ratio_count(z, 'instruction_pass', 'instruction_total'), ratio_count(z, 'constraint_raw_pass', 'constraint_total'),
                     ratio_count(z, 'constraint_pass', 'constraint_total')])
    lines += [table(['Model', 'Raw prompts', 'Final prompts', 'Raw constraints', 'Final constraints'], rows), '',
              'Qwen failed only the six-word gravity definition, four-word snack, and ten-word cloud explanation. '
              'LFM2.5\'s three spot failures were exact word counts. LFM3\'s raw failures include reasoning duplication, '
              'format/language leakage, and lost answers; even after stripping thinking it passes only 18/30.', '',
              '### 4. Thinking control — Evidence: High for observed cases', '',
              'Both main models use the published templates with `enable_thinking=False`; the injected empty think '
              'block is **prompt text, not emitted reasoning**. Disabled output limit 192; enabled limit 512. '
              'Twenty paired prompts include all ten voice turns plus arithmetic/logical traps. Counts below are '
              'conservative **generated tag** counts; untagged verbose derivations are not automatically classified as private reasoning. '
              'The 101 off generations include ten repeated voice prompts, not 101 independent samples.', '']
    rows = []
    for name in LABEL:
        z = q[name]
        rows.append([LABEL[name], ratio_count(z, 'off_tag_emissions', 'off_generations'),
                     f'{z["off_truncations"]}/{z["off_generations"]}',
                     f'{z["mean_extra_tokens"]:.2f}' if z.get('thinking_pairs') else 'N/A',
                     f'{z["enabled_truncations"]}/{z["thinking_pairs"]}' if z.get('thinking_pairs') else 'N/A'])
    lines += [table(['Model', 'Off tags', 'Off trunc.', 'Mean extra tokens', 'On trunc.'], rows), '']
    rows = []
    for name in ['qwen', 'lfm3']:
        z = q[name]
        rows.append([LABEL[name], f'{z["enabled_mean_reasoning_tokens"]:.2f}', f'{z["enabled_mean_total_tokens"]:.2f}'])
    lines += [table(['Enabled / 20 pairs', 'Mean reasoning tokens', 'Mean total tokens'], rows), '',
              f'Qwen thinking-on hit the 512-token limit in **{q["qwen"]["enabled_truncations"]}/20** pairs. '
              'These averages/extra tokens are **censored lower bounds**, not measurements of unbounded thinking cost. '
              'LFM3 had one enabled truncation. Thinking tokens are those before the first `</think>`; absent a closing tag, '
              'the entire generated budget is counted as reasoning. Qwen quality-shard elapsed times are deliberately not compared.', '',
              'LFM3 tagged leakage breakdown: **0/41 tool requests**, **16/30 instruction turns**, **3/10 voice turns**, '
              '**8/20 paired off turns**. Four instruction turns (bedtime thought, walking tip, study tip, dog description) '
              'hit 192 tokens inside thinking without a final answer. Many leaks have **only an unexpected closing '
              '`</think>`**, preceded by reasoning then followed by a duplicate answer. A post-generation stripper cannot '
              'restore missing answers or guarantee clean low-latency streaming.', '',
              'A bill-splitting spot observation: LFM3 off wrongly said the $20 payer owes $10; enabled eventually correctly '
              'said the $10 payer owes the $20 payer $5, after 472 tokens. Its no-tag bat-and-ball off answer also gives an '
              'overlong algebra derivation. These are observations, not a scored reasoning benchmark.', '',
              '### 5. Assistant feel — raw non-thinking replies for owner judgment', '',
              'All ten turns use the same friendly/brief voice system prompt. **No tools are supplied in this section**, '
              'so the reminder checks honest limitations, not real scheduling. Scheduling is separately tested in the tool suite. '
              'Only normal EOS markers are removed below; generated thinking tags/repetition are preserved.', '']
    voice_maps = {name: {r['prompt']: r for r in q[name]['voice']} for name in LABEL}
    for i, prompt in enumerate(VOICE):
        lines += [f'#### Turn {i + 1}', '', f'**User:** {prompt}', '']
        for name in LABEL:
            if prompt not in voice_maps[name]:
                continue
            lines += [f'**{LABEL[name]}**' + (' (spot)' if name == 'lfm25' else ''), '```text',
                      assistant_visible_text(voice_maps[name][prompt]['text']), '```', '']
    lines += ['Judgment notes: both main models correctly advise against mixing bleach and vinegar, but LFM3 incorrectly '
              'names **chloramine** rather than **chlorine**, and repeats the warning around a thinking closer. '
              'Qwen\'s reminder offers an immediate reminder instead of the requested timed one; LFM3 clearly declines scheduling; '
              'LFM2.5 answers “Sure!” then says to drink now. All require actual tool plumbing for timers.', '',
              '### 6. What helium\'s Qwen loop already handles — Evidence: High', '',
              '- State binding names already match: `past_conv.N → present_conv.N`, '
              '`past_key_values.N.* → present.N.*`. Zero fixed conv state/empty attention caches and greedy last-logit '
              'selection transfer. Qwen has 24 conv + 24 recurrent states + eight KV pairs; LFM3 has 13 conv + 11 KV pairs; '
              'LFM2.5 has ten conv + six KV pairs. No recurrent state is required by LFM.',
              '- The **unmodified engine will not load LFM**: it requires separate embedding/decoder graphs and '
              '`inputs_embeds`; LFM is one graph accepting `input_ids`. LFM positions are `[B,S]`, not Qwen\'s `[3,B,S]`, '
              'and LFM requires int64 `logits_to_keep=[1]`. Attention masks remain `[B,total_S]`; all tested caches are float32.',
              '- **No new operators** versus the union of Qwen embedding + decoder. LFM\'s `GatherBlockQuantized` is '
              'already in Qwen\'s embedding graph. Opset 21 + Microsoft domain 1. Full recursive inventories/I/O are '
              'in `graphs.json`. Qwen\'s older decoder includes 24 `Scan` operators; LFM has no recurrent scans.',
              '- Liquid tokenizers are byte-level BPE with metadata-driven split regexes, but **no NFC normalizer**; '
              'helium applies NFC unconditionally. BOS/EOS IDs and chat/tool templates differ; tokenizer parity must be '
              'tested, not assumed. The existing `FormatChat` does not render the non-thinking prefix used here.',
              '- “Single graph” is still **graph + external weight sidecar + tokenizer/config assets**, not a literal '
              'one-model-file distribution. The planned bundle remains necessary.', '',
              'The requested Qwen graph headers were SHA256-verified byte-identical to helium\'s Cattery-hosted '
              'embedding/decoder files; registry weight sizes match. Those weight payloads were not re-fetched. '
              'See `cattery_graph_check.json`.', '',
              'A newer linked Qwen `Qwen3.5-4B-ONNX-OPT` export uses `CausalConvWithState`, `LinearAttention`, '
              'scalar `num_logits_to_keep`, and conv cache length 3 rather than 4. Neither new operator is registered '
              'in this ORT 1.24.4 wheel; minimal-op probes fail with “not a registered function/op”, and the graph '
              'has no embedded fallback functions. **Metadata only; no OPT weights downloaded or benchmark claims.** '
              'See `qwen_opt_probe.json`. Revisit only with a compatible runtime.', '',
              '## Contradictions and uncertainty', '',
              '- LFM3\'s thinking-disable warning is empirically confirmed for this export/common greedy runtime; '
              'vendor IFEval/BFCL advantages are **not independently reproduced** by this small suite. Different '
              'precision, thinking, sampling, caps and test distributions mean this does not prove the vendor card is wrong.',
              '- Tool cases are mostly unambiguous and easy; 36/36 is not general agent safety or BFCL reliability. '
              'No actual tool side effects, long dialogues, retrieval corpus, adversarial instructions, or multilingual '
              'tool suite were tested.',
              '- Compute controls can change logits/outputs. No full quality/parity test was run for those derived graphs. '
              'Neither Altra int8 speedups nor Python RSS are verified Pi 4/Go measurements.',
              '- The Qwen 1-thread 1k sweep was omitted for budget. Thinking-on limits censor overhead; no uncapped '
              'run was attempted. The benchmark is roughly three hours, not a production soak.', '',
              '## Recommendation', '',
              '**Global default: keep Qwen3.5-4B, non-thinking for voice/chat.** It follows the tested constraints much '
              'more reliably and honors thinking disable in these samples. Its current four-thread native export is '
              '**not low-latency enough for comfortable voice**; prioritize validating a faster export/compute policy '
              'and/or prefix reuse rather than promoting an unreliable reasoning toggle. Keeping the model does not '
              'mean the current Go formatter already implements the tested template.', '',
              '**LFM3: opt-in tool-first alternative.** Half the ONNX asset size and much higher native decoder speed '
              'are real. Its clean tool context is encouraging, but do not make it the global voice/chat default until '
              'plain constrained turns, streaming, and thinking-disable behavior are fixed or robustly guarded. '
              'Hiding tags alone does not recover four missing answers.', '',
              '**Pi-class: LFM2.5-1.2B-Instruct, yes by size and short-context working memory; no unconditional '
              '≤1.5 GB RSS guarantee.** Good quick tool spot, acceptable short replies, non-thinking checkpoint, '
              'but imperfect exact word counts and unproven physical Pi 4 latency. Keep prompts/context bounded.', '',
              'Recommendation confidence: **moderate** for the product choice; high for these measured behaviors on '
              'this VM. Nothing is wired into helium by this lane.', '',
              '## Next steps', '',
              '1. Owner judges the raw voice replies; retain Qwen and ensure future voice/chat rendering actually '
              'passes the non-thinking convention (current Go formatter does not).',
              '2. Validate quality/parity of the accuracy-level-4 controls before adopting any derived export; '
              'surface different compute policies in future model manifests/benchmark notes.',
              '3. Benchmark LFM2.5 on a physical Pi 4 with memory/context caps. Measure Go RSS and shared STT/TTS/LLM '
              'working memory, not only this Python process.',
              '4. Re-test LFM3 with vendor sampling, explicit guards and always-tools voice contexts; verify streaming '
              'and latency under failures before considering global promotion. A compatible future ORT/Qwen OPT export '
              'also deserves a new bake-off.', '',
              '## Model provenance, licenses and hashes', '']
    rows = []
    for name, data in manifest.items():
        size = sum(v['bytes'] for k, v in data['files'].items() if k.startswith('onnx/'))
        rows.append([LABEL[name], f'{size / 1e9:.3f} / {size / 2**30:.3f}', 'Apache-2.0' if name == 'qwen' else 'LFM Open License v1.0'])
    lines += [table(['Model', 'ONNX assets GB / GiB', 'Weight license'], rows), '',
              'LFM license accepted by the owner. Redistribution requires the license/notices and marking modified '
              'files; commercial use has the $10M legal-entity revenue limitation. The definition says “$10M or more” '
              'while Section 5 says “exceeds”; do not promise eligibility exactly at the boundary. This is not Apache-2.0. '
              'No weights or external datasets are committed. Model files: `~/models/llm/`; complete raw JSONL and '
              '`/usr/bin/time -v` evidence: `~/datasets/llm/results/` (Qwen shard details under `shards/`). '
              'No WAV/listening samples apply to this text-only lane.', '',
              '**Authoritative manifest:** `bakeoff/llm/manifest.json` records sizes/SHA256 for every downloaded '
              'graph, weight file, tokenizer, template, config and card/license. `summary.json` records checked scores, '
              'medians and raw-result fingerprints. Exact graph/weight URLs and SHA256 are reproduced below.', '']
    for name, data in manifest.items():
        lines += [f'### {LABEL[name]}', '', f'- Repository: https://huggingface.co/{data["repo"]}',
                  f'- Immutable revision: `{data["revision"]}`', '']
        for file, item in data['files'].items():
            if file.startswith('onnx/'):
                url = f'https://huggingface.co/{data["repo"]}/resolve/{data["revision"]}/{file}'
                lines += [f'- [`{file}`]({url})', f'  - SHA256: `{item["sha256"]}`']
        lines += ['']
    lines += ['## Sources consulted', '',
              '- Local: `koder/STATE.md`, `koder/research/02_model_survey.md` — baseline and vendor-claim context.',
              '- Local: `llm/qwen/qwen.go`, `llm/qwen/decode.go`, `llm/qwen/tokenizer.go`, `registry/registry.go` — '
              'actual engine/session/cache/normalization/formatter assumptions.',
              '- Model cards and templates at the immutable repositories/revisions above; base cards/licenses: '
              'https://huggingface.co/Qwen/Qwen3.5-4B , https://huggingface.co/LiquidAI/LFM3-1.7B , '
              'https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct .',
              '- ORT 1.24.4 source, `ACCURACY_LEVEL` / `GetComputeType`, lines 37–61: '
              'https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/contrib_ops/cpu/quantization/matmul_nbits.cc',
              '- Metadata-only Qwen OPT repository: https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX-OPT '
              '(revision `bb072268d0912bdc5cf4f41c8c6f53a03fd68624`, graph SHA256 '
              '`97a9351ca56a3e736f2bd9eac33de321224e7b0f97fcf30c7540a8b93371f699`).',
              '- Cattery graph URLs and matching SHA256: `bakeoff/llm/cattery_graph_check.json`.', '']
    target = Path('koder/research/03_bakeoff_llm.md')
    target.write_text('\n'.join(lines))
    print(target)


if __name__ == '__main__':
    main()
