#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="$HOME/models/stt/venv/bin/python"
OUT=bakeoff/stt/results
mkdir -p "$OUT"
run() { taskset -c 8-15 /usr/bin/time -v -o "$OUT/$1.rss.txt" "$PY" bakeoff/stt/bench.py "${@:2}" > "$OUT/$1.log" 2>&1; }
for model in moonshine parakeet parakeet-fp32; do
 run "$model-accuracy" accuracy --model "$model" --output "$OUT/$model-accuracy.jsonl"
 for snr in 10 0; do
  run "$model-noise-${snr}" accuracy --model "$model" --snr "$snr" --output "$OUT/$model-noise-${snr}.jsonl"
 done
 for threads in 4 1; do
  run "$model-short-${threads}" timing --model "$model" --threads "$threads" --audio "$HOME/bakeoff-samples/stt/parity.wav" --output "$OUT/$model-short-${threads}.json"
 done
done
# Large single passes are separate: global attention scales quadratically.
for threads in 4 1; do
 run "parakeet-long5-${threads}" timing --model parakeet --threads "$threads" --audio "$HOME/bakeoff-samples/stt/long-5min.wav" --reference --output "$OUT/parakeet-long5-${threads}.json"
 run "moonshine-long5fixed-${threads}" timing --model moonshine --threads "$threads" --audio "$HOME/bakeoff-samples/stt/long-5min.wav" --chunk 30 --reference --output "$OUT/moonshine-long5fixed-${threads}.json"
done
# The upstream graph has a traced [1,9999,512] position table. Keep failures
# as evidence and continue with bounded chunks rather than stopping the lane.
if ! run parakeet-long12-4 timing --model parakeet --audio "$HOME/bakeoff-samples/stt/long-12min.wav" --reference --output "$OUT/parakeet-long12-4.json"; then
 echo '12-minute single pass failed; see results/parakeet-long12-4.log'
fi
if ! run parakeet-long20-4 timing --model parakeet --audio "$HOME/bakeoff-samples/stt/long-20min.wav" --reference --output "$OUT/parakeet-long20-4.json"; then
 echo '20-minute single pass failed; see results/parakeet-long20-4.log'
fi
run moonshine-long12fixed-4 timing --model moonshine --audio "$HOME/bakeoff-samples/stt/long-12min.wav" --chunk 30 --reference --output "$OUT/moonshine-long12fixed-4.json"
run parakeet-long12chunk-4 timing --model parakeet --audio "$HOME/bakeoff-samples/stt/long-12min.wav" --chunk 30 --reference --output "$OUT/parakeet-long12chunk-4.json"
