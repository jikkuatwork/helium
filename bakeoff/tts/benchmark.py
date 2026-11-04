"""One isolated measurement cell. Wrap with /usr/bin/time -v, taskset 0-7."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import time

import soundfile as sf
from runners import Phonon, Kokoro


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=['kokoro', 'phonon-int8', 'phonon-fp32', 'phonon-mixed'], required=True)
    p.add_argument('--threads', type=int, choices=[1,4], required=True)
    p.add_argument('--shape', choices=['short','paragraph','long'], required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    text = json.loads((Path.home()/'datasets/tts/speed_texts.json').read_text())[a.shape]
    start = time.perf_counter()
    if a.model == 'kokoro': e = Kokoro(threads=a.threads)
    else: e = Phonon(precision='fp32' if a.model == 'phonon-fp32' else 'int8', threads=a.threads,
                     decoder_precision='fp32' if a.model == 'phonon-mixed' else None)
    load = time.perf_counter()-start
    _, warm = e.speak(text)
    rows = []
    for i in range(5):
        pcm, result = e.speak(text)
        rows.append(result)
        print(json.dumps({'model':a.model,'threads':a.threads,'shape':a.shape,'run':i,**result}),flush=True)
    out = {'model':a.model,'threads':a.threads,'shape':a.shape,'words':len(text.split()),
           'load_s':load,'warmup':warm,'runs':rows,
           'median':{key:statistics.median(x[key] for x in rows) for key in ['wall_s','ttfa_s','audio_s','rtfx']},
           'ru_maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    sf.write(str(Path.home()/f'datasets/tts/bench-{a.model}-{a.threads}-{a.shape}.wav'),pcm,24000,subtype='FLOAT')

if __name__ == '__main__': main()
