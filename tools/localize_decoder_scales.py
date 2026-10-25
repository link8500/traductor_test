"""Keep int4 scales local to If branches for ORT 1.23.2's ARM64 prepacker.

Only initializer placement changes. Tensor values, operators, quantization and
decoder inputs/outputs remain identical. No training or new weights are used.
"""
import argparse
import copy
import pathlib
import onnx


def localize_scales(model):
    copied_names=set()
    copied=0

    def visit(graph,ancestors):
        nonlocal copied
        local={tensor.name:tensor for tensor in graph.initializer}
        available={**ancestors,**local}
        for node in graph.node:
            if node.op_type=='MatMulNBits' and node.domain=='com.microsoft':
                name=node.input[2]
                if name not in local and name in available:
                    tensor=copy.deepcopy(available[name])
                    graph.initializer.append(tensor)
                    local[name]=tensor
                    copied_names.add(name)
                    copied+=1
            for attribute in node.attribute:
                if attribute.type==onnx.AttributeProto.GRAPH:
                    visit(attribute.g,{**available,**local})

    visit(model.graph,{})

    def prune(graph):
        # A local initializer shadows its parent's name. Only unshadowed child
        # dependencies keep the parent copy alive (e.g. another embedding op).
        needed={name for node in graph.node for name in node.input if name}
        for node in graph.node:
            for attribute in node.attribute:
                if attribute.type==onnx.AttributeProto.GRAPH:
                    needed.update(prune(attribute.g))
        for index in reversed(range(len(graph.initializer))):
            tensor=graph.initializer[index]
            if tensor.name in copied_names and tensor.name not in needed:
                del graph.initializer[index]
        defined={tensor.name for tensor in graph.initializer}
        defined.update(value.name for value in graph.input)
        defined.update(name for node in graph.node for name in node.output)
        return needed-defined

    prune(model.graph)
    return copied


def check_local_scales(graph):
    local={tensor.name for tensor in graph.initializer}
    for node in graph.node:
        if node.op_type=='MatMulNBits' and node.domain=='com.microsoft':
            if node.input[2] not in local:
                raise ValueError(f'Int4 scale is outside its graph: {node.name}')
        for attribute in node.attribute:
            if attribute.type==onnx.AttributeProto.GRAPH:
                check_local_scales(attribute.g)


def repair_file(path):
    model=onnx.load(path)
    count=localize_scales(model)
    check_local_scales(model.graph)
    onnx.checker.check_model(model)
    if count:
        partial=pathlib.Path(str(path)+'.partial')
        onnx.save(model,partial)
        partial.replace(path)
    return count


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model',type=pathlib.Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.check:
        check_local_scales(onnx.load(args.model).graph)
        print('All MatMulNBits scales are local')
    else:
        print('Localized int4 scale tensors:',repair_file(args.model))
