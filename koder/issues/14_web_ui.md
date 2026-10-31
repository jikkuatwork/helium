# 14 — Embedded Web UI

## Status: open (idea)
## Priority: P3

Zero-build, zero-dependency web UI served by helium itself:
- Single HTML file embedded via `embed.FS`
- Vanilla JS, no framework, no build step
- Clean, minimal design
- Connects to the same server endpoints

Features:
- Text input → play audio (via /v1/tts)
- Voice selector dropdown (via /v1/voices)
- Server status display (via /v1/status)
- If LLM proxy exists (#12): chat interface
- If STT exists (#08): microphone input → transcribe → respond → play

Served at `GET /` when running `helium serve`.

## Why

- `helium serve` and open browser — that's it
- No npm, no node, no webpack
- Works on any device with a browser
- Demo-friendly: show someone what helium does in 5 seconds
