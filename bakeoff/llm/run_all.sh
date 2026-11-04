#!/usr/bin/env bash
# One process at a time on this lane's cores; plain validation background jobs only.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/llm/venv/bin/python"
OUT="$HOME/datasets/llm/results"
mkdir -p "$OUT"
for model in lfm25 lfm3 qwen; do
  for threads in 4 8 1; do
    base="$OUT/speed-${model}-${threads}t"
    taskset -c 16-23 /usr/bin/time -v "$PY" bakeoff/llm/evaluate.py speed --model "$model" --threads "$threads" --out "$base.jsonl" > "$base.log" 2> "$base.time"
  done
  extra=()
  if [[ "$model" == lfm25 ]]; then extra=(--spot); fi
  base="$OUT/quality-${model}-4t"
  taskset -c 16-23 /usr/bin/time -v "$PY" bakeoff/llm/evaluate.py quality --model "$model" --threads 4 "${extra[@]}" --out "$base.jsonl" > "$base.log" 2> "$base.time"
done
