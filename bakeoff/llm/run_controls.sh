#!/usr/bin/env bash
# Supplemental compute-policy controls, not the requested native export results.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/llm/venv/bin/python"
OUT="$HOME/datasets/llm/results"
"$PY" bakeoff/llm/prepare_accuracy4.py
for model in lfm25 qwen; do
  base="$OUT/speed-${model}-acc4-4t"
  if [[ -f "$base.jsonl" ]]; then
    if grep -q 'Exit status: 0' "$base.time"; then continue; fi
    echo "incomplete control evidence: $base" >&2; exit 1
  fi
  taskset -c 16-23 /usr/bin/time -v "$PY" bakeoff/llm/evaluate.py speed --model "$model" --threads 4 --accuracy4 --out "$base.jsonl" > "$base.log" 2> "$base.time"
done
