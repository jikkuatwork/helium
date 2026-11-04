"""Text-only summary and paired sentence bootstrap. Run after run_quality.sh."""
import json
from pathlib import Path
import re

import numpy as np

ROOT=Path(__file__).parent/'results'


def main():
    transcripts=json.loads((ROOT/'transcripts.json').read_text())
    synth=json.loads((ROOT/'synthesis.json').read_text())
    result={'literal_wer':{},'capped_chunks':{},'paired_bootstrap':{}}
    for mode in ['controlled','raw']:
        for model in ['kokoro','phonon-int8','phonon-fp32']:
            key=f'{mode}/{model}'
            rows=[x for x in transcripts if x['mode']==mode and x['model']==model]
            n=sum(x['literal_counts']['words'] for x in rows)
            e=sum(x['literal_counts']['errors'] for x in rows)
            result['literal_wer'][key]={'words':n,'errors':e,'wer':e/n}
            chunks=[c for x in synth if x['mode']==mode and x['model']==model for c in x['chunks']]
            result['capped_chunks'][key]={'chunks':len(chunks),'capped':sum(c.get('capped',False) for c in chunks)}
        base={x['id']:x for x in transcripts if x['model']=='kokoro' and x['mode']==mode}
        for other in ['phonon-int8','phonon-fp32']:
            pair={x['id']:x for x in transcripts if x['model']==other and x['mode']==mode}
            ids=sorted(base.keys()&pair.keys())
            words=np.array([base[k]['counts']['words'] for k in ids])
            deltas=np.array([pair[k]['counts']['errors']-base[k]['counts']['errors'] for k in ids])
            rng=np.random.default_rng(20261104)
            indices=rng.integers(0,len(ids),size=(5000,len(ids)))
            boot=deltas[indices].sum(axis=1)/words[indices].sum(axis=1)*100
            result['paired_bootstrap'][f'{mode}/{other}-kokoro']={
                'sentences':len(ids),'seed':20261104,'resamples':5000,
                'difference_pp':float(deltas.sum()/words.sum()*100),
                'ci95_pp':np.quantile(boot,[.025,.975]).tolist()}
    speed=[]
    for model in ['kokoro','phonon-int8','phonon-fp32']:
        for threads in [4,1]:
            for shape in ['short','paragraph','long']:
                file=ROOT/f'{model}-{threads}-{shape}.json'
                row=json.loads(file.read_text())
                log=file.with_name(file.name.replace('.json','.time.txt')).read_text()
                rss=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',log)[1])/1024
                speed.append({'model':model,'threads':threads,'shape':shape,'rss_mib':rss,**row['median']})
    result['speed']=speed
    (ROOT/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
