"""A single preregistered adapter trial regularized against its frozen base."""
import json
import random
import shutil
import time
import torch
import torch.nn.functional as F
from peft import LoraConfig,TaskType,get_peft_model
from transformers import MarianMTModel,MarianTokenizer
from sacrebleu.metrics import CHRF
import finetune8032_guards as g
from train_opus_lora8031 import read,sha,write,batch,generate,base_hash
from quality_resources import wait_for_inference_memory

ROOT=g.ROOT;META=ROOT/'benchmarks/finetune8033';OUT=ROOT/'build/finetune8033'


def token_kl(student_logits,teacher_logits,labels):
    mask=labels.ne(-100)
    assert mask.any()
    student=F.log_softmax(student_logits[mask].float(),dim=-1)
    teacher=F.log_softmax(teacher_logits[mask].detach().float(),dim=-1)
    return F.kl_div(student,teacher,reduction='sum',log_target=True)/mask.sum()


def main():
    protocol=read(META/'protocol.json');data=read(g.META/'dataset.json');assert sha(g.META/'dataset.json')==protocol['dataset_sha256']
    OUT.mkdir(exist_ok=True);folder=OUT/'lora-pilot';assert not folder.exists();folder.mkdir()
    wait_for_inference_memory();assert shutil.disk_usage(OUT).free>4*1024**3
    torch.set_num_threads(2);random.seed(protocol['seed']);torch.manual_seed(protocol['seed']);torch.cuda.manual_seed_all(protocol['seed'])
    torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True)
    training,validation=g.validate_dataset(data,tokenizer)
    proof=dict(protocol_sha256=sha(META/'protocol.json'),dataset_sha256=sha(g.META/'dataset.json'),
        execution_script_sha256=sha(__file__),shared_helpers_sha256=sha(ROOT/'tools/train_opus_lora8031.py'),
        validation_guards_sha256=sha(ROOT/'tools/finetune8032_guards.py'),base_provenance_sha256=sha(g.OLD_OUT/'base-model-provenance.json'),
        training_ids=[r['id'] for r in training],validation_ids=[r['id'] for r in validation],
        teacher_input_ids_are_training_only=True,test_sources_or_targets_loaded_for_training=False,application_modified=False)
    write(folder/'run-input-proof.json',proof)
    base=MarianMTModel.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=get_peft_model(base,LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM,r=protocol['rank'],lora_alpha=protocol['alpha'],
        lora_dropout=protocol['dropout'],target_modules=protocol['target_modules'],bias='none')).to('cuda')
    frozen_before=base_hash(model)
    baseline=generate(model,tokenizer,validation,disabled=True)
    assert baseline==read(g.OUT/'lora-pilot/baseline-validation.json');write(folder/'baseline-validation.json',baseline)
    model.config.use_cache=False
    # eval() disables stochastic dropout; it does not disable autograd.
    # Equal teacher/student distributions at initialization are an explicit guard.
    model.eval();trainable=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(trainable,lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'])
    order=[];cursor=0;logs=[];started=time.monotonic();initial_kl=None
    for step in range(protocol['optimizer_steps']):
        optimizer.zero_grad(set_to_none=True);ce_total=0;kl_total=0;sample_ids=[]
        for micro in range(protocol['gradient_accumulation_steps']):
            selected=[]
            while len(selected)<protocol['micro_batch_size']:
                if cursor>=len(order):order=list(range(len(training)));random.shuffle(order);cursor=0
                selected.append(training[order[cursor]]);cursor+=1
            sample_ids.extend(r['id'] for r in selected);inputs=batch(tokenizer,selected,'cuda')
            with torch.no_grad(),model.disable_adapter(),torch.autocast('cuda',dtype=torch.bfloat16):
                teacher_logits=model(**inputs).logits.detach()
            with torch.autocast('cuda',dtype=torch.bfloat16):
                output=model(**inputs);ce=output.loss
            kl=token_kl(output.logits,teacher_logits,inputs['labels'])
            if initial_kl is None:
                initial_kl=float(kl.detach());assert abs(initial_kl)<1e-5,'Untrained adapter/base KL must be zero without dropout'
            loss=ce+protocol['kl_weight']*kl
            assert torch.isfinite(loss).item() and float(kl.detach())>=-1e-5
            ce_total+=float(ce.detach());kl_total+=float(kl.detach())
            (loss/protocol['gradient_accumulation_steps']).backward()
            del teacher_logits,output,ce,kl,loss
        norm=torch.nn.utils.clip_grad_norm_(trainable,1.0);assert torch.isfinite(norm).item()
        factor=min((step+1)/protocol['warmup_steps'],(protocol['optimizer_steps']-step)/(protocol['optimizer_steps']-protocol['warmup_steps']))
        for group in optimizer.param_groups:group['lr']=protocol['learning_rate']*factor
        optimizer.step();row=dict(step=step+1,cross_entropy=ce_total/protocol['gradient_accumulation_steps'],
            token_kl=kl_total/protocol['gradient_accumulation_steps'],training_sample_ids=sample_ids)
        logs.append(row)
        if (step+1)%10==0:print(json.dumps(dict(state='training',**{k:v for k,v in row.items() if k!='training_sample_ids'})),flush=True)
    frozen_after=base_hash(model);assert frozen_before==frozen_after
    model.config.use_cache=True;model.save_pretrained(folder/'adapter',safe_serialization=True)
    candidate=generate(model,tokenizer,validation);write(folder/'candidate-validation.json',candidate);write(folder/'training-log.json',logs)
    metric=CHRF(word_order=2);refs=[[r['target'] for r in validation]]
    result=dict(actual_weight_training_completed=True,optimizer_steps=len(logs),original_training_pairs=86,packed_training_examples=130,
        validation_pairs=14,initial_token_kl=initial_kl,kl_weight=protocol['kl_weight'],
        baseline_chrfpp=metric.corpus_score([r['translation'] for r in baseline],refs).score,
        candidate_chrfpp=metric.corpus_score([r['translation'] for r in candidate],refs).score,
        changed_validation_outputs=sum(a['translation']!=b['translation'] for a,b in zip(baseline,candidate)),
        frozen_base_sha256_before=frozen_before,frozen_base_sha256_after=frozen_after,adapter_sha256=sha(folder/'adapter/adapter_model.safetensors'),
        training_seconds=round(time.monotonic()-started,2),peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
        all_backpropagation_and_teacher_ids_are_training_only=all(set(r['training_sample_ids'])<=set(proof['training_ids']) for r in logs),
        application_weights_modified=False,manual_meanings_reviewed=False,automatic_metric_is_not_failure_probability=True,target_achieved=False,ready_for_application=False)
    write(folder/'summary.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
