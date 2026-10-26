"""Evaluate the frozen expanded-data adapter only on source text of known controls."""
import json
import torch
from peft import PeftModel
from transformers import MarianMTModel,MarianTokenizer
from train_opus_lora8031 import OUT as BASE,generate,prepare_source,read,sha,write
from finetune8034_data import ROOT,META,OUT,validate_dataset
from train_opus_lora8034 import source_only
from quality_resources import wait_for_inference_memory


def checkpoint():
    folder=OUT/'lora-pilot';proof=read(folder/'run-input-proof.json');summary=read(folder/'summary.json')
    assert proof['dataset_sha256']==sha(META/'dataset.json')
    assert proof['protocol_sha256']==sha(META/'training-protocol.json')
    assert proof['execution_script_sha256']==sha(ROOT/'tools/train_opus_lora8034.py')
    assert proof['dataset_builder_sha256']==sha(ROOT/'tools/finetune8034_data.py')
    assert proof['regularizer_helper_sha256']==sha(ROOT/'tools/train_opus_lora8033.py')
    assert sha(folder/'adapter/adapter_model.safetensors')==summary['adapter_sha256']
    assert summary['frozen_base_sha256_before']==summary['frozen_base_sha256_after']
    return folder,summary


def main():
    folder,summary=checkpoint();wait_for_inference_memory(minimum_free_bytes=3*1024**3)
    torch.set_num_threads(2);torch.manual_seed(8032);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(BASE/'base-model',local_files_only=True)
    _,validation=validate_dataset(read(META/'dataset.json'),tokenizer)
    base=MarianMTModel.from_pretrained(BASE/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=PeftModel.from_pretrained(base,folder/'adapter',is_trainable=False,local_files_only=True).to('cuda')
    assert generate(model,tokenizer,source_only(validation),disabled=True)==read(folder/'baseline-validation.json')
    assert generate(model,tokenizer,source_only(validation))==read(folder/'candidate-validation.json')
    print(json.dumps(dict(state='reload_verified',validation_pairs=len(validation))),flush=True)
    cached=ROOT/'build/finetune8033/lora-pilot'
    for name in ['regression-core','known-test','early-known-test']:
        if name=='early-known-test':
            path=BASE/'lora-pilot/baseline-heldout.json';baseline=read(path)['test']
            frozen=read(ROOT/'benchmarks/finetune8031/pilot-review.json')
            proof=next(r for r in frozen['evidence'] if r['path']=='build/finetune8031/lora-pilot/baseline-heldout.json')
            assert sha(path)==proof['sha256'];provenance=sha(path)
        else:
            prefix='regression-core' if name=='regression-core' else 'fresh-test'
            path=cached/(prefix+'-baseline.json');prior=read(cached/(prefix+'-summary.json'))
            assert sha(path)==prior['baseline_sha256'];baseline=read(path);provenance=sha(cached/(prefix+'-summary.json'))
        inputs=[dict(id=r['id'],source=r['source'],prepared_source=prepare_source(r['source'])) for r in baseline]
        p=folder/(name+'-input.jsonl');assert not p.exists();p.write_text(''.join(json.dumps(r)+'\n' for r in inputs),encoding='utf-8')
        candidate=generate(model,tokenizer,inputs)
        write(folder/(name+'-baseline.json'),baseline);write(folder/(name+'-candidate.json'),candidate)
        changes=[dict(input=r,baseline=a['translation'],candidate=b['translation'],meaning_reviewed=False)
            for r,a,b in zip(inputs,baseline,candidate) if a['translation']!=b['translation']]
        write(folder/(name+'-changes.json'),changes)
        result=dict(adapter_reload_exact_output_parity=True,validation_pairs_reloaded=len(validation),regions=len(inputs),changed_regions=len(changes),
            baseline_reused_after_exact_validation_parity=True,baseline_provenance_sha256=provenance,
            source_only_generation=True,runtime_errors=0,adapter_sha256=summary['adapter_sha256'],execution_script_sha256=sha(__file__),
            manifest_sha256=sha(p),baseline_sha256=sha(folder/(name+'-baseline.json')),candidate_sha256=sha(folder/(name+'-candidate.json')),
            already_known_control_not_new_blind_test=True,evaluation_examples_used_for_gradients=False,
            production_ocr_or_capture_repeated=False,production_clause_rules_applied=False,app_failure_rate_comparable=False,
            application_weights_modified=False,target_achieved=False)
        write(folder/(name+'-summary.json'),result)
        print(json.dumps(dict(state='control_complete',name=name,regions=len(inputs),changed_regions=len(changes))),flush=True)


if __name__=='__main__':main()
