# Bake-off: LLM — Qwen3.5-4B vs LFM3-1.7B (+ LFM2.5-1.2B speed)

Area name: `llm`. Your cores: `taskset -c 16-23` (use 4 threads inside that;
also report 8 threads).

## Question

Helium's default local LLM is **Qwen3.5-4B** (q4 ONNX from onnx-community,
~2.9 GiB, Apache-2.0; helium already runs it: `/tmp/helium llm "prompt"`).
**LFM3-1.7B** (Liquid AI, released 2026-10-27, LFM Open License — accepted by
the owner) claims much better instruction following and tool calling at half
the size, but the claims are vendor-only and 8 days old, and its card says
turning thinking off "can be inconsistent". Which should be the default for a
personal voice/chat assistant (short replies, tool calls, low latency)?
Also: is **LFM2.5-1.2B-Instruct** a good Pi-class (≤ 1.5 GB) option?

## Candidates

- Qwen3.5-4B q4: `https://huggingface.co/onnx-community/Qwen3.5-4B-ONNX`
  (helium's engine is in `llm/qwen/`; you may use it, or Python ORT with the
  same files). Non-thinking via `enable_thinking=false` in the chat template.
- LFM3-1.7B q4: `https://huggingface.co/LiquidAI/LFM3-1.7B-ONNX` (official,
  single graph; card has a Python ORT sample loop: bind each `past_*` input
  to its `present_*` output, empty initial caches).
- LFM2.5-1.2B-Instruct q4: `https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-ONNX`
  (speed + a quick quality spot check only).

Use Python + onnxruntime 1.24.x with the same decode loop shape for all, so
speed numbers compare like with like.

## Measure

1. **Speed:** prefill tokens/s (prompts of ~100, ~1000 tokens) and decode
   tokens/s, at 4 and 8 threads; time to first token. Peak RSS.
2. **Tool calling:** a small suite you write (≥ 30 cases): 3–5 function
   schemas (weather, reminders, notes search, send message, calculator);
   single calls, argument extraction, choosing no tool when none fits,
   two-step calls. Score exact function name + argument correctness. Both
   models use the `<tool_call>` XML style — check each card's template.
3. **Thinking control:** with thinking disabled, how often does each model
   still emit reasoning (`<think>` or equivalent)? With it enabled, how many
   extra tokens on average?
4. **Instruction following:** ~30 IFEval-style prompts with checkable
   constraints (word limits, format, language, "answer in one sentence").
5. **Assistant feel:** 10 short voice-assistant turns (casual questions,
   a reminder, a summary of a short text) — record replies in the results
   doc for the owner to judge.

## Verdict wanted

Default LLM for helium: Qwen3.5-4B or LFM3-1.7B — with the numbers. Pi-class
pick: LFM2.5-1.2B yes/no. Note anything in the LFM graphs that helium's
existing Qwen decode loop (`llm/qwen/`) would not already handle.
