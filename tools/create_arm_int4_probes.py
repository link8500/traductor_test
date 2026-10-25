"""Generate tiny, deterministic probes for the Android ARM64 decoder crash."""
import copy
import pathlib
import numpy as np
import onnx
from onnx import helper as h,numpy_helper as n,TensorProto as T
from localize_decoder_scales import localize_scales,check_local_scales

output=pathlib.Path(__file__).resolve().parents[1]/'android/app/src/androidTest/assets'
output.mkdir(parents=True,exist_ok=True)


def model(graph):
    return h.make_model(graph,opset_imports=[h.make_opsetid('',21),h.make_opsetid('com.microsoft',1)],ir_version=10)


def save(value,name):
    onnx.checker.check_model(value)
    onnx.save(value,output/f'arm-int4-{name}.onnx')


weights=n.from_array(np.full((1024,32,16),0x99,dtype=np.uint8),'B')
scales=n.from_array(np.full((1024,32),.0625,dtype=np.float32),'scales')
input_=h.make_tensor_value_info('A',T.FLOAT,[1,1024])
output_=h.make_tensor_value_info('Y',T.FLOAT,[1,1024])
node=h.make_node('MatMulNBits',['A','B','scales'],['Y'],domain='com.microsoft',
    K=1024,N=1024,bits=4,block_size=32,accuracy_level=4)
# q=9, zero=8, scale=1/16 and A=1 -> every result must equal 64.
for level in [0,4]:
    current=copy.deepcopy(node)
    next(a for a in current.attribute if a.name=='accuracy_level').i=level
    save(model(h.make_graph([current],'local-weights',[input_],[output_],[weights,scales])),f'level{level}')

branches={name:h.make_graph([copy.deepcopy(node)],name,[],[output_]) for name in ['then_branch','else_branch']}
nodes=[h.make_node('ReduceSum',['A'],['sum'],keepdims=0),
    h.make_node('Greater',['sum','zero'],['condition']),
    h.make_node('If',['condition'],['result'],**branches)]
scoped=model(h.make_graph(nodes,'parent-weights',[input_],[h.make_tensor_value_info('result',T.FLOAT,[1,1024])],
    [weights,scales,n.from_array(np.array(0,dtype=np.float32),'zero')]))
# Dynamic condition retains both branches. A constant condition would be folded
# and would accidentally hide the ARM64 prepacking regression.
save(scoped,'subgraph')
fixed=copy.deepcopy(scoped)
assert localize_scales(fixed)==2
check_local_scales(fixed.graph)
save(fixed,'subgraph-local-scales')
fp32=copy.deepcopy(scoped)
for attribute in fp32.graph.node[-1].attribute:
    for item in attribute.g.node:
        next(a for a in item.attribute if a.name=='accuracy_level').i=0
save(fp32,'subgraph-level0')
print('Generated five ARM int4 probes; expected output is 64.0')
