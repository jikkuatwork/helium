# Plan 39 — Model bake-off (first run on the remote worker VM)

Status: **done 2026-11-05.** Results landed: `koder/research/03_bakeoff_{tts,stt,llm}.md`.
Verdicts: TTS conditional (keep Kokoro for now), STT conditional yes (Parakeet 110M
int8, 30 s chunks), LLM keep Qwen3.5-4B non-thinking; LFM2.5-1.2B as Pi pick.

Verifies the picks in `koder/research/02_model_survey.md` on real hardware
before helium builds on them. Three independent lanes, each a Pi/GPT worker
on the plan-38 VM, pinned to its own cores:

| Lane | Question | Cores |
|---|---|---|
| `tts` | Phonon 31m-en vs Kokoro-82M | 0-7 |
| `stt` | Parakeet TDT-CTC 110M vs Moonshine-tiny | 8-15 |
| `llm` | Qwen3.5-4B vs LFM3-1.7B (+ LFM2.5-1.2B) | 16-23 |

Results land as `koder/research/03_bakeoff_<area>.md` (samples stay on the VM
under `~/bakeoff-samples/`).

## Dispatch

Each brief = area file + `_common.md` (workers have not seen any context):

```
for a in tts stt llm; do
  cat koder/plans/39_model_bakeoff/$a.md koder/plans/39_model_bakeoff/_common.md > /tmp/brief-$a.md
  scripts/hvm delegate helium bake-$a /tmp/brief-$a.md
done
scripts/hvm run helium harnex lanes        # check-ins
scripts/hvm fetch helium bake-tts          # review as a local worktree
```
