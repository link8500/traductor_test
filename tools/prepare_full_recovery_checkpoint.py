"""Freeze the available full-chapter 8012 OCR comparison at fixed locations.

All available locations enter the checkpoint. Only byte-identical output and
source with unambiguous geometry can reuse a judgment. Changed output is left
pending until its original pixels are inspected.
"""
import argparse
import json
import re
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-name',default='full8012-review-checkpoint01');args=parser.parse_args()
    assert re.fullmatch('[a-z][a-z0-9-]+',args.output_name)
    folder=QA/args.output_name;folder.mkdir(exist_ok=True);sample_path=folder/'sample.json'
    if sample_path.exists():sample=read(sample_path)
    else:
        previous_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json';previous=read(previous_path)
        templates={}
        for group,name in [('a','current8011-full-a'),('b','current8011-full-b'),('short','corpus-review-short8011'),('next','corpus-review-next8011'),('sixth','corpus-review-sixth8011')]:
            for case in read(QA/name/'sample.json')['cases']:templates[(group,case['id'])]=case
        chapters={};all_pairs=[];pending=[]
        for old in previous['entries']:
            report=QA/'translated-en8012-recovery'/(old['chapter']+'-en.jsonl');done=report.with_name(report.stem+'.done.json')
            if not done.exists():continue
            status=read(done);assert status['all_files_traversed'] and status['runtime_errors']==0
            assert status['native_engine']=='769e45816118cc1a494071584fde5a90ef9a73cb78366dec52760502d3cc1101'
            assert status['translation_signature']==previous['translation_signature']
            chapters[old['chapter']]=dict(report_sha256=digest(report),done_sha256=digest(done))
            rows=[(i,r) for i,r in enumerate(records(report)) if r['image']==old['source_image'] and sheets.overlap(r['bounds'],old['bounds'])>.65]
            rows.sort(key=lambda pair:(pair[1]['bounds'][1],pair[1]['bounds'][0]))
            source=' '.join(r['source'] for _,r in rows);translation=' '.join(r['translation'] for _,r in rows)
            identical=len(rows)==1 and source==old['source'] and translation==old['translation']
            pair=dict(id=old['id'],chapter=old['chapter'],before_judgment=old['after'],before_translation=old['translation'],source=source,
                translation=translation,selected_regions=[i for i,_ in rows],source_image=old['source_image'],anchor_bounds=old['bounds'],
                judgment_reused_for_identical_output=identical,comparison_excluded='unresolved' in (old['before'],old['after']))
            all_pairs.append(pair)
            if identical:continue
            template=templates[(old['group'],old['original_id'])]
            box=[min([old['bounds'][0]]+[r['bounds'][0] for _,r in rows]),min([old['bounds'][1]]+[r['bounds'][1] for _,r in rows]),
                max([old['bounds'][2]]+[r['bounds'][2] for _,r in rows]),max([old['bounds'][3]]+[r['bounds'][3] for _,r in rows])]
            pending.append({**template,**pair,'id':len(pending)+1,'original_id':old['id'],'bounds':box,'meaning_reviewed':False})
        sample=dict(cases=pending,all_pairs=all_pairs,chapters=len(chapters),reviewed_locations=len(all_pairs),changed_locations=len(pending),
            identical_output_judgments_reused=len(all_pairs)-len(pending),frozen_reports=chapters,previous_review_sha256=digest(previous_path),
            selection='All fixed sample locations with a completed 8012 full-chapter report at snapshot creation',
            translation_weights_changed=False,all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False)
        atomic(sample_path,json.dumps(sample,ensure_ascii=False,indent=2))
    sheets.OUT=folder;sheets.render(sample,100,90)
    print(json.dumps({k:v for k,v in sample.items() if k not in ['cases','all_pairs','frozen_reports']}))


if __name__=='__main__':main()
