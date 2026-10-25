"""Fresh native OCR/MT on all fixed views and every changed broad location.

Broad frames reproduce their recorded first viewport, without improving the
crop or supplying recognized/reference words to the app.
"""
import json
import pathlib
import shutil
import subprocess

from PIL import Image
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder=QA/'windows8029-refinement-full-viewports';folder.mkdir(exist_ok=True)
    binary=QA/'frozen-windows802901/traductor.exe';snapshot=QA/'windows-engine802901.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    old_path=QA/'windows8028-opening-translation-replay/fixed-output.jsonl';old=records(old_path)
    reference=QA/'recovery-viewports801201';parts=[];pixels=[]
    fixed=[]
    for i in range(1,125):
        item=records(reference/f'{i:03d}.input.jsonl')[0];status=read(reference/f'{i:03d}.done.json')
        path=pathlib.Path(item['path']);assert digest(path)==status['viewport_png_sha256']
        item.update(ocr_only=False,augment_detection=True,recover_paragraphs=True,complete_lines=True)
        assert not any(key in item for key in ['source','translation','reference','inventory','consensus_first_directory','consensus_second_directory','reader_consensus'])
        fixed.append(item);pixels.append(dict(image=i,path=str(path),sha256=digest(path),scope='fixed_original_viewport'))
    cases=read(QA/'refinement8029/changes.json');pages={(p['chapter'],p['image']):p for p in read(QA/'images-en.json')}
    broad=[];anchors=[]
    for c in cases:
        report=QA/'postprocessed-en8028-openings'/c['report'];rows=records(report)
        matches=[r for r in rows if r['image']==c['image'] and r['bounds']==c['bounds']]
        assert len(matches)==1
        actual_old=matches[0];assert actual_old['source']==c['source']
        page=pages[(report.stem,c['image'])];source=pathlib.Path(page['path']);assert digest(source)==page['sha256']
        top=actual_old['cropTop'];path=folder/f'broad-{c["id"]:03d}.png'
        with Image.open(source) as image:
            bottom=min(top+2000,image.height)
            if not path.exists():image.crop((0,top,image.width,bottom)).convert('RGB').save(path)
        ident=124+c['id']
        broad.append(dict(chapter='broad-diagnostic',image=ident,language='en',path=str(path),ocr_only=False,
                          augment_detection=True,recover_paragraphs=True,complete_lines=True))
        pixels.append(dict(image=ident,path=str(path),sha256=digest(path),original_image_sha256=page['sha256'],
                           crop=[0,top,page['width'],bottom],scope='same_recorded_first_viewport_not_best_crop'))
        anchors.append(dict(case_id=c['id'],image=ident,bounds=[c['bounds'][0],c['bounds'][1]-top,c['bounds'][2],c['bounds'][3]-top],
                            old=actual_old,report_sha256=digest(report)))
    parts=[broad]+[fixed[i:i+31] for i in range(0,124,31)]
    proof=dict(build='802901',binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),pixels=pixels,
               previous_fixed_output_sha256=digest(old_path),broad_case_manifest_sha256=digest(QA/'refinement8029/changes.json'),
               source_and_reference_text_supplied=False,no_explicit_reader_paths_or_activation=True,
               fresh_native_ocr=True,fresh_translation=True,live_desktop_capture=False)
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    outputs=[]
    for n,items in enumerate(parts):
        manifest=folder/f'part-{n}.input.jsonl';contents=''.join(json.dumps(r)+'\n' for r in items)
        if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
        else:atomic(manifest,contents)
        target=folder/f'part-{n}.jsonl';done=pathlib.Path(str(target)+'.summary.json')
        if not done.exists():
            assert shutil.disk_usage(folder).free>=4*1024**3
            wait_for_inference_memory()
            with (folder/f'part-{n}.log').open('ab') as log:
                subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(target)],check=True,
                               creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log,timeout=3600)
        result=read(done);assert result['images']==len(items) and result['runtime_errors']==0
        outputs.extend(records(target))
        print(json.dumps(dict(parts_completed=n+1,parts_expected=5,images_completed=sum(len(p) for p in parts[:n+1]),
                              images_expected=131,runtime_errors=0)),flush=True)
    current=[r for r in outputs if r['image']<=124]
    assert len(current)==len(old)==229
    assert [(r['image'],r['bounds']) for r in current]==[(r['image'],r['bounds']) for r in old]
    predicted=records(QA/'ocr-morph-edit8029/fixed124_views-output.jsonl')
    assert [r['source'] for r in current]==[r['selected'] for r in predicted]
    changes=[]
    for i in range(1,125):
        a=[r for r in old if r['image']==i];b=[r for r in current if r['image']==i]
        fields=['source','translation','bounds','retained_original','sentence_recovered']
        if [{k:r.get(k) for k in fields} for r in a]!=[{k:r.get(k) for k in fields} for r in b]:changes.append(dict(id=i,before=a,after=b))
    broad_selected=[]
    for a in anchors:
        matches=[r for r in outputs if r['image']==a['image'] and r['bounds']==a['bounds']]
        assert len(matches)==1,'Changed broad location geometry must be reviewed before publishing'
        broad_selected.append(dict(a,after=matches[0]))
    atomic(folder/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in current))
    atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    atomic(folder/'broad-selected.json',json.dumps(broad_selected,ensure_ascii=False,indent=2))
    summary=dict(build='802901',fixed_viewports=124,fixed_regions=229,broad_actual_frames=7,
                 total_native_images=131,total_native_output_records=len(outputs),runtime_errors=0,
                 fixed_changed_views=[r['id'] for r in changes],all_fixed_sources_match_pure_policy_prediction=True,
                 fresh_native_ocr=True,fresh_translation=True,live_desktop_capture=False,
                 output_sha256=digest(folder/'output.jsonl'),provenance_sha256=digest(pin),
                 broad_selected_sha256=digest(folder/'broad-selected.json'),all_new_meanings_reviewed=False,
                 all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
