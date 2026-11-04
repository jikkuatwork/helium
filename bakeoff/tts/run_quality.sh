#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/tts/venv/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
# Can be started while run_speed.sh is active; never overlaps assigned CPUs.
while [[ ! -f "$HOME/datasets/tts/speed.done" ]]; do sleep 10; done
for phase in synthesize transcribe signal_compare; do
 echo "$(date -u +%FT%TZ) $phase"
 /usr/bin/time -v -o "bakeoff/tts/results/$phase.time.txt" taskset -c 0-7 "$PY" "bakeoff/tts/$phase.py" \
  > "$HOME/datasets/tts/$phase.log" 2>&1
 echo "$(date -u +%FT%TZ) $phase complete"
done
