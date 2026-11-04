#!/usr/bin/env bash
# No concurrent jobs: prevent contention within assigned cores.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/tts/venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
rm -f "$HOME/datasets/tts/speed.done"
mkdir -p bakeoff/tts/results
for model in kokoro phonon-int8 phonon-fp32; do
 for threads in 4 1; do
  for shape in short paragraph long; do
   cell="$model-$threads-$shape"
   echo "$(date -u +%FT%TZ) $cell"
   /usr/bin/time -v -o "bakeoff/tts/results/$cell.time.txt" taskset -c 0-7 "$PY" bakeoff/tts/benchmark.py \
    --model "$model" --threads "$threads" --shape "$shape" --output "bakeoff/tts/results/$cell.json" \
    > "$HOME/datasets/tts/$cell.log" 2>&1
  done
 done
done
printf '%s\n' "$(date -u +%FT%TZ) speed matrix complete" > "$HOME/datasets/tts/speed.done"
