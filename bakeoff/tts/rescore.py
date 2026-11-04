"""Rescore immutable ASR transcripts after an orthographic-equivalence audit.

No ASR or synthesis rerun; retain pre-audit counts for transparent comparison.
Apply the same tested, model-independent formatting rules to both sides.
"""
import json
from pathlib import Path
from transcribe import canonical,counts

ROOT=Path(__file__).parent/'results'


def main():
    path=ROOT/'transcripts.json'
    rows=json.loads(path.read_text())
    for row in rows:
        row.setdefault('pre_format_audit_counts',row['counts'])
        row['canonical_reference']=canonical(row['reference'])
        row['canonical_hypothesis']=canonical(row['transcript'])
        row['counts']=counts(row['canonical_reference'],row['canonical_hypothesis'])
    totals={}
    for mode in ['controlled','raw']:
        totals[mode]={}
        for model in sorted({x['model'] for x in rows}):
            totals[mode][model]={}
            for category in ['all','prose','structured','names','acronyms','long']:
                xs=[x for x in rows if x['model']==model and x['mode']==mode and (category=='all' or x['category']==category)]
                if not xs:continue
                n=sum(x['counts']['words'] for x in xs);e=sum(x['counts']['errors'] for x in xs)
                totals[mode][model][category]={'sentences':len(xs),'words':n,'errors':e,'wer':e/n}
    path.write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'wer.json').write_text(json.dumps(totals,indent=2)+'\n')
    print(json.dumps(totals,indent=2))

if __name__=='__main__':main()
