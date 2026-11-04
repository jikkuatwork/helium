#!/usr/bin/env python3
"""CPU-only STT evaluation using helium's exact Moonshine weights/greedy loop.

All downloads and audio stay outside the repo. Run via taskset -c 8-15.
Outputs are JSONL (per-utterance), JSON (timing/aggregate), and time -v logs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import resource
import statistics
import time

# Avoid a hidden BLAS thread pool. ORT's threads are set independently below.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import jiwer
import numpy as np
import onnxruntime as ort
import soundfile as sf
from onnx_asr.preprocessors.preprocessor import OnnxPreprocessor

HOME = Path.home()
MODELS = HOME / 'models/stt'
DATA = HOME / 'datasets/stt'
SAMPLES = HOME / 'bakeoff-samples/stt'


def normalize(text):
    # Keep within-word apostrophes by deleting punctuation, not replacing it.
    return ' '.join(re.sub(r'[^\w\s]', '', text.lower()).split())


def session(path, threads):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.log_severity_level = 3
    return ort.InferenceSession(str(path), options, providers=['CPUExecutionProvider'])


class Moonshine:
    def __init__(self, threads):
        root = MODELS / 'moonshine'
        self.encoder = session(root / 'encoder_model_quantized.onnx', threads)
        self.decoder = session(root / 'decoder_model_merged_quantized.onnx', threads)
        self.vocab = {v: k for k, v in json.loads((root / 'tokenizer.json').read_text())['model']['vocab'].items()}
        self.cache_names = [i.name for i in self.decoder.get_inputs() if i.name.startswith('past_key_values')]
        self.output_names = [i.name for i in self.decoder.get_outputs()]

    def __call__(self, x):
        h = self.encoder.run(None, {'input_values': x[None]})[0]
        cache = {name: np.empty((1, 8, 0, 36), dtype=np.float32) for name in self.cache_names}
        token, tokens = 1, []
        for step in range(448):
            out = self.decoder.run(None, {
                'input_ids': np.array([[token]], dtype=np.int64),
                'encoder_hidden_states': h,
                'use_cache_branch': np.array([step > 0]), **cache,
            })
            token = int(out[0][0, -1].argmax())
            # Helium retains encoder K/V from step zero; later outputs are empty.
            for name, value in zip(self.output_names[1:], out[1:]):
                key = name.replace('present', 'past_key_values', 1)
                if step == 0 or '.decoder.' in key:
                    cache[key] = value
            if token == 2:
                break
            tokens.append(token)
        return ''.join(self.vocab.get(t, '') for t in tokens).replace('▁', ' ').strip()


class Parakeet:
    def __init__(self, threads, fp32=False):
        self.model = session(MODELS / 'parakeet110' / ('model.onnx' if fp32 else 'model.int8.onnx'), threads)
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.log_severity_level = 3
        self.preprocessor = OnnxPreprocessor('nemo80', {'sess_options': options, 'providers': ['CPUExecutionProvider']})
        self.vocab = {int(i): t for t, i in (line.rstrip('\n').rsplit(' ', 1) for line in (MODELS / 'parakeet110/tokens.txt').read_text().splitlines())}

    def __call__(self, x):
        features, length = self.preprocessor(x[None], np.array([len(x)], dtype=np.int64))
        out = self.model.run(None, {'audio_signal': features, 'length': length})[0]
        ids = out[0, :int((length[0] - 1) // 8 + 1)].argmax(-1)
        return ''.join(self.vocab.get(int(token), '') for j, token in enumerate(ids)
                       if token != 1024 and (j == 0 or token != ids[j-1])).replace('▁', ' ').strip()


class Large:
    def __init__(self, threads):
        import onnx_asr
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.model = onnx_asr.load_model('nemo-conformer-tdt', path=str(MODELS / 'parakeet600'),
            quantization='int8', sess_options=options, providers=['CPUExecutionProvider'])

    def __call__(self, x):
        return self.model.recognize(x, sample_rate=16000)


def get_model(name, threads):
    assert ort.__version__ == '1.24.4', ort.__version__
    return {'moonshine': lambda: Moonshine(threads), 'parakeet': lambda: Parakeet(threads),
            'parakeet-fp32': lambda: Parakeet(threads, True), 'large': lambda: Large(threads)}[name]()


def read_audio(path):
    x, sr = sf.read(path, dtype='float32')
    assert sr == 16000 and x.ndim == 1, (sr, x.shape)
    return x


def prepare(args):
    manifest = []
    for split in ['test-clean', 'test-other']:
        refs = {}
        root = DATA / 'LibriSpeech' / split
        for p in sorted(root.glob('*/*/*.trans.txt')):
            for line in p.read_text().splitlines():
                uid, text = line.split(' ', 1)
                refs[uid] = text
        # Uniform random utterance sample, not prefix/chapter biased.
        paths = sorted(root.glob('*/*/*.flac'))
        rng = random.Random(20261104 if split == 'test-clean' else 20261105)
        rng.shuffle(paths)
        selected = [p for p in paths if sf.info(p).duration <= 29.5][:args.count]
        for p in selected:
            manifest.append({'id': p.stem, 'split': split, 'path': str(p), 'reference': refs[p.stem], 'duration': sf.info(p).duration})
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    clean = [r for r in manifest if r['split'] == 'test-clean']
    SAMPLES.mkdir(parents=True, exist_ok=True)
    long = []
    for minutes in [5, 12, 20]:
        parts, selected, total = [], [], 0.0
        for r in clean:
            x = read_audio(r['path'])
            parts.append(x)
            selected.append(r)
            total += len(x)/16000
            if total >= minutes * 60:
                break
        path = SAMPLES / f'long-{minutes}min.wav'
        sf.write(path, np.concatenate(parts), 16000, subtype='PCM_16')
        long.append({'id': f'long-{minutes}min', 'split': 'long', 'path': str(path),
                     'reference': ' '.join(r['reference'] for r in selected), 'duration': total,
                     'source_ids': [r['id'] for r in selected]})
    (DATA / 'long.json').write_text(json.dumps(long, indent=2))
    # Save listening examples, without clipping added noise (float WAV).
    for snr in [10, 0]:
        for j, r in enumerate(clean[:3]):
            sf.write(SAMPLES / f'noise-{snr}db-{j}.wav', add_noise(read_audio(r['path']), snr, r['id']), 16000, subtype='FLOAT')
    print(json.dumps({'utterances': len(manifest), 'seconds': sum(r['duration'] for r in manifest), 'long': long}, indent=2))


def add_noise(x, snr, uid):
    seed = int.from_bytes(hashlib.sha256(uid.encode()).digest()[:8], 'little')
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(x), dtype=np.float32)
    noise *= np.sqrt(np.mean(x*x) / (10**(snr/10) * np.mean(noise*noise)))
    return x + noise


def aggregate(rows):
    ref = [normalize(r['reference']) for r in rows]
    hyp = [normalize(r['hypothesis']) for r in rows]
    w = jiwer.process_words(ref, hyp)
    seconds = sum(r['elapsed'] for r in rows)
    duration = sum(r['duration'] for r in rows)
    return {'utterances': len(rows), 'reference_words': w.hits + w.substitutions + w.deletions,
            'wer': w.wer, 'substitutions': w.substitutions, 'insertions': w.insertions,
            'deletions': w.deletions, 'audio_seconds': duration, 'inference_seconds': seconds,
            'rtf': seconds/duration, 'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def accuracy(args):
    rows = json.loads((DATA / 'manifest.json').read_text())
    if args.split:
        rows = [r for r in rows if r['split'] == args.split]
    if args.snr is not None:
        rows = [r for r in rows if r['split'] == 'test-clean'][:50]
    if args.limit:
        rows = rows[:args.limit]
    model = get_model(args.model, args.threads)
    model(read_audio(rows[0]['path']))  # Untimed warm-up.
    done = []
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w') as f:
        for i, r in enumerate(rows):
            x = read_audio(r['path'])
            if args.snr is not None:
                x = add_noise(x, args.snr, r['id'])
            start = time.perf_counter()
            hyp = model(x)
            elapsed = time.perf_counter() - start
            row = {**r, 'model': args.model, 'threads': args.threads, 'snr': args.snr,
                   'hypothesis': hyp, 'elapsed': elapsed}
            f.write(json.dumps(row) + '\n')
            f.flush()
            done.append(row)
            if (i + 1) % 25 == 0:
                print(i+1, args.model, aggregate(done), flush=True)
    summary = {split: aggregate([r for r in done if r['split'] == split]) for split in sorted(set(r['split'] for r in done))}
    out.with_suffix('.summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


def fixed_chunks(model, x, seconds):
    # Separate controlled chunking experiment, NOT claimed identical to helium.
    size = int(seconds*16000)
    return ' '.join(model(x[start:start+size]) for start in range(0, len(x), size))


def timing(args):
    x = read_audio(args.audio)
    start = time.perf_counter()
    model = get_model(args.model, args.threads)
    load = time.perf_counter()-start
    call = lambda: fixed_chunks(model, x, args.chunk) if args.chunk else model(x)
    print('loaded', args.model, load, flush=True)
    start = time.perf_counter()
    hyp = call()
    print('warmup', time.perf_counter()-start, flush=True)
    runs = []
    for i in range(args.runs):
        start = time.perf_counter()
        hyp = call()
        runs.append(time.perf_counter()-start)
        print('run', i+1, runs[-1], flush=True)
    result = {'model': args.model, 'threads': args.threads, 'audio': args.audio,
              'duration': len(x)/16000, 'chunk_seconds': args.chunk, 'load_seconds': load,
              'runs_seconds': runs, 'median_seconds': statistics.median(runs),
              'median_rtf': statistics.median(runs)/(len(x)/16000),
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'hypothesis': hyp,
              'ort_version': ort.__version__, 'affinity': sorted(os.sched_getaffinity(0))}
    if args.reference:
        ref = next(r['reference'] for r in json.loads((DATA/'long.json').read_text()) if r['path'] == args.audio)
        result['wer'] = jiwer.wer(normalize(ref), normalize(hyp))
    Path(args.output).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('command', choices=['prepare', 'accuracy', 'timing'])
    parser.add_argument('--model', choices=['moonshine', 'parakeet', 'parakeet-fp32', 'large'], default='parakeet')
    parser.add_argument('--threads', type=int, choices=[1, 4], default=4)
    parser.add_argument('--count', type=int, default=320)
    parser.add_argument('--split', choices=['test-clean', 'test-other'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--snr', type=float)
    parser.add_argument('--audio')
    parser.add_argument('--chunk', type=float, default=0)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--reference', action='store_true')
    parser.add_argument('--output', default='bakeoff/stt/results/output.jsonl')
    args = parser.parse_args()
    {'prepare': prepare, 'accuracy': accuracy, 'timing': timing}[args.command](args)
