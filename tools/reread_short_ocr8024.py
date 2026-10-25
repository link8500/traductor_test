"""Try upright short-detection proposals using only cached detector evidence."""
import json
import pathlib
import shutil
import subprocess
import tempfile
from PIL import Image
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    original=QA/'short-ocr8024';folder=QA/'short-ocr8024-axis';folder.mkdir(exist_ok=True)
    binary=ROOT/'build/local-model/Release/luma_ocr.exe';models=ROOT/'assets/models/opus-en-es'
    proposals=read(original/'short-detections.json');groups={}
    for index,row in enumerate(proposals):groups.setdefault(row['id'],[]).append((index,row))
    proof=dict(binary_sha256=digest(binary),source_sha256=digest(ROOT/'native/ocr_cli.cpp'),
        original_detection_provenance_sha256=digest(original/'provenance.json'),
        short_detections_sha256=digest(original/'short-detections.json'),
        upright_axis_proposals=True,right_padding_height_ratios=[0,.25],
        no_reference_or_inventory_inputs=True,application_modified=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    output=[]
    with tempfile.TemporaryDirectory(prefix='pixels-',dir=folder) as scratch,(folder/'native.log').open('ab') as log:
        child=subprocess.Popen([str(binary),str(models),str(models)],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for ident in range(1,125):
                if ident not in groups:continue
                source=pathlib.Path(records(QA/f'recovery-viewports801201/{ident:03d}.input.jsonl')[0]['path'])
                assert digest(source)==read(original/f'{ident:03d}.json')['original_pixels_sha256']
                assert shutil.disk_usage(folder).free>4*1024**3
                with Image.open(source) as image:
                    width,height=image.size;pixels=image.convert('RGBA').tobytes('raw','BGRA')
                raw=pathlib.Path(scratch)/'current.bgra';raw.write_bytes(pixels);quads=[]
                for index,row in groups[ident]:
                    q=row['quad'];left=min(q[::2]);right=max(q[::2]);top=min(q[1::2]);bottom=max(q[1::2])
                    for padding in [0,.25]:
                        end=min(width-1,right+(bottom-top)*padding)
                        quads.append(dict(id=f'{index}:{padding}',quad=[left,top,end,top,end,bottom,left,bottom]))
                body=dict(id=ident,path=str(raw),width=width,height=height,quads=quads,skip_detection=True)
                child.stdin.write((json.dumps(body)+'\n').encode());child.stdin.flush()
                line=child.stdout.readline();assert line
                result=json.loads(line);assert 'error' not in result;result.pop('path')
                result['original_pixels_sha256']=digest(source);output.append(result)
                atomic(folder/f'{ident:03d}.json',json.dumps(result,ensure_ascii=False,indent=2))
            child.stdin.close();assert child.wait(timeout=30)==0
        finally:
            if child.poll() is None:child.terminate();child.wait(timeout=30)
    atomic(folder/'output.jsonl',''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in output))
    print(json.dumps(dict(all_original_frames_checked=124,frames_with_short_proposals=len(groups),
        detections=len(proposals),upright_quad_pairs=sum(len(r['quad_reads']) for r in output),
        all_meanings_reviewed=False,application_modified=False)),flush=True)


if __name__=='__main__':main()
