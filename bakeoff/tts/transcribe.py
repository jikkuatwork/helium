"""Whisper small.en CPU round trip. Auditable text-only outputs; no reference prompts.

Soundfile/scipy avoids faster-whisper 1.2.1's incompatibility with PyAV 19.
ASR uses CTranslate2, not ORT; all TTS sessions and any installed ORT are 1.24.4.
"""
import json
from pathlib import Path
import re
import time

from faster_whisper import WhisperModel
import jiwer
import numpy as np
from scipy.signal import resample_poly
import soundfile as sf
from whisper_normalizer.english import EnglishTextNormalizer

ROOT=Path(__file__).parent
INITIALISMS=['cpu','gpu','api','http','https','fbi','usb','ssd','bbc','cnn','dns','mri','sql','url','am','pm']
normalizer=EnglishTextNormalizer()


def canonical(text):
    text=text.lower()
    # Orthographic equivalences only: never repair a wrong digit/name/content word.
    text=re.sub(r'\b(\d{3})[- ]+(\d{3})[- ]+(\d{4})\b',r'\1\2\3',text)
    text=re.sub(r'\b(?:\d\s+){9}\d\b',lambda m:re.sub(r'\s+','',m[0]),text)
    text=re.sub(r'\b(\d{1,2})[.: ](\d{2})(?=\s*(?:[ap]\.?m\.?|[ap]\s+m))',r'\1\2',text)
    text=re.sub(r'\b[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]+)+\b',lambda m:m[0].replace('.', ' dot '),text)
    text=re.sub(r'\bjay\s+son\b','json',text)
    text=re.sub(r'\bkg\b','kilograms',text)
    text=re.sub(r'\bdegrees c\b','degrees celsius',text)
    # Joined, dotted, and partly joined ASR initialisms share the spoken spelling.
    for acronym in INITIALISMS:
        pattern=r'\b'+r'[\s.]*'.join(acronym)+r'\b'
        text=re.sub(pattern,' '.join(acronym),text)
    result=normalizer(text).strip()
    months='january|february|march|april|may|june|july|august|september|october|november|december'
    return re.sub(r'\b('+months+r') (\d+)(?:st|nd|rd|th)\b',r'\1 \2',result)


def literal(text):
    return re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',text.lower())).strip()


def counts(reference,hypothesis):
    result=jiwer.process_words(reference,hypothesis)
    return {'words':result.hits+result.substitutions+result.deletions,
            'errors':result.substitutions+result.deletions+result.insertions,
            'substitutions':result.substitutions,'deletions':result.deletions,'insertions':result.insertions}


def main():
    corpus={x['id']:x for x in json.loads((Path.home()/'datasets/tts/corpus.json').read_text())}
    synth=json.loads((ROOT/'results/synthesis.json').read_text())
    recognizer=WhisperModel(str(Path.home()/'models/tts/whisper-small.en'),device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
    outputs=[]
    for item in synth:
        audio,sr=sf.read(item['path'],dtype='float32')
        assert sr==24000
        start=time.perf_counter()
        segments,info=recognizer.transcribe(resample_poly(audio,2,3).astype(np.float32),language='en',beam_size=5,
                   temperature=0,condition_on_previous_text=False,vad_filter=False)
        hypothesis=' '.join(x.text.strip() for x in segments)
        row=corpus[item['id']]
        ref=canonical(row['spoken']);hyp=canonical(hypothesis)
        result={'id':item['id'],'model':item['model'],'mode':item['mode'],'category':row['category'],
                'reference':row['spoken'],'transcript':hypothesis,'canonical_reference':ref,
                'canonical_hypothesis':hyp,'counts':counts(ref,hyp),
                'literal_counts':counts(literal(row['spoken']),literal(hypothesis)),
                'asr_wall_s':time.perf_counter()-start}
        outputs.append(result)
        (ROOT/'results/transcripts.json').write_text(json.dumps(outputs,indent=2,ensure_ascii=False)+'\n')
        print(item['model'],item['id'],result['counts'],hypothesis,flush=True)
    totals={}
    for mode in ['controlled','raw']:
        totals[mode]={}
        for model in sorted({x['model'] for x in outputs}):
            totals[mode][model]={}
            for cat in ['all','prose','structured','names','acronyms','long']:
                xs=[x for x in outputs if x['model']==model and x['mode']==mode and (cat=='all' or x['category']==cat)]
                if not xs:
                    continue
                n=sum(x['counts']['words'] for x in xs);e=sum(x['counts']['errors'] for x in xs)
                totals[mode][model][cat]={'sentences':len(xs),'words':n,'errors':e,'wer':e/n}
    (ROOT/'results/wer.json').write_text(json.dumps(totals,indent=2)+'\n')
    print(json.dumps(totals,indent=2),flush=True)

if __name__=='__main__':main()
