"""Export a small, explicitly post-hoc diagnostic listening set; not WER selection."""
import json
from pathlib import Path
import soundfile as sf

ROOT=Path(__file__).parent
DATA=Path.home()/'datasets/tts'
DEST=Path.home()/'bakeoff-samples/tts/diagnostics'


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    corpus={x['id']:x for x in json.loads((DATA/'corpus.json').read_text())}
    selected=[('structured-12','raw'),('acronyms-36','controlled'),('acronyms-36','raw'),('names-29','controlled')]
    index=[]
    for model in ['kokoro','phonon-int8','phonon-fp32']:
        for key,mode in selected:
            raw='raw-' if mode=='raw' else ''
            source=DATA/f'{model}-{raw}{key}.wav'
            pcm,sr=sf.read(source,dtype='float32')
            name=f'{model}-{mode}-{key}.wav'
            sf.write(str(DEST/name),pcm,sr,subtype='PCM_16')
            index.append({'file':'diagnostics/'+name,'model':model,'voice':'bella' if model=='kokoro' else 'easton',
                          'corpus_id':key,'mode':mode,'text':corpus[key]['raw' if mode=='raw' else 'spoken']})
    (ROOT/'results/diagnostic_index.json').write_text(json.dumps(index,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
