"""Run every page, checkpointing complete chapters and cleaning generated PNGs.

Full file traversal is recorded separately from human word/meaning review.
"""
import argparse,concurrent.futures,hashlib,json,pathlib,re,shutil,subprocess,time
from PIL import Image
from comic_capture_selection import select_captures
from quality_resources import wait_for_inference_memory

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['en','es'],required=True);parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    parser.add_argument('--series',choices=['all','absolute-regression','greatest-estate-developer'],default='all')
    parser.add_argument('--start',type=int,default=1);parser.add_argument('--end',type=int,default=124)
    parser.add_argument('--ocr-only',action='store_true');parser.add_argument('--reference-recognizer',type=pathlib.Path)
    parser.add_argument('--resolve-overlaps',action='store_true',help='Choose complete paragraphs from all overlapping native viewport candidates')
    parser.add_argument('--resume-partial-engine',help='Explicit provenance of an interrupted report made before running markers were added')
    parser.add_argument('--engine-snapshot',type=pathlib.Path,help='Pinned executable/model fingerprint for an intentionally frozen baseline')
    parser.add_argument('--report-name',help='Separate QA output directory, for a new engine without overwriting a baseline')
    parser.add_argument('--binary',type=pathlib.Path,default=ROOT/'build/windows/x64/runner/Release/traductor.exe',
        help='Executable from a complete copied release directory; its hash is checked against the snapshot')
    args=parser.parse_args()
    if args.report_name and not re.fullmatch(r'[a-z][a-z0-9-]+',args.report_name):parser.error('Invalid report directory name')
    if args.binary.resolve() != (ROOT/'build/windows/x64/runner/Release/traductor.exe').resolve() and not args.engine_snapshot:
        parser.error('A copied executable requires --engine-snapshot to identify its actual engine')
    inputs=json.loads((QA/f'images-{args.language}.json').read_text(encoding='utf-8'))
    grouped={}
    for row in inputs:
        if args.start<=row['number']<=args.end and (args.series=='all' or row['series']==args.series):grouped.setdefault(row['chapter'],[]).append(row)
    destination=QA/(args.report_name or ('ocr-'+args.language if args.ocr_only else 'translated-'+args.language));destination.mkdir(parents=True,exist_ok=True)
    source_files=['native/local_translation.cpp','native/local_translation.h','native/ocr_recovery.h','native/translation_coverage.h','native/overlay_background.h','windows/runner/screen_translator.cpp','windows/runner/screen_translator.h','windows/runner/review_export.cpp','assets/models/opus-en-es/manifest.json']
    engine=hashlib.sha256(b''.join((ROOT/f).read_bytes() for f in source_files)).hexdigest()
    if args.engine_snapshot:
        snapshot=json.loads(args.engine_snapshot.read_text(encoding='utf-8'))
        assert hashlib.sha256(args.binary.read_bytes()).hexdigest()==snapshot['binary_sha256'],'Baseline binary changed'
        packaged=args.binary.parent/'data/flutter_assets/assets/models/opus-en-es'
        assert hashlib.sha256((packaged/'manifest.json').read_bytes()).hexdigest()==snapshot['manifest_sha256'],'Copied release manifest changed'
        for name,digest in json.loads((packaged/'manifest.json').read_text(encoding='utf-8'))['files'].items():
            assert hashlib.sha256((packaged/name).read_bytes()).hexdigest()==digest,('Copied release asset changed',name)
        if snapshot.get('windows_reader_manifest_sha256'):
            readers=args.binary.parent/'ocr-readers'
            assert hashlib.sha256((readers/'manifest.json').read_bytes()).hexdigest()==snapshot['windows_reader_manifest_sha256']
            for name,digest in json.loads((readers/'manifest.json').read_text(encoding='utf-8'))['files'].items():
                assert hashlib.sha256((readers/name).read_bytes()).hexdigest()==digest,('Copied Windows reader changed',name)
        engine=snapshot['engine']
    native_engine=engine
    if args.resolve_overlaps:
        assert args.ocr_only,'Resolve captures before requesting translation'
        engine=hashlib.sha256((engine+'overlap-context-v2').encode()+(ROOT/'tools/comic_capture_selection.py').read_bytes()).hexdigest()
    def run(item):
        chapter,images=item;start=time.monotonic();report=destination/(chapter+'.jsonl');status=destination/(chapter+'.done.json')
        image_signature=hashlib.sha256(''.join(r['sha256'] for r in images).encode()).hexdigest()
        if status.exists():
            old=json.loads(status.read_text(encoding='utf-8'))
            if old['engine']==engine and old['image_signature']==image_signature and report.exists():return old
        running=destination/(chapter+'.running.json');working=destination/(chapter+'.work.jsonl');cache=destination/(chapter+'.partial.jsonl')
        marker=json.loads(running.read_text(encoding='utf-8')) if running.exists() else {}
        same=marker.get('engine')==engine and marker.get('image_signature')==image_signature
        if not marker and args.resume_partial_engine:
            assert args.resume_partial_engine==engine,'Partial report engine differs from this build'
            same=True
        saved={}
        if same:
            for path in [cache,report,working]:
                if not path.exists():continue
                latest={}
                for line in path.read_text(encoding='utf-8').splitlines():
                    try:row=json.loads(line)
                    except ValueError:continue
                    latest.setdefault(row['image'],[]).append(row)
                saved.update(latest)
        last=max(saved,default=-1)
        complete={r['image'] for r in images if r['image']<last}
        preserved=[row for index,rows in saved.items() if index in complete for row in rows]
        cache.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in preserved),encoding='utf-8')
        running.write_text(json.dumps({'engine':engine,'image_signature':image_signature,'completed_images':sorted(complete)}),encoding='utf-8')
        wait_for_inference_memory()
        directory=QA/'temporary-png'/destination.name/chapter;directory.mkdir(parents=True,exist_ok=True);manifest=[]
        for image in images:
            if image['image'] in complete:continue
            target=directory/f"{image['image']:03d}.png"
            with Image.open(image['path']) as bitmap:
                # Do not consume the last free space or remove evidence to
                # continue. A resumed run retains the exact same inputs.
                assert shutil.disk_usage(directory).free>4*1024**3+bitmap.width*bitmap.height*4, 'Traversal postponed: preserve 4 GiB of free disk space'
                bitmap.convert('RGB').save(target,compress_level=1)
            row={k:image[k] for k in ['chapter','image','language']};row.update(path=str(target.resolve()),ocr_only=args.ocr_only,augment_detection=True)
            if args.resolve_overlaps:row['all_candidates']=True
            if args.reference_recognizer:row['recognizer_directory']=str(args.reference_recognizer.resolve())
            manifest.append(row)
        input_=directory/'input.jsonl';input_.write_text(''.join(json.dumps(r)+'\n' for r in manifest),encoding='utf-8')
        result=subprocess.run([str(args.binary.resolve()),'--comic-benchmark',str(input_.resolve()),str(working.resolve())],
            creationflags=subprocess.CREATE_NO_WINDOW,check=False)
        if result.returncode:
            error=pathlib.Path(str(working)+'.error.txt');raise RuntimeError(chapter+': '+(error.read_text(encoding='utf-8') if error.exists() else str(result.returncode)))
        actual=json.loads(pathlib.Path(str(working)+'.summary.json').read_text(encoding='utf-8'))
        assert actual['images']==len(manifest),(chapter,actual)
        rows=preserved+[json.loads(line) for line in working.read_text(encoding='utf-8').splitlines()]
        candidate_count=len(rows)
        if args.resolve_overlaps:rows=select_captures(rows)
        report.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        actual.update(images=len(images),regions=len(rows),runtime_errors=sum('error' in r for r in rows),
            viewports=actual['viewports']+sum(max(1,(max(0,r['height']-2000)+1299)//1300+1) for r in images if r['image'] in complete))
        completed={'chapter':chapter,'engine':engine,'image_signature':image_signature,'all_files_traversed':True,
            'word_review_complete':False,'semantic_review_complete':False,'ocr_only':args.ocr_only,
            'native_engine':native_engine,'capture_selection':'overlap-context-v2' if args.resolve_overlaps else 'first-overlapping-region',
            'capture_candidates':candidate_count,
            **actual,'words_read_by_system_ocr':sum(len(r.get('native_words',[])) for r in rows),
            'resumed_images':len(complete),
            'regions_with_additional_detection':sum(r.get('additional_detection',False) for r in rows),
            'seconds':round(time.monotonic()-start,2)}
        publication=status.with_suffix('.pending')
        publication.write_text(json.dumps(completed,ensure_ascii=False,indent=2),encoding='utf-8');publication.replace(status)
        for generated in directory.iterdir():
            assert generated.resolve().is_relative_to((QA/'temporary-png').resolve())
            if generated.suffix=='.png' or generated.name=='input.jsonl':generated.unlink()
        directory.rmdir();return completed
    errors=[];reports=[];started=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run,item):item[0] for item in sorted(grouped.items())}
        for future in concurrent.futures.as_completed(futures):
            try:
                report=future.result();reports.append(report);print('Completed',len(reports),'/',len(grouped),report['chapter'],report['regions'],'regions',report['seconds'],'s',flush=True)
            except Exception as error:errors.append({'chapter':futures[future],'error':str(error)});print('ERROR',errors[-1],flush=True)
            summary={'engine':engine,'language':args.language,'chapters_requested':len(grouped),'chapters_completed':len(reports),'errors':errors,
                'files_processed':sum(r['images'] for r in reports),'regions':sum(r['regions'] for r in reports),
                'runtime_errors':sum(r['runtime_errors'] for r in reports),'all_requested_files_traversed':len(reports)==len(grouped) and not errors,
                'word_review_complete':False,'semantic_accuracy':None,'seconds':round(time.monotonic()-started,2),'chapters':reports}
            (destination/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    if errors:raise SystemExit('Some chapter jobs failed; inspect summary.json and resume')

if __name__=='__main__':main()
