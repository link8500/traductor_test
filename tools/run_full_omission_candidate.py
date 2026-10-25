"""Apply source-only omission candidate selection to all 124 fixed-OCR reports.

The native plan sees actual OCR plus the same model's previous output, never
reference text. Only selected sources need fresh inference; every other output
is explicitly retained, without implying it is semantically correct.
"""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,CHAPTERS,read,records,digest,atomic


def main():
    out=QA/'full-omission-candidate8016';out.mkdir(exist_ok=True)
    native=ROOT/'build/coverage8016/compiled/Release/luma_translate.exe';plan=ROOT/'build/ocr8016/Release/luma_coverage_candidate_plan.exe'
    seed=QA/'sentence-coverage8016';seed_proof=read(seed/'provenance.json');assert digest(native)==seed_proof['binary_sha256']
    cache={r['source']:r for r in records(seed/'output.jsonl')}
    assert digest(seed/'output.jsonl')==read(seed/'summary.json')['output_sha256']
    inputs=[];chapters={};all_rows={}
    for chapter in CHAPTERS:
        path=QA/'translated-en8014-fixed-ocr'/(chapter+'-en.jsonl');rows=records(path);status=read(path.with_name(path.stem+'.done.json'))
        assert status['all_files_traversed'] and status['runtime_errors']==0
        chapters[chapter]=dict(report_sha256=digest(path),status_sha256=digest(path.with_name(path.stem+'.done.json')))
        all_rows[chapter]=rows
        for i,row in enumerate(rows):inputs.append(dict(chapter=chapter,region=i,source=row['source'],translation=row.get('whole_translation',row['translation'])))
    manifest=out/'plan-input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    plan_output=out/'plan-output.jsonl'
    if not plan_output.exists():
        with manifest.open('rb') as src,plan_output.open('wb') as dest:subprocess.run([str(plan)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    plan_rows=records(plan_output);assert len(plan_rows)==len(inputs) and all(all(r[k]==s[k] for k in ['chapter','region','source','translation']) for r,s in zip(plan_rows,inputs))
    selected=[r for r in plan_rows if r['retry']];sources={r['source'] for r in selected};output=out/'inferences.jsonl'
    proof=dict(candidate_provenance_sha256=digest(seed/'provenance.json'),reused_seed_output_sha256=digest(seed/'output.jsonl'),
        binary_sha256=digest(native),plan_binary_sha256=digest(plan),plan_input_sha256=digest(manifest),plan_output_sha256=digest(plan_output),chapters=chapters,
        reference_or_answers_supplied=False,translator_weights_changed=False,application_modified=False)
    proof_path=out/'provenance.json'
    if proof_path.exists():assert read(proof_path)==proof
    else:atomic(proof_path,json.dumps(proof,indent=2))
    fresh={r['source']:r for r in records(output)} if output.exists() else {};assert set(fresh)<=sources
    cache.update(fresh);model=None
    try:
        for source in sorted(sources):
            if source in cache:continue
            if model is None:model=subprocess.Popen([str(native),str(ROOT/'assets/models/opus-en-es')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
            model.stdin.write(json.dumps(dict(source=source))+'\n');model.stdin.flush();line=model.stdout.readline();assert line,'Missing native output'
            row=json.loads(line);assert row['source']==source and 'error' not in row,row
            with output.open('a',encoding='utf-8') as handle:handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            cache[source]=row;fresh[source]=row
            if len(fresh)%25==0:print('Additional native omission candidates:',len(fresh),'/',len(sources),flush=True)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)
    changed=[]
    for entry in selected:
        old=all_rows[entry['chapter']][entry['region']];current=cache[entry['source']]
        if current['translation']==old['translation']:continue
        changed.append(dict(chapter=entry['chapter'],region=entry['region'],image=old['image'],bounds=old['bounds'],source=entry['source'],before_translation=old['translation'],translation=current['translation'],inference=current,meaning_reviewed=False))
    atomic(out/'changed.json',json.dumps(dict(cases=changed),ensure_ascii=False,indent=2))
    summary=dict(chapters_scanned=124,regions_scanned=len(inputs),native_plan_candidates=len(selected),unique_candidate_sources=len(sources),
        fresh_inferences=len(fresh),reused_identical_native_seed_sources=len(sources)-len(fresh),changed_regions=len(changed),
        unchanged_regions=len(inputs)-len(changed),all_changed_regions_semantically_reviewed=False,application_modified=False,
        all_chapter_words_visually_reviewed=False,screen_attempt_failure_probability=None,provenance_sha256=digest(proof_path),changed_sha256=digest(out/'changed.json'))
    atomic(out/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
