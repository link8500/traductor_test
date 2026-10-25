"""Coverage and execution checks, deliberately not a semantic accuracy score."""
import collections,hashlib,json,pathlib

root=pathlib.Path(__file__).resolve().parents[1]
qa=root/'build/comic-quality'
manifest=json.loads((qa/'manifest.json').read_text(encoding='utf-8'))
model=json.loads((root/'assets/models/opus-en-es/manifest.json').read_text(encoding='utf-8'))
result={'model':model['upstream'],'quantization':model['quantization'],
        'model_files':model['files'],'platforms':{},
        'semantic_accuracy':'Not established: no independently reviewed reference translation for every region.',
        'limitations':['Stylized lettering can still be misread or missed.',
                       'Short fragments, names and cultivation terminology can still be mistranslated.',
                       'An execution error count of zero is not a translation error count.']}
for platform,name in [('android','android-full.jsonl'),('windows','windows-ctc-translations.jsonl')]:
    path=qa/name
    if not path.exists():continue
    summary_path=qa/('android-full-summary.json' if platform=='android' else name+'.summary.json')
    if not summary_path.exists():raise SystemExit(f'Incomplete {platform} run: summary missing')
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    if platform=='android':
        summary['subsequent_grouping_fix']='The final APK accepts wider spacing between uppercase lines. Validated on screen fixtures; the 130-image corpus was not rerun after that change.'
    if platform=='windows' and (qa/'windows-final-translated-regions.jsonl').exists():
        summary['full_pipeline_runtime_errors_before_recovery_fix']=summary['runtime_errors']
        summary['translation_replay']='Final shared C++ core; OCR and coordinates from the complete native Windows pass.'
        path=qa/'windows-final-translated-regions.jsonl'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        summary['runtime_errors']=sum('error' in row for row in rows)
        summary['retained_original']=sum(bool(row.get('retained_original')) for row in rows)
    assert summary['images']==130 and summary['viewports']==966,(platform,summary)
    chapters=[]
    for chapter in manifest:
        group=[row for row in rows if row['chapter']==chapter['id']]
        chapters.append({'id':chapter['id'],'url':chapter['url'],'images':len(chapter['images']),
            'regions':len(group),'runtime_errors':sum('error' in row for row in group),
            'second_reading_changed':sum(row.get('native_source',row['source'])!=row['source'] for row in group),
            'unchanged':sum(row.get('translation','').casefold()==row['source'].casefold() for row in group)})
    result['platforms'][platform]={**summary,'chapters':chapters,'report_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
(qa/'quality-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for platform,data in result['platforms'].items():
    print(platform,data['images'],'images',data['viewports'],'viewports',data['regions'],'regions',data['runtime_errors'],'runtime errors')
    for chapter in data['chapters']:print(' ',chapter['id'],chapter['regions'],'regions;',chapter['second_reading_changed'],'changed by second OCR')
