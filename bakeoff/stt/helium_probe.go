// Evaluation helper: run helium's unchanged Moonshine engine, including its
// silence-aware chunker and overlap stitcher. Session options remain helium's
// defaults; this helper is for parity/long-audio checks, NOT 4/1-thread rankings.
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
 model := flag.String("model", os.Getenv("HOME")+"/models/stt/moonshine", "model directory")
 lib := flag.String("lib", os.Getenv("HOME")+"/.helium/ort/libonnxruntime.so.1.24.4", "ORT shared library")
 runs := flag.Int("runs", 5, "timed repetitions after one warm-up")
 flag.Parse()
 if flag.NArg()!=1 { panic("one WAV path required") }
 ortgo.SetSharedLibraryPath(*lib)
 if err:=ortgo.InitializeEnvironment(); err!=nil { panic(err) }
 defer ortgo.DestroyEnvironment()
 engine,err:=moonshine.New(*model,nil); if err!=nil { panic(err) }; defer engine.Close()
 call:=func() *stt.Result {
  f,err:=os.Open(flag.Arg(0)); if err!=nil { panic(err) }; defer f.Close()
  r,err:=engine.Transcribe(f,stt.Options{}); if err!=nil { panic(err) }; return r
 }
 warm:=call(); fmt.Fprintf(os.Stderr,"warmup: %+v\n",warm)
 elapsed:=[]float64{}; var r *stt.Result
 for i:=0;i<*runs;i++ { t:=time.Now(); r=call(); elapsed=append(elapsed,time.Since(t).Seconds()) }
 if err:=json.NewEncoder(os.Stdout).Encode(map[string]any{"result":r,"wall_seconds":elapsed,"note":"helium default ORT threads; not explicitly 4/1"}); err!=nil { panic(err) }
}
