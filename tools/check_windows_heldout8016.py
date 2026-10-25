"""Exercise the frozen real Windows app on all124 held-out pixel crops."""
import argparse
import collections
import json
import pathlib
import subprocess
import time

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_reader_comparison import compare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',choices=['801501','801601','801701','801702','801703','801704','801801','801901'],default='801601')
    args=parser.parse_args();version=args.build[:4]
    prefix={'801702':'windows8017-preserve','801703':'windows8017-final','801704':'windows8017-render','801801':'windows8018'}.get(args.build,f'windows{version}')
    folder = QA / f'{prefix}-heldout-pixels';folder.mkdir(exist_ok=True)
    seed_path = QA / 'ocr-reader-heldout8016/sample.json'
    sample = read(seed_path)
    binary = QA / f'frozen-windows{args.build}/traductor.exe'
    snapshot=QA/f'windows-engine{args.build}.json'
    release_path=QA / f'release{version}.json'
    if release_path.exists():
        assert digest(snapshot)==read(release_path)['frozen_snapshot_sha256']
    else:
        assert args.build in ['801701','801702','801703','801704','801801','801901'],'Only a current frozen unshipped trial may precede packaging'
    assert digest(binary) == read(snapshot)['binary_sha256']
    inputs = []
    for case in sample['cases']:
        image = pathlib.Path(case['preview'])
        assert digest(image) == case['preview_sha256']
        inputs.append(dict(chapter=f'heldout-location-{case["id"]:03d}',image=case['id'],
            path=str(image),language='en',ocr_only=False,augment_detection=True,
            all_candidates=True,recover_paragraphs=True,complete_lines=True))
    manifest = folder / 'input.jsonl'
    atomic(manifest,''.join(json.dumps(row)+'\n' for row in inputs))
    target = folder / 'output.jsonl'
    proof_path = folder / 'provenance.json'
    proof = dict(binary_sha256=digest(binary),seed_sha256=digest(seed_path),
        manifest_sha256=digest(manifest),original_pixels_only=True,
        manual_answers_supplied_to_app=False,experimental_ocr_readers_used=False,
        model_weights_changed=False,actual_frozen_windows_app=True,
        cropped_region_attempts_not_complete_desktop_screens=True)
    if proof_path.exists():
        assert read(proof_path) == proof
    else:
        atomic(proof_path,json.dumps(proof,indent=2))
    if not pathlib.Path(str(target)+'.summary.json').exists():
        start = time.monotonic()
        subprocess.run([str(binary),'--comic-benchmark',str(manifest),str(target)],
            check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=1800)
        atomic(folder/'timing.json',json.dumps(dict(elapsed_seconds=time.monotonic()-start)))
    report = read(pathlib.Path(str(target)+'.summary.json'))
    assert report['images'] == 124 and report['runtime_errors'] == 0
    rows = records(target)
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['image']].append(row)
    # Human transcriptions enter only this scoring step, after the complete
    # real app inference process has finished. They never enter its input.
    manual_path = ROOT / 'benchmarks/full-comics/ocr8016-heldout-full-manual-transcriptions.json'
    manual = {row[0]:row for row in read(manual_path)}
    entries = []
    for case in sample['cases']:
        ident = case['id'];parts = sorted(grouped[ident],key=lambda row:(row['bounds'][1],row['bounds'][0]))
        source = ' '.join(row['source'] for row in parts)
        entries.append(dict(id=ident,expected_visible_english=manual[ident][1],
            source=source,source_quality=compare(manual[ident][1],source),
            regions=len(parts),retained_original_regions=sum(row.get('retained_original',False) for row in parts),
            translations=[row['translation'] for row in parts],
            meaning_reviewed=False))
    counts = collections.Counter()
    for entry in entries:
        counts.update(entry['source_quality']['edit_categories'])
    value = dict(pixel_crops=124,native_app_processes=1,runtime_errors=report['runtime_errors'],
        recognized_regions=len(rows),crop_source_word_errors=sum(e['source_quality']['word_errors'] for e in entries),
        words=sum(e['source_quality']['expected_words'] for e in entries),
        crops_with_source_word_errors=sum(e['source_quality']['word_errors']>0 for e in entries),
        source_edit_categories=dict(counts),crops_without_detected_text=sum(e['regions']==0 for e in entries),
        source_quality_compared_against_manual_pixels=True,translation_meaning_reviewed=False,
        screen_attempt_failure_probability=None,all_chapter_words_visually_reviewed=False,
        sample_sha256=digest(seed_path),manual_sha256=digest(manual_path),
        provenance_sha256=digest(proof_path),native_output_sha256=digest(target),
        app_summary_sha256=digest(pathlib.Path(str(target)+'.summary.json')),entries=entries)
    atomic(folder/'summary.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k!='entries'}),flush=True)


if __name__ == '__main__':
    main()
