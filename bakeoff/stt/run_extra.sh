#!/usr/bin/env bash
# Execute only after run.sh has finished; no concurrent timed candidates.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/stt/venv/bin/python"
OUT=bakeoff/stt/results
mkdir -p "$OUT"
python3 bakeoff/stt/build_probe.py > "$OUT/probe-build.log"
run() { taskset -c 8-15 /usr/bin/time -v -o "$OUT/$1.rss.txt" "$PY" bakeoff/stt/bench.py "${@:2}" > "$OUT/$1.log" 2>&1; }
taskset -c 8-15 "$PY" bakeoff/stt/features.py > "$OUT/feature-parity.json"
for threads in 4 1; do
 for minutes in 5 12; do
  HELIUM_BAKE_THREADS=$threads taskset -c 8-15 /usr/bin/time -v -o "$OUT/helium-long${minutes}-${threads}.rss.txt" /tmp/stt-helium-probe "$HOME/bakeoff-samples/stt/long-${minutes}min.wav" > "$OUT/helium-long${minutes}-${threads}.json" 2> "$OUT/helium-long${minutes}-${threads}.log"
 done
 HELIUM_BAKE_THREADS=$threads taskset -c 8-15 /usr/bin/time -v -o "$OUT/helium-short-${threads}.rss.txt" /tmp/stt-helium-probe "$HOME/bakeoff-samples/stt/parity.wav" > "$OUT/helium-short-${threads}.json" 2> "$OUT/helium-short-${threads}.log"
done
for model in moonshine parakeet; do
 for threads in 4 1; do
  run "$model-batch-${threads}" timing --model "$model" --threads "$threads" --batch 30 --output "$OUT/$model-batch-${threads}.json"
 done
done
run large-accuracy accuracy --model large --output "$OUT/large-accuracy.jsonl"
for snr in 10 0; do
 run "large-noise-${snr}" accuracy --model large --snr "$snr" --output "$OUT/large-noise-${snr}.jsonl"
done
for threads in 4 1; do
 run "large-short-${threads}" timing --model large --threads "$threads" --audio "$HOME/bakeoff-samples/stt/parity.wav" --output "$OUT/large-short-${threads}.json"
done
run large-long5chunk-4 timing --model large --audio "$HOME/bakeoff-samples/stt/long-5min.wav" --chunk 30 --reference --output "$OUT/large-long5chunk-4.json"
run parakeet-long5chunk-4 timing --model parakeet --audio "$HOME/bakeoff-samples/stt/long-5min.wav" --chunk 30 --reference --output "$OUT/parakeet-long5chunk-4.json"
run large-long5single-4 timing --model large --audio "$HOME/bakeoff-samples/stt/long-5min.wav" --reference --output "$OUT/large-long5single-4.json"
run parakeet-long20chunk-4 timing --model parakeet --audio "$HOME/bakeoff-samples/stt/long-20min.wav" --chunk 30 --reference --output "$OUT/parakeet-long20chunk-4.json"
HELIUM_BAKE_THREADS=4 taskset -c 8-15 /usr/bin/time -v -o "$OUT/helium-long20-4.rss.txt" /tmp/stt-helium-probe "$HOME/bakeoff-samples/stt/long-20min.wav" > "$OUT/helium-long20-4.json" 2> "$OUT/helium-long20-4.log"
for model in large; do
 for threads in 4 1; do
  run "$model-batch-${threads}" timing --model "$model" --threads "$threads" --batch 30 --output "$OUT/$model-batch-${threads}.json"
 done
done
taskset -c 8-15 /usr/bin/time -v -o "$OUT/length-boundary.rss.txt" "$PY" bakeoff/stt/limits.py > "$OUT/length-boundary.log" 2>&1
taskset -c 8-15 "$PY" bakeoff/stt/parity.py > "$OUT/moonshine-parity.log" 2>&1
python3 bakeoff/stt/build_probe.py --program bakeoff/stt/actual/main.go --output /tmp/stt-actual-probe > "$OUT/actual-build.log"
taskset -c 8-15 "$PY" bakeoff/stt/actual.py prepare > "$OUT/actual-prepare.log" 2>&1
HELIUM_BAKE_THREADS=4 taskset -c 8-15 /usr/bin/time -v -o "$OUT/helium-actual.rss.txt" /tmp/stt-actual-probe "$HOME/datasets/stt/actual-manifest.json" > "$OUT/helium-actual.jsonl" 2> "$OUT/helium-actual.log"
taskset -c 8-15 "$PY" bakeoff/stt/actual.py compare > "$OUT/helium-actual-compare.log" 2>&1
