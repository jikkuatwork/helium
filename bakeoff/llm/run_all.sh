#!/usr/bin/env bash
# One process at a time on this lane's cores; plain validation background jobs only.
# Resume completed runs; refuse to overwrite incomplete evidence.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/llm/venv/bin/python"
OUT="$HOME/datasets/llm/results"
mkdir -p "$OUT"
run() {
  local mode="$1" model="$2" threads="$3"; shift 3
  local base="$OUT/${mode}-${model}-${threads}t"
  if [[ -f "$base.jsonl" ]]; then
    if grep -q 'Exit status: 0' "$base.time"; then
      echo "skip completed: $base"; return
    fi
    echo "incomplete evidence at $base; inspect before resuming" >&2; exit 1
  fi
  taskset -c 16-23 /usr/bin/time -v "$PY" bakeoff/llm/evaluate.py "$mode" --model "$model" --threads "$threads" "$@" --out "$base.jsonl" > "$base.log" 2> "$base.time"
}
for threads in 4 8 1; do run speed lfm25 "$threads"; done
run quality lfm25 4 --spot
# Prioritize the default decision's 4-thread speed + full quality before extra threads.
for model in lfm3 qwen; do
  if [[ "$model" == qwen ]]; then bash bakeoff/llm/run_controls.sh; fi
  run speed "$model" 4
  if [[ "$model" == qwen ]]; then
    bash bakeoff/llm/run_quality_parallel.sh qwen
  else
    run quality "$model" 4
  fi
  run speed "$model" 8
  run speed "$model" 1
done
