"""Compare real Windows OCR with clipped-line completion on 132 screen images.

124 fixed screens are supplemented by eight lettering/nontext diagnostics.
The diagnostics are reported separately and do not increase corpus coverage.
"""
import collections
import argparse
import json
import pathlib
import subprocess
import time

from PIL import Image
from audit_corpus_quality import QA, read, records, digest, atomic


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',default='801302')
    args=parser.parse_args();assert args.build.isdecimal()
    out=QA/('line-completion'+args.build);out.mkdir(exist_ok=True)
    old_folder=QA/'recovery-viewports801201'
    probe=QA/'omitted-lettering-probe8012'
    native=read(QA/('windows-engine'+args.build+'.json'))
    binary=QA/('frozen-windows'+args.build)/'traductor.exe'
    assert digest(binary)==native['binary_sha256']
    assert read(QA/'windows8013-recovery-test.json')['success']
    inputs=[];evidence=[]
    for index in range(1,125):
        status=read(old_folder/f'{index:03d}.done.json')
        item=records(old_folder/f'{index:03d}.input.jsonl')[0]
        assert digest(pathlib.Path(item['path']))==status['viewport_png_sha256']
        item['complete_lines']=True;inputs.append(item)
        evidence.append(dict(image=index,cohort='fixed-screen',source_sha256=status['viewport_png_sha256'],old_output_sha256=status['source_output_sha256']))
    for case in read(probe/'inputs.json')['cases']:
        if case['variant']!='original':continue
        request=case['request'];source=pathlib.Path(request['path'])
        assert digest(source)==case['raw_pixels_sha256']
        image=Image.frombytes('RGBA',(request['width'],request['height']),source.read_bytes(),'raw','BGRA').convert('RGB')
        png=out/f'diagnostic-{case["case_id"]:03d}.png';image.save(png,compress_level=1)
        index=1000+case['case_id']
        inputs.append(dict(chapter=f'diagnostic-{case["case_id"]:03d}',image=index,path=str(png.resolve()),language='en',ocr_only=True,
            augment_detection=True,all_candidates=True,recover_paragraphs=True,complete_lines=True))
        evidence.append(dict(image=index,cohort='diagnostic',source_sha256=digest(png),original_probe_input_sha256=digest(probe/'inputs.json')))
    manifest=out/'input.jsonl';target=out/'output.jsonl';done=out/'done.json'
    atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    if done.exists():
        status=read(done);assert status['input_sha256']==digest(manifest) and status['output_sha256']==digest(target)
        print('Preserved completed native regression',flush=True);return
    started=time.monotonic()
    run=subprocess.run([str(binary.resolve()),'--comic-benchmark',str(manifest.resolve()),str(target.resolve())],creationflags=subprocess.CREATE_NO_WINDOW)
    assert run.returncode==0,run.returncode
    summary=read(pathlib.Path(str(target)+'.summary.json'))
    assert summary['images']==132 and summary['runtime_errors']==0
    rows=records(target);old=[]
    for index in range(1,125):old.extend(records(old_folder/f'{index:03d}.jsonl'))
    old_by_image=collections.defaultdict(list);new_by_image=collections.defaultdict(list)
    for row in old:old_by_image[row['image']].append(row)
    for row in rows:new_by_image[row['image']].append(row)
    changed=[]
    for index in range(1,125):
        keys=['source','bounds','native_source','native_words','paragraph_recovered','additional_detection','cropTop']
        previous=[{k:r.get(k) for k in keys} for r in old_by_image[index]]
        current=[{k:r.get(k) for k in keys} for r in new_by_image[index]]
        if previous!=current:changed.append(index)
        if not any(r.get('line_completed') for r in new_by_image[index]):assert previous==current,('Unexpected change without completion',index)
    status=dict(native_engine=native['engine'],binary_sha256=digest(binary),input_sha256=digest(manifest),output_sha256=digest(target),
        summary=summary,fixed_screen_viewports=124,diagnostic_viewports=8,changed_fixed_screens=changed,
        completed_fixed_screen_regions=sum(r.get('line_completed',False) for r in rows if r['image']<1000),
        completed_diagnostic_regions=sum(r.get('line_completed',False) for r in rows if r['image']>=1000),
        seconds=round(time.monotonic()-started,2),all_words_visually_reviewed=False,semantic_accuracy=None,
        full_chapter_traversal=False,cases=evidence)
    atomic(done,json.dumps(status,indent=2));print(json.dumps({k:v for k,v in status.items() if k!='cases'}),flush=True)


if __name__=='__main__':main()
