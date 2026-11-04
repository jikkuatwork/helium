"""Signal differences: end-to-end (AR timing drift) and decoder-only isolation."""
import json
from pathlib import Path

import numpy as np
from scipy.signal import stft
import soundfile as sf
from runners import Phonon

ROOT=Path(__file__).parent


def distance(a,b):
    n=min(len(a),len(b));a=a[:n].astype(np.float64);b=b[:n].astype(np.float64)
    snr=10*np.log10(np.sum(a*a)/max(np.sum((a-b)**2),1e-30))
    _,_,x=stft(a,fs=24000,nperseg=512,noverlap=384)
    _,_,y=stft(b,fs=24000,nperseg=512,noverlap=384)
    # Symmetric floored magnitude log spectral distance over every time/bin.
    floor=max(np.max(np.abs(x)),np.max(np.abs(y)))*1e-4
    lsd=np.sqrt(np.mean((20*np.log10(np.maximum(np.abs(x),floor))-20*np.log10(np.maximum(np.abs(y),floor)))**2))
    return {'overlap_samples':n,'snr_db':float(snr),'lsd_db':float(lsd)}


def main():
    corpus=json.loads((ROOT/'corpus.json').read_text())
    texts=[corpus[i]['spoken'] for i in [0,10,20,30,40]]
    results=[]
    fp=Phonon('fp32',threads=4)
    q=Phonon('int8',threads=4)
    for temperature in [.3,0.]:
        for text in texts:
            a,ra=fp.speak(text,seed=1234,temperature=temperature)
            latents=[x.copy() for x in fp.last_latents]
            b,rb=q.speak(text,seed=1234,temperature=temperature)
            isolated=[]
            for lat in latents:
                isolated.append(q.decoder.run(None,{'audio_latents':lat,'num_frames':np.array([lat.shape[1]],np.int64)})[0].ravel())
            c=np.concatenate(isolated)
            results.append({'text':text,'seed':1234,'temperature':temperature,
                 'fp32_s':len(a)/24000,'int8_s':len(b)/24000,'end_to_end':distance(a,b),
                 'decoder_only':distance(a,c),'fp32_chunks':ra['chunks'],'int8_chunks':rb['chunks']})
    (ROOT/'results/signal.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2),flush=True)

if __name__=='__main__':main()
