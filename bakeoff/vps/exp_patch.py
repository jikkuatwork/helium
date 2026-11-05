"""Throwaway experiment patch (never committed): env knobs for Kokoro chunk tokens and ORT arena."""
import pathlib, sys
root = pathlib.Path(sys.argv[1])
p = root / "tts/kokoro/kokoro.go"; s = p.read_text()
old_sess = '''	session, err := ort.NewDynamicAdvancedSession(
		modelPath,
		[]string{"input_ids", "style", "speed"},
		[]string{"waveform"},
		nil,
	)'''
new_sess = '''	var expOpts *ort.SessionOptions
	if os.Getenv("HELIUM_EXP_NO_ARENA") == "1" {
		o, oerr := ort.NewSessionOptions()
		if oerr != nil {
			return nil, oerr
		}
		defer o.Destroy()
		_ = o.SetCpuMemArena(false)
		_ = o.SetMemPattern(false)
		expOpts = o
	}
	session, err := ort.NewDynamicAdvancedSession(
		modelPath,
		[]string{"input_ids", "style", "speed"},
		[]string{"waveform"},
		expOpts,
	)'''
assert s.count(old_sess) == 1; s = s.replace(old_sess, new_sess)
old_chunk = "	chunks := chunkPhonemes(phonemes, chunkTokenLimit)"
new_chunk = '''	expTokens := chunkTokenLimit
	if v, perr := strconv.Atoi(os.Getenv("HELIUM_EXP_KOKORO_TOKENS")); perr == nil && v > 0 {
		expTokens = v
	}
	chunks := chunkPhonemes(phonemes, expTokens)'''
assert s.count(old_chunk) == 1; s = s.replace(old_chunk, new_chunk)
imp = "import (\n"
assert s.count(imp) == 1
add = ""
if '\t"os"\n' not in s: add += '\t"os"\n'
if '\t"strconv"\n' not in s: add += '\t"strconv"\n'
s = s.replace(imp, imp + add, 1)
p.write_text(s); print("patched", p)
