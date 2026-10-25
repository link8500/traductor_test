"""Translate every fixed full reading viewport, preserving unreviewed status.

These are saved reading viewports, not live desktop capture attempts. Native
OCR and translation run without human/reference inputs. Their complete visible
dialogue inventories must be reviewed before assigning any per-viewport pass.
"""
import argparse
import json
import pathlib
import subprocess
import time
from audit_corpus_quality import QA,atomic,digest,read,records


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--variant',choices=['baseline','consensus','full-agreement'],required=True);args=parser.parse_args()
    variant=args.variant;build='801901' if variant=='baseline' else '802101' if variant=='full-agreement' else '802001'
    with_readers=variant!='baseline'
    folder=QA/(('windows8021-full-viewports-' if variant=='full-agreement' else 'windows8020-full-viewports-')+variant);folder.mkdir(exist_ok=True)
    source=QA/'recovery-viewports801201';binary=QA/f'frozen-windows{build}/traductor.exe';snapshot=QA/f'windows-engine{build}.json'
    assert digest(binary)==read(snapshot)['binary_sha256'];inputs=[];frames=[]
    for ident in range(1,125):
        status=read(source/f'{ident:03d}.done.json');item=records(source/f'{ident:03d}.input.jsonl')[0]
        path=pathlib.Path(item['path']);assert digest(path)==status['viewport_png_sha256']
        item.update(ocr_only=False,complete_lines=True)
        if with_readers:item.update(consensus_first_directory=str(QA/'ocr-candidates8016/english-v5'),consensus_second_directory=str(QA/'ocr-candidates8016/multilingual-v6-small'))
        inputs.append(item);frames.append(dict(id=ident,pixels_sha256=digest(path),source_status_sha256=digest(source/f'{ident:03d}.done.json')))
    manifest=folder/'input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    proof=dict(build=build,binary_sha256=digest(binary),snapshot_sha256=digest(snapshot),input_sha256=digest(manifest),
        frames=frames,variant=variant,human_or_reference_text_supplied=False,live_desktop_capture=False,
        toolbar_actions_included=False,all_chapter_words_reviewed=False,complete_app_uses_reviewed=False)
    if with_readers:
        proof['reader_assets']={name:{part:digest(QA/'ocr-candidates8016'/name/part) for part in ['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json']}
            for name in ['english-v5','multilingual-v6-small']}
    pin=folder/'provenance.json'
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))
    output=folder/'output.jsonl';raw_status=pathlib.Path(str(output)+'.summary.json')
    if not raw_status.exists():
        start=time.monotonic();subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(output)],
            check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=14400)
        atomic(folder/'timing.json',json.dumps(dict(elapsed_seconds=time.monotonic()-start)))
    raw=read(raw_status);rows=records(output);assert raw['images']==124 and raw['runtime_errors']==0
    summary=dict(variant=variant,build=build,reading_viewports_processed=124,viewports_native=raw['viewports'],
        regions=len(rows),runtime_errors=raw['runtime_errors'],native_output_sha256=digest(output),
        native_summary_sha256=digest(raw_status),provenance_sha256=digest(pin),
        original_visible_dialogue_inventory_complete=False,all_output_meanings_reviewed=False,
        complete_chapter_traversal=False,complete_app_use_including_capture_and_toolbar=False,
        screen_attempt_failure_probability=None,target_achieved=False)
    atomic(folder/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
