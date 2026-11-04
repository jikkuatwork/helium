#!/usr/bin/env python3
"""Experimental graph-only accuracy-level control; original exports untouched."""
import hashlib
import json
from pathlib import Path
import onnx


def patch(graph):
    count = 0
    for node in graph.node:
        if node.op_type == 'MatMulNBits' and node.domain == 'com.microsoft':
            for attr in list(node.attribute):
                if attr.name == 'accuracy_level':
                    node.attribute.remove(attr)
            node.attribute.append(onnx.helper.make_attribute('accuracy_level', 4))
            count += 1
        for attr in node.attribute:
            if attr.type == onnx.AttributeProto.GRAPH:
                count += patch(attr.g)
            elif attr.type == onnx.AttributeProto.GRAPHS:
                count += sum(patch(g) for g in attr.graphs)
    return count


def main():
    result = {}
    for name in ['qwen', 'lfm25']:
        root = Path.home() / 'models/llm' / name / 'onnx'
        file = 'decoder_model_merged_q4.onnx' if name == 'qwen' else 'model_q4.onnx'
        src = root / file
        dst = root / file.replace('.onnx', '_acc4.onnx')
        m = onnx.load(src, load_external_data=False)
        changed = patch(m.graph)
        # Preserve external-data paths/offsets and the original weights exactly.
        onnx.save_model(m, dst)
        result[name] = {'original_file': file, 'derived_file': dst.name, 'changed_nodes': changed,
                        'original_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                        'derived_sha256': hashlib.sha256(dst.read_bytes()).hexdigest(),
                        'change': 'MatMulNBits accuracy_level=4 only; no weight or IO changes'}
    Path('bakeoff/llm/accuracy4_control.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
