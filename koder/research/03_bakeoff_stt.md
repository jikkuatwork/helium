# STT bake-off: Moonshine-tiny vs Parakeet 110M CTC

Evaluated **2026-11-04**, Ubuntu 24.04 aarch64, Ampere Altra / Neoverse-N1.
Evaluation only: **no existing helium package, registry, or downloader changed**.

## Verdict

**Conditional yes: prefer Parakeet 110M int8 CTC, with bounded chunking.**

- On 320 LibriSpeech test-clean + 320 test-other utterances, WER improves
  **5.21% → 3.40% / 12.23% → 5.92%**: 34.8% / 51.6% fewer errors.
- On a balanced 60-clip timing batch, it is **1.7× faster** than Moonshine
  at both four and one ORT threads. Four-thread RTF: **0.02330 vs 0.03994**.
- At 0 dB added white noise, WER is **21.80% vs 52.05%**.
- Costs: **131.65 MB** of NN weights instead of 28.18 MB; representative
  short-process RSS **725 MiB vs 398 MiB**.
- **Do not replace helium's bounded audio handling with whole-file calls.**
  A five-minute CTC single pass peaks at **5.22 GiB**, already too much for
  a 4 GB Pi 4. The export also has a broken long-position boundary around
  400 seconds; twelve/twenty-minute single passes fail. Fixed 30 s chunks
  process twenty minutes in **28.70 s**, at **0.71 GiB peak RSS**.
- Keep Moonshine as the smallest-download/low-memory fallback. Gate a Pi 4
  default change on native Pi 4 timing, a validated pure-Go frontend, and
  long-chunk/stitch regression tests. This VM has ARM dot-product; Pi 4
  does not. These are **not measured Pi 4 speeds**.

**Offer Parakeet 0.6B v2 int8 as an optional large tier: yes, for quality-first
CPU desktops / adequately provisioned devices, not the low-end default.**
It gives **1.97% / 3.04% WER** and **7.19% at 0 dB noise**, roughly halving
110M's clean/other errors. Tradeoff: 661.18 MB weights, ~1.54 GiB short RSS,
and ~2.9× / 3.8× slower than 110M at four/one threads. This evaluates
**English v2**, not multilingual v3.

## Method, environment, and evidence

- CPU: 32 vCPU Neoverse-N1, no SMT; all timed processes pinned with
  `taskset -c 8-15`. Intra-op **4 or 1**, inter-op **1**, sequential ORT
  execution; auxiliary NumPy/BLAS threads capped at 1. Other bake-off lanes
  may share the VM's memory bandwidth/cache, not our assigned cores.
- Go **1.25.1**, Python **3.12.3**, ONNX Runtime **1.24.4 CPU EP everywhere**;
  onnx-asr **0.12.0**, NumPy **2.5.4**. Exact package pins are in
  [`bakeoff/stt/requirements.txt`](../../bakeoff/stt/requirements.txt).
- One untimed warm-up, then **five repetitions**, reporting the median.
  Speed includes feature extraction and decoding, excludes model load and
  Python disk reads/scoring. Actual Go long timings include WAV streaming,
  chunk planning and stitching. `/usr/bin/time -v` measures whole-process
  peak RSS, including load/warm-up/native allocations, not just weights.
- Main speed comparison runs **both candidates in Python**, using helium's
  unchanged Moonshine graphs, six-layer KV loop, BOS=1, EOS=2, greedy argmax,
  max 448 steps, and its tokenizer's decode rules. A temporary **Go build
  overlay changes only session thread options** for actual-engine checks;
  no tracked product source is modified. The Go engine matches Python's
  text **740/740 cases exactly**, including all clean/other/noise cases.
- Helium's shipped ORT library and Python's wheel are different binaries
  of the same **1.24.4** version; Go asserts its native version. Main model
  rankings use the same Python ORT build. Both library hashes are recorded
  in [`environment.json`](../../bakeoff/stt/results/environment.json).
- LibriSpeech/OpenSLR 12: uniform shuffled utterance sampling, Python seeds
  **20261104 / 20261105**, 320 per split, excluding >29.5 s clips so short
  tests are one graph call for both models. This excludes 10/2620 clean and
  9/2939 other clips; the sample covers all **40 / 33 speakers** and 82/85
  chapters. Audio: **2407.62 / 2085.52 s**; reference words: **6509 / 5813**.
- WER is corpus-micro `(substitutions + deletions + insertions) / ref words`:
  lowercase, punctuation deleted, whitespace collapsed. **No numeric or
  abbreviation expansion**, beam search, language model, or text repair.
- Per-case transcripts, per-run durations, RSS logs, manifests, bootstrap
  results and reproducibility commands are under
  [`bakeoff/stt/`](../../bakeoff/stt/README.md). Weights/audio are outside Git:
  `~/models/stt/`, `~/datasets/stt/`, `~/bakeoff-samples/stt/`.

NVIDIA's cross-corpus 7.49 and Moonshine's 12.66 are not this experiment's
LibriSpeech numbers. NVIDIA's default hybrid decoder is **TDT**; this
110M experiment deliberately uses **CTC**, not its TDT head.

## Accuracy

Weights are decimal MB, excluding vocabulary/config; all WER is percent.

| Build | Weights MB | Clean WER | Other WER |
|---|---:|---:|---:|
| Moonshine-tiny quantized | 28.18 | 5.21 | 12.23 |
| Parakeet 110M int8 CTC | 131.65 | 3.40 | 5.92 |
| Parakeet 110M fp32 CTC | 458.16 | 3.44 | 5.54 |
| Parakeet 0.6B v2 int8 TDT | 661.18 | 1.97 | 3.04 |

Paired utterance bootstrap, 2000 draws, seed 20261104: 110M-int8 minus
Moonshine WER is **-1.81 points** (95% CI -2.50 to -1.11) on clean and
**-6.31 points** (-7.53 to -5.08) on other. Large minus 110M is -1.43
(-1.84 to -1.05) / -2.87 (-3.56 to -2.26) points. These are descriptive
**utterance**, not speaker, resampling CIs; not a real-world guarantee.

Int8 is not free: versus fp32, test-other costs **+0.38 WER points** and
0 dB noise costs **+3.63 points**. The tiny clean difference favoring int8
is only three errors; its bootstrap CI includes zero.

## Noise robustness

Same first 50 sampled clean clips, **1266 reference words**, deterministic
Gaussian white noise seeded from SHA-256(utterance ID). Noise is scaled
using **whole-clip mean signal/noise power**, including silence. No clipping,
peak normalization or denoising; float32 samples are identical across models.

| Build | Original WER | 10 dB WER | 0 dB WER |
|---|---:|---:|---:|
| Moonshine quantized | 5.61 | 12.80 | 52.05 |
| Parakeet 110M int8 CTC | 3.16 | 5.77 | 21.80 |
| Parakeet 110M fp32 CTC | 3.32 | 5.21 | 18.17 |
| Parakeet 0.6B v2 int8 TDT | 1.74 | 2.61 | 7.19 |

This supports the large tier especially for adverse audio, but white noise
is not room reverberation, traffic, microphones, accents or competing speech.

## Speed and short memory

Balanced **60 clips / 442.57 s**: 30 per split, loaded before timing; warm
once on the entire batch, then five entire-batch runs. Lower RTF is better.

| Build | RTF, 4 threads | RTF, 1 thread | RSS, 4 threads |
|---|---:|---:|---:|
| Moonshine quantized | 0.03994 | 0.07653 | 397.6 MiB |
| Parakeet 110M int8 CTC | 0.02330 | 0.04416 | 724.6 MiB |
| Parakeet 0.6B v2 int8 TDT | 0.06747 | 0.16687 | 1575.9 MiB |

Median batch times, four/one threads: **17.68/33.87 s**, **10.31/19.55 s**,
**29.86/73.85 s** respectively. One-thread RSS: 398.3 / 718.3 / 1561.9 MiB.
Larger CTC is faster than tiny AR Moonshine because it avoids the serial
text-decoder loop; parameter count alone does not predict throughput.

The independent **9.19 s** clip also has five-run four/one-thread RTF:
Moonshine **0.0381/0.0766**, 110M-int8 **0.0223/0.0432**, 110M-fp32
**0.0286/0.0952**, large **0.0652/0.1683**. Four-thread RSS on that one clip:
221.4 / 361.2 / 847.4 / 1235.7 MiB. Dynamic-shape arena high-water marks
make the representative batch appreciably larger than one short clip.
Initial model loads were roughly 0.9 / 1.7 / 3.1 s (single observations,
not cold-start medians). Full-corpus RTF is diagnostic only, not the ranking.

## Long audio: bounded chunks are necessary

Whole clean utterances are concatenated with no inserted gaps or cropped
words: **34 / 90 / 151 utterances**, **301.735 / 720.89994 / 1201.23494 s**.
These deliberately mix speakers/books; they are not natural single-speaker
lectures or independent held-out data.

All rows below are **four threads**, one warm-up + median of five runs.
`fixed` means identical non-overlapping 30 s blocks, independently normalized,
with text joined by spaces. `Go` means helium's actual silence-aware cuts,
0.5 s overlap and existing stitcher. Do not treat different cuts/runners as
an isolated model-quality comparison.

| Path | WER % | Time s | RTF | RSS GiB |
|---|---:|---:|---:|---:|
| Moonshine Go, 5 min | 16.37 | 12.91 | 0.04278 | 0.40 |
| Moonshine Go, 12 min | 10.78 | 32.80 | 0.04550 | 0.44 |
| Moonshine Go, 20 min | 8.83 | 52.44 | 0.04365 | 0.43 |
| Moonshine fixed, 5 min | 9.13 | 13.20 | 0.04375 | 0.38 |
| Moonshine fixed, 12 min | 7.50 | 29.77 | 0.04129 | 0.41 |
| 110M single, 5 min | 4.86 | 22.12 | 0.07330 | 5.22 |
| 110M fixed, 5 min | 5.22 | 7.15 | 0.02369 | 0.66 |
| 110M fixed, 12 min | 4.82 | 17.44 | 0.02420 | 0.69 |
| 110M fixed, 20 min | 5.00 | 28.70 | 0.02389 | 0.71 |
| Large single, 5 min | 3.08 | 50.65 | 0.16785 | 5.34 |
| Large fixed, 5 min | 3.56 | 21.58 | 0.07153 | 1.52 |

One-thread five-minute totals: 110M single **53.06 s / 5.22 GiB**, Moonshine
fixed **27.77 s / 0.38 GiB**, actual Moonshine Go **27.02 s / 0.40 GiB**.
Actual Go twelve-minute one-thread total: **70.92 s / 0.41 GiB**.

The current Go chunk/stitch policy scores worse than fixed cuts here. The
cause has **not** been isolated; it is a regression-test target, not a fixed
bug or a promise that reusing it unchanged will preserve Parakeet's quality.
The controlled twelve-minute comparison still favors 110M: **4.82% vs 7.50%
WER, 17.44 vs 29.77 s**, with the same fixed cuts and Python runner.

### Export cap and a silent edge case

The 110M export contains a fixed **`[1,9999,512]`** relative-position table.
The exact extracted position-slicing subgraph confirms:

- 5000 encoder frames → **9999** position rows, as intended.
- 5001 frames → **one** position row from ONNX negative-index slicing.
  `Add` accepts singleton broadcasting: it **runs but loses the intended
  position representation**. Successful execution is not valid long support.
- 5002 frames → two position rows; `Add` fails, **2 vs 5002**.
- Twelve/twenty minutes fail at `/layers.0/self_attn/Add_2`, **4012 vs 9012**
  and **9999 vs 15016**. These are export shape errors, not missing ORT ops.

With the tested frontend, **399.9999375 s** gives 5000 encoder frames;
**400.000–400.0799375 s** falls in the silently broadcast edge band;
**400.08 s** hard-fails. Earlier boundary assertions assuming an immediate
400 s exception were disproved and are retained as exploratory evidence.
`position_probe.py` extracts the original slicing nodes unchanged into a
local graph outside Git; `limits.py` verifies the final exception boundary.

Use **<=5000 encoder frames / less than 400 s** as the export's conservative
upper limit, **not** its advertised NeMo-model 20 minutes. In practice use
**~30 s chunks**: five-minute single-pass attention memory is already unsafe
for a 4 GB Pi 4. Extending the position table alone would not fix that RAM cost.

## What Go needs

### Exact 110M frontend used here

The timed frontend is onnx-asr 0.12.0's **`nemo80.onnx`**, CPU STFT backend,
not sherpa's historical Kaldi defaults. Its independently implemented NumPy
reference is [`features.py`](../../bakeoff/stt/features.py).

1. **16,000 Hz mono float32 PCM**, PCM16 divided by 32768. No waveform peak/
   RMS normalization, DC removal, or dither.
2. Continuous waveform pre-emphasis: `y[0]=x[0]`,
   `y[n]=x[n]-0.97*x[n-1]` (not reset per frame).
3. **512-point real FFT**, **400-sample/25 ms symmetric Hann**, hop
   **160 samples/10 ms**. Hann denominator is **399**, not a periodic Hann;
   pad its 400 values with **56 zeros each side** to width 512.
4. **256 zero samples on both waveform ends**, centered STFT; no reflection
   padding. Use squared magnitude/power, not magnitude or dB.
5. **80 triangular Slaney mel bins**, **0–8000 Hz**, librosa/Slaney scale,
   **area normalization** `2/(right_hz-left_hz)`, **not HTK mel**. FFT bins
   are 257 equally spaced frequencies from 0 to 8000 Hz.
6. Natural log with **additive `2^-24`** guard: `log(mel_power + 2^-24)`,
   not `log(max(power, epsilon))` and no upper clamp.
7. **Per-feature temporal normalization**, independently for each chunk:
   subtract that bin's mean over valid frames, divide by
   **sample stddev (`F-1`) + 1e-5**. No normalization across bins.
8. Valid frame count **`F=floor(num_samples/160)`**; centered STFT returns
   a tensor of **`F+1`** frames. The extra/invalid frame is **zeroed** and
   excluded from normalization. Feed `[1,80,F+1]` plus int64 `[F]`.
   Reject/buffer inputs with fewer than two valid frames.

Reference vs actual ONNX frontend on ten clips: max absolute feature error
**1.10e-4**, RMS <=**3.41e-6**; **collapsed CTC tokens match 10/10**. Frame
argmax positions are not bit-identical under dynamic quantization. This is
**not yet a Go frontend implementation**; validate the eventual Go math and
operation order against the supplied corpus/goldens before switching defaults.

### Graph, vocabulary and decoder

- NN inputs: `audio_signal` float32 `[B,80,T]`, `length` int64 `[B]`.
  Output: `logprobs` float32 `[B,U,1025]`; valid `U=ceil(F/8)`.
- `tokens.txt`: **piece + space + integer ID**, 9953 bytes; preserve the
  Unicode `▁` word-boundary marker. **Blank ID 1024**, 1024 other entries.
- Greedy CTC: argmax each valid frame; collapse adjacent repeated IDs
  **before** removing blank; map remaining pieces, concatenate, replace
  `▁` with space, trim. No beam search, recurrent decoder, KV state,
  SentencePiece encoder, or NeMo runtime required.
- One NN graph is not yet one physical deliverable: bundle/embed the tiny
  vocabulary and required license attribution; self-host through
  `cattery-artefacts`, **not a new production HF download dependency**.
- 0.6B v2 uses the same frontend parameters except **128 mel bins**. This
  istupakov export has **two NN graphs** (encoder and merged decoder/joint),
  not sherpa's separate three. Go would additionally need the TDT greedy
  loop, previous token, two LSTM state tensors, duration-based frame advance,
  and emission-loop safeguards; inspect state shapes from graph metadata.

### Punctuation, casing and ORT notes

Both the existing Moonshine and Parakeet outputs already contain casing and
punctuation. Spot-checked Parakeet strings are legible and punctuated (e.g.
`J. B. Hobson's letter`); don't sell punctuation as uniquely new. LibriSpeech
references are uppercase and punctuation-poor, so **no quantitative casing/
punctuation score** is justified here; normalized WER deliberately ignores it.

The 110M graph is **opset 17**, standard CPU ops including `ConvInteger`,
`MatMulInteger`, `LayerNormalization`; feature `STFT` also works in ORT
1.24.4 CPU EP. No custom ops or inference blockers for any short/chunked
candidate. Long 110M errors are the position-table defect above.

Helium's CLI has no thread option and initializes sessions with nil options.
Its `ort.Init` stderr-restore defer order is also wrong (close runs before
restore), suppressing its timing/error output. Evaluation probes use direct
ORT initialization. **No product fix is included** for either issue.

## Weight licenses, exact URLs and hashes

Primary weight cards: [Moonshine-tiny](https://huggingface.co/UsefulSensors/moonshine-tiny)
**MIT** (`390624ed33d594443aa4aa221f5b9f283b545b5a`);
[NVIDIA 110M](https://huggingface.co/nvidia/parakeet-tdt_ctc-110m) **CC-BY-4.0**
(`431a349f3051ab85c22b9b7a2741b5fe77065665`);
[NVIDIA 0.6B v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2)
**CC-BY-4.0** (`ae9ad07059c7c739ffaf932226a8fe64ae2620b0`). CC-BY attribution
must credit NVIDIA and identify export/quantization changes when redistributed.

All URLs below are fixed-revision base directories; append the listed filename.
[`download.py`](../../bakeoff/stt/download.py) contains complete URLs and verifies
these SHA-256s before use. No weights, WAVs, FLACs or archives are committed.

**Moonshine runtime assets**, helium's actual self-hosted files:
<https://raw.githubusercontent.com/jikkuatwork/cattery-artefacts/d46bb2c528750c6a5db66deca2df88db71cc2261/models/moonshine-tiny-v1.0/>

- [`encoder_model_quantized.onnx`](https://raw.githubusercontent.com/jikkuatwork/cattery-artefacts/d46bb2c528750c6a5db66deca2df88db71cc2261/models/moonshine-tiny-v1.0/encoder_model_quantized.onnx) (7937661 bytes):
  `c6fc4b7bc5af75c0591fd157a1f3829b533d18e9769a888fd95a62e470dd4f4a`
- [`decoder_model_merged_quantized.onnx`](https://raw.githubusercontent.com/jikkuatwork/cattery-artefacts/d46bb2c528750c6a5db66deca2df88db71cc2261/models/moonshine-tiny-v1.0/decoder_model_merged_quantized.onnx) (20243286):
  `eed87831c3a6103534aae7d47a5d485025c659a1323901513961c39fe8a1a367`
- `tokenizer.json` (3761754):
  `7b913404bdd039af4756783218af4440bc07fb7d6d8258d677e34f95b3ec416f`

**110M fp32 CTC**, csukuangfj/sherpa export:
<https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000/resolve/3af92f152d32c836acabf38f4c993bc96b80eb2d/>

- [`model.onnx`](https://huggingface.co/csukuangfj/sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000/resolve/3af92f152d32c836acabf38f4c993bc96b80eb2d/model.onnx) (458161021):
  `936806cf3dd0db5aba53f8c7410bb5632d7a8ad6b2c51009f5e4fc0890ec76bf`
- `tokens.txt` (9953):
  `450e56bd2f036fe5b6aa821865838cc5aa9d8b0106134ce9a9ba0664abe6cd10`

**110M int8 CTC**, VocaHQ, explicit CC-BY-4.0 attribution/change notice:
<https://huggingface.co/VocaHQ/sherpa-onnx-nemo-parakeet-tdt-ctc-110m-en-int8/resolve/43869f73831659dd8b0ccee617ee42474b7aa974/>

- [`model.int8.onnx`](https://huggingface.co/VocaHQ/sherpa-onnx-nemo-parakeet-tdt-ctc-110m-en-int8/resolve/43869f73831659dd8b0ccee617ee42474b7aa974/model.int8.onnx) (131652171):
  `9177a9146cf32ee0cc8152276ef95116f312018d316be37ccf57f7efea81fc1a`
- Dynamic **QUInt8** quantization of the fp32 model. Upstream quantizer used
  ORT **1.30.0**; **all inference here uses 1.24.4**. The vocabulary is
  unchanged. Canonical csukuangfj int8 HF repo was empty, hence this source.

**0.6B v2 int8**, istupakov, CC-BY-4.0:
<https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/0bbb45a3365852604aef28b538a8f066f4ccaa85/>

- [`encoder-model.int8.onnx`](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/0bbb45a3365852604aef28b538a8f066f4ccaa85/encoder-model.int8.onnx) (652184014):
  `3e0581fda6ab843888b51e56d7ee78b6d5bc3237ec113af1f732d1d5286aa155`
- [`decoder_joint-model.int8.onnx`](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/0bbb45a3365852604aef28b538a8f066f4ccaa85/decoder_joint-model.int8.onnx) (8998286):
  `a449f49acd68979d418651dd2dcb737cc0f1bf0225e009e29ee326354edbf7d3`
- `vocab.txt` (9384):
  `ec182b70dd42113aff6c5372c75cac58c952443eb22322f57bbd7f53977d497d`
- `config.json` (97):
  `666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466`

Timed frontend graphs come from the pinned onnx-asr package, not the downloaded
v2 repository's optional `nemo128.onnx`. SHA-256s:

- `nemo80.onnx`:
  `7ab6b0d1f57832e56f59aa7cab4289de50df7f8d5296cdfd281d9c9b7b8d73e0`
- `nemo128.onnx`:
  `5b4a84c52eeaa615dc46d781cc7e4598f9b432184831d57493c48adcd01371a9`

**Dataset**, [OpenSLR 12 / LibriSpeech](https://www.openslr.org/12), **CC-BY-4.0**,
Panayotov, Chen, Povey and Khudanpur; LibriVox recordings:

- <https://www.openslr.org/resources/12/test-clean.tar.gz>
  `39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23`
- <https://www.openslr.org/resources/12/test-other.tar.gz>
  `d09c181bba5cf717b3dee7d4d592af11a3ee3a09e08ae025c5506f6ebe961c29`

## Listening/input sample index

All files are **outside Git** under `~/bakeoff-samples/stt/`, mono 16 kHz.
These are STT inputs, not synthesized speech. Exact WAV hashes are in
[`sample-index.json`](../../bakeoff/stt/results/sample-index.json).

| File(s) | Source | Duration |
|---|---|---:|
| `parity.wav` | clean 8463-294828-0001 | 9.19 s |
| `noise-{10,0}db-0.wav` | same clip, white noise | 9.19 s |
| `noise-{10,0}db-1.wav` | clean 8455-210777-0034 | 7.70 s |
| `noise-{10,0}db-2.wav` | clean 4970-29095-0030 | 4.67 s |
| `long-5min.wav` | first 34 sampled clean clips | 301.735 s |
| `long-12min.wav` | first 90 | 720.89994 s |
| `long-20min.wav` | first 151 | 1201.23494 s |

## Follow-ups / deliberately not done

- Native Pi 4 CPU/RSS validation; no Pi 4 performance claim is made here.
- Implement/test pure-Go log-mel, CTC/vocabulary packaging and CC-BY notices;
  preserve bounded memory, validate long boundary/stitch behavior.
- Investigate the existing Moonshine long-policy degradation and stderr/
  threading controls separately. No changes to those packages in this lane.
- Port TDT and bundle its two NN graphs if the owner adopts the large tier.
- Real microphones/accents/reverberation/natural long talks, formal punctuation
  scoring, GPU paths, multilingual v3 and full-large twenty-minute support
  were not evaluated. No new model was integrated into helium.

Validation: all assets rehashed; ten frontend CTC-token matches; **740 actual
Go/Python exact text matches**; five-run timing metadata/RSS; position-subgraph
and exception-boundary probes; `go test ./stt/...`, Go vet on both helpers,
Python compilation and shell syntax checks passed.
