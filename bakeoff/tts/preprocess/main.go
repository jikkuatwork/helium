// Evaluation-only bridge to helium's exact normalizer and phonemizer.
package main

import (
	"encoding/json"
	"fmt"
	"github.com/jikkuatwork/helium/normalize"
	"github.com/jikkuatwork/helium/phonemize"
	"os"
	"path/filepath"
)

func main() {
	if len(os.Args) != 2 {
		panic("usage: tts-preprocess TEXT")
	}
	home, _ := os.UserHomeDir()
	phonemize.BinPath = filepath.Join(home, ".helium/espeak-ng/bin/espeak-ng")
	phonemize.DataPath = filepath.Join(home, ".helium/espeak-ng/data")
	normalized := normalize.Normalize(os.Args[1])
	p := &phonemize.EspeakPhonemizer{Voice: "en-us"}
	ipa, err := p.Phonemize(normalized)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	json.NewEncoder(os.Stdout).Encode(map[string]string{"normalized": normalized, "phonemes": ipa})
}
