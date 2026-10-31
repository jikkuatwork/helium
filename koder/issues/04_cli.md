# 04 — CLI with Model Download Support

**Status**: open
**Priority**: P1

## Goal

`helium --text "hello" --voice Leo --output out.wav`

## Acceptance criteria

- [ ] CLI parses text, voice, output flags
- [ ] Downloads model files on first run (or via `helium download`)
- [ ] Lists available voices via `helium voices`
- [ ] Streams output for long text (not buffer-all-then-write)

## Dependencies

- Depends on issues 01, 02, 03
