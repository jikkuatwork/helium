#!/usr/bin/env python3
"""Prepare WAVs for the actual Go engine and compare its full 740-case output."""
import argparse
import json
from pathlib import Path
import soundfile as sf
from bench import DATA, add_noise, aggregate, read_audio

OUT = Path('bakeoff/stt/results')
p = argparse.ArgumentParser(__doc__)
p.add_argument('command', choices=['prepare', 'compare'])
args = p.parse_args()
if args.command == 'prepare':
    rows = json.loads((DATA/'manifest.json').read_text())
    cases = [{**r, 'snr': None} for r in rows]
    cases += [{**r, 'snr': snr} for snr in [10, 0] for r in rows[:50]]
    wavdir = DATA/'actual-wavs'
    wavdir.mkdir(exist_ok=True)
    for r in cases:
        x = read_audio(r['path'])
        if r['snr'] is not None:
            x = add_noise(x, r['snr'], r['id'])
        path = wavdir/f"{r['id']}-{r['snr']}.wav"
        sf.write(path, x, 16000, subtype='PCM_16' if r['snr'] is None else 'FLOAT')
        r['path'] = str(path)
    (DATA/'actual-manifest.json').write_text(json.dumps(cases, indent=2))
    print('prepared', len(cases))
else:
    actual = [json.loads(line) for line in (OUT/'helium-actual.jsonl').read_text().splitlines()]
    expected = []
    for name in ['moonshine-accuracy', 'moonshine-noise-10', 'moonshine-noise-0']:
        expected.extend(json.loads(line) for line in (OUT/f'{name}.jsonl').read_text().splitlines())
    assert len(actual) == len(expected) == 740
    different = []
    for a, e in zip(actual, expected):
        assert (a['id'], a['snr']) == (e['id'], e['snr'])
        if a['hypothesis'] != e['hypothesis']:
            different.append({'id': a['id'], 'snr': a['snr'], 'helium_text': a['hypothesis'], 'python_text': e['hypothesis']})
    summary = {'cases': 740, 'exact_matches': 740-len(different), 'differences': different, 'accuracy': {}}
    for split in ['test-clean','test-other']:
        summary['accuracy'][split] = aggregate([r for r in actual if r['split']==split and r['snr'] is None])
    for snr in [10,0]:
        summary['accuracy'][f'noise_{snr}db'] = aggregate([r for r in actual if r['snr']==snr])
    # Actual-process RSS is in helium-actual.rss.txt, not this scorer's RSS.
    for stats in summary['accuracy'].values():
        stats.pop('peak_rss_kib')
    (OUT/'helium-actual.summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
