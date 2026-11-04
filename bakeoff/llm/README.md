# LLM bake-off harness

Evaluation only. Existing helium packages are unchanged. All inference is local
CPU ONNX Runtime **1.24.4**, no torch or remote inference. Hugging Face access is
for downloading the user-authorized candidates only.

```sh
python3 -m venv ~/models/llm/venv
~/models/llm/venv/bin/pip install -r bakeoff/llm/requirements.txt
~/models/llm/venv/bin/python bakeoff/llm/download.py
bash bakeoff/llm/run_all.sh
~/models/llm/venv/bin/python bakeoff/llm/summarize.py
(cd bakeoff/llm && ~/models/llm/venv/bin/python -m unittest -v test_suites)
```

- `manifest.json`: immutable revisions, exact filenames, sizes and SHA256; used
  to pin subsequent downloads and verify their contents. Weights live only in
  `~/models/llm/{qwen,lfm3,lfm25}/`.
- `runner.py`: shared NumPy/ORT greedy autoregressive loop; past inputs mapped
  to present outputs, zero state per request. Model-specific adaptations are
  solely required embedding/token inputs, positions and logits control. Uses
  published local chat templates, no `trust_remote_code` execution.
- `evaluate.py`: one warm-up and five trials, 100 / 1000 exact input tokens,
  32 post-TTFT decode steps. Intra-op threads 1/4/8, inter-op 1, sequential,
  CPU EP, full ORT optimization, worker spinning disabled equally for all.
  Timing begins before state allocation and required Qwen embedding, ends after
  argmax/cache replacement; excludes tokenization and detokenization. Decode
  token count excludes first token, includes forced EOS tokens during speed
  trials to guarantee equal steps. Text is identical before per-tokenizer
  truncation, but tokenizers differ. Extra LFM full-logits trials distinguish
  the export's last-logit optimization from architecture speed.
- `suites.py`: 36 tool cases (25 single, 6 no-tool/clarification, 5 dependent),
  30 checkable instruction cases, 10 voice turns and 20 thinking pairs.
  Relative dates use fixed system time 2026-11-04 12:00 UTC. XML is scored
  exactly except outer argument whitespace; no fuzzy argument judging. LFM2.5
  spot uses native Pythonic calls parsed with AST/literal_eval, never executed.
  Word counts use Unicode word regex with internal apostrophes/hyphens;
  one-sentence check counts terminal punctuation boundaries. Fixed translation
  whitelist checks language. Output limits: 192 off / 512 on; report censoring.
- `run_all.sh`: serialized core-pinned inference; resumes completed jobs,
  refuses to overwrite incomplete evidence. Four-thread quality is prioritized
  for the main candidates before supplemental thread sweeps. Every process is
  wrapped by `/usr/bin/time -v`. No real tools/messages/reminders are executed.
- `summarize.py`: reads raw JSONL, independently checks scores, emits a small
  committed summary (raw generated outputs remain outside the repo).
- `graphs.json`: complete graph I/O + recursive operator inventory.
- `qwen_opt_probe.json`: metadata-only finding that a newer Qwen OPT export
  needs two operators absent from ORT 1.24.4. Not a fourth benchmark candidate.

Evidence: `~/datasets/llm/results/*.jsonl`, `.time`, `.log` on the VM. Each
request is written immediately, including rendered prompt, raw generated text,
IDs, timings and termination reason. No datasets or weights are committed.
Results/verdict: `koder/research/03_bakeoff_llm.md`.
