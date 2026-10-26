"""Source-only evaluation of the frozen second adapter, with exact reload parity."""
import argparse
import json
import pathlib
import torch
from peft import PeftModel
from transformers import MarianMTModel,MarianTokenizer
import finetune8032_guards as g
from train_opus_lora8031 import generate,prepare_source,write
from quality_resources import wait_for_inference_memory


def main(mode):
    summary=g.validate_checkpoint();folder=g.OUT/'lora-pilot';data=g.read(g.META/'dataset.json')
    wait_for_inference_memory(minimum_free_bytes=3*1024**3)
    torch.set_num_threads(2);torch.manual_seed(8032);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True)
    _,validation=g.validate_dataset(data,tokenizer)
    base=MarianMTModel.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=PeftModel.from_pretrained(base,folder/'adapter',is_trainable=False,local_files_only=True).to('cuda')
    assert generate(model,tokenizer,validation,disabled=True)==g.read(folder/'baseline-validation.json')
    assert generate(model,tokenizer,validation)==g.read(folder/'candidate-validation.json')
    print(json.dumps(dict(state='reload_verified',pairs=len(validation))),flush=True)
    if mode=='regression':
        old=g.OLD_OUT/'lora-pilot';inputs=[json.loads(s) for s in (old/'regression-core-input.jsonl').read_text(encoding='utf-8').splitlines()]
        old_summary=g.read(old/'regression-core-summary.json')
        assert old_summary['manifest_sha256']==g.sha(old/'regression-core-input.jsonl')
        assert old_summary['baseline_sha256']==g.sha(old/'regression-core-baseline.json')
        baseline=g.read(old/'regression-core-baseline.json')
        assert [r['source'] for r in baseline]==[r['source'] for r in inputs]
        prefix='regression-core'
    else:
        approved=g.read(g.META/'fresh-test-labels.json');protocol=g.read(g.META/'fresh-test-protocol.json')
        assert approved['adapter_sha256_frozen_before_review']==summary['adapter_sha256']
        assert approved['test_protocol_sha256']==g.sha(g.META/'fresh-test-protocol.json')
        assert approved['all_selected_proposals_reviewed'] and not approved['model_answers_used_for_annotation']
        assert not approved['training_allowed']
        inputs=[dict(id=r['id'],source=r['source']) for r in approved['entries']]
        assert all(r['chapter'] in protocol['selected_chapters'] and r['split']=='test' for r in approved['entries'])
        baseline=None;prefix='fresh-test'
    prepared=[dict(id=r['id'],source=r['source'],prepared_source=prepare_source(r['source'])) for r in inputs]
    contents=''.join(json.dumps(r)+'\n' for r in prepared);manifest=folder/(prefix+'-input.jsonl')
    assert not manifest.exists(),'Do not overwrite an executed evaluation'
    manifest.write_text(contents,encoding='utf-8')
    if baseline is None:baseline=generate(model,tokenizer,prepared,disabled=True)
    candidate=generate(model,tokenizer,prepared)
    write(folder/(prefix+'-baseline.json'),baseline);write(folder/(prefix+'-candidate.json'),candidate)
    changes=[dict(input=r,baseline=a['translation'],candidate=b['translation'],meaning_reviewed=False)
             for r,a,b in zip(inputs,baseline,candidate) if a['translation']!=b['translation']]
    write(folder/(prefix+'-changes.json'),changes)
    result=dict(adapter_reload_exact_output_parity=True,validation_pairs_reloaded=14,regions=len(inputs),changed_regions=len(changes),runtime_errors=0,
        source_only_generation=True,adapter_sha256=summary['adapter_sha256'],manifest_sha256=g.sha(manifest),
        baseline_sha256=g.sha(folder/(prefix+'-baseline.json')),candidate_sha256=g.sha(folder/(prefix+'-candidate.json')),
        execution_script_sha256=g.sha(__file__),shared_helpers_sha256=g.sha(g.ROOT/'tools/train_opus_lora8031.py'),
        production_clause_rules_applied=False,production_ocr_or_capture_repeated=False,production_app_error_rate_comparable=False,
        application_weights_modified=False,screen_attempt_failure_probability=None,target_achieved=False,meanings_reviewed=False)
    if mode=='regression':result.update(saved_views=len({r['image'] for r in inputs}),baseline_reused_after_exact_validation_parity=True,
        baseline_provenance_sha256=g.sha(g.OLD_OUT/'lora-pilot/regression-core-summary.json'))
    else:result.update(labels_sha256=g.sha(g.META/'fresh-test-labels.json'),test_protocol_sha256=g.sha(g.META/'fresh-test-protocol.json'))
    write(folder/(prefix+'-summary.json'),result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['regression','fresh']);main(parser.parse_args().mode)
