"""Run the previous Windows binary on the exact 124 frozen screen images.

This control is independent of the full-chapter overlap selection. It preserves
every actual native OCR output and never uses a Spanish reference for inference.
"""
import json
import pathlib
import subprocess
import time

from audit_corpus_quality import QA, read, records, digest, atomic


def main():
    folder=QA/'recovery-viewports801201'
    out=folder/'paired-control801101';out.mkdir(exist_ok=True)
    old=read(QA/'windows-engine801101.json')
    binary=QA/'frozen-windows801101/traductor.exe'
    assert digest(binary)==old['binary_sha256']
    manifest=out/'input.jsonl';target=out/'output.jsonl';done=out/'done.json'
    inputs=[];proof=[]
    for index in range(1,125):
        status=read(folder/f'{index:03d}.done.json')
        path=folder/f'{index:03d}.png'
        assert digest(path)==status['viewport_png_sha256']
        item=records(folder/f'{index:03d}.input.jsonl')[0]
        item['recover_paragraphs']=False
        inputs.append(item)
        proof.append(dict(id=index,viewport_png_sha256=digest(path),new_output_sha256=status['source_output_sha256']))
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    if done.exists():
        value=read(done)
        assert value['input_sha256']==digest(manifest) and value['output_sha256']==digest(target)
        print('Preserved completed paired control',flush=True);return
    started=time.monotonic()
    result=subprocess.run([str(binary.resolve()),'--comic-benchmark',str(manifest.resolve()),str(target.resolve())],
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.returncode
    summary=read(pathlib.Path(str(target)+'.summary.json'))
    assert summary['images']==124 and summary['runtime_errors']==0
    value=dict(native_engine=old['engine'],binary_sha256=digest(binary),input_sha256=digest(manifest),
        output_sha256=digest(target),summary=summary,seconds=round(time.monotonic()-started,2),
        full_chapter_traversal=False,all_words_visually_reviewed=False,semantic_accuracy=None,cases=proof)
    atomic(done,json.dumps(value,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='cases'}),flush=True)


if __name__=='__main__':main()
