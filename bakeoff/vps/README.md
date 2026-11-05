# Small-VPS stress test (DigitalOcean $6 shape)

Evaluation only. No helium package changes. Write-up:
`koder/research/04_small_vps.md`.

## Machine

An Azure `Standard_D2s_v3` (Intel Xeon E5-2673 v4, Broadwell, AVX2, no
AVX-512) booted as a 1 vCPU / ~1 GiB box with kernel arguments
`mem=4170M nr_cpus=1`. On this VM, RAM sits below 1 GiB and again above
4 GiB, so `mem=` must reach just past 4 GiB to give the ~960 MiB MemTotal
a 1 GB droplet shows. No swap unless a run says so.

## Steps

```bash
scripts/hvm up do6 --size Standard_D2s_v3 --disk 32   # sponsored guard first
scripts/hvm push do6
scp bakeoff/vps/*.sh bakeoff/vps/*.py hvm-do6:
ssh hvm-do6 ./setup.sh                 # full size: Go, build, helium download (tts, stt, llm)
ssh hvm-do6 ./bench.py inputs          # full size: STT inputs spoken by helium's own TTS
ssh hvm-do6 'MEM=4170M CPUS=1 ./limit.sh'   # reboot as 1 vCPU / 959 MiB
ssh hvm-do6 'for p in cli server soak llm; do ./bench.py $p; done'
ssh hvm-do6 ./exp.sh                   # Kokoro chunk-token / arena experiment (throwaway build)
ssh hvm-do6 ./chain2.sh                # 160-token build, then stock + 2 GB swap, then candidates
scripts/hvm stop do6
```

- `bench.py` is stdlib-only Python. Each phase writes `~/bench/<phase><BENCH_TAG>.json`.
  `HELIUM_BIN` picks the binary; `SOAK_MIN` sets the soak length.
- `exp_patch.py` adds two environment knobs to a throwaway copy of
  `tts/kokoro/kokoro.go` (`HELIUM_EXP_KOKORO_TOKENS`, `HELIUM_EXP_NO_ARENA`).
  It is applied to `git archive` output on the VM, never to this checkout.
- `cand.sh` runs the landed bake-off harness (`bakeoff/tts`, `bakeoff/stt`)
  unchanged for Phonon int8 and Parakeet 110M int8 at one thread. The recorded
  Parakeet numbers came from a rerun after fixing a module-name clash between
  the two `download.py` files; the fix is now in `cand.sh`.

## Results

`results/` holds every phase's JSON, `exp-kokoro-chunks.txt` and
`cand-summary.txt`. RT× is audio seconds per wall second (higher is faster).
