"""Evaluation runners, not helium integration. CPU EP; current Phonon export.

Phonon HF revision f0f522a: 8 AR frames/call, stateless Mimi decoding.
Already-normalized text is required. Neither sampler nor PCM is time-stretched.
"""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

PHONON = Path.home() / 'models/tts/phonon'
KOKORO = Path.home() / '.helium/artefacts/models/kokoro-82m-v1.0'
VOICES = {'easton': 'LMDIYE0Oa377Qh6Z', 'zoey': 'NbpkqMVS3CJeq2j8', 'default': 'default'}


def session(path, threads):
    assert ort.__version__ == '1.24.4', ort.__version__
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.log_severity_level = 3
    return ort.InferenceSession(str(path), opts, providers=['CPUExecutionProvider'])


def split_text(text, tokenizer, limit=50):
    """Sentence/clause/word chunks, <=50 Unigram tokens. No silent truncation."""
    text = re.sub(r'\s+', ' ', text.strip())
    def split(s, level=0):
        if len(tokenizer.encode(s, add_special_tokens=False).ids) <= limit:
            return [s]
        patterns = [r'(?<=[.!?])\s+', r'(?<=[,;:])\s+', r'\s+']
        if level >= len(patterns):
            raise ValueError('Single word exceeds token budget')
        parts = re.split(patterns[level], s)
        result = []
        for part in parts:
            result.extend(split(part, level + 1))
        return result
    # Sentence isolation is deliberate: matches runtime reset at sentence boundaries.
    chunks = []
    for sentence in re.split(r'(?<=[.!?])\s+', text):
        current = ''
        for piece in split(sentence):
            joined = (current + ' ' + piece).strip()
            # Budget includes the final period that speak() may append.
            candidate = joined if not joined[-1:].isalnum() else joined + '.'
            if current and len(tokenizer.encode(candidate, add_special_tokens=False).ids) > limit:
                chunks.append(current)
                current = piece
            else:
                current = joined
        if current:
            chunks.append(current)
    return chunks


class Phonon:
    def __init__(self, precision='int8', threads=4, voice='easton', decoder_precision=None):
        suffix = '_int8' if precision == 'int8' else ''
        decsuffix = '_int8' if (decoder_precision or precision) == 'int8' else ''
        self.flow = session(PHONON / f'onnx/model{suffix}.onnx', threads)
        self.decoder = session(PHONON / f'onnx/mimi_decoder{decsuffix}.onnx', threads)
        self.tokenizer = Tokenizer.from_file(str(PHONON / 'tokenizer.json'))
        self.voice = np.fromfile(PHONON / f'voices/{VOICES.get(voice, voice)}.bin', dtype='<f4').reshape(1, 512, -1).transpose(0, 2, 1).copy()
        self.names = [x.name for x in self.flow.get_outputs()]
        self.last_latents = []

    def speak(self, text, seed=1234, temperature=.3):
        start = time.perf_counter()
        rng = np.random.default_rng(seed)
        audio, details = [], []
        first = None
        self.last_latents = []
        for sentence in split_text(text, self.tokenizer):
            sentence = sentence[0].upper() + sentence[1:]
            if sentence[-1].isalnum():
                sentence += '.'
            ids = self.tokenizer.encode(sentence, add_special_tokens=False).ids
            state = {f'past_key_values.{i}.{k}': np.zeros((1, 8, 0, 64), np.float32) for i in range(6) for k in ['key', 'value']}
            state['past_key_values.audio_latents'] = np.zeros((1, 0, 32), np.float32)
            stop = None
            cap = math.ceil((len(ids) / 3 + 2) * 12.5)
            tail = 3 if len(sentence.split()) <= 4 else 1
            for block in range(math.ceil(cap / 8)):
                past = state['past_key_values.0.key'].shape[2]
                new = self.voice.shape[1] + len(ids) + 1 if block == 0 else 1
                # All 8 positions/mask columns must be supplied, not only prefill.
                feed = dict(state, input_ids=np.array([ids] if block == 0 else [[]], np.int64),
                            audio_prompt_latents=self.voice if block == 0 else np.zeros((1, 0, 512), np.float32),
                            attention_mask=np.ones((1, past + new + 7), np.int64),
                            position_ids=np.arange(past, past + new + 7, dtype=np.int64)[None, :],
                            noise=(rng.standard_normal((1, 8, 32)) * math.sqrt(temperature)).astype(np.float32))
                out = dict(zip(self.names, self.flow.run(None, feed)))
                state = {k.replace('present.', 'past_key_values.'): v for k, v in out.items() if k.startswith('present.')}
                hits = np.flatnonzero(out['eos_logits'][0] > 4.)
                if stop is None and len(hits):
                    stop = block * 8 + int(hits[0]) + 1 + tail
                if stop is not None and (block + 1) * 8 >= stop:
                    break
            n = min(stop or cap, out['audio_latents'].shape[1])
            lat = out['audio_latents'][:, :n].copy()
            self.last_latents.append(lat)
            pcm = self.decoder.run(None, {'audio_latents': lat, 'num_frames': np.array([n], np.int64)})[0].ravel()
            if not np.isfinite(pcm).all():
                raise ValueError('Non-finite Phonon PCM')
            if first is None:
                first = time.perf_counter() - start
            audio.append(pcm)
            details.append({'text': sentence, 'tokens': len(ids), 'frames': n, 'eos': stop, 'capped': stop is None})
        pcm = np.concatenate(audio)
        elapsed = time.perf_counter() - start
        return pcm, {'wall_s': elapsed, 'ttfa_s': first, 'audio_s': len(pcm) / 24000,
                     'rtfx': len(pcm) / 24000 / elapsed, 'chunks': details}


# Same vocabulary and chunk policy as helium, stored explicitly for reproducibility.
VOCAB = json.loads((Path(__file__).parent / 'kokoro_vocab.json').read_text())


def kokoro_chunks(phonemes, limit=480):
    def count(s): return sum(c in VOCAB for c in s)
    def divide(s, level=0):
        if count(s) <= limit: return [s]
        patterns = [r'(?<=[.!?])\s+', r'(?<=[,;:—…])\s+', r'\s+']
        if level == len(patterns):
            raise ValueError('Single phoneme word over 480 tokens')
        return [v for p in re.split(patterns[level], s) for v in divide(p, level+1)]
    chunks, current = [], ''
    for p in divide(phonemes):
        joined = (current + ' ' + p).strip()
        if count(joined) > limit:
            chunks.append(current)
            current = p
        else: current = joined
    if current: chunks.append(current)
    return chunks


class Kokoro:
    def __init__(self, precision='int8', threads=4, voice='bella'):
        self.model = session(KOKORO / 'model_quantized.onnx', threads)
        self.voice = np.fromfile(KOKORO / f'voices/af_{voice}.bin', dtype='<f4').reshape(-1, 256)

    def speak(self, text, **_):
        start = time.perf_counter()
        # Exact existing Go normalization + phonemizer, including subprocesses.
        data = json.loads(subprocess.check_output(['/tmp/tts-preprocess', text]))
        audio, first, details = [], None, []
        for chunk in kokoro_chunks(data['phonemes']):
            ids = [VOCAB[c] for c in chunk if c in VOCAB]
            if not ids: continue
            pcm = self.model.run(None, {'input_ids': np.array([[0]+ids+[0]], np.int64),
                  'style': self.voice[min(len(ids), len(self.voice)-1)][None, :], 'speed': np.array([1.], np.float32)})[0].ravel()
            if first is None: first = time.perf_counter() - start
            if audio: audio.append(np.zeros(1800, np.float32))
            audio.append(pcm)
            details.append({'tokens': len(ids)})
        pcm = np.concatenate(audio)
        elapsed = time.perf_counter() - start
        return pcm, {'wall_s': elapsed, 'ttfa_s': first, 'audio_s': len(pcm) / 24000,
                     'rtfx': len(pcm) / 24000 / elapsed, 'chunks': details, 'normalized': data['normalized']}
