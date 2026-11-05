#!/usr/bin/env bash
# Bake-off candidates (Phonon int8 TTS, Parakeet 110M int8 STT) at 1 thread on the 1 vCPU / 1 GiB box.
# Uses the landed harness in ~/work/helium/bakeoff/ unchanged. Results: ~/bench/cand/.
set -uo pipefail
cd ~/work/helium
OUT=~/bench/cand; mkdir -p "$OUT" ~/datasets/tts ~/bakeoff-samples/stt
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
log() { echo "[cand] $*"; }
if [ ! -x ~/models/venv/bin/python ]; then
  log "venv"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv >/dev/null
  python3 -m venv ~/models/venv
  ~/models/venv/bin/pip -q install -c bakeoff/tts/requirements.txt numpy onnxruntime ptts tokenizers soundfile scipy
  ~/models/venv/bin/pip -q install -c bakeoff/stt/requirements.txt onnx-asr jiwer
fi
PY=~/models/venv/bin/python
log "ort $($PY -c 'import onnxruntime as o; print(o.__version__)')"
log "fetch Phonon int8 (pinned HF revision) and Parakeet 110M int8 (pinned, sha-checked)"
$PY - <<'PYX'
import sys, urllib.request
from pathlib import Path
sys.path.insert(0, 'bakeoff/tts'); import download as td, corpus
root = Path.home()/'models/tts/phonon'
files = ['config.json','generation_config.json','tokenizer.json','tokenizer_config.json','processor_config.json',
         'preprocessor_config.json','voices/default.bin','voices/LMDIYE0Oa377Qh6Z.bin','voices/NbpkqMVS3CJeq2j8.bin',
         'voices/voices.jsonl'] + [f'onnx/{n}.onnx{s}' for n in ['model_int8','mimi_decoder_int8'] for s in ['', '_data']]
for name in files:
    p = root/name; p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        try: urllib.request.urlretrieve(f'https://huggingface.co/{td.PHONON_REPO}/resolve/{td.PHONON_REV}/{name}', p)
        except Exception as e: print('skip', name, e)
import json
(Path.home()/'datasets/tts/speed_texts.json').write_text(json.dumps({'short': corpus.SHORT, 'paragraph': corpus.PARAGRAPH, 'long': corpus.LONG}))
import importlib.util  # both bake-off folders have download.py; load the STT one by path
spec = importlib.util.spec_from_file_location('stt_download', 'bakeoff/stt/download.py')
sd = importlib.util.module_from_spec(spec); spec.loader.exec_module(sd)
for a in sd.ASSETS:
    if 'parakeet110/model.int8' in a[0] or 'parakeet110/tokens' in a[0]: sd.fetch(*a)
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
for n in ['note10', 'min1', 'min5']:
    x, sr = sf.read(str(Path.home()/f'bench/inputs/{n}.wav'), dtype='float32')
    sf.write(str(Path.home()/f'bakeoff-samples/stt/{n}-16k.wav'), resample_poly(x, 2, 3).astype('float32'), 16000, subtype='PCM_16')
print('fetched')
PYX
for shape in short paragraph long; do
  log "phonon-int8 1t $shape"
  /usr/bin/time -v -o "$OUT/phonon-int8-1-$shape.time.txt" $PY bakeoff/tts/benchmark.py --model phonon-int8 --threads 1 \
    --shape "$shape" --output "$OUT/phonon-int8-1-$shape.json" > "$OUT/phonon-int8-1-$shape.log" 2>&1
  log "  rc=$? $(grep -o '"rtfx": [0-9.]*' "$OUT/phonon-int8-1-$shape.json" 2>/dev/null | tail -1) rss=$(grep -o 'Maximum resident set size (kbytes): [0-9]*' "$OUT/phonon-int8-1-$shape.time.txt" | grep -o '[0-9]*$')KiB"
done
for spec in "note10 5 0" "min1 3 0" "min5 1 30"; do
  set -- $spec
  log "parakeet 1t $1 chunk=$3"
  /usr/bin/time -v -o "$OUT/parakeet-1-$1.time.txt" $PY bakeoff/stt/bench.py timing --model parakeet --threads 1 \
    --audio ~/bakeoff-samples/stt/$1-16k.wav --runs "$2" --chunk "$3" --output "$OUT/parakeet-1-$1.json" > "$OUT/parakeet-1-$1.log" 2>&1
  log "  rc=$? $(grep -o '"median_rtf": [0-9.e-]*' "$OUT/parakeet-1-$1.json" 2>/dev/null) rss=$(grep -o 'Maximum resident set size (kbytes): [0-9]*' "$OUT/parakeet-1-$1.time.txt" | grep -o '[0-9]*$')KiB"
done
log "CAND-DONE"
