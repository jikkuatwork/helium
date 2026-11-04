"""Fetch pinned public evaluation artifacts outside the repository.

After download, compare every SHA256 with results/artifacts.json. Helium owns
its default Kokoro location; this script does not modify existing Go packages.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.request

PHONON_REV='f0f522a750bf515227cb478abb97b2ffca7e6d8c'
PHONON_REPO='onnx-community/phonon-31m-en-ONNX'


def main():
    root=Path.home()/'models/tts/phonon'
    files=['config.json','generation_config.json','tokenizer.json','tokenizer_config.json',
           'processor_config.json','preprocessor_config.json','README.md','voices/default.bin',
           'voices/LMDIYE0Oa377Qh6Z.bin','voices/NbpkqMVS3CJeq2j8.bin','voices/voices.jsonl']
    files += [f'onnx/{name}.onnx{suffix}' for name in ['model','model_int8','mimi_decoder','mimi_decoder_int8'] for suffix in ['', '_data']]
    def get(name):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        url=f'https://huggingface.co/{PHONON_REPO}/resolve/{PHONON_REV}/{name}'
        if not path.exists(): urllib.request.urlretrieve(url,path)
        print(name,path.stat().st_size,flush=True)
    with ThreadPoolExecutor(4) as pool:list(pool.map(get,files))
    (root/'revision.txt').write_text(PHONON_REV+'\n')
    for voice in ['af_bella','af_heart']:
        path=Path.home()/f'.helium/artefacts/models/kokoro-82m-v1.0/voices/{voice}.bin'
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            urllib.request.urlretrieve(f'https://github.com/jikkuatwork/cattery-artefacts/raw/main/models/kokoro-82m-v1.0/voices/{voice}.bin',path)
    manifest=Path(__file__).parent/'results/artifacts.json'
    if manifest.exists():
        from huggingface_hub import snapshot_download
        data=json.loads(manifest.read_text())
        snapshot_download('Systran/faster-whisper-small.en',revision=data['whisper_revision'],
                          local_dir=str(Path.home()/'models/tts/whisper-small.en'),
                          allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.txt'])
    else:
        print('Whisper revision comes from final results/artifacts.json; download that exact revision.')

if __name__=='__main__':main()
