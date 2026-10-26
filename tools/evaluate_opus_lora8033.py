"""Compare the regularized adapter on known controls, without training on them."""
import json
import torch
from peft import PeftModel
from transformers import MarianMTModel,MarianTokenizer
import finetune8032_guards as g
from train_opus_lora8031 import generate,prepare_source,write
from train_opus_lora8033 import META,OUT
from quality_resources import wait_for_inference_memory


def main():
    folder=OUT/'lora-pilot';summary=g.read(folder/'summary.json');proof=g.read(folder/'run-input-proof.json')
    assert proof['dataset_sha256']==g.sha(g.META/'dataset.json')
    assert proof['protocol_sha256']==g.sha(META/'protocol.json')
    assert proof['execution_script_sha256']==g.sha(g.ROOT/'tools/train_opus_lora8033.py')
    assert proof['validation_guards_sha256']==g.sha(g.ROOT/'tools/finetune8032_guards.py')
    assert g.sha(folder/'adapter/adapter_model.safetensors')==summary['adapter_sha256']
    assert summary['frozen_base_sha256_before']==summary['frozen_base_sha256_after']
    wait_for_inference_memory(minimum_free_bytes=3*1024**3);torch.set_num_threads(2);torch.manual_seed(8032);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True)
    _,validation=g.validate_dataset(g.read(g.META/'dataset.json'),tokenizer)
    base=MarianMTModel.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=PeftModel.from_pretrained(base,folder/'adapter',is_trainable=False,local_files_only=True).to('cuda')
    assert generate(model,tokenizer,validation,disabled=True)==g.read(folder/'baseline-validation.json')
    assert generate(model,tokenizer,validation)==g.read(folder/'candidate-validation.json')
    print(json.dumps(dict(state='reload_verified',pairs=14)),flush=True)
    for prefix in ['regression-core','fresh-test']:
        old=g.OUT/'lora-pilot';previous=g.read(old/(prefix+'-summary.json'))
        assert previous['baseline_sha256']==g.sha(old/(prefix+'-baseline.json'))
        baseline=g.read(old/(prefix+'-baseline.json'));old_candidate=g.read(old/(prefix+'-candidate.json'))
        prepared=[dict(id=r['id'],source=r['source'],prepared_source=prepare_source(r['source'])) for r in baseline]
        manifest=folder/(prefix+'-input.jsonl');assert not manifest.exists()
        manifest.write_text(''.join(json.dumps(r)+'\n' for r in prepared),encoding='utf-8')
        candidate=generate(model,tokenizer,prepared)
        write(folder/(prefix+'-baseline.json'),baseline);write(folder/(prefix+'-candidate.json'),candidate)
        changes=[dict(input=r,baseline=a['translation'],candidate=b['translation'],meaning_reviewed=False)
                 for r,a,b in zip(prepared,baseline,candidate) if a['translation']!=b['translation']]
        relative=[dict(id=r['id'],source=r['source'],baseline=a['translation'],previous=p['translation'],candidate=b['translation'])
                  for r,a,p,b in zip(prepared,baseline,old_candidate,candidate) if p['translation']!=b['translation']]
        write(folder/(prefix+'-changes.json'),changes);write(folder/(prefix+'-vs8032.json'),relative)
        result=dict(adapter_reload_exact_output_parity=True,regions=len(prepared),changed_regions=len(changes),changed_from_previous_candidate=len(relative),
            runtime_errors=0,source_only_generation=True,previous_baseline_reused_after_exact_validation_parity=True,
            baseline_provenance_sha256=g.sha(old/(prefix+'-summary.json')),manifest_sha256=g.sha(manifest),
            baseline_sha256=g.sha(folder/(prefix+'-baseline.json')),candidate_sha256=g.sha(folder/(prefix+'-candidate.json')),
            adapter_sha256=summary['adapter_sha256'],evaluation_script_sha256=g.sha(__file__),
            test_already_inspected_not_blind=True if prefix=='fresh-test' else None,
            no_evaluation_sources_or_targets_used_for_training=True,production_clause_rules_applied=False,
            production_app_error_rate_comparable=False,application_weights_modified=False,screen_attempt_failure_probability=None,target_achieved=False)
        write(folder/(prefix+'-summary.json'),result);print(json.dumps(dict(state='evaluated',scope=prefix,regions=len(prepared),changed_regions=len(changes),changed_from_previous_candidate=len(relative))),flush=True)


if __name__=='__main__':main()
