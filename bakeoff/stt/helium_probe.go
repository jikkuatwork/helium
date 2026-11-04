// Evaluation helper: run helium's Moonshine engine, including its unchanged
// silence-aware chunker and overlap stitcher. Build with build_probe.py for an
// evaluation-only Go overlay that controls intra-op threads (HELIUM_BAKE_THREADS).
// Direct ORT init avoids ort.Init's stderr redirection so errors remain visible.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"github.com/jikkuatwork/helium/stt"
	"github.com/jikkuatwork/helium/stt/moonshine"
	ortgo "github.com/yalue/onnxruntime_go"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	model := flag.String("model", os.Getenv("HOME")+"/models/stt/moonshine", "model directory")
	lib := flag.String("lib", os.Getenv("HOME")+"/.helium/ort/libonnxruntime.so.1.24.4", "ORT shared library")
	runs := flag.Int("runs", 5, "timed repetitions after one warm-up")
	flag.Parse()
	if flag.NArg() != 1 || *runs < 1 {
		return fmt.Errorf("one WAV path and positive run count required")
	}
	ortgo.SetSharedLibraryPath(*lib)
	if err := ortgo.InitializeEnvironment(); err != nil {
		return fmt.Errorf("initialize ORT: %w", err)
	}
	defer ortgo.DestroyEnvironment()
	engine, err := moonshine.New(*model, nil)
	if err != nil {
		return fmt.Errorf("load Moonshine: %w", err)
	}
	defer engine.Close()
	call := func() (*stt.Result, error) {
		f, err := os.Open(flag.Arg(0))
		if err != nil {
			return nil, err
		}
		defer f.Close()
		return engine.Transcribe(f, stt.Options{})
	}
	warm, err := call()
	if err != nil {
		return fmt.Errorf("warm-up: %w", err)
	}
	fmt.Fprintf(os.Stderr, "warmup: %.3fs audio, %.3fs elapsed\n", warm.Duration, warm.Elapsed)
	elapsed := make([]float64, 0, *runs)
	var result *stt.Result
	for i := 0; i < *runs; i++ {
		start := time.Now()
		result, err = call()
		if err != nil {
			return fmt.Errorf("run %d: %w", i+1, err)
		}
		elapsed = append(elapsed, time.Since(start).Seconds())
		fmt.Fprintf(os.Stderr, "run %d: %.3fs\n", i+1, elapsed[i])
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]any{
		"result": result, "wall_seconds": elapsed,
		"threads": os.Getenv("HELIUM_BAKE_THREADS"),
		"note":    "build with build_probe.py for controlled threads",
	})
}
