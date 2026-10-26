"""Apply predeclared quality gates and report newly observed fatal output failures."""
import json
import pathlib
from prepare_finetune8031 import ROOT,sha,save

META=ROOT/'benchmarks/finetune8034';OUT=ROOT/'build/finetune8034/lora-pilot'
def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))


def assess(protocol,validation,core,audit):
    gates=protocol['gates'];new=validation['new'];known=validation['known']
    checks=dict(known_validation=known['confirmed_errors_after']<=gates['known_validation_confirmed_errors_maximum'],
        new_validation_net_corrections=new['complete_content_corrections']-new['new_confirmed_content_regressions']>=gates['new_validation_minimum_net_complete_corrections'],
        new_validation_no_regressions=new['new_confirmed_content_regressions']<=gates['new_validation_maximum_new_content_regressions'],
        old_core_no_regressions=core['new_confirmed_complete_region_regressions']<=gates['old_core_maximum_new_content_regressions'],
        old_core_no_additional_partial_losses=core['additional_partial_meaning_losses']<=gates['old_core_maximum_additional_partial_meaning_losses'],
        old_core_no_new_source_artifacts=core['new_rendered_source_artifacts']<=gates['old_core_maximum_new_source_artifacts'])
    collapsed=[r for r in audit['alerts'] if r['model']=='candidate' and 'no_alphabetic_content_for_alphabetic_source' in r['issues']]
    return dict(predeclared_checks=checks,all_predeclared_quality_gates_passed=all(checks.values()),
        observed_candidate_collapse_count=len(collapsed),collapse_is_an_additional_observed_blocker_not_a_lowered_threshold=True,
        ready_for_native_parity=all(checks.values()) and not collapsed,ready_for_installation=False,
        production_end_to_end_checks_completed=False,app_failure_probability=None,target_achieved=False)


def main():
    result=assess(read(META/'training-protocol.json'),read(META/'validation-meaning-decisions.json'),
        read(META/'regression-core-meaning-decisions.json'),read(OUT/'generation-format-audit.json'))
    result.update(execution_script_sha256=sha(__file__),protocol_sha256=sha(META/'training-protocol.json'),
        evidence_sha256={name:sha(META/name) for name in ['validation-meaning-decisions.json','regression-core-meaning-decisions.json','known-test-meaning-decisions.json','early-known-test-meaning-decisions.json']},
        audit_sha256=sha(OUT/'generation-format-audit.json'),new_blind_test_chapters_opened=0,application_modified=False)
    save(META/'quality-gates.json',result)
    print(json.dumps(dict(quality_passed=result['all_predeclared_quality_gates_passed'],failed_gates=[k for k,v in result['predeclared_checks'].items() if not v],
        observed_generation_collapses=result['observed_candidate_collapse_count'],promoted=False)),flush=True)


if __name__=='__main__':main()
