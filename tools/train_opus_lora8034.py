"""Train one preregistered expanded-data adapter with no evaluation gradients."""
import json
import random
import shutil
import time
import torch
from peft import LoraConfig,TaskType,get_peft_model
from transformers import MarianMTModel,MarianTokenizer
from sacrebleu.metrics import CHRF
from train_opus_lora8031 import read,sha,write,batch,generate,base_hash,OUT as BASE
from train_opus_lora8033 import token_kl
from finetune8034_data import ROOT,META,OUT,validate_dataset
from quality_resources import wait_for_inference_memory


def source_only(rows):return [dict(id=r['id'],source=r['source'],prepared_source=r['prepared_source']) for r in rows]


def main():
    protocol=read(META/'training-protocol.json');data=read(META/'dataset.json')
    wait_for_inference_memory();assert shutil.disk_usage(OUT).free>4*1024**3
    folder=OUT/'lora-pilot';assert not folder.exists();folder.mkdir()
    torch.set_num_threads(2);random.seed(protocol['seed']);torch.manual_seed(protocol['seed']);torch.cuda.manual_seed_all(protocol['seed']);torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer=MarianTokenizer.from_pretrained(BASE/'base-model',local_files_only=True)
    training,validation=validate_dataset(data,tokenizer);steps=data['optimizer_steps']
    proof=dict(dataset_sha256=sha(META/'dataset.json'),protocol_sha256=sha(META/'training-protocol.json'),execution_script_sha256=sha(__file__),
        dataset_builder_sha256=sha(ROOT/'tools/finetune8034_data.py'),shared_helpers_sha256=sha(ROOT/'tools/train_opus_lora8031.py'),
        regularizer_helper_sha256=sha(ROOT/'tools/train_opus_lora8033.py'),base_provenance_sha256=sha(BASE/'base-model-provenance.json'),
        training_ids=[r['id'] for r in training],validation_ids=[r['id'] for r in validation],teacher_input_ids_are_training_only=True,
        evaluation_sources_and_targets_used_for_gradients=False,new_blind_test_chapters_opened=0,application_modified=False)
    write(folder/'run-input-proof.json',proof)
    base=MarianMTModel.from_pretrained(BASE/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=get_peft_model(base,LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM,r=protocol['rank'],lora_alpha=protocol['alpha'],lora_dropout=protocol['dropout'],
        target_modules=protocol['target_modules'],bias='none')).to('cuda')
    frozen_before=base_hash(model)
    baseline=generate(model,tokenizer,source_only(validation),disabled=True)
    assert [r for r in baseline if r['id']<200000]==read(ROOT/'build/finetune8033/lora-pilot/baseline-validation.json')
    write(folder/'baseline-validation.json',baseline)
    (folder/'validation-source-only-input.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in source_only(validation)),encoding='utf-8')
    model.config.use_cache=False;model.eval();trainable=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(trainable,lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'])
    order=[];cursor=0;logs=[];started=time.monotonic();initial_kl=None
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True);ce_sum=0;kl_sum=0;ids=[]
        for micro in range(protocol['gradient_accumulation_steps']):
            selected=[]
            while len(selected)<protocol['micro_batch_size']:
                if cursor>=len(order):order=list(range(len(training)));random.shuffle(order);cursor=0
                selected.append(training[order[cursor]]);cursor+=1
            ids.extend(r['id'] for r in selected);inputs=batch(tokenizer,selected,'cuda')
            with torch.no_grad(),model.disable_adapter(),torch.autocast('cuda',dtype=torch.bfloat16):teacher=model(**inputs).logits.detach()
            with torch.autocast('cuda',dtype=torch.bfloat16):output=model(**inputs);ce=output.loss
            kl=token_kl(output.logits,teacher,inputs['labels'])
            if initial_kl is None:initial_kl=float(kl.detach());assert abs(initial_kl)<1e-5
            loss=ce+protocol['kl_weight']*kl;assert torch.isfinite(loss).item() and float(kl.detach())>=-1e-5
            ce_sum+=float(ce.detach());kl_sum+=float(kl.detach());(loss/protocol['gradient_accumulation_steps']).backward()
            del teacher,output,ce,kl,loss
        norm=torch.nn.utils.clip_grad_norm_(trainable,1.0);assert torch.isfinite(norm).item()
        factor=min((step+1)/protocol['warmup_steps'],(steps-step)/(steps-protocol['warmup_steps']))
        for group in optimizer.param_groups:group['lr']=protocol['learning_rate']*factor
        optimizer.step();r=dict(step=step+1,cross_entropy=ce_sum/protocol['gradient_accumulation_steps'],token_kl=kl_sum/protocol['gradient_accumulation_steps'],training_sample_ids=ids);logs.append(r)
        if (step+1)%20==0:print(json.dumps(dict(state='training',step=step+1,total_steps=steps,cross_entropy=r['cross_entropy'],token_kl=r['token_kl'])),flush=True)
    frozen_after=base_hash(model);assert frozen_before==frozen_after
    model.config.use_cache=True;model.save_pretrained(folder/'adapter',safe_serialization=True)
    candidate=generate(model,tokenizer,source_only(validation));write(folder/'candidate-validation.json',candidate);write(folder/'training-log.json',logs)
    metric=CHRF(word_order=2);scores={}
    for group in ['known','new']:
        ids={r['id'] for r in validation if r['validation_group']==group};refs=[[r['target'] for r in validation if r['id'] in ids]]
        scores[group]=dict(pairs=len(ids),baseline_chrfpp=metric.corpus_score([r['translation'] for r in baseline if r['id'] in ids],refs).score,
            candidate_chrfpp=metric.corpus_score([r['translation'] for r in candidate if r['id'] in ids],refs).score)
    summary=dict(actual_weight_training_completed=True,optimizer_steps=steps,**data['counts'],initial_token_kl=initial_kl,validation_scores=scores,
        changed_validation_outputs=sum(a['translation']!=b['translation'] for a,b in zip(baseline,candidate)),
        adapter_sha256=sha(folder/'adapter/adapter_model.safetensors'),frozen_base_sha256_before=frozen_before,frozen_base_sha256_after=frozen_after,
        training_seconds=round(time.monotonic()-started,2),peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
        all_backpropagation_and_teacher_ids_are_training_only=all(set(r['training_sample_ids'])<=set(proof['training_ids']) for r in logs),
        manual_meanings_reviewed=False,application_weights_modified=False,new_blind_test_chapters_opened=0,screen_attempt_failure_probability=None,
        automatic_metric_is_not_failure_probability=True,target_achieved=False,ready_for_application=False)
    write(folder/'summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
