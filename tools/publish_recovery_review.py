"""Validate and publish manually inspected production recovery decisions."""
import json
from audit_corpus_quality import QA, ROOT, read, digest, atomic, CLEAR_ERRORS, reduction


def main():
    folder=QA/'recovery-viewports801201/evaluation'
    decisions=folder/'manual-decisions.json'
    entries=[]
    for viewport,region,before,after,note in read(decisions):
        path=folder/f'{viewport:03d}.json';report=read(path)
        case=next(v for v in report['cases'] if v['region_index']==region)
        assert len(case['control_regions'])==1
        entries.append(dict(viewport_id=viewport,region_index=region,before=before,after=after,note_es=note,
            evaluation_report_sha256=digest(path),source_pixels_inspected=True,reference_pixels_inspected=True,
            reference_correspondence_verified=viewport not in [65,74,89,108] or (viewport==65 and region==1),
            all_balloon_words_approved=False))
    keys=[(e['viewport_id'],e['region_index']) for e in entries]
    assert len(keys)==len(set(keys))
    reports=[read(p) for p in folder.glob('[0-9][0-9][0-9].json')]
    expected={(r['viewport_id'],c['region_index']) for r in reports for c in r['cases']}
    old=sum(e['before'] in CLEAR_ERRORS for e in entries);new=sum(e['after'] in CLEAR_ERRORS for e in entries)
    summary=dict(schema=1,build_snapshot='801201',reviewer='assistant',
        scope='Only recovered production paragraphs in a fixed 124 viewport regression set. No population or complete chapter accuracy claim.',
        reference_used_for_inference=False,all_chapter_words_reviewed=False,
        evaluated_viewports=len(reports),viewports_expected=124,recovered_regions=len(expected),
        reviewed_regions=len(entries),all_recoveries_reviewed=set(keys)==expected,
        before_clear_errors=old,after_clear_errors=new,relative_error_reduction_in_reviewed_recoveries_percent=reduction(old,new),
        corrected_regions=sum(e['before'] in CLEAR_ERRORS and e['after'] not in CLEAR_ERRORS for e in entries),
        regressed_regions=sum(e['before'] not in CLEAR_ERRORS and e['after'] in CLEAR_ERRORS for e in entries),
        decisions_sha256=digest(decisions),entries=entries)
    atomic(ROOT/'benchmarks/full-comics/windows8012-recovery-semantic-review.json',json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='entries'}))


if __name__=='__main__':main()
