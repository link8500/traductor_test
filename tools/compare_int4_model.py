"""Prepare a smaller weight-only model for device/storage quality checks."""
import pathlib, shutil, gc
import onnx
from onnx import numpy_helper
from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer, DefaultWeightOnlyQuantConfig
from onnxruntime.quantization.quant_utils import QuantFormat
from localize_decoder_scales import repair_file

root=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
source=root/'tc-big';output=root/'tc-big-int4';output.mkdir(exist_ok=True)
for name in ['tokenizer.json','terminology.json','manifest.json','config.json','source.spm','vocab.json']:
    shutil.copyfile(source/name,output/name)
for part in ['encoder','decoder']:
    if (output/f'{part}.onnx').exists() and (output/f'{part}.onnx').stat().st_size<200_000_000:
        repair_file(output/f'{part}.onnx')
        continue
    print('quantizing int4',part,flush=True)
    configuration=DefaultWeightOnlyQuantConfig(block_size=32,is_symmetric=True,accuracy_level=4,
        quant_format=QuantFormat.QOperator,op_types_to_quantize=('MatMul','Gather'),quant_axes=(('MatMul',0),('Gather',1)))
    graph=onnx.load(str(source/f'{part}.float.onnx'))
    # Marian ties the output projection to a transposed embedding. Folding
    # that constant transpose lets the quantizer include the output head.
    original={tensor.name:tensor for tensor in graph.graph.initializer};folded={}
    def fold(subgraph):
        replacements={};remove=[]
        for node in subgraph.node:
            if node.op_type=='Transpose' and node.input[0] in original:
                tensor=original[node.input[0]];permutation=tuple(next((a.ints for a in node.attribute if a.name=='perm'),reversed(range(len(tensor.dims)))))
                key=(tensor.name,permutation)
                if key not in folded:
                    name=tensor.name+'_constant_transpose'
                    graph.graph.initializer.append(numpy_helper.from_array(numpy_helper.to_array(tensor).transpose(permutation).copy(),name))
                    folded[key]=name
                replacements[node.output[0]]=folded[key];remove.append(node)
            for attribute in node.attribute:
                if attribute.type==onnx.AttributeProto.GRAPH:fold(attribute.g)
        for node in subgraph.node:
            for index,value in enumerate(node.input):
                if value in replacements:node.input[index]=replacements[value]
        for node in remove:subgraph.node.remove(node)
    fold(graph.graph)
    quantizer=MatMulNBitsQuantizer(graph,algo_config=configuration)
    quantizer.process();quantizer.model.save_model_to_file(str(output/f'{part}.onnx'),False)
    repair_file(output/f'{part}.onnx')
    print(part,(output/f'{part}.onnx').stat().st_size,flush=True)
    del quantizer
    gc.collect()
