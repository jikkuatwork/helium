#!/usr/bin/env python3
"""Summarize stored evidence, rechecking all scores. Does not run inference."""
import argparse
import hashlib
import json
import re
import statistics
from pathlib import Path
from suites import parse_calls, parse_pythonic_calls, validate_instruction, final_text


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=Path.home() / 'datasets/llm/results')
    p.add_argument('--out', type=Path, default=Path('bakeoff/llm/summary.json'))
    a = p.parse_args()
    out = {'speed': {}, 'quality': {}, 'evidence': {}}
    for path in sorted(a.root.glob('*.jsonl')):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        env = rows[0]
        name = env['model']
        key = f'{name}-{env["threads"]}t'
        out['evidence'][path.name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size, 'rows': len(rows)}
        if path.name.startswith('speed-'):
            out['speed'][key] = {'medians': [r for r in rows if r['kind'] in ['median', 'full_logits_median']], 'environment': env}
            timefile = path.with_suffix('.time')
            if timefile.exists():
                text = timefile.read_text()
                match = re.search(r'Maximum resident set size \(kbytes\): (\d+)', text)
                out['speed'][key]['process_peak_rss_mib'] = int(match.group(1)) / 1024 if match else None
                out['speed'][key]['process_exit_success'] = 'Exit status: 0' in text
            continue
        if not path.name.startswith('quality-'):
            continue
        parse = parse_pythonic_calls if name == 'lfm25' else parse_calls
        tools = [r for r in rows if r['kind'] == 'tool']
        ins = [r for r in rows if r['kind'] == 'instruction']
        voice = [r for r in rows if r['kind'] == 'voice']
        thinking = [r for r in rows if r['kind'] == 'thinking']
        for r in tools:
            assert parse(final_text(r['text'])) == r['parsed']
            assert (r['parsed'] == r['case']['expected']) == r['first_pass']
            if 'second' in r:
                assert parse(final_text(r['second']['text'])) == r['second_parsed']
                assert r['pass'] == (r['first_pass'] and r['second_pass'])
        for r in ins:
            assert validate_instruction(r['text'], r['case']['rules']) == r['checks']
        q = {'quality_timings_comparable': env.get('quality_timings_comparable', True),
             'tool_total': len(tools), 'tool_pass': sum(r['pass'] for r in tools),
             'tool_categories': {}, 'instruction_total': len(ins), 'instruction_pass': sum(r['pass'] for r in ins),
             'instruction_raw_pass': sum(all(validate_instruction(r['text'], r['case']['rules'], strip_thinking=False).values()) for r in ins),
             'constraint_raw_pass': sum(sum(validate_instruction(r['text'], r['case']['rules'], strip_thinking=False).values()) for r in ins),
             'instruction_raw_failures': [{'id': r['id'], 'prompt': r['case']['prompt'], 'text': r['text'], 'checks': validate_instruction(r['text'], r['case']['rules'], strip_thinking=False)} for r in ins if not all(validate_instruction(r['text'], r['case']['rules'], strip_thinking=False).values())],
             'constraint_pass': sum(sum(r['checks'].values()) for r in ins), 'constraint_total': sum(len(r['checks']) for r in ins),
             'instruction_failures': [{'id': r['id'], 'prompt': r['case']['prompt'], 'text': final_text(r['text']), 'checks': r['checks']} for r in ins if not r['pass']],
             'tool_failures': [{'id': r['id'], 'prompt': r['case']['prompt'], 'text': r['text'], 'parsed': r['parsed'], 'expected': r['case']['expected'],
                                'second_text': r.get('second', {}).get('text'), 'second_parsed': r.get('second_parsed'), 'second_expected': r['case'].get('second_expected')} for r in tools if not r['pass']],
             'voice': [{'prompt': r['prompt'], 'text': r['text'], 'final_text': final_text(r['text']), 'generated_tokens': r['generated_tokens'], 'total_s': r['total_s']} for r in voice]}
        for category in ['single', 'no_tool', 'two_step']:
            rs = [r for r in tools if r['case']['category'] == category]
            q['tool_categories'][category] = {'total': len(rs), 'pass': sum(r['pass'] for r in rs)}
        seconds = [r for r in tools if 'second' in r]
        q['continuation_pass'] = sum(r['second_pass'] for r in seconds)
        q['continuation_total'] = len(seconds)
        off = [r for r in rows if r['kind'] in ['tool', 'instruction', 'voice'] or (r['kind'] == 'thinking' and not r['enabled'])]
        off_second = [r['second'] for r in tools if 'second' in r]
        from suites import emitted_reasoning
        q['off_generations'] = len(off) + len(off_second)
        q['off_tag_emissions'] = sum(bool(re.search(r'<think>|</think>|<reasoning>|<analysis>', r['text'])) for r in off + off_second)
        q['off_reasoning_leaks'] = sum(emitted_reasoning(r['text']) for r in off + off_second)
        q['off_truncations'] = sum(r['finish'] == 'length' for r in off + off_second)
        q['off_leak_outputs'] = [{'id': r.get('id'), 'text': r['text']} for r in off + off_second if emitted_reasoning(r['text'])]
        enabled = [r for r in thinking if r['enabled']]
        disabled = [r for r in thinking if not r['enabled']]
        q['thinking_pairs'] = min(len(enabled), len(disabled))
        if enabled:
            off_by_prompt = {r['prompt']: r for r in disabled}
            pairs = [(r, off_by_prompt[r['prompt']]) for r in enabled if r['prompt'] in off_by_prompt]
            q['enabled_mean_reasoning_tokens'] = statistics.mean(r['reasoning_tokens'] for r in enabled)
            q['enabled_mean_total_tokens'] = statistics.mean(r['generated_tokens'] for r in enabled)
            q['enabled_truncations'] = sum(r['finish'] == 'length' for r in enabled)
            if pairs:
                q['mean_extra_tokens'] = statistics.mean(on['generated_tokens'] - off['generated_tokens'] for on, off in pairs)
                q['mean_extra_seconds'] = statistics.mean(on['total_s'] - off['total_s'] for on, off in pairs) if q['quality_timings_comparable'] else None
            q['paired_off_leaks'] = sum(emitted_reasoning(r['text']) for r in disabled)
        out['quality'][name] = q
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(a.out)


if __name__ == '__main__':
    main()
