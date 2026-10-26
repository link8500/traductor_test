"""Flag unmistakable output collapse; alerts never certify semantic correctness."""
import itertools
import json
import pathlib
from prepare_finetune8031 import ROOT,sha,save

OUT=ROOT/'build/finetune8034/lora-pilot'


def issues(source,target):
    result=[]
    if sum(c.isalpha() for c in source)>=4 and not any(c.isalpha() for c in target):result.append('no_alphabetic_content_for_alphabetic_source')
    longest=max((len(list(g)) for _,g in itertools.groupby(target)),default=0)
    if longest>=32:result.append('same_character_run_at_least32')
    return result


def main():
    rows=[];counts={}
    for scope in ['validation','regression-core','known-test','early-known-test']:
        for model in ['baseline','candidate']:
            p=OUT/(model+'-validation.json') if scope=='validation' else OUT/(scope+'-'+model+'.json')
            values=json.loads(p.read_text(encoding='utf-8'));counts[scope+'-'+model]=len(values)
            for r in values:
                flags=issues(r['source'],r['translation'])
                if flags:rows.append(dict(scope=scope,model=model,id=r['id'],issues=flags,output_characters=len(r['translation']),output_sha256=__import__('hashlib').sha256(r['translation'].encode()).hexdigest()))
    save(OUT/'generation-format-audit.json',dict(counts=counts,alerts=rows,execution_script_sha256=sha(__file__),all_outputs_scanned=True,
        automatic_alerts_are_not_semantic_approval=True,app_use_failure_probability=None,application_modified=False))
    print(json.dumps(dict(outputs_scanned=sum(counts.values()),alerts=len(rows),candidate_alerts=sum(r['model']=='candidate' for r in rows))),flush=True)


if __name__=='__main__':main()
