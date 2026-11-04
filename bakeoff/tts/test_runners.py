"""Fast, inference-free checks for the evaluation glue."""
import json
from pathlib import Path
import unittest

import numpy as np
from tokenizers import Tokenizer
from runners import PHONON,VOCAB,kokoro_chunks,split_text
from signal_compare import distance
from transcribe import canonical,counts


class RunnerTests(unittest.TestCase):
    def test_vocab_boundaries(self):
        self.assertEqual(VOCAB[' '],16)
        self.assertEqual(VOCAB['ˈ'],156)
        self.assertEqual(VOCAB['ᵻ'],177)
        self.assertNotIn('🙂',VOCAB)

    def test_all_text_preserved(self):
        tokenizer=Tokenizer.from_file(str(PHONON/'tokenizer.json'))
        root=Path(__file__).parent
        texts=list(json.loads((root/'speed_texts.json').read_text()).values())
        texts += [r['spoken'] for r in json.loads((root/'corpus.json').read_text())]
        for text in texts:
            chunks=split_text(text,tokenizer)
            self.assertEqual(' '.join(chunks),text)
            for chunk in chunks:
                punctuation='' if not chunk[-1].isalnum() else '.'
                self.assertLessEqual(len(tokenizer.encode(chunk+punctuation,add_special_tokens=False).ids),50)

    def test_kokoro_budget(self):
        chunks=kokoro_chunks(' '.join(['həlˈoʊ.']*150))
        self.assertGreater(len(chunks),1)
        self.assertTrue(all(sum(c in VOCAB for c in x)<=480 for x in chunks))

    def test_scoring_numbers_initialisms(self):
        self.assertEqual(canonical('twenty three dollars and forty five cents'),canonical('$23.45'))
        self.assertEqual(canonical('c p u and g p u'),canonical('CPU and GPU'))
        self.assertEqual(canonical('March fifteenth twenty twenty six'),canonical('March 15th, 2026'))
        self.assertEqual(counts('hello world','hello world')['errors'],0)
        self.assertEqual(counts('hello world','hello there')['errors'],1)

    def test_signal_identity(self):
        a=np.sin(np.arange(4096)*.3).astype(np.float32)
        result=distance(a,a.copy())
        self.assertGreater(result['snr_db'],100)
        self.assertEqual(result['lsd_db'],0)

if __name__=='__main__':unittest.main()
