#!/usr/bin/env python3
"""Aggregate reproducible WER, paired bootstrap, RSS and timing from raw logs."""
import json
from pathlib import Path
import statistics
import jiwer
import numpy as np
from bench import DATA, normalize

OUT = Path(__file__).resolve().parent / 'results'


def rows(model):
    return [json.loads(line) for line in (OUT/f'{model}-accuracy.jsonl').read_text().splitlines()]


def paired_bootstrap(a, b, draws=2000):
    assert [r['id'] for r in a] == [r['id'] for r in b]
    counts = []
    for x, y in zip(a, b):
        w = jiwer.process_words(normalize(x['reference']), normalize(x['hypothesis']))
        v = jiwer.process_words(normalize(y['reference']), normalize(y['hypothesis']))
        counts.append((w.hits+w.substitutions+w.deletions,
                       w.substitutions+w.deletions+w.insertions,
                       v.substitutions+v.deletions+v.insertions))
    counts = np.asarray(counts)
    rng = np.random.default_rng(20261104)
    totals = counts[rng.integers(0, len(a), (draws, len(a)))].sum(axis=1)
    difference = (totals[:, 2] - totals[:, 1])/totals[:, 0]*100
    return {'delta_wer_percentage_points': float((counts[:, 2].sum()-counts[:, 1].sum())/counts[:, 0].sum()*100),
            'paired_utterance_bootstrap_95_ci_pp': list(np.quantile(difference, [0.025, 0.975])),
            'draws': draws, 'seed': 20261104}


def main():
    result = {'accuracy': {}, 'timing': {}, 'paired': {}}
    available = [m for m in ['moonshine', 'parakeet', 'parakeet-fp32', 'large'] if (OUT/f'{m}-accuracy.summary.json').exists()]
    for model in available:
        result['accuracy'][model] = json.loads((OUT/f'{model}-accuracy.summary.json').read_text())
        for snr in [10, 0]:
            p = OUT/f'{model}-noise-{snr}.summary.json'
            if p.exists():
                result['accuracy'][model][f'noise_{snr}db'] = json.loads(p.read_text())['test-clean']
    for a, b in [('moonshine', 'parakeet'), ('parakeet-fp32', 'parakeet'), ('parakeet', 'large')]:
        if a not in available or b not in available:
            continue
        ar, br = rows(a), rows(b)
        result['paired'][f'{a}_to_{b}'] = {split: paired_bootstrap(
            [r for r in ar if r['split'] == split], [r for r in br if r['split'] == split])
            for split in ['test-clean', 'test-other']}
    for path in sorted(OUT.glob('*.json')):
        if path.name.endswith('.summary.json') or path.name == 'summary.json':
            continue
        try:
            t = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(t, dict) and 'median_rtf' in t:
            result['timing'][path.stem] = {k: v for k, v in t.items() if k != 'hypothesis'}
        elif isinstance(t, dict) and 'wall_seconds' in t and 'result' in t:
            duration = t['result']['Duration']
            rss_path = path.with_suffix('.rss.txt')
            rss = None
            if rss_path.exists():
                for line in rss_path.read_text().splitlines():
                    if 'Maximum resident set size' in line:
                        rss = int(line.rsplit(':', 1)[1].strip())
            entry = {'duration': duration, 'runs_seconds': t['wall_seconds'],
                     'median_seconds': statistics.median(t['wall_seconds']),
                     'median_rtf': statistics.median(t['wall_seconds'])/duration,
                     'peak_rss_kib': rss, 'threads': t.get('threads')}
            if 'long' in path.stem:
                minutes = path.stem.split('long')[1].split('-')[0]
                ref = next(r['reference'] for r in json.loads((DATA/'long.json').read_text()) if r['id'] == f'long-{minutes}min')
                entry['wer'] = jiwer.wer(normalize(ref), normalize(t['result']['Text']))
            result['timing'][path.stem] = entry
    (OUT/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
