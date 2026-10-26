"""Second actual adapter trial; validation-only, without reopening the known test."""
import collections
import json
import pathlib
import random
import shutil
import time
import torch
from peft import LoraConfig,TaskType,get_peft_model
from transformers import MarianMTModel,MarianTokenizer
from sacrebleu.metrics import CHRF
from train_opus_lora8031 import ROOT,OUT as OLD_OUT,read,sha,write,batch,generate,base_hash
from quality_resources import wait_for_inference_memory

OUT=ROOT/'build/finetune8032';META=ROOT/'benchmarks/finetune8032'


def main():
    protocol=read(META/'protocol.json');data=read(META/'dataset.json');assert torch.cuda.is_available()
    assert not data['test_rows_present'] and not data['validation_targets_used_in_training']
    assert data['proofs']['protocol_sha256']==sha(META/'protocol.json')
    folder=OUT/'lora-pilot';assert not folder.exists(),'Never overwrite a trained trial';folder.mkdir()
    wait_for_inference_memory();assert shutil.disk_usage(OUT).free>4*1024**3
    torch.set_num_threads(2);random.seed(8032);torch.manual_seed(8032);torch.cuda.manual_seed_all(8032);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(OLD_OUT/'base-model',local_files_only=True)
    training=data['original_training']+data['packed_training'];validation=data['validation']
    assert not {r['chapter'] for r in training}&{r['chapter'] for r in validation}
    write(folder/'run-input-proof.json',dict(dataset_sha256=sha(META/'dataset.json'),protocol_sha256=sha(META/'protocol.json'),
        execution_script_sha256=sha(__file__),shared_training_helpers_sha256=sha(ROOT/'tools/train_opus_lora8031.py'),
        base_provenance_sha256=sha(OLD_OUT/'base-model-provenance.json'),train_ids=[r['id'] for r in training],
        validation_ids=[r['id'] for r in validation],test_answers_loaded=False,application_modified=False))
    base=MarianMTModel.from_pretrained(OLD_OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=get_peft_model(base,LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM,r=4,lora_alpha=8,lora_dropout=.05,target_modules=['q_proj','v_proj'],bias='none')).to('cuda')
    frozen_before=base_hash(model);baseline=generate(model,tokenizer,validation,disabled=True)
    assert baseline==read(OLD_OUT/'lora-pilot/baseline-heldout.json')['validation'],'Untrained base must reproduce the frozen validation control'
    write(folder/'baseline-validation.json',baseline)
    model.config.use_cache=False;model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads()
    trainable=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(trainable,lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'])
    order=[];cursor=0;logs=[];started=time.monotonic();model.train()
    for step in range(protocol['optimizer_steps']):
        optimizer.zero_grad(set_to_none=True);total=0;sample_ids=[]
        for micro in range(protocol['gradient_accumulation_steps']):
            selected=[]
            while len(selected)<protocol['micro_batch_size']:
                if cursor>=len(order):order=list(range(len(training)));random.shuffle(order);cursor=0
                selected.append(training[order[cursor]]);cursor+=1
            sample_ids.extend(r['id'] for r in selected)
            with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch(tokenizer,selected,'cuda')).loss
            assert torch.isfinite(loss).item();total+=loss.detach().item();(loss/protocol['gradient_accumulation_steps']).backward()
        norm=torch.nn.utils.clip_grad_norm_(trainable,1.0);assert torch.isfinite(norm).item()
        factor=min((step+1)/protocol['warmup_steps'],(protocol['optimizer_steps']-step)/(protocol['optimizer_steps']-protocol['warmup_steps']))
        for g in optimizer.param_groups:g['lr']=protocol['learning_rate']*factor
        optimizer.step();row=dict(step=step+1,training_loss=total/protocol['gradient_accumulation_steps'],training_sample_ids=sample_ids)
        logs.append(row)
        if (step+1)%5==0:print(json.dumps(dict(state='training',step=step+1,loss=row['training_loss'])),flush=True)
    frozen_after=base_hash(model);assert frozen_before==frozen_after
    model.gradient_checkpointing_disable();model.config.use_cache=True;model.save_pretrained(folder/'adapter',safe_serialization=True)
    candidate=generate(model,tokenizer,validation);write(folder/'candidate-validation.json',candidate);write(folder/'training-log.json',logs)
    refs=[[r['target'] for r in validation]];metric=CHRF(word_order=2)
    value=dict(actual_weight_training_completed=True,optimizer_steps=len(logs),training_examples=len(training),verified_original_training_pairs=86,
        packed_training_examples=len(data['packed_training']),validation_pairs=14,test_evaluation_performed=False,
        changed_validation_outputs=sum(a['translation']!=b['translation'] for a,b in zip(baseline,candidate)),
        baseline_chrfpp=metric.corpus_score([r['translation'] for r in baseline],refs).score,
        candidate_chrfpp=metric.corpus_score([r['translation'] for r in candidate],refs).score,
        automatic_metric_is_not_semantic_accuracy=True,frozen_base_sha256_before=frozen_before,frozen_base_sha256_after=frozen_after,
        adapter_sha256=sha(folder/'adapter/adapter_model.safetensors'),training_seconds=round(time.monotonic()-started,2),
        peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),all_backpropagation_ids_are_training_only=all(set(r['training_sample_ids'])<=set(x['id'] for x in training) for r in logs),
        manual_validation_meanings_reviewed=False,application_weights_modified=False,target_achieved=False,ready_for_application=False)
    write(folder/'summary.json',value);print(json.dumps(value),flush=True)


if __name__=='__main__':main()
