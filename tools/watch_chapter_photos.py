"""Publish complete new inference cohorts as a running corpus finishes."""
import argparse,datetime,hashlib,json,pathlib,re,subprocess,sys,time

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def publication_rank(folder):
    match=re.fullmatch(r'translated-en(\d+)(-context)?',folder)
    return (int(match[1]),bool(match[2])) if match else (0,False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',required=True)
    parser.add_argument('--reports',help='Explicit completed inference cohort, including a capture-selection revision')
    args=parser.parse_args()
    assert re.fullmatch(r'[0-9]+',args.build)
    folder=args.reports or 'translated-en'+args.build;assert re.fullmatch(r'[a-z][a-z0-9-]+',folder)
    previous=None
    while True:
        states=[]
        for number in range(1,125):
            chapter=f'absolute-regression-{number:02d}';report=QA/folder/(chapter+'-en.jsonl');done=report.with_name(chapter+'-en.done.json')
            if not done.exists() or not report.exists():continue
            status=read(done)
            if not status.get('all_files_traversed') or status.get('runtime_errors'):continue
            proof=QA/'chapter-photos'/chapter/'provenance.json';sha=digest(report)
            old=read(proof) if proof.exists() else {}
            # A control pass must not roll a newer published chapter back.
            if publication_rank(old.get('report_directory',''))>publication_rank(folder):
                states.append(chapter);continue
            if old.get('report_directory')!=folder or old.get('report_sha256')!=sha:
                subprocess.run([sys.executable,'-u',str(ROOT/'tools/export_chapter_photos.py'),'--start',str(number),'--end',str(number),'--workers','1','--current-reports',folder],check=True,cwd=ROOT)
                subprocess.run([sys.executable,str(ROOT/'tools/audit_chapter_translations.py')],check=True,cwd=ROOT)
                subprocess.run([sys.executable,str(ROOT/'tools/evaluate_visual_word_reviews.py'),'--english-reports',folder,
                    '--output-name',folder.replace('translated-en','visual-evaluation')],check=True,cwd=ROOT)
            states.append(chapter)
        if previous!=len(states):
            subprocess.run([sys.executable,str(ROOT/'tools/export_chapter_photos.py'),'--html-only'],check=True,cwd=ROOT)
            value=dict(build=int(args.build),chapters_expected=124,complete_new_translation_and_photo_chapters=len(states),
                all_words_visually_reviewed=False,semantic_accuracy=None,generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            path=QA/f'photo-workflow{args.build}.json';pending=path.with_suffix('.pending');pending.write_text(json.dumps(value,indent=2),encoding='utf-8');pending.replace(path)
            print('Latest cohort published:',len(states),'/124, build',args.build,flush=True);previous=len(states)
        if len(states)==124:break
        time.sleep(20)

if __name__=='__main__':main()
