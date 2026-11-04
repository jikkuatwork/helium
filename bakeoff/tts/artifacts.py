"""Record hashes, graph I/O and ops, corpus checksums, and machine environment."""
import collections
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

import onnx
import onnxruntime as ort
from download import PHONON_REPO,PHONON_REV

ROOT=Path(__file__).parent


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        while data:=stream.read(1024*1024):h.update(data)
    return h.hexdigest()


def main():
    artifacts=[];graphs=[]
    def add(path,url):
        artifacts.append({'path':str(path),'url':url,'bytes':path.stat().st_size,'sha256':sha(path)})
    p=Path.home()/'models/tts/phonon'
    for f in sorted(p.rglob('*')):
        if not f.is_file() or f.name=='revision.txt':continue
        add(f,f'https://huggingface.co/{PHONON_REPO}/resolve/{PHONON_REV}/{f.relative_to(p)}')
    k=Path.home()/'.helium/artefacts/models/kokoro-82m-v1.0'
    for f in sorted(k.rglob('*')):
        if f.is_file():add(f,f'https://github.com/jikkuatwork/cattery-artefacts/raw/main/models/kokoro-82m-v1.0/{f.relative_to(k)}')
    whisper_api=json.loads((Path.home()/'models/tts/whisper-api.json').read_text())
    w=Path.home()/'models/tts/whisper-small.en'
    for f in sorted(w.iterdir()):
        if f.is_file():add(f,f"https://huggingface.co/Systran/faster-whisper-small.en/resolve/{whisper_api['sha']}/{f.name}")
    for f in sorted(p.glob('onnx/*.onnx'))+list(k.glob('*.onnx')):
        graph=onnx.load(str(f),load_external_data=False)
        def io(v):
            return {'name':v.name,'shape':[d.dim_param if d.dim_param else d.dim_value for d in v.type.tensor_type.shape.dim],
                    'type':onnx.TensorProto.DataType.Name(v.type.tensor_type.elem_type)}
        graphs.append({'path':str(f),'producer':graph.producer_name,'producer_version':graph.producer_version,
                       'ir':graph.ir_version,'opsets':{x.domain:x.version for x in graph.opset_import},
                       'ops':dict(collections.Counter(f'{x.domain}:{x.op_type}' for x in graph.graph.node)),
                       'inputs':[io(v) for v in graph.graph.input],'outputs':[io(v) for v in graph.graph.output]})
    out={'phonon_revision':PHONON_REV,'whisper_revision':whisper_api['sha'],
         'reference_revision':subprocess.check_output(['git','-C',str(Path.home()/'models/tts/xn-ptts'),'rev-parse','HEAD'],text=True).strip(),
         'artifacts':artifacts,'graphs':graphs,'environment':{
             'platform':platform.platform(),'machine':platform.machine(),'python':platform.python_version(),
             'ort':ort.__version__,'affinity':sorted(os.sched_getaffinity(0)),
             'go':subprocess.check_output(['go','version'],text=True).strip(),
             'lscpu':subprocess.check_output(['lscpu'],text=True),
             'corpus_sha256':sha(ROOT/'corpus.json'),'speed_texts_sha256':sha(ROOT/'speed_texts.json')}}
    (ROOT/'results/artifacts.json').write_text(json.dumps(out,indent=2)+'\n')

if __name__=='__main__':main()
