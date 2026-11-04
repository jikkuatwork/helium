# Reproduce the TTS bake-off

Evaluation only. No helium package changes. Python 3.12, Linux aarch64.
Models live under `~/models/tts/` (Kokoro remains in helium's own cache),
measurement audio under `~/datasets/tts/`, listening PCM under
`~/bakeoff-samples/tts/`. Do not add those files to git.

```bash
python3 -m venv ~/models/tts/venv
~/models/tts/venv/bin/pip install -r bakeoff/tts/requirements.txt
go build -o /tmp/helium ./cmd/helium
go build -o /tmp/tts-preprocess ./bakeoff/tts/preprocess
# Downloads helium's ORT 1.24.4, Kokoro weights, Bella, and espeak-ng.
taskset -c 0-7 /tmp/helium tts --voice bella -o /tmp/setup.wav 'Hello world.'
~/models/tts/venv/bin/python bakeoff/tts/download.py
~/models/tts/venv/bin/python bakeoff/tts/corpus.py
# Optional source inspection used in report (no code from this checkout executes).
git clone https://github.com/gradium-ai/xn-ptts ~/models/tts/xn-ptts
git -C ~/models/tts/xn-ptts checkout ee395caac058950cbcabfa3785c63630942f31ed
bash bakeoff/tts/run_speed.sh
bash bakeoff/tts/run_quality.sh
~/models/tts/venv/bin/python bakeoff/tts/rescore.py
~/models/tts/venv/bin/python bakeoff/tts/summarize.py
~/models/tts/venv/bin/python bakeoff/tts/export_diagnostics.py
```

`download.py` gets the ASR revision from `results/artifacts.json`. If the
final manifest is absent, first fetch the reported Whisper revision into
`~/models/tts/whisper-small.en` with huggingface_hub.snapshot_download and
record its API metadata in `~/models/tts/whisper-api.json` for artifacts.py.
Likewise artifacts.py records the inspected reference checkout, not code
used to run inference: normalization uses the pinned `ptts==0.6.0` wheel.

Each speed cell is an isolated Python process under `/usr/bin/time -v` and
`taskset -c 0-7`, with one warm-up of that input and five subsequent runs.
The graphs use CPU EP, ORT 1.24.4, intra-op 4 or 1, inter-op 1, sequential
execution. BLAS threads are 1. No inference jobs overlap. RT× means audio
seconds / wall seconds, **not** the inverse RTF convention. Model loading,
WAV file writes, download and ASR are excluded from warm timing; text
preprocessing, cache allocations, sampling and PCM conversion are included.

Phonon is the **current eight-frame-block export**, not the outdated
stateful graph described by the community README. It regenerates the voice
prompt and resets flow/Mimi at each <=50-token text chunk. Mimi is stateless,
so measured TTFA is a complete first text chunk, not a streaming first frame.
Kokoro uses helium's existing Go normalization and espeak path through the
small `preprocess` bridge, its exact vocabulary, 480-token phoneme budget,
75ms inter-chunk silence, Bella and speed 1.0.

Primary quality: 45 fixed sentences, already-spoken text, one primary voice
per model (Bella vs Easton); Phonon fp32 separately tests quantization.
Supplement: 20 raw structured/acronym inputs with each model's normalizer.
Whisper small.en uses CTranslate2 int8 on CPU, beam 5, temperature 0,
English forced, no VAD, no prompts, no previous-text conditioning. It is
**not** an ORT STT model. All ORT installations/sessions remain 1.24.4.
Soundfile + scipy resample_poly avoids a PyAV API mismatch.

WER canonicalizes English numbers/currency with whisper-normalizer and
explicitly expands a fixed list of initialisms identically in reference
and hypothesis. A symmetric orthographic audit equates grouped/spaced phone
digits, dotted/spaced clocks, calendar ordinals, written domains, JSON and
units with their spoken forms. It never repairs a wrong digit or name;
`rescore.py` retains the pre-audit counts. Literal punctuation/case-stripped
edit counts are also retained. Do not call this vendor-equivalent LLM WER
or a listening MOS.
`signal_compare.py` records same-seed full-waveform differences and isolated
decoder int8/fp32 comparisons on identical fp32 latents, at temperatures 0
and 0.3. Full-waveform SNR does not align AR-generated timing differences.

Six text selections × two voices × three model variants = 36 PCM16 WAVs.
See `results/sample_index.json`; 12 separate post-hoc diagnostic files
compare raw dates, spelled/native BBC, and Worcester/Gloucester. They were
not used to select the WER corpus. Synthesis outputs/ASR references never
contain secrets or user recordings. Voice catalogue descriptions are not
independent listening assessments.
