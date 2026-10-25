"""Exercise the production recovery stage on full comic screen viewports.

The 124 locations are fixed independently of translation outcomes. A viewport
per chapter is a regression set, not a complete chapter traversal or approval.
"""
import argparse
import collections
import datetime
import json
import pathlib
import subprocess
import time

from PIL import Image

from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic
from evaluate_paragraph_probe import matching


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', default='801201')
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    assert args.build.isdecimal()
    out = QA/('recovery-viewports'+args.build);out.mkdir(exist_ok=True)
    binary = QA/('frozen-windows'+args.build)/'traductor.exe'
    snapshot = read(QA/('windows-engine'+args.build+'.json'))
    assert digest(binary) == snapshot['binary_sha256']
    seed_path = QA/'corpus-review-sample/sample.json'
    seeds = read(seed_path)['cases']
    previous = None
    while True:
        for seed in seeds:
            case_id = seed['id']
            done = out/f'{case_id:03d}.done.json'
            if done.exists():
                status = read(done)
                assert status['binary_sha256'] == snapshot['binary_sha256']
                continue
            control = QA/CURRENT/(seed['chapter']+'-en.jsonl')
            if not control.with_name(seed['chapter']+'-en.done.json').exists():
                continue
            candidates = matching(seed, records(control))
            # Keep the full screen even if the reference location is split.
            anchor = max(candidates,key=lambda r:(r['bounds'][2]-r['bounds'][0])*(r['bounds'][3]-r['bounds'][1])) if candidates else None
            top = anchor.get('cropTop', 0) if anchor else max(0, seed['bounds'][1]-500)
            page = seed['source_page'];source = pathlib.Path(page['path'])
            assert digest(source) == page['sha256']
            image_path = out/f'{case_id:03d}.png'
            with Image.open(source) as bitmap:
                bottom = min(bitmap.height, top+2000)
                bitmap.crop((0,top,bitmap.width,bottom)).convert('RGB').save(image_path,compress_level=1)
            input_path = out/f'{case_id:03d}.input.jsonl'
            output = out/f'{case_id:03d}.jsonl'
            item = dict(chapter=f'fixed-screen-{case_id:03d}', image=case_id, path=str(image_path.resolve()),
                        language='en', ocr_only=True, augment_detection=True, all_candidates=True, recover_paragraphs=True)
            atomic(input_path,json.dumps(item)+'\n')
            started = time.monotonic()
            result = subprocess.run([str(binary.resolve()),'--comic-benchmark',str(input_path.resolve()),str(output.resolve())],
                creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode == 0, f'Screen regression failed: {case_id}'
            summary = read(pathlib.Path(str(output)+'.summary.json'))
            assert summary['images']==1 and summary['runtime_errors']==0
            rows = records(output)
            status = dict(id=case_id, chapter=seed['chapter'], source_image=seed['source_image'],
                source_sha256=page['sha256'], viewport_top=top, viewport_bottom=bottom,
                viewport_png_sha256=digest(image_path), engine=snapshot['engine'], binary_sha256=digest(binary),
                baseline_report_directory=CURRENT, baseline_report_sha256=digest(control),
                fixed_sample_sha256=digest(seed_path), regions=len(rows),
                recovered_regions=sum(r.get('paragraph_recovered',False) for r in rows),
                source_output_sha256=digest(output), seconds=round(time.monotonic()-started,3),
                full_chapter_traversal=False, words_visually_reviewed=False)
            atomic(done,json.dumps(status,indent=2))
            print('Full screen regressions completed:',len(list(out.glob('*.done.json'))),'/124;',
                  status['recovered_regions'],'regions recovered in this screen',flush=True)
        states = [read(p) for p in out.glob('*.done.json')]
        summary = dict(build_snapshot=args.build, generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            full_screen_viewports_completed=len(states), full_screen_viewports_expected=124,
            recovered_regions=sum(s['recovered_regions'] for s in states),
            all_original_chapter_words_reviewed=False, full_chapter_traversal=False,
            semantic_accuracy=None, cases=sorted(states,key=lambda s:s['id']))
        atomic(out/'summary.json',json.dumps(summary,indent=2))
        if len(states)!=previous:
            print('Production viewport coverage:',len(states),'/124',flush=True);previous=len(states)
        if not args.watch or len(states)==124:
            break
        time.sleep(20)


if __name__=='__main__':
    main()
