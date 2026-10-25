"""Reuse finished reports only after exact original-reader input equivalence.

Preserve original marker bytes. No report text, pixels or native MT is changed.
"""
import json
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    folder=QA/'postprocessed-en8029-refinement';compat=QA/'refinement8029/input-equivalence';compat.mkdir(exist_ok=True)
    program=ROOT/'tools/postprocess_full_refinement8029.py'
    policy=QA/'refinement8029/ocr-policy.exe';tokenizer=QA/'frozen-windows802901/data/flutter_assets/assets/models/opus-en-es/tokenizer.json'
    pending=[]
    for path in sorted(folder.glob('*.done.json')):
        value=read(path);proof=value['refinement_derivation_proof']
        if proof.get('selection_base')=='original_recorded_before_consensus':continue
        parent=QA/'postprocessed-en8028-openings'/path.name.replace('.done.json','.jsonl')
        target=path.with_name(path.name.replace('.done.json','.jsonl'))
        assert digest(parent)==proof['parent_report_sha256'] and digest(target)==value['derived_report_sha256']
        assert digest(policy)==proof['ocr_policy_sha256'] and digest(tokenizer)==proof['vocabulary_sha256']
        before,after=records(parent),records(target)
        inputs=''.join(json.dumps(dict(id=i+1,base=r.get('before_consensus',r['source']),first=r.get('first_reader',''),second=r.get('second_reader','')))+'\n' for i,r in enumerate(before))
        actual=subprocess.run([str(policy),str(tokenizer)],input=inputs,text=True,encoding='utf-8',capture_output=True,
                              check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        selected=[json.loads(line) for line in actual.stdout.splitlines() if line.strip()]
        assert len(selected)==len(before)==len(after)
        assert [r['selected'] for r in selected]==[r['source'] for r in after], 'New original-reader selection differs; preserve the old result for separate review'
        old=path.read_text(encoding='utf-8')
        import hashlib
        evidence=dict(previous_marker_sha256=digest(path),parent_report_sha256=digest(parent),output_sha256=digest(target),
                      policy_sha256=digest(policy),vocabulary_sha256=digest(tokenizer),
                      original_input_sha256=hashlib.sha256(inputs.encode()).hexdigest(),
                      original_selection_output_sha256=hashlib.sha256(actual.stdout.encode()).hexdigest(),
                      source_proposals_identical_for_all_rows=True,rows=len(after),new_model_inferences=0,
                      translation_bytes_changed=False,migration_script_sha256=digest(ROOT/'tools/migrate_refinement8029_input_proof.py'))
        pending.append((path,value,old,evidence))
    # Commit only after all existing reports have passed the equivalence check.
    for path,value,old,evidence in pending:
        saved=compat/path.name.replace('.done.json','.prior-marker.json')
        if saved.exists():assert saved.read_text(encoding='utf-8')==old
        else:atomic(saved,old)
        proof_path=compat/path.name.replace('.done.json','.equivalence.json');atomic(proof_path,json.dumps(evidence,indent=2))
        value['previous_selection_marker_sha256']=evidence['previous_marker_sha256']
        value['original_reader_input_equivalence_sha256']=digest(proof_path)
        value['refinement_derivation_proof'].update(selection_base='original_recorded_before_consensus',execution_script_sha256=digest(program))
        atomic(path,json.dumps(value,indent=2))
    print(json.dumps(dict(reports_reused_after_exact_input_equivalence=len(pending),new_model_inferences=0,original_reports_preserved=True)),flush=True)


if __name__=='__main__':main()
