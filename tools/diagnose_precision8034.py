"""Reproduce a failed batch and compare FP32 without changing official results."""
import json
import torch
from peft import PeftModel
from transformers import MarianMTModel,MarianTokenizer
from finetune8034_data import ROOT,META,OUT,BASE,read,write,sha
from evaluate_opus_lora8034 import checkpoint
from quality_resources import wait_for_inference_memory


def main():
    folder,summary=checkpoint();rows=read(folder/'early-known-test-candidate.json')[4:8]
    assert [r['id'] for r in rows]==[57,60,63,64]
    wait_for_inference_memory(minimum_free_bytes=3*1024**3);torch.set_num_threads(2);torch.manual_seed(8032)
    torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(BASE/'base-model',local_files_only=True)
    model=PeftModel.from_pretrained(MarianMTModel.from_pretrained(BASE/'base-model',local_files_only=True,torch_dtype=torch.float32),
        folder/'adapter',is_trainable=False,local_files_only=True).to('cuda').eval()
    inputs=tokenizer([r['prepared_source'] for r in rows],padding=True,return_tensors='pt').to('cuda');results={}
    for name,dtype in [('original_bfloat16',torch.bfloat16),('diagnostic_float32',None)]:
        with torch.inference_mode(),torch.autocast('cuda',dtype=dtype or torch.bfloat16,enabled=dtype is not None):
            ids=model.generate(**inputs,num_beams=4,max_new_tokens=160,do_sample=False,early_stopping=True,renormalize_logits=True,use_cache=True)
        decoded=tokenizer.batch_decode(ids,skip_special_tokens=True)
        results[name]=[dict(id=r['id'],source=r['source'],translation=t) for r,t in zip(rows,decoded)]
    exact=all(a['translation']==b['translation'] for a,b in zip(rows,results['original_bfloat16']))
    result=dict(adapter_sha256=summary['adapter_sha256'],same_original_batch_composition=True,bfloat16_exact_reproduction=exact,
        outputs=results,diagnostic_only=True,official_benchmark_outputs_unchanged=True,gold_targets_used=False,
        no_model_weights_modified=True,execution_script_sha256=sha(__file__))
    p=folder/'precision-diagnostic.json';assert not p.exists();write(p,result)
    print(json.dumps(dict(bfloat16_exact_reproduction=exact,
        bf16_failure_has_letters=any(c.isalpha() for c in results['original_bfloat16'][2]['translation']),
        fp32_failure_has_letters=any(c.isalpha() for c in results['diagnostic_float32'][2]['translation']),official_results_replaced=False)),flush=True)


if __name__=='__main__':main()
