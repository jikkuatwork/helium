#!/usr/bin/env bash
# Parallel correctness-only requests; never use these request latencies as speed results.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/llm/venv/bin/python"
OUT="$HOME/datasets/llm/results"
PARTS="$OUT/shards"
mkdir -p "$PARTS"
MODEL="${1:-qwen}"
MERGED="$OUT/quality-${MODEL}-4t.jsonl"
if [[ -f "$MERGED" ]]; then echo "completed quality evidence: $MERGED"; exit 0; fi
pids=()
for shard in 0 1; do
  base="$PARTS/quality-${MODEL}-4t-shard${shard}"
  if [[ -f "$base.jsonl" ]]; then
    if grep -q 'Exit status: 0' "$base.time"; then continue; fi
    echo "incomplete shard evidence: $base" >&2; exit 1
  fi
  cores=16-19; if [[ "$shard" == 1 ]]; then cores=20-23; fi
  taskset -c "$cores" /usr/bin/time -v "$PY" bakeoff/llm/evaluate.py quality --model "$MODEL" --threads 4 --shard "$shard/2" --out "$base.jsonl" > "$base.log" 2> "$base.time" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
"$PY" - "$MODEL" <<'PY'
import json,sys
from pathlib import Path
model=sys.argv[1];root=Path.home()/'datasets/llm/results'
rows=[];envs=[]
for i in range(2):
    data=[json.loads(line)for line in (root/'shards'/f'quality-{model}-4t-shard{i}.jsonl').read_text().splitlines()]
    envs.append(data[0]);rows.extend(data[1:])
env=dict(envs[0]);env['quality_parallel_shards']=envs;env['quality_timings_comparable']=False
env['affinity']=[16,17,18,19,20,21,22,23]
assert len({r['id']for r in rows})==len(rows)
assert sum(r['kind']=='tool'for r in rows)==36
assert sum(r['kind']=='instruction'for r in rows)==30
assert sum(r['kind']=='voice'for r in rows)==10
assert sum(r['kind']=='thinking'for r in rows)==40
path=root/f'quality-{model}-4t.jsonl'
with path.open('x')as f:
    for r in [env]+rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
PY
