"""Score inventoried dialogue on all same full viewports, not whole chapters.

Manual non-dialogue row roles apply only in evaluation, never to inference.
Keep edit-alignment deletions separate from proven physical OCR omissions.
"""
import collections
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from evaluate_ocr_apostrophes8019 import strict_compare


def measure(entries,variant):
    scores=[r['variants'][variant] for r in entries]
    words=sum(r['expected_words'] for r in scores);errors=sum(r['word_errors'] for r in scores)
    kinds=collections.Counter(edit['kind'] for row in scores for edit in row['edits'])
    return dict(viewports=len(scores),expected_dialogue_words=words,word_errors=errors,
        word_error_rate_percent=100*errors/words,viewports_with_word_errors=sum(r['word_errors']>0 for r in scores),
        alignment_edit_categories=dict(kinds))


def main():
    inventory_path=ROOT/'benchmarks/full-comics/viewport8020-original-inventory.json'
    roles_path=ROOT/'benchmarks/full-comics/viewport8023-ocr-row-roles.json'
    inventory=read(inventory_path);roles=read(roles_path)
    assert inventory['all124_original_inventories_complete'] and len(inventory['entries'])==124
    paths=dict(baseline=QA/'windows8020-full-viewports-baseline/output.jsonl',
        partial_consensus=QA/'windows8020-full-viewports-consensus/output.jsonl',
        full_consensus=QA/'windows8021-full-viewports-full-agreement/output.jsonl')
    variants={k:records(p) for k,p in paths.items()};current=variants['full_consensus']
    assert all(len(rows)==228 for rows in variants.values())
    excluded={r[0]:r for r in roles['excluded_from_dialogue_score']};assert len(excluded)==21
    for index,_,source in excluded.values():assert current[index]['source']==source
    for rows in variants.values():assert [(r['image'],r['bounds']) for r in rows]==[(r['image'],r['bounds']) for r in current]
    entries=[]
    for original in inventory['entries']:
        ident=original['id'];expected=' '.join(original['dialogue']);results={}
        for variant,rows in variants.items():
            actual=' '.join(r['source'] for i,r in enumerate(rows) if r['image']==ident and i not in excluded)
            score=strict_compare(expected,actual)
            for edit in score['edits']:
                edit['kind']='inserted_word' if edit['expected'] is None else 'alignment_deleted_word' if edit['actual'] is None else 'substituted_word'
            results[variant]=dict(score,actual=actual)
        entries.append(dict(id=ident,expected_visible_dialogue=expected,
            visible_dialogue_clipped=original['visible_dialogue_clipped'],variants=results))
    cohorts={}
    for name,subset in [('all124_fixed_reading_viewports',entries),
                        ('no_visible_dialogue_clipped',[r for r in entries if not r['visible_dialogue_clipped']])]:
        scores={name:measure(subset,name) for name in variants}
        old=scores['baseline'];new=scores['full_consensus']
        paired=dict(before_word_errors=old['word_errors'],after_word_errors=new['word_errors'],
            relative_word_error_reduction_percent=100*(old['word_errors']-new['word_errors'])/old['word_errors'],
            corrected_viewports=sum(r['variants']['baseline']['word_errors']>0 and r['variants']['full_consensus']['word_errors']==0 for r in subset),
            regressed_viewports=sum(r['variants']['baseline']['word_errors']==0 and r['variants']['full_consensus']['word_errors']>0 for r in subset))
        cohorts[name]=dict(variants=scores,paired=paired)
    value=dict(schema=1,viewports=124,native_regions=228,dialogue_rows=207,excluded_non_dialogue_rows=21,
        excluded_roles=dict(collections.Counter(r[1] for r in excluded.values())),
        inventory_sha256=digest(inventory_path),manual_row_roles_sha256=digest(roles_path),
        native_outputs={k:digest(p) for k,p in paths.items()},cohorts=cohorts,entries=entries,
        strict_internal_apostrophes=True,case_and_outer_punctuation_ignored=True,
        alignment_deletions_include_segmentation_defects=True,dialogue_is_not_limited_to_detected_boxes=True,
        translation_meaning_not_measured_by_this_report=True,screen_attempt_failure_probability=None,
        all_chapter_words_visually_reviewed=False,target_achieved=False,application_modified=False)
    atomic(ROOT/'benchmarks/full-comics/viewport8023-dialogue-ocr-review.json',json.dumps(value,ensure_ascii=False,indent=2))
    print(json.dumps(dict(cohorts=cohorts,screen_attempt_failure_probability=None,target_achieved=False)),flush=True)


if __name__=='__main__':main()
