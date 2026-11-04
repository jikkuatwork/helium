#!/usr/bin/env python3
"""Compare 10 exact helium engine outputs to the fair Python Moonshine loop."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import soundfile as sf
from bench import DATA, read_audio

rows = [json.loads(line) for line in Path('bakeoff/stt/results/moonshine-accuracy.jsonl').read_text().splitlines()][:10]
checks = []
with tempfile.TemporaryDirectory(prefix='parity-', dir=DATA) as temporary:
    for row in rows:
        wav = Path(temporary)/f"{row['id']}.wav"
        sf.write(wav, read_audio(row['path']), 16000, subtype='PCM_16')
        run = subprocess.run(['taskset', '-c', '8-15', '/tmp/stt-helium-probe', '-runs', '1', str(wav)],
                             env={**os.environ, 'HELIUM_BAKE_THREADS': '4'}, text=True, capture_output=True, check=True)
        go = json.loads(run.stdout)
        checks.append({'id': row['id'], 'exact_text_equal': row['hypothesis'] == go['result']['Text'],
                       'python_text': row['hypothesis'], 'helium_text': go['result']['Text'],
                       'ort_version': go['ort_version'], 'threads': go['threads']})
Path('bakeoff/stt/results/moonshine-parity.json').write_text(json.dumps(checks, indent=2))
print(json.dumps({'clips': len(checks), 'exact_matches': sum(r['exact_text_equal'] for r in checks)}, indent=2))
assert all(r['exact_text_equal'] for r in checks), checks
