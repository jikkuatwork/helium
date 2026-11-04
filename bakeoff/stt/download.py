#!/usr/bin/env python3
"""Fetch verified STT assets outside repo; existing hash-valid files are reused."""
import argparse
import hashlib
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path.home()
HF = 'https://huggingface.co/'
C = 'https://raw.githubusercontent.com/jikkuatwork/cattery-artefacts/d46bb2c528750c6a5db66deca2df88db71cc2261/models/moonshine-tiny-v1.0/'
P = HF+'csukuangfj/sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000/resolve/3af92f152d32c836acabf38f4c993bc96b80eb2d/'
Q = HF+'VocaHQ/sherpa-onnx-nemo-parakeet-tdt-ctc-110m-en-int8/resolve/43869f73831659dd8b0ccee617ee42474b7aa974/'
L = HF+'istupakov/parakeet-tdt-0.6b-v2-onnx/resolve/0bbb45a3365852604aef28b538a8f066f4ccaa85/'
ASSETS = [
 ('models/stt/moonshine/encoder_model_quantized.onnx', C+'encoder_model_quantized.onnx', 'c6fc4b7bc5af75c0591fd157a1f3829b533d18e9769a888fd95a62e470dd4f4a'),
 ('models/stt/moonshine/decoder_model_merged_quantized.onnx', C+'decoder_model_merged_quantized.onnx', 'eed87831c3a6103534aae7d47a5d485025c659a1323901513961c39fe8a1a367'),
 ('models/stt/moonshine/tokenizer.json', C+'tokenizer.json', '7b913404bdd039af4756783218af4440bc07fb7d6d8258d677e34f95b3ec416f'),
 ('models/stt/parakeet110/model.onnx', P+'model.onnx', '936806cf3dd0db5aba53f8c7410bb5632d7a8ad6b2c51009f5e4fc0890ec76bf'),
 ('models/stt/parakeet110/model.int8.onnx', Q+'model.int8.onnx', '9177a9146cf32ee0cc8152276ef95116f312018d316be37ccf57f7efea81fc1a'),
 ('models/stt/parakeet110/tokens.txt', P+'tokens.txt', '450e56bd2f036fe5b6aa821865838cc5aa9d8b0106134ce9a9ba0664abe6cd10'),
 ('datasets/stt/test-clean.tar.gz', 'https://www.openslr.org/resources/12/test-clean.tar.gz', '39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23'),
 ('datasets/stt/test-other.tar.gz', 'https://www.openslr.org/resources/12/test-other.tar.gz', 'd09c181bba5cf717b3dee7d4d592af11a3ee3a09e08ae025c5506f6ebe961c29'),
]
LARGE = [
 ('encoder-model.int8.onnx', '3e0581fda6ab843888b51e56d7ee78b6d5bc3237ec113af1f732d1d5286aa155'),
 ('decoder_joint-model.int8.onnx', 'a449f49acd68979d418651dd2dcb737cc0f1bf0225e009e29ee326354edbf7d3'),
 ('vocab.txt', 'ec182b70dd42113aff6c5372c75cac58c952443eb22322f57bbd7f53977d497d'),
 ('config.json', '666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466'),
 ('nemo128.onnx', 'a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f'),
]


def sha256(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def fetch(relative, url, expected):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or sha256(path) != expected:
        temp = path.with_name(path.name+'.part')
        print('download', url, flush=True)
        urllib.request.urlretrieve(url, temp)
        actual = sha256(temp)
        if actual != expected:
            raise ValueError(f'{path}: SHA-256 mismatch: {actual}, expected {expected}')
        temp.replace(path)
    print(expected, path, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--large', action='store_true')
    args = p.parse_args()
    for item in ASSETS:
        fetch(*item)
    if args.large:
        for name, sha in LARGE:
            fetch('models/stt/parakeet600/'+name, L+name, sha)
    for split in ['test-clean', 'test-other']:
        if not (ROOT/'datasets/stt/LibriSpeech'/split).is_dir():
            with tarfile.open(ROOT/'datasets/stt'/f'{split}.tar.gz') as archive:
                archive.extractall(ROOT/'datasets/stt', filter='data')
