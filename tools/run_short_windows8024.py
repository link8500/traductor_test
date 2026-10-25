"""Exercise the short-dialogue guard in the native Windows executable on 124 frames."""
import argparse
import concurrent.futures
import json
import pathlib
import subprocess
import time
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--default',action='store_true');parser.add_argument('--packaged',action='store_true');parser.add_argument('--inflection',action='store_true');parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    assert 1<=args.workers<=4
    assert sum([args.default,args.packaged,args.inflection])<=1
    normal=args.default or args.packaged or args.inflection;build='802601' if args.inflection else '802501' if args.packaged else '802402' if normal else '802401'
    folder=QA/('windows8026-inflection-full-viewports' if args.inflection else 'windows8025-packaged-full-viewports' if args.packaged else 'windows8024-short-default-full-viewports' if normal else 'windows8024-short-full-viewports');folder.mkdir(exist_ok=True)
    binary=QA/f'frozen-windows{build}/traductor.exe';snapshot=QA/f'windows-engine{build}.json'
    assert digest(binary)==read(snapshot)['binary_sha256']
    origin=QA/('windows8020-full-viewports-baseline' if normal else 'windows8021-full-viewports-full-agreement')
    old=QA/'windows8025-packaged-full-viewports' if args.inflection else QA/'windows8024-short-default-full-viewports' if args.packaged else origin
    inputs=records(origin/'input.jsonl');assert len(inputs)==124
    frames=read(origin/'provenance.json')['frames']
    for item,frame in zip(inputs,frames):assert item['image']==frame['id'] and digest(pathlib.Path(item['path']))==frame['pixels_sha256']
    inputs=inputs if normal else [dict(r,recover_short_dialogue=True) for r in inputs]
    if normal:assert all(not any(k in r for k in ['recover_short_dialogue','consensus_first_directory','consensus_second_directory']) for r in inputs)
    pin=folder/'provenance.json'
    proof=dict(build=build,binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),
        previous_native_output_sha256=digest(old/'output.jsonl'),frames=frames,
        original_pixels_only=True,no_reference_or_inventory_inputs=True,additional_short_guard_enabled=True,
        default_live_worker_enabled=normal,all_chapter_words_reviewed=False)
    if args.packaged or args.inflection:
        proof['packaged_reader_manifest_sha256']=digest(binary.parent/'ocr-readers/manifest.json')
        proof['no_explicit_reader_paths_or_activation_flag']=True
    if args.inflection:
        proof['inflection_selection_summary_sha256']=digest(QA/'ocr-morph-consensus8026/summary.json')
        proof['isolated_translation_output_sha256']=digest(QA/'ocr-morph-consensus8026/translation-output.jsonl')
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    def run(part):
        manifest=folder/f'part-{part}.input.jsonl';output=folder/f'part-{part}.output.jsonl'
        items=inputs[part::4];atomic(manifest,''.join(json.dumps(r)+'\n' for r in items))
        done=pathlib.Path(str(output)+'.summary.json')
        if not done.exists():
            # Only the final image may have been interrupted. Keep all earlier
            # complete image groups and rerun the incomplete image from pixels.
            saved=[]
            for candidate in [output,folder/f'part-{part}.work.jsonl']:
                if not candidate.exists():continue
                parsed=[]
                for line in candidate.read_bytes().splitlines():
                    try:parsed.append(json.loads(line))
                    except ValueError:pass
                if parsed:
                    last=parsed[-1]['image'];complete=[r for r in parsed if r['image']!=last]
                    existing={r['image'] for r in saved};saved.extend(r for r in complete if r['image'] not in existing)
            complete_ids={r['image'] for r in saved};pending=[r for r in items if r['image'] not in complete_ids]
            run_manifest=folder/f'part-{part}.pending.input.jsonl';work=folder/f'part-{part}.work.jsonl'
            atomic(run_manifest,''.join(json.dumps(r)+'\n' for r in pending))
            started=time.monotonic()
            wait_for_inference_memory()
            with (folder/f'part-{part}.log').open('ab') as log:
                subprocess.run([str(binary),'--comic-benchmark',str(run_manifest),str(work)],check=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,timeout=3600,stdout=log,stderr=log)
            actual=read(pathlib.Path(str(work)+'.summary.json'))
            assert actual['images']==len(pending) and actual['runtime_errors']==0
            combined=saved+records(work);combined.sort(key=lambda r:(r['image'],r['bounds'][1],r['bounds'][0]))
            atomic(output,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in combined))
            atomic(done,json.dumps(dict(images=len(items),viewports=actual['viewports']+len(complete_ids),runtime_errors=0,
                resumed_complete_images=len(complete_ids),resumed_output_sha256=digest(output)),indent=2))
            atomic(folder/f'part-{part}.timing.json',json.dumps(dict(elapsed_seconds=time.monotonic()-started)))
        status=read(done);assert status['images']==len(items) and status['runtime_errors']==0
        print(json.dumps(dict(parts_completed=part,images=status['images'])),flush=True)
        return records(output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:parts=list(pool.map(run,range(4)))
    rows=[r for part in parts for r in part];rows.sort(key=lambda r:(r['image'],r['bounds'][1],r['bounds'][0]))
    assert len({r['image'] for r in rows})==124
    atomic(folder/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    previous=records(old/'output.jsonl');changes=[]
    for ident in range(1,125):
        a=[r for r in previous if r['image']==ident];b=[r for r in rows if r['image']==ident]
        fields=lambda group:[{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in group]
        if fields(a)!=fields(b):changes.append(dict(id=ident,before=a,after=b))
    atomic(folder/'changes.json',json.dumps(changes,ensure_ascii=False,indent=2))
    summary=dict(viewports=124,regions=len(rows),runtime_errors=0,changed_viewports=len(changes),
        recovered_short_regions=sum(r['short_dialogue_recovered'] for r in rows),
        output_sha256=digest(folder/'output.jsonl'),provenance_sha256=digest(pin),
        changes_sha256=digest(folder/'changes.json'),all_new_meanings_reviewed=False,
        screen_attempt_failure_probability=None,target_achieved=False,default_live_worker_enabled=normal)
    if args.packaged or args.inflection:
        assert all(r['reader_consensus_enabled'] for r in rows)
        expected=records(QA/('windows8025-packaged-full-viewports/output.jsonl' if args.inflection else 'windows8024-short-full-viewports/output.jsonl'))
        if args.inflection:
            selected=records(QA/'ocr-morph-consensus8026/full-viewports-output.jsonl')
            translated={r['id']:r for r in records(QA/'ocr-morph-consensus8026/translation-output.jsonl')}
            expected=[dict(r) for r in expected]
            for ident,(r,selection) in enumerate(zip(expected,selected),1):
                assert ident==selection['id']
                if r['source']!=selection['selected']:
                    fresh=translated[ident];assert fresh['source']==selection['selected']
                    r.update(source=fresh['source'],translation=fresh['translation'],retained_original=fresh['retained_original'],sentence_recovered=fresh['sentence_recovered'])
        fields=lambda group:[{k:r.get(k) for k in ['source','translation','bounds','retained_original','sentence_recovered']} for r in group]
        equal=[ident for ident in range(1,125) if fields([r for r in expected if r['image']==ident])==fields([r for r in rows if r['image']==ident])]
        summary.update(actual_consensus_enabled_for_every_region=True,identical_to_reviewed_experiment_viewports=equal,
            expected_native_output_sha256=digest(QA/('ocr-morph-consensus8026/full-viewports-output.jsonl' if args.inflection else 'windows8024-short-full-viewports/output.jsonl')))
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
