"""Probe an offline retry for multi-sentence translations with likely omissions.

This reads only real English OCR and model outputs. No Spanish references,
transcriptions, known answers, or comic-specific rules enter selection.
Production translation code and saved inference reports are not modified.
"""
import argparse
import json
import pathlib
import re
import subprocess
import time
from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic


def sentences(source):
    # A complete sentence end is followed by an independent capitalized clause.
    # Ellipses and common title abbreviations do not establish that boundary.
    cuts=[]
    for match in re.finditer(r'[.!?]+\s+(?=["\']?[A-Z])',source):
        end=match.end();prefix=source[:match.start()+1]
        if len(match.group().strip())!=1:continue
        if re.search(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|No|vs|etc)\.$',prefix,re.I):continue
        if re.search(r'\b[A-Z]\.$',prefix):continue
        cuts.append(end)
    parts=[];start=0
    for end in cuts+[len(source)]:
        parts.append(source[start:end].strip());start=end
    if not 2<=len(parts)<=4:return []
    if not all(3<=len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",part))<=70 for part in parts):return []
    return parts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    out=QA/'sentence-coverage-probe8011';out.mkdir(exist_ok=True)
    provenance=read(QA/CURRENT/'inference-provenance.json')
    model=None
    previous=None
    try:
        while True:
            for status in sorted((QA/CURRENT).glob('absolute-regression-*-en.done.json')):
                chapter=read(status)['chapter'];target=out/(chapter+'.json')
                report=status.with_name(chapter+'.jsonl')
                if target.exists():
                    assert read(target)['source_report_sha256']==digest(report)
                    continue
                candidates=[]
                for index,row in enumerate(records(report)):
                    source=row['source'];translation=row.get('translation','')
                    parts=sentences(source)
                    if not parts or not translation or len(translation)>=.70*len(source):continue
                    terminal_count=len(re.findall(r'[.!?](?:\s|$)',translation))
                    if terminal_count>=len(parts):continue
                    if model is None:
                        model=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(ROOT/'assets/models/opus-en-es')],
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW)
                    results=[]
                    for part in parts:
                        model.stdin.write(json.dumps(dict(source=part))+'\n');model.stdin.flush()
                        line=model.stdout.readline();assert line,'No model output'
                        result=json.loads(line);assert 'error' not in result,result
                        results.append(result)
                    candidate=' '.join(r['translation'] for r in results)
                    candidates.append(dict(region_index=index,image=row['image'],bounds=row['bounds'],source=source,
                        control_translation=translation,parts=parts,part_inferences=results,candidate_translation=candidate,
                        source_report_sha256=digest(report),meaning_reviewed=False))
                atomic(target,json.dumps(dict(chapter=chapter,source_report_sha256=digest(report),translation_signature=provenance['translation_signature'],
                    reference_used_for_inference=False,production_code_modified=False,cases=candidates),ensure_ascii=False,indent=2))
                if candidates:print('Offline omission candidates:',len(candidates),'in next completed report',flush=True)
            reports=[read(p) for p in out.glob('absolute-regression-*-en.json')]
            summary=dict(chapters_scanned=len(reports),chapters_expected=124,automatic_candidates=sum(len(r['cases']) for r in reports),
                confirmed_errors=None,semantic_accuracy=None,production_code_modified=False)
            atomic(out/'summary.json',json.dumps(summary,indent=2))
            if summary!=previous:print(json.dumps(summary),flush=True);previous=summary
            if not args.watch or len(reports)==124:break
            if model is not None:model.stdin.close();model.wait(timeout=30);model=None
            time.sleep(20)
    finally:
        if model is not None:model.stdin.close();model.wait(timeout=30)


if __name__=='__main__':main()
