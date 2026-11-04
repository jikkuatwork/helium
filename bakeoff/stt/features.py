#!/usr/bin/env python3
"""Go-ready NeMo feature specification; validate against timed ONNX frontend.

No librosa/PyTorch dependency. NumPy is only the FFT/array reference runtime.
"""
import json
from pathlib import Path
import numpy as np
from bench import DATA, MODELS, Parakeet, read_audio


def mel_filters(bins=80):
    # librosa Slaney scale: linear below 1 kHz, logarithmic above; NOT HTK.
    def hz_to_mel(hz):
        hz = np.asarray(hz)
        return np.where(hz < 1000, hz/(200/3), 15 + np.log(np.maximum(hz, 1000)/1000)/(np.log(6.4)/27))
    def mel_to_hz(mel):
        return np.where(mel < 15, mel*(200/3), 1000*np.exp((mel-15)*(np.log(6.4)/27)))
    edge = mel_to_hz(np.linspace(hz_to_mel(0), hz_to_mel(8000), bins+2))
    frequencies = np.linspace(0, 8000, 257)
    lower = (frequencies[:, None] - edge[:-2]) / np.diff(edge)[:-1]
    upper = (edge[2:] - frequencies[:, None]) / np.diff(edge)[1:]
    # librosa first rounds unnormalized triangles to float32, then scales.
    filters = np.maximum(0, np.minimum(lower, upper)).astype(np.float32)
    filters *= (2/(edge[2:]-edge[:-2])).astype(np.float32)
    return filters


def log_mel(x, bins=80):
    length = len(x)//160
    # Continuous waveform pre-emphasis, not per-frame; zero left boundary.
    x = x - np.float32(0.97)*np.pad(x, (1, 0))[:-1]
    x = np.pad(x, (256, 256), mode='constant')
    frames = np.lib.stride_tricks.sliding_window_view(x, 512)[::160]
    window = np.pad(np.hanning(400).astype(np.float32), (56, 56))
    power = np.abs(np.fft.rfft(frames*window, 512)).astype(np.float32)**2
    logged = np.log(power @ mel_filters(bins) + np.float32(2**-24))
    valid = logged[:length]
    mean = valid.mean(axis=0)
    std = valid.std(axis=0, ddof=1)
    features = np.zeros_like(logged)
    features[:length] = (valid - mean)/(std + np.float32(1e-5))
    return features.T[None], np.array([length], dtype=np.int64)


def main():
    model = Parakeet(4)
    rows = json.loads((DATA/'manifest.json').read_text())[:10]
    errors = []
    parity = []
    frame_parity = []
    differences = []
    for r in rows:
        x = read_audio(r['path'])
        expected, el = model.preprocessor(x[None], np.array([len(x)]))
        actual, al = log_mel(x)
        assert expected.shape == actual.shape and np.array_equal(el, al)
        errors.append({'id': r['id'], 'max_abs': float(np.abs(expected-actual).max()),
                       'rms': float(np.sqrt(np.mean((expected-actual)**2)))})
        a = model.model.run(None, {'audio_signal': actual, 'length': al})[0].argmax(-1)[0]
        e = model.model.run(None, {'audio_signal': expected, 'length': el})[0].argmax(-1)[0]
        valid = int((al[0]-1)//8+1)
        a, e = a[:valid], e[:valid]
        collapse = lambda ids: [int(t) for i,t in enumerate(ids) if t != 1024 and (i == 0 or t != ids[i-1])]
        at, et = collapse(a), collapse(e)
        frame_parity.append(bool(np.array_equal(a, e)))
        parity.append(at == et)
        differences.append({'id': r['id'], 'different_frames': int(np.count_nonzero(a != e)),
                            'frames': valid, 'numpy_text': ''.join(model.vocab[t] for t in at).replace('▁',' '),
                            'onnx_text': ''.join(model.vocab[t] for t in et).replace('▁',' ')})
    result = {'features': errors, 'frame_argmax_equal': frame_parity,
              'ctc_tokens_equal': parity, 'details': differences,
              'mel_filter_sha256': __import__('hashlib').sha256(mel_filters().tobytes()).hexdigest()}
    print(json.dumps(result, indent=2))
    assert max(r['max_abs'] for r in errors) < 0.002
    assert all(parity)

if __name__ == '__main__':
    main()
