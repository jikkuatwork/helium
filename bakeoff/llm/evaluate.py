#!/usr/bin/env python3
"""Run warmed speed trials or synthetic quality; persist each request immediately."""
import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path

import onnxruntime as ort
from runner import Runner
from suites import (TOOLS, TOOL_SYSTEM, VOICE_SYSTEM, VOICE, THINK, tool_cases,
                    instruction_cases, final_text, emitted_reasoning, parse_calls, parse_pythonic_calls, validate_instruction)


def emit(path, obj):
    with path.open('a') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    print(obj.get('id', obj.get('kind')), obj.get('pass', ''), obj.get('generated_tokens', ''), flush=True)


def speed(r, path, repeats, tokens):
    for n in [100, 1000]:
        # Same text repeated, independently tokenized then exactly truncated to length.
        ids = r.encode(r.render([{'role': 'user', 'content': 'This is a short document about weather, travel, shopping, and personal reminders. ' * 300}]))[:n]
        assert len(ids) == n
        r.generate(ids, max_tokens=tokens, force_length=True)
        rows = []
        for i in range(repeats):
            result = r.generate(ids, max_tokens=tokens, force_length=True)
            result.update(kind='speed', id=f'speed{n}_{i}', run=i, full_logits=False)
            emit(path, result)
            rows.append(result)
        summary = {k: statistics.median(row[k] for row in rows) for k in ['ttft_s', 'prefill_tps', 'decode_tps', 'total_s', 'peak_rss_mib']}
        summary.update(kind='median', id=f'median{n}', prompt_tokens=n, repeats=repeats, decode_steps=tokens-1)
        emit(path, summary)
    # Isolate export's last-token-logits advantage; native Qwen always computes full logits.
    if r.model != 'qwen':
        ids = r.encode('This is a short document about weather and reminders. ' * 300)[:1000]
        r.generate(ids, max_tokens=2, force_length=True, full_logits=True)
        rows = []
        for i in range(repeats):
            result = r.generate(ids, max_tokens=2, force_length=True, full_logits=True)
            result.update(kind='full_logits', id=f'full_logits1000_{i}', run=i, full_logits=True)
            emit(path, result)
            rows.append(result)
        emit(path, {'kind': 'full_logits_median', 'id': 'full_logits_median1000', 'ttft_s': statistics.median(x['ttft_s'] for x in rows), 'prefill_tps': statistics.median(x['prefill_tps'] for x in rows)})


def quality(r, path, spot=False):
    r.chat([{'role': 'user', 'content': 'Say hello.'}], max_tokens=8)
    parse = parse_pythonic_calls if r.model == 'lfm25' else parse_calls
    for case in (tool_cases() if not spot else tool_cases()[::4]):
        messages = [{'role': 'system', 'content': TOOL_SYSTEM}, {'role': 'user', 'content': case['prompt']}]
        result = r.chat(messages, tools=TOOLS, max_tokens=192)
        parsed = parse(final_text(result['text']))
        first_ok = parsed == case['expected']
        result.update(kind='tool', id=case['id'], case=case, parsed=parsed, first_pass=first_ok,
                      reasoning_leak=emitted_reasoning(result['text']))
        if 'second_expected' in case:
            # Always test continuation with ground-truth first call, not corrupted history.
            # Also score end-to-end as conjunction of first + continuation, making failures visible.
            tc = case['expected'][0]
            assistant = {'role': 'assistant', 'content': '', 'tool_calls': [{'type': 'function', 'id': 'call_1', 'function': tc}]}
            if r.model == 'lfm25':
                arg_text = ', '.join(k + '=' + repr(v) for k, v in tc['arguments'].items())
                assistant['content'] = '<|tool_call_start|>[' + tc['name'] + '(' + arg_text + ')]<|tool_call_end|>'
            messages += [assistant, {'role': 'tool', 'tool_call_id': 'call_1', 'name': tc['name'], 'content': json.dumps(case['tool_result'])}]
            second = r.chat(messages, tools=TOOLS, max_tokens=192)
            second_parsed = parse(final_text(second['text']))
            result['second'] = second
            result['second_parsed'] = second_parsed
            result['second_pass'] = second_parsed == case['second_expected']
            result['pass'] = first_ok and result['second_pass']
        else:
            result['pass'] = first_ok
        emit(path, result)
    for case in (instruction_cases() if not spot else instruction_cases()[::3]):
        result = r.chat([{'role': 'user', 'content': case['prompt']}], max_tokens=192)
        checks = validate_instruction(result['text'], case['rules'])
        result.update(kind='instruction', id=case['id'], case=case, checks=checks, **{'pass': all(checks.values())}, reasoning_leak=emitted_reasoning(result['text']))
        emit(path, result)
    for i, prompt in enumerate(VOICE if not spot else VOICE[:5]):
        result = r.chat([{'role': 'system', 'content': VOICE_SYSTEM}, {'role': 'user', 'content': prompt}], max_tokens=192)
        result.update(kind='voice', id=f'voice{i}', prompt=prompt, reasoning_leak=emitted_reasoning(result['text']))
        emit(path, result)
    if spot:
        return
    for i, prompt in enumerate(THINK):
        messages = [{'role': 'system', 'content': VOICE_SYSTEM}, {'role': 'user', 'content': prompt}]
        for enabled in [False, True]:
            result = r.chat(messages, thinking=enabled, max_tokens=512 if enabled else 192)
            text = result['text']
            closing = r.tokenizer.encode('</think>', add_special_tokens=False)
            close_idx = None
            for j in range(len(result['ids'])):
                if result['ids'][j:j+len(closing)] == closing:
                    close_idx = j
                    break
            result.update(kind='thinking', id=f'think{i}_{enabled}', prompt=prompt, enabled=enabled,
                          reasoning_tokens=(close_idx if close_idx is not None else result['generated_tokens']) if enabled else 0,
                          reasoning_leak=emitted_reasoning(text) if not enabled else None)
            emit(path, result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['speed', 'quality'])
    p.add_argument('--model', choices=['qwen', 'lfm3', 'lfm25'], required=True)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--tokens', type=int, default=33, help='one prefill token + 32 timed decode tokens')
    p.add_argument('--spot', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise RuntimeError('Refusing to overwrite existing results: ' + str(a.out))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    r = Runner(a.model, a.threads)
    emit(a.out, {'kind': 'environment', 'ort': ort.__version__, 'python': platform.python_version(), 'model': a.model, 'threads': a.threads,
                 'affinity': sorted(os.sched_getaffinity(0)), 'load_s': r.load_s, 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    if a.mode == 'speed': speed(r, a.out, a.repeats, a.tokens)
    else: quality(r, a.out, a.spot)


if __name__ == '__main__':
    main()
