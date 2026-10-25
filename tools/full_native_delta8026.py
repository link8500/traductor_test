"""Account for every row in matched full chapters without approving meanings."""
import collections
import json
import pathlib
import re
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records, reduction
from translation_quality_signals import signals


def pair_same_geometry(before,after):
    def key(row):return (row['image'],tuple(row['bounds']))
    waiting=collections.defaultdict(collections.deque)
    for index,row in enumerate(before):waiting[key(row)].append(index)
    pairs=[];added=[]
    for index,row in enumerate(after):
        candidates=waiting[key(row)]
        if candidates:pairs.append((candidates.popleft(),index))
        else:added.append(index)
    removed=sorted(index for queue in waiting.values() for index in queue)
    assert len(pairs)+len(removed)==len(before)
    assert len(pairs)+len(added)==len(after)
    return pairs,removed,added


def publish(source_name='translated-en8026-inflection',output_name='full-native-delta8026'):
    assert re.fullmatch('[a-z][a-z0-9-]+',source_name) and re.fullmatch('[a-z][a-z0-9-]+',output_name)
    old_folder=QA/'translated-en8017-geometry';new_folder=QA/source_name
    destination=QA/output_name;destination.mkdir(exist_ok=True)
    summaries=[]
    for number in range(1,125):
        chapter=f'absolute-regression-{number:02d}-en'
        done=[folder/(chapter+'.done.json') for folder in [old_folder,new_folder]]
        if not all(p.exists() for p in done):continue
        status=[read(p) for p in done]
        if any(not s.get('all_files_traversed') or s.get('runtime_errors') for s in status):continue
        assert status[0]['image_signature']==status[1]['image_signature'] and status[0]['images']==status[1]['images']
        paths=[folder/(chapter+'.jsonl') for folder in [old_folder,new_folder]]
        proof=dict(before_output_sha256=digest(paths[0]),after_output_sha256=digest(paths[1]),
                   before_done_sha256=digest(done[0]),after_done_sha256=digest(done[1]),script_sha256=digest(SCRIPT_PATH))
        target=destination/(chapter+'.json')
        if target.exists() and read(target)['proof']==proof:
            summaries.append(read(target)['summary']);continue
        before,after=[records(p) for p in paths];pairs,removed,added=pair_same_geometry(before,after)
        fields=lambda r:{k:r.get(k) for k in ['source','translation','bounds','image','retained_original','sentence_recovered']}
        changed=[dict(before_index=i,after_index=j,before=fields(before[i]),after=fields(after[j]),meaning_reviewed=False)
                 for i,j in pairs if fields(before[i])!=fields(after[j])]
        summary=dict(chapter=chapter,regions_before=len(before),regions_after=len(after),exact_geometry_pairs=len(pairs),
                     changed_pairs=len(changed),unchanged_pairs=len(pairs)-len(changed),
                     unmatched_old_regions=len(removed),unmatched_new_regions=len(added),
                     before_alert_regions=sum(bool(signals(r)) for r in before),after_alert_regions=sum(bool(signals(r)) for r in after),
                     meaning_reviewed=False)
        value=dict(proof=proof,summary=summary,changed_pairs=changed,
                   unmatched_old=[dict(index=i,row=fields(before[i])) for i in removed],
                   unmatched_new=[dict(index=i,row=fields(after[i])) for i in added],
                   geometry_mismatch_is_not_a_confirmed_omission=True,unchanged_output_is_not_automatically_approved=True,
                   all_chapter_words_visually_reviewed=False,semantic_accuracy=None)
        atomic(target,json.dumps(value,ensure_ascii=False,indent=2));summaries.append(summary)
    totals={key:sum(s[key] for s in summaries) for key in ['regions_before','regions_after','exact_geometry_pairs','changed_pairs',
            'unchanged_pairs','unmatched_old_regions','unmatched_new_regions','before_alert_regions','after_alert_regions']}
    result=dict(chapters_expected=124,matched_complete_chapters=len(summaries),**totals,
                relative_alert_reduction_percent=reduction(totals['before_alert_regions'],totals['after_alert_regions']),
                alerts_are_not_confirmed_errors=True,all_changes_in_exact_geometry_pairs_listed=True,
                every_unmatched_row_preserved=True,all_chapter_words_visually_reviewed=False,
                semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False,
                after_report_directory=source_name,derived_after_reports=source_name.startswith('postprocessed-'))
    atomic(destination/'summary.json',json.dumps(result,indent=2))
    return result


SCRIPT_PATH=pathlib.Path(__file__)

if __name__=='__main__':print(json.dumps(publish()),flush=True)
