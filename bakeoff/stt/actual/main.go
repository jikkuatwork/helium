// Evaluate helium's actual Moonshine WAV reader, silence gate and decoder.
// Build using the same session-thread-only overlay as helium_probe.go.
package main

import (
	"encoding/json"
	"fmt"
	"github.com/jikkuatwork/helium/stt"
	"github.com/jikkuatwork/helium/stt/moonshine"
	ortgo "github.com/yalue/onnxruntime_go"
	"os"
)

type row struct {
	ID        string   `json:"id"`
	Split     string   `json:"split"`
	Path      string   `json:"path"`
	Reference string   `json:"reference"`
	SNR       *float64 `json:"snr"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	if len(os.Args) != 2 {
		return fmt.Errorf("one WAV manifest JSON path required")
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		return err
	}
	var rows []row
	if err = json.Unmarshal(data, &rows); err != nil {
		return err
	}
	if len(rows) == 0 {
		return fmt.Errorf("empty manifest")
	}
	ortgo.SetSharedLibraryPath(os.Getenv("HOME") + "/.helium/ort/libonnxruntime.so.1.24.4")
	if err = ortgo.InitializeEnvironment(); err != nil {
		return err
	}
	defer ortgo.DestroyEnvironment()
	if ortgo.GetVersion() != "1.24.4" {
		return fmt.Errorf("expected ORT 1.24.4, got %s", ortgo.GetVersion())
	}
	engine, err := moonshine.New(os.Getenv("HOME")+"/models/stt/moonshine", nil)
	if err != nil {
		return err
	}
	defer engine.Close()
	call := func(path string) (*stt.Result, error) {
		f, err := os.Open(path)
		if err != nil {
			return nil, err
		}
		defer f.Close()
		return engine.Transcribe(f, stt.Options{})
	}
	if _, err = call(rows[0].Path); err != nil {
		return fmt.Errorf("warm-up: %w", err)
	}
	encoder := json.NewEncoder(os.Stdout)
	for i, r := range rows {
		result, err := call(r.Path)
		if err != nil {
			return fmt.Errorf("%s: %w", r.ID, err)
		}
		out := struct {
			row
			Hypothesis string  `json:"hypothesis"`
			Elapsed    float64 `json:"elapsed"`
			Duration   float64 `json:"duration"`
		}{r, result.Text, result.Elapsed, result.Duration}
		if err = encoder.Encode(out); err != nil {
			return err
		}
		if (i+1)%50 == 0 {
			fmt.Fprintf(os.Stderr, "%d/%d\n", i+1, len(rows))
		}
	}
	return nil
}
