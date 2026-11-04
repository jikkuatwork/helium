#!/usr/bin/env python3
"""Shared, CPU-only ORT greedy/cache loop. No transformers model execution."""
import argparse
import json
import os
import resource
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer


def state_output(name):
    if name.startswith('past_key_values.'):
        return name.replace('past_key_values.', 'present.', 1)
    return name.replace('past_', 'present_', 1)


class Runner:
    def __init__(self, model, threads=4):
        if not set(os.sched_getaffinity(0)) <= set(range(16, 24)):
            raise RuntimeError('Run under taskset -c 16-23')
        if not ort.__version__.startswith('1.24.'):
            raise RuntimeError('ORT 1.24.x required')
        self.model = model
        self.root = Path.home() / 'models/llm' / model
        self.tokenizer = AutoTokenizer.from_pretrained(self.root, local_files_only=True, trust_remote_code=False)
        opt = ort.SessionOptions()
        opt.intra_op_num_threads = threads
        opt.inter_op_num_threads = 1
        opt.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opt.log_severity_level = 3
        # Stop worker spinning between invocations; apply identically to all models.
        opt.add_session_config_entry('session.intra_op.allow_spinning', '0')
        start = time.perf_counter()
        self.embed = None
        if model == 'qwen':
            self.embed = ort.InferenceSession(str(self.root / 'onnx/embed_tokens_q4.onnx'), opt, providers=['CPUExecutionProvider'])
        self.session = ort.InferenceSession(str(self.root / 'onnx' / ('decoder_model_merged_q4.onnx' if model == 'qwen' else 'model_q4.onnx')), opt, providers=['CPUExecutionProvider'])
        self.load_s = time.perf_counter() - start
        self.inputs = {i.name: i for i in self.session.get_inputs()}
        self.outputs = [i.name for i in self.session.get_outputs()]
        self.state_names = [n for n in self.inputs if n.startswith('past_')]
        for n in self.state_names:
            assert state_output(n) in self.outputs
        cfg = json.loads((self.root / 'generation_config.json').read_text())
        eos = cfg['eos_token_id']
        self.eos = set(eos if isinstance(eos, list) else [eos])

    def render(self, messages, thinking=False, tools=None):
        return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=thinking, tools=tools)

    def encode(self, rendered):
        return self.tokenizer.encode(rendered, add_special_tokens=False)

    def zero_state(self):
        state = {}
        for n in self.state_names:
            info = self.inputs[n]
            shape = [d if isinstance(d, int) else (0 if 'past_sequence' in d else 1) for d in info.shape]
            dtype = np.float16 if info.type == 'tensor(float16)' else np.float32
            state[n] = np.zeros(shape, dtype=dtype)
        return state

    def generate(self, ids, max_tokens=192, force_length=False, full_logits=False):
        # Same NumPy feeds/session.run/output->input state mapping for all.
        # Reset context for every request; warm session, no cross-request prefix cache.
        start = time.perf_counter()
        state = self.zero_state()
        total = len(ids)
        step_ids = np.asarray([ids], dtype=np.int64)
        generated = []
        first = None
        finish = 'length'
        for step in range(max_tokens):
            feed = dict(state)
            if self.embed:
                feed['inputs_embeds'] = self.embed.run(None, {'input_ids': step_ids})[0]
            else:
                feed['input_ids'] = step_ids
            if 'attention_mask' in self.inputs:
                feed['attention_mask'] = np.ones((1, total), dtype=np.int64)
            if 'position_ids' in self.inputs:
                positions = np.arange(total - step_ids.shape[1], total, dtype=np.int64)[None, :]
                feed['position_ids'] = np.repeat(positions[None, :, :], 3, axis=0) if len(self.inputs['position_ids'].shape) == 3 else positions
            if 'logits_to_keep' in self.inputs:
                feed['logits_to_keep'] = np.array([0 if full_logits else 1], dtype=np.int64)
            values = self.session.run(None, feed)
            logits = values[self.outputs.index('logits')]
            next_id = int(np.argmax(logits[0, -1]))
            state = {n: values[self.outputs.index(state_output(n))] for n in self.state_names}
            generated.append(next_id)
            if first is None:
                first = time.perf_counter()
            del feed, values, logits
            if next_id in self.eos and not force_length:
                finish = 'eos'
                break
            total += 1
            step_ids = np.array([[next_id]], dtype=np.int64)
        end = time.perf_counter()
        prefill_s = first - start
        decode_s = end - first
        return {'prompt_tokens': len(ids), 'generated_tokens': len(generated), 'ids': generated,
                'text': self.tokenizer.decode(generated, skip_special_tokens=False),
                'clean_text': self.tokenizer.decode(generated, skip_special_tokens=True),
                'finish': finish, 'ttft_s': prefill_s, 'total_s': end - start,
                'prefill_tps': len(ids) / prefill_s,
                'decode_tps': (len(generated) - 1) / decode_s if len(generated) > 1 else None,
                'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}

    def chat(self, messages, thinking=False, tools=None, **kwargs):
        rendered = self.render(messages, thinking, tools)
        result = self.generate(self.encode(rendered), **kwargs)
        result['rendered_prompt'] = rendered
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=['qwen', 'lfm3', 'lfm25'], required=True)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--prompt', default='What is the capital of France? Answer in five words or fewer.')
    p.add_argument('--thinking', action='store_true')
    p.add_argument('--max-tokens', type=int, default=128)
    a = p.parse_args()
    runner = Runner(a.model, a.threads)
    print(json.dumps(runner.chat([{'role': 'user', 'content': a.prompt}], thinking=a.thinking, max_tokens=a.max_tokens), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
