#!/usr/bin/env python3
"""Boundary probe for the sherpa CTC export's fixed relative-position cache.

One call per length: this is a graph-validity test, not a speed benchmark.
"""
import json
from pathlib import Path
import resource
import time
from bench import Parakeet, SAMPLES, read_audio

model = Parakeet(4)
x = read_audio(SAMPLES/'long-12min.wav')
rows = []
# The extra frontend frame gives T=5001 in a tiny edge band: the position
# Slice has one row there and Add silently broadcasts it. T=5002 hard-fails.
for samples in [6_401_279, 6_401_280]:
    start = time.perf_counter()
    try:
        text = model(x[:samples])
        row = {'samples': samples, 'seconds': samples/16000, 'success': True,
               'hypothesis_words': len(text.split())}
    except Exception as error:
        row = {'samples': samples, 'seconds': samples/16000, 'success': False,
               'exception': str(error)}
    row['elapsed_seconds_single_probe'] = time.perf_counter()-start
    row['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rows.append(row)
    print(json.dumps(row), flush=True)
Path('bakeoff/stt/results/length-boundary.json').write_text(json.dumps(rows, indent=2))
assert rows[0]['success'] and not rows[1]['success'], rows
