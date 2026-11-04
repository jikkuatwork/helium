#!/usr/bin/env python3
"""Download just the CPU q4 artefacts at immutable HF revisions."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download

REPOS = {
    'qwen': 'onnx-community/Qwen3.5-4B-ONNX',
    'lfm3': 'LiquidAI/LFM3-1.7B-ONNX',
    'lfm25': 'LiquidAI/LFM2.5-1.2B-Instruct-ONNX',
}


def main():
    manifest = {}
    for name, repo in REPOS.items():
        root = Path.home() / 'models/llm' / name
        info = HfApi().model_info(repo, files_metadata=True)
        revision = json.loads((root / 'hf-api.json').read_text())['sha'] if (root / 'hf-api.json').exists() else info.sha
        files = HfApi().list_repo_files(repo, revision=revision)
        prefixes = ['onnx/decoder_model_merged_q4.onnx', 'onnx/embed_tokens_q4.onnx'] if name == 'qwen' else ['onnx/model_q4.onnx']
        selected = [f for f in files if any(f == p or f.startswith(p + '_data') for p in prefixes) or f in ['README.md', 'LICENSE', 'config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja']]
        manifest[name] = {'repo': repo, 'revision': revision, 'files': {}}
        for f in selected:
            print(name, f, flush=True)
            path = Path(hf_hub_download(repo, f, revision=revision, local_dir=root))
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    h.update(block)
            manifest[name]['files'][f] = {'bytes': path.stat().st_size, 'sha256': h.hexdigest()}
        (root / 'manifest.json').write_text(json.dumps(manifest[name], indent=2))
    Path('bakeoff/llm/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
