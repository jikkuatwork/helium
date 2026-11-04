"""Synthesize fixed corpus and samples outside the repository; no ASR in this process."""
import json
from pathlib import Path
import time

import soundfile as sf
from runners import Phonon, Kokoro

ROOT = Path(__file__).parent
DATA = Path.home()/'datasets/tts'
SAMPLES = Path.home()/'bakeoff-samples/tts'


def main():
    SAMPLES.mkdir(parents=True,exist_ok=True)
    (ROOT/'results').mkdir(parents=True,exist_ok=True)
    rows = json.loads((DATA/'corpus.json').read_text())
    meta = []
    # No concurrent model sessions during synthesis or timing.
    for model in ['kokoro','phonon-int8','phonon-fp32']:
        engine = Kokoro(threads=4) if model=='kokoro' else Phonon(precision=model.split('-')[1],threads=4)
        engine.speak('This is a warm up before the evaluation.')
        for row in rows:
            path = DATA/f"{model}-{row['id']}.wav"
            pcm, detail = engine.speak(row['spoken'])
            sf.write(str(path),pcm,24000,subtype='FLOAT')
            meta.append({'model':model,'mode':'controlled','id':row['id'],'category':row['category'],'path':str(path),**detail})
            (ROOT/'results/synthesis.json').write_text(json.dumps(meta,indent=2)+'\n')
            print(model,row['id'],round(detail['rtfx'],2),flush=True)
        # Separate production-input audit: do not mix normalization with controlled WER.
        for row in rows:
            if row['category'] not in ['structured','acronyms']:
                continue
            path = DATA/f"{model}-raw-{row['id']}.wav"
            pcm, detail = engine.speak(row['raw'])
            sf.write(str(path),pcm,24000,subtype='FLOAT')
            meta.append({'model':model,'mode':'raw','id':row['id'],'category':row['category'],'path':str(path),**detail})
            (ROOT/'results/synthesis.json').write_text(json.dumps(meta,indent=2)+'\n')
            print(model,'raw',row['id'],round(detail['rtfx'],2),flush=True)
        del engine
    selected = [0,10,11,20,30,40]
    index = []
    for model in ['kokoro','phonon-int8','phonon-fp32']:
        for voice in (['bella','heart'] if model=='kokoro' else ['easton','zoey']):
            engine = Kokoro(threads=4,voice=voice) if model=='kokoro' else Phonon(precision=model.split('-')[1],threads=4,voice=voice)
            for i,num in enumerate(selected,1):
                row=rows[num]
                pcm,_=engine.speak(row['spoken'])
                name=f"{i:02}-{model}-{voice}.wav"
                sf.write(str(SAMPLES/name),pcm,24000,subtype='PCM_16')
                index.append({'file':name,'model':model,'voice':voice,'corpus_id':row['id'],'text':row['spoken']})
            del engine
    (ROOT/'results/sample_index.json').write_text(json.dumps(index,indent=2)+'\n')

if __name__=='__main__':main()
