"""Verify adapter reload and compare the same core on preserved OCR sources.

These are floating-point model-core diagnostics, not a replay of production's
OCR repairs, terminology, clause recovery or screen interaction.
"""
import json
import pathlib
import torch
from peft import PeftModel
from transformers import MarianMTModel,MarianTokenizer
from train_opus_lora8031 import ROOT,OUT,META,read,sha,write,generate,prepare_source,validate_data
from quality_resources import wait_for_inference_memory


def main():
    folder=OUT/'lora-pilot';summary=read(folder/'summary.json');assert summary['actual_weight_training_completed']
    adapter=folder/'adapter';assert sha(adapter/'adapter_model.safetensors')==summary['trained_adapter_sha256']
    proof=read(folder/'run-input-proof.json');assert proof['dataset_sha256']==sha(META/'approved-pairs.json')
    raw=ROOT/'build/full-comics/windows8030-tail-translation-replay/fixed-output.jsonl'
    original=[json.loads(s) for s in raw.read_text(encoding='utf-8').splitlines() if s.strip()]
    inputs=[dict(id=i+1,image=r['image'],bounds=r['bounds'],source=r['source']) for i,r in enumerate(original)]
    manifest=folder/'regression-core-input.jsonl';contents=''.join(json.dumps(r)+'\n' for r in inputs)
    if manifest.exists():assert manifest.read_text(encoding='utf-8')==contents
    else:manifest.write_text(contents,encoding='utf-8')
    wait_for_inference_memory(minimum_free_bytes=3*1024**3);torch.set_num_threads(2)
    torch.manual_seed(8031);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(OUT/'base-model',local_files_only=True)
    base=MarianMTModel.from_pretrained(OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=PeftModel.from_pretrained(base,adapter,is_trainable=False,local_files_only=True).to('cuda')
    sets=validate_data(read(META/'protocol.json'),tokenizer)
    old_a=read(folder/'baseline-heldout.json');old_b=read(folder/'candidate-heldout.json')
    for s in ['validation','test']:
        assert generate(model,tokenizer,sets[s],disabled=True)==old_a[s],('Base reload mismatch',s)
        assert generate(model,tokenizer,sets[s])==old_b[s],('Adapter reload mismatch',s)
    print(json.dumps(dict(state='adapter_reload_verified',heldout_pairs=27)),flush=True)
    prepared=[dict(r,prepared_source=prepare_source(r['source'])) for r in inputs]
    baseline=generate(model,tokenizer,prepared,disabled=True);candidate=generate(model,tokenizer,prepared)
    write(folder/'regression-core-baseline.json',baseline);write(folder/'regression-core-candidate.json',candidate)
    changes=[dict(input=r,baseline=a['translation'],candidate=b['translation'],meaning_reviewed=False)
             for r,a,b in zip(inputs,baseline,candidate) if a['translation']!=b['translation']]
    write(folder/'regression-core-changes.json',changes)
    value=dict(adapter_reload_exact_output_parity=True,heldout_pairs_verified=27,regression_regions=len(inputs),
        regression_saved_views=len({r['image'] for r in inputs}),changed_regions=len(changes),runtime_errors=0,
        original_ocr_report_sha256=sha(raw),manifest_sha256=sha(manifest),source_only_generation=True,
        adapter_sha256=sha(adapter/'adapter_model.safetensors'),baseline_sha256=sha(folder/'regression-core-baseline.json'),
        candidate_sha256=sha(folder/'regression-core-candidate.json'),execution_script_sha256=sha(__file__),
        production_clause_rules_applied=False,production_ocr_or_capture_repeated=False,
        production_app_error_rate_comparable=False,all_changed_meanings_reviewed=False,
        application_weights_modified=False,screen_attempt_failure_probability=None,target_achieved=False)
    write(folder/'regression-core-summary.json',value);print(json.dumps(value),flush=True)


if __name__=='__main__':main()
