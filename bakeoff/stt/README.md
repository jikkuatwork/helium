# STT CPU bake-off harness

Evaluation only: no existing helium package is changed. Audio and weights
stay under `~/datasets/stt/`, `~/bakeoff-samples/stt/`, and `~/models/stt/`.
Results and public LibriSpeech transcript metadata can be committed; **never
commit weights, WAV, FLAC, or archives**.

## Reproduce

From the helium repo root (Ubuntu aarch64; `go`, `taskset`, `/usr/bin/time`):

```sh
python3 -m venv ~/models/stt/venv
~/models/stt/venv/bin/pip install -r bakeoff/stt/requirements.txt
python3 bakeoff/stt/download.py --large
# Fixed seeds; writes manifests outside the repo and three concatenated WAVs.
taskset -c 8-15 ~/models/stt/venv/bin/python bakeoff/stt/bench.py prepare
# Evaluation-only Go build overlay: changes only session thread options.
python3 bakeoff/stt/build_probe.py
bash bakeoff/stt/run.sh
bash bakeoff/stt/run_extra.sh
OPENBLAS_NUM_THREADS=1 taskset -c 8-15 \
  ~/models/stt/venv/bin/python bakeoff/stt/summarize.py
```

`helium_probe.go` needs an ORT shared library. Default is helium's downloaded
`~/.helium/ort/libonnxruntime.so.1.24.4`. To use the pinned Python wheel's
same-version library instead, pass:

```sh
HELIUM_BAKE_THREADS=4 taskset -c 8-15 /tmp/stt-helium-probe \
  -lib ~/models/stt/venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.so.1.24.4 \
  ~/bakeoff-samples/stt/long-5min.wav
```

Do not run timed candidates concurrently. Each process is pinned to cores
8–15, intra-op 4 or 1, inter-op 1, sequential execution; NumPy/BLAS auxiliary
threads are capped at 1. The initial full-corpus pass is for WER, with its
RTF only diagnostic. Speed rankings use one untimed warm-up followed by
five repetitions on a 9.19 s clip and a balanced 60-clip batch, plus long
files. `time -v` measures whole-process peak RSS including load/warm-up;
model load, disk audio reads, and WER scoring are outside timed inference.
The Go probe times its actual WAV streaming/chunking as well as inference.

## Files

- `download.py`: fixed-revision URLs and verified SHA-256s; safe tar extraction.
- `bench.py`: helium-equivalent Moonshine greedy loop, CTC argmax, optional
  onnx-asr TDT; fixed dataset/noise generation; accuracy and timing modes.
  Frame-level argmax positions can differ for tiny frontend rounding errors
  under dynamic quantization; `features.py` separately checks identical
  collapsed CTC token streams, not bit-identical frame alignment.
- `features.py`: independent, Go-ready Slaney mel + STFT reference and
  validation against the **actual timed** NeMo80 ONNX feature graph.
- `helium_probe.go`, `build_probe.py`: actual helium Moonshine WAV/chunk/
  decoder/tokenizer path with only evaluation-time ORT thread control.
  Building the Go file directly without the overlay does **not** control
  its threads. No tracked package is edited, and no integration is shipped.
- `run.sh`: primary accuracy/noise/short/long measurements, preserving failed
  12/20-minute single-pass attempts as evidence.
- `run_extra.sh`: independent feature check, actual helium long handling,
  optional 0.6B v2 int8, and representative balanced-batch speed measurements.
- `limits.py`: one-call boundary validity probes around the fixed position
  table's maximum; not used as speed measurements.
- `parity.py`: exact-text check of 10 actual helium engine outputs against
  the fair Python Moonshine decoder, using temporary WAVs outside the repo.
- `summarize.py`: aggregate WER, paired utterance bootstrap, medians, RSS.
- `manifest.json`, `long-manifest.json`: public selection/reference metadata,
  not audio. Exact preparation is repeated from the archives with fixed seeds.
- `results/`: per-utterance JSONL, summaries, per-run timing JSON and RSS logs.

Normalization is lowercase, delete punctuation, collapse whitespace. Numbers
are **not** spelled out and abbreviations are **not** expanded. Bootstrap CIs
resample utterances in paired fashion, not speakers; they are descriptive
sample uncertainty and do not establish real-world generalization.

Model licenses: original English Moonshine **MIT**; both NVIDIA Parakeets
**CC-BY-4.0**. LibriSpeech/OpenSLR 12 is **CC-BY-4.0**. See
`koder/research/03_bakeoff_stt.md` for results, caveats, and provenance.
