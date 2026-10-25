"""Freeze available combined OCR/NMT outputs at all six fixed locations.

Previous pixel judgments are reused only for byte-identical source/output in
the same original region. Every other changed location stays pending.
"""
import json
import prepare_corpus_review_sample as sheets
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    folder=QA/'combined-recovery8016-checkpoint01';folder.mkdir(exist_ok=True);path=folder/'sample.json'
    if path.exists():sample=read(path)
    else:
        base_path=ROOT/'benchmarks/full-comics/coverage8014-six-regions-semantic-review.json';base=read(base_path)
        locations_path=ROOT/'benchmarks/full-comics/current8011-six-regions-semantic-review.json';locations={r['id']:r for r in read(locations_path)['entries']}
        templates={}
        for group,name in [('a','current8011-full-a'),('b','current8011-full-b'),('short','corpus-review-short8011'),('next','corpus-review-next8011'),('sixth','corpus-review-sixth8011')]:
            for case in read(QA/name/'sample.json')['cases']:templates[(group,case['id'])]=case
        old_path=ROOT/'benchmarks/full-comics/full8012-checkpoint01-semantic-review.json';old=read(old_path);old_entries={e['id']:e for e in old['entries']}
        old_sample=read(ROOT/old['sample_path']);old_cases={c['original_id']:c for c in old_sample['cases']}
        all_pairs=[];pending=[];chapters={}
        for entry in base['entries']:
            report=QA/'translated-en8014-recovery'/(entry['chapter']+'-en.jsonl');done=report.with_name(report.stem+'.done.json')
            if not done.exists():continue
            status=read(done);assert status['all_files_traversed'] and status['runtime_errors']==0
            assert status['native_engine']=='769e45816118cc1a494071584fde5a90ef9a73cb78366dec52760502d3cc1101'
            assert status['translation_signature']=='89d2eedb90c0f53b7b6b5c573df3f4d8097a2e1ed87187ea9a1e24ad6d4904a3'
            chapters[entry['chapter']]=dict(report_sha256=digest(report),done_sha256=digest(done))
            location=locations[entry['id']]
            rows=[(i,r) for i,r in enumerate(records(report)) if r['image']==location['source_image'] and sheets.overlap(r['bounds'],entry['bounds'])>.65]
            rows.sort(key=lambda pair:(pair[1]['bounds'][1],pair[1]['bounds'][0]))
            source=' '.join(r['source'] for _,r in rows);translation=' '.join(r['translation'] for _,r in rows)
            bounds=[min([entry['bounds'][0]]+[r['bounds'][0] for _,r in rows]),min([entry['bounds'][1]]+[r['bounds'][1] for _,r in rows]),
                max([entry['bounds'][2]]+[r['bounds'][2] for _,r in rows]),max([entry['bounds'][3]]+[r['bounds'][3] for _,r in rows])]
            same=len(rows)==1 and source==entry['source'] and translation==entry['translation']
            reused='same_fixed_location_output' if same else None;after=entry['after'] if same else None;note='Fuente y salida idénticas en la misma ubicación.' if same else None
            prior=old_entries.get(entry['id']);prior_case=old_cases.get(entry['id'])
            if not same and prior and prior_case and prior['source']==source and prior['translation']==translation and prior_case['bounds']==bounds and location['source_image']==prior['source_image']:
                reused='previous_pixel_review_same_source_output_geometry';after=prior['after'];note=prior['note_es']
            pair=dict(id=entry['id'],chapter=entry['chapter'],source_image=location['source_image'],anchor_bounds=entry['bounds'],bounds=bounds,
                before=entry['after'],before_translation=entry['translation'],source=source,translation=translation,selected_regions=[i for i,_ in rows],
                comparison_excluded=entry['comparison_excluded'],judgment_reuse=reused,after=after,note_es=note)
            all_pairs.append(pair)
            if reused:continue
            template=templates[(location['group'],location['original_id'])]
            pending.append({**template,**pair,'id':len(pending)+1,'original_id':entry['id'],'meaning_reviewed':False})
        sample=dict(cases=pending,all_pairs=all_pairs,chapters=len(chapters),frozen_reports=chapters,base_review_sha256=digest(base_path),location_review_sha256=digest(locations_path),
            previous_pixel_review_sha256=digest(old_path),selection='All six fixed locations in every completed combined OCR/NMT report at freeze time; no output-based selection',
            reviewed_locations=len(all_pairs),pending_visual_review=len(pending),identical_output_judgments_reused=sum(p['judgment_reuse'] is not None for p in all_pairs),
            all_chapter_words_visually_reviewed=False,population_accuracy_estimate=False,translation_weights_changed=False)
        atomic(path,json.dumps(sample,ensure_ascii=False,indent=2))
    sheets.OUT=folder;sheets.render(sample,100,90)
    print(json.dumps({k:v for k,v in sample.items() if k not in ['cases','all_pairs','frozen_reports']}),flush=True)


if __name__=='__main__':main()
