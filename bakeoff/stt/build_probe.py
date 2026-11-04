#!/usr/bin/env python3
"""Build evaluation-only Go probe with controlled ORT threads via Go overlay.

No tracked product file is edited. Only session options differ from helium's
Moonshine package. Chunking, decoder, tokenizer, WAV reader remain unchanged.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(__doc__)
parser.add_argument('--program', default='bakeoff/stt/helium_probe.go')
parser.add_argument('--output', default='/tmp/stt-helium-probe')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
source = root / 'stt/moonshine/moonshine.go'
text = source.read_text()
old = '\tencoder, err := ortgo.NewDynamicAdvancedSession('
new = '''\t// Evaluation-only thread control (Go build overlay, not product integration).
\tthreads := 4
\tif os.Getenv("HELIUM_BAKE_THREADS") == "1" { threads = 1 }
\tsessionOptions, err := ortgo.NewSessionOptions()
\tif err != nil { return nil, err }
\tdefer sessionOptions.Destroy()
\tif err := sessionOptions.SetIntraOpNumThreads(threads); err != nil { return nil, err }
\tif err := sessionOptions.SetInterOpNumThreads(1); err != nil { return nil, err }
\tencoder, err := ortgo.NewDynamicAdvancedSession('''
assert text.count(old) == 1
assert text.count('\n\t\tnil,\n') == 2
text = text.replace(old, new).replace('\n\t\tnil,\n', '\n\t\tsessionOptions,\n').replace('"io"', '"io"\n "os"')
with tempfile.TemporaryDirectory(prefix='stt-overlay-') as tmp:
    temp = Path(tmp)
    (temp/'moonshine.go').write_text(text)
    (temp/'overlay.json').write_text(json.dumps({'Replace': {str(source): str(temp/'moonshine.go')}}))
    subprocess.run(['taskset', '-c', '8-15', 'go', 'build', '-overlay', str(temp/'overlay.json'),
                    '-o', args.output, str(root/args.program)], cwd=root, check=True)
print(f'{args.output} (evaluation-only overlay; product files unchanged)')
