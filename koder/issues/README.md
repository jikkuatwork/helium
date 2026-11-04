# Issue Index

Every issue with its status. [../STATE.md](../STATE.md) lists only the open ones;
when filing an issue, add its row here and, while open, there.

| # | Title | Status | Pri |
|---|---|---|---|
| [01](01_onnx_inference_spike.md) | ONNX inference spike | **done** | P0 |
| [02](02_phonemizer_strategy.md) | Phonemizer strategy | **done** (espeak os/exec) | P0 |
| [03](03_wav_writer.md) | WAV writer | **done** | P1 |
| [04](04_cli.md) | CLI + model download | **done** | P1 |
| [05](05_cross_platform_build.md) | Cross-platform build | open | P2 |
| [06](06_rest_server.md) | REST API server | **done** | P1 |
| [07](07_license_audit.md) | License audit (model hosting, deps) | open (audit + repo license done) | P1 |
| [08](08_stt_module.md) | Speech-to-text module | **done** (superseded by #16-#21) | P1 |
| [09](09_pretty_help.md) | Pretty CLI help | **done** (subsumed by #19) | P3 |
| [10](10_server_api_audit.md) | Server API audit for apps | **done** (subsumed by #21) | P2 |
| [11](11_server_auth.md) | Optional server auth | **done** (plan 34) | P2 |
| [12](12_llm_proxy.md) | LLM proxy (Ollama/OpenRouter) | open | P2 |
| [13](13_local_4b_model.md) | Local LLM via ONNX | **done** (plan 36 spikes + plan 37 implementation) | P1 |
| [14](14_web_ui.md) | Embedded web UI | open | P3 |
| [15](15_mirror_json.md) | Artefact mirror registry (mirror.json) | **done** | P2 |
| [16](16_extract_ort_runtime.md) | Extract shared ORT runtime from engine/ | **done** | P0 |
| [17](17_tts_engine_interface.md) | TTS engine interface + package restructure | **done** | P0 |
| [18](18_registry_redesign.md) | Registry redesign for multi-modal artefacts | **done** | P1 |
| [19](19_cli_redesign.md) | CLI redesign: subcommand-per-modality | **done** | P1 |
| [20](20_stt_package.md) | STT package: Moonshine-tiny | **done** | P1 |
| [21](21_server_api_redesign.md) | Server API redesign for multi-modality | **done** | P2 |
| [22](22_bundle_espeak.md) | Bundle espeak-ng (zero system deps) | **done** | P1 |
| [23](23_openai_remote_engines.md) | OpenAI-compatible remote engines | open | P2 |
| [24](24_tts_sentence_chunking.md) | Transparent sentence chunking for long text TTS | **done** | P1 |
| [25](25_text_normalizer.md) | Pure Go text normalizer for TTS preprocessing | **done** | P1 |
| [26](26_stt_audio_chunking.md) | STT audio chunking to prevent hallucination | **done** | P1 |
| [27](27_bounded_memory_streaming.md) | Bounded-memory streaming for TTS/STT | **done** (native memtest validated; 4 GB / 1 GB cgroup run requires manual host) | P1 |
| [28](28_rss_validation.md) | RSS validation: TTS accumulation + STT baseline overage | **done** | P1 |
| [29](29_fix_memtest.md) | Fix memtest suite: test artifacts causing false failures and OOM risk | **done** | P1 |
| [30](30_rename_verbs.md) | Rename speak/listen → tts/stt | **done** (plan 35) | P2 |
| [31](31_simplified_ux.md) | Simplified default UX with --advanced escape hatch | **done** (plan 35) | P2 |
| [32](32_openai_compat_api.md) | OpenAI-compatible server API | **done** (plan 32) | P1 |
| [33](33_gh_actions_pr_permission.md) | Enable GH Actions PR creation permission | open | P3 |
| [34](34_trim_espeak_data.md) | Trim espeak-ng-data to English-only | **dropped** | P3 |
| [35](35_mirror_ort.md) | Mirror ORT into cattery-artefacts | **done** | P1 |
| [36](36_serve_memory_semantics.md) | Serve --memory semantics | open | P3 |

Tracker drift: 15 issue files still say `Status: open` though done here (01–04,
08–10, 16–20, 24, 25).
