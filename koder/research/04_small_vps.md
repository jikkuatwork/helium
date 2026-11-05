# Helium on a $6 VPS (DigitalOcean Basic shape)

Date: 2026-11-05. Harness and raw results: `bakeoff/vps/`.

## Question

The Pi 4 is the design target, but the most common deployment will be a
$6 DigitalOcean droplet. Can helium run there, and what breaks?

## Verdict

**Yes for speech-to-text and text-to-speech, no for the local LLM, and not
with today's defaults.**

- **STT (Moonshine)** fits easily: a 10 s voice note in about 1 s warm,
  20 min of audio in about 2 min, never above 270 MiB.
- **TTS (Kokoro)** works only with a fix, and it is slow on this CPU:
  about 0.33x realtime, so a 15 s spoken reply takes about 42 s.
- **As shipped, the server dies.** After one TTS reply it keeps ~650 MiB
  resident; the next STT request triggers the kernel OOM killer. Any TTS
  input over roughly 80 words is OOM-killed on its own.
- **Two fixes work.** Smaller Kokoro chunks (160 phoneme tokens instead of
  480) cut TTS peak memory by half at no speed cost. A 2 GB swapfile makes
  the stock binary stable with no visible latency cost.
- **Today's local LLM does not fit.** Qwen3.5-4B is OOM-killed after 10 s,
  before a token. A 1 GB box needs a much smaller local model.
- **Phonon would change the TTS story.** At one thread it ran at 3.2x
  realtime here, about 10x faster than Kokoro.

## Target and emulation

A $6 Basic droplet is 1 shared vCPU, 1 GB RAM, 25 GB SSD and 1 TB transfer.
DigitalOcean documents Regular CPUs as second-generation-or-older Xeon
Scalable; third-party benchmarks have also seen E5-series and Gold 6140.

| Property | Test box |
|---|---|
| VM | Azure Standard_D2s_v3 |
| CPU | Xeon E5-2673 v4, AVX2, no AVX-512 |
| Boot args | `mem=4170M nr_cpus=1` |
| Visible | 1 vCPU, 959 MiB total |
| Free at idle | ~696 MiB, no swap |
| Disk read | 223 MB/s uncached |

- On this VM, RAM sits below 1 GiB and again above 4 GiB, so `mem=` has to
  reach just past 4 GiB to reach a droplet's ~960 MiB total.
- Azure's agent uses roughly 60 MiB more than DigitalOcean's agents, so
  memory results are slightly pessimistic.
- The test vCPU is a dedicated hyperthread. A droplet's shared vCPU can be
  slower under noisy neighbours, so speed results are a best case.

## Results — stock helium 0.9.1, no swap

### One process per request (cold)

| Task | Input | Wall | RT× | Peak |
|---|---|---|---|---|
| TTS | 9 words | 12.0 s | 0.32 | 236 MiB |
| TTS | 40 words | 42.2 s | 0.33 | 525 MiB |
| TTS | 88 words | killed | — | >717 MiB |
| TTS | 344 words | killed | — | >717 MiB |
| STT | 10 s | 2.3 s | 4.3 | 194 MiB |
| STT | 1 min | 7.7 s | 7.8 | 221 MiB |
| STT | 5 min | 32.8 s | 9.1 | 252 MiB |
| STT | 20 min | 126 s | 9.5 | 267 MiB |
| LLM | 16 tokens | killed at 10.6 s | — | >709 MiB |

### Server

- **TTS only:** five warm 15 s replies at 40–42 s each.
- **Then one STT request:** server OOM-killed. Kokoro's ORT arena keeps
  ~646 MiB after a reply, and Moonshine does not fit beside it.
- **Soak** (STT note + TTS reply every 30 s): one cycle, then OOM.

## Kokoro chunk size is the cause

Kokoro splits phonemes into chunks of up to 480 tokens, about 30 s of audio
per inference. `tts/kokoro/kokoro.go` ignores the low-memory `ChunkSize`
that `preflight` already computes. A throwaway build (`exp_patch.py`) made
the token limit and the ORT arena configurable. Input: the 88-word text.

| Tokens | Arena | Peak | Result |
|---|---|---|---|
| 480 | on | >721 MiB | killed |
| 480 | off | >718 MiB | killed |
| 240 | on | 515 MiB | 31.9 s audio in 92 s |
| 160 | on | 355 MiB | 32.5 s audio in 93 s |
| 160 | off | >719 MiB | killed |
| 100 | on | 313 MiB | 34.0 s audio in 96 s |

- Speed does not depend on chunk size; memory does.
- Turning the arena off makes memory worse. Keep it on.
- At 160 tokens, the 40-word reply peaks at 338 MiB (from 525) and the
  344-word text completes at 546 MiB.

## Results — with a fix

| Run | Server tests | 15 min soak | Peak |
|---|---|---|---|
| Stock | dies on first STT | 1 cycle, then OOM | 701 MiB |
| 160 tokens | ok, except STT ×4/×8 | 21/21 ok | 686 MiB |
| Stock + 2 GB swap | all ok | 22/22 ok | 724 MiB + 654 swap |

- **160-token build, no swap:** sequential use is stable for 15 min (RSS
  641–659 MiB, no leak) with only ~70 MiB free. Four concurrent STT
  requests thrash (latency 38–65 s); eight get the server OOM-killed.
- **Stock binary + 2 GB swapfile:** every test passes. Swap holds Kokoro's
  idle arena while STT runs. Latencies match the no-swap runs: STT ~1.0 s,
  15 s reply ~41 s. The 88-word CLI text also completes (30.5 s audio in
  93 s).
- **Concurrency:** one TTS worker serializes requests; the queue of 5
  returns 503 beyond that, as designed. Throughput stays ~0.36x realtime.

## Bake-off candidates at one thread

Landed harness from `bakeoff/tts` and `bakeoff/stt`, Python ORT 1.24.4.
Peak memory includes the Python process, so a Go engine may use less.

| Model | Input | RT× | Peak |
|---|---|---|---|
| Phonon int8 | 10 words | 3.25 | 330 MiB |
| Phonon int8 | 76 words | 3.21 | 601 MiB |
| Phonon int8 | 275 words | 3.25 | 659 MiB |
| Parakeet 110M int8 | 10 s | 11.9 | 378 MiB |
| Parakeet 110M int8 | 1 min, one pass | killed | >687 MiB |
| Parakeet 110M int8 | 5 min, 30 s chunks | 10.8 | 657 MiB |

- Phonon's first audio arrived in 0.9–1.5 s; a 25 s paragraph took 7.9 s.
  Kokoro needs about 90 s for the same length here.
- Parakeet is about as fast as Moonshine on this CPU but needs roughly twice
  the memory and must be chunked. Moonshine is the better fit at 1 GiB.

## Implications

1. **Make Kokoro's chunk size follow available memory** (e.g. 160 tokens at
   ≤1 GiB). The low-memory signal already exists in `preflight`; Kokoro
   just does not read it. Keep the ORT arena on.
2. **Document a 2 GB swapfile** for hosts at or under 1 GiB. It works with
   the shipped binary today.
3. **A local LLM here must be much smaller.** All weights stay resident while
   it generates. The owner fixed 250 MiB as an absolute ceiling on
   2026-11-05, so that means a ~300M-parameter model at 4-bit today, with
   larger ones joining as they shrink (ROADMAP.md).
4. **Phonon is what makes TTS pleasant on a $6 box.** This strengthens the
   bake-off's "conditional replace"; the Go-side memory still needs
   measuring.
5. **Keep Moonshine as the ≤1 GiB STT default**, whatever the larger tiers use.

## Caveats

- One emulated box, not a real droplet: dedicated hyperthread, slightly
  less free memory than DigitalOcean's agents leave.
- STT inputs are helium's own Kokoro speech, looped for long files. These
  runs measure speed and memory, not accuracy.
- Telegram voice notes are OGG/Opus; helium takes WAV, so a host needs a
  decoder step that was not measured.
- Kokoro chunk experiments used one text per setting and single runs.
