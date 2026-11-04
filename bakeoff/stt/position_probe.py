#!/usr/bin/env python3
"""Extract the exact position-slicing subgraph; expose silent singleton edge.

The extracted ONNX graph stays outside the repository and is NOT a model
replacement. Width/values are unchanged from the downloaded CTC export.
"""
import json
from pathlib import Path
import numpy as np
import onnx
from onnx import helper, TensorProto
from bench import MODELS, session

original = onnx.load(MODELS/'parakeet110/model.int8.onnx')
nodes = [n for n in original.graph.node if n.name == 'Constant_1869' or
         (n.name.startswith('/pos_enc/') and n.op_type != 'DynamicQuantizeLinear')]
graph = helper.make_graph(nodes, 'position_slice_probe',
    [helper.make_tensor_value_info('/Gather_output_0', TensorProto.INT64, [])],
    [helper.make_tensor_value_info('/pos_enc/Slice_output_0', TensorProto.FLOAT, [1, None, 512])])
probe = helper.make_model(graph, opset_imports=list(original.opset_import))
probe.ir_version = original.ir_version
onnx.checker.check_model(probe)
path = MODELS/'position-slice-probe.onnx'
onnx.save(probe, path)
model = session(path, 4)
rows = []
for frames in [3750, 5000, 5001, 5002, 9012, 15016]:
    output = model.run(None, {'/Gather_output_0': np.array(frames, dtype=np.int64)})[0]
    rows.append({'encoder_frames': frames, 'position_tensor_shape': list(output.shape),
                 'expected_position_rows': 2*frames-1})
Path('bakeoff/stt/results/position-slice.json').write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
assert rows[1]['position_tensor_shape'][1] == 9999
assert rows[2]['position_tensor_shape'][1] == 1
assert rows[3]['position_tensor_shape'][1] == 2
