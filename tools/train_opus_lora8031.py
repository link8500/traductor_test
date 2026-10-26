"""Train a small local adapter only from approved bilingual pixel transcriptions.

The reference is a supervised training label only in the training split. Test
and validation targets never enter loss/backpropagation or a generation input.
The installed ONNX app remains untouched; the adapter is a separate candidate.
"""
import collections
import contextlib
import hashlib
import importlib.metadata
import json
import math
import pathlib
import random
import re
import shutil
import time
import unicodedata

import torch
from peft import LoraConfig,TaskType,get_peft_model
from transformers import MarianMTModel,MarianTokenizer
from sacrebleu.metrics import CHRF

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'build/finetune8031'
META=ROOT/'benchmarks/finetune8031'


def read(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,v):
    p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def normalized(s):return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',s).casefold()))


def prepare_source(text):
    # Mirrors generic casing in LocalTranslationModel::PrepareSource; no
    # chapter glossary, manual answer, or learned typo substitution is used.
    text=re.sub(r'[\t\r\n ]+',' ',unicodedata.normalize('NFKC',text)).strip()
    letters=sum('A'<=c<='Z' or 'a'<=c<='z' for c in text);lower=sum('a'<=c<='z' for c in text)
    label=letters>=5 and lower==0 and re.fullmatch(r'''[A-Z ,.!?;:'"()\-]*''',text) is not None
    if text in {'ASCII','HTTPS','HTTP','JSON','HTML','ONNX','CUDA','RGBA','ARGB'}:label=False
    if (letters>12 and lower==0 and text.count(' ')>=2) or label:
        result=[];initial=True
        for c in text:
            if 'A'<=c<='Z':result.append(c if initial else c.lower());initial=False
            else:result.append(c)
            if c in '.!?':initial=True
        text=re.sub(r'\bi\b','I',''.join(result))
    return text


def base_hash(model):
    h=hashlib.sha256()
    for name,p in model.named_parameters():
        if 'lora_' in name:continue
        h.update(name.encode());flat=p.detach().flatten()
        for start in range(0,flat.numel(),1024*1024):h.update(flat[start:start+1024*1024].cpu().numpy().tobytes())
    return h.hexdigest()


def validate_data(protocol,tokenizer):
    data=read(META/'approved-pairs.json');assert data['reviewer']=='assistant_visual_pixel_review'
    assert data['review_selection_sha256']==sha(OUT/'review-selection.json')
    proposals={r['id']:r for r in read(OUT/'review-selection.json')}
    source=read(META/'sources.json');assignments={n:s for s,ns in source['assignments'].items() for n in ns}
    sets={s:[] for s in ['train','validation','test']};seen={};chapters={}
    for r in data['entries']:
        if not r['approved']:continue
        proposal=proposals[r['id']];assert proposal['chapter']==r['chapter'] and proposal['split']==r['split']
        for field in ['source_image','reference_image']:
            assert sha(proposal[field]['path'])==proposal[field]['sha256']
        assert r['split']==assignments[r['chapter']]
        assert all(r[k] for k in protocol['training_pairs_require'])
        assert r['source'].strip() and r['target'].strip()
        assert r['chapter'] not in chapters or chapters[r['chapter']]==r['split'];chapters[r['chapter']]=r['split']
        key=normalized(r['source']);assert key not in seen,('Duplicate source',r['id'],seen.get(key));seen[key]=r['id']
        source_ids=tokenizer(prepare_source(r['source']))['input_ids'];target_ids=tokenizer(text_target=r['target'])['input_ids']
        assert len(source_ids)<=protocol['max_source_tokens'] and len(target_ids)<=protocol['max_target_tokens'],('Do not silently truncate',r['id'])
        sets[r['split']].append(dict(r,prepared_source=prepare_source(r['source'])))
    for s,n in protocol['minimum_approved_pairs'].items():assert len(sets[s])>=n,(s,len(sets[s]),n)
    return sets


def batch(tokenizer,rows,device):
    x=tokenizer([r['prepared_source'] for r in rows],padding=True,return_tensors='pt')
    y=tokenizer(text_target=[r['target'] for r in rows],padding=True,return_tensors='pt')['input_ids']
    y[y==tokenizer.pad_token_id]=-100
    return {**{k:v.to(device) for k,v in x.items()},'labels':y.to(device)}


def generate(model,tokenizer,rows,disabled=False):
    model.eval();result=[]
    with model.disable_adapter() if disabled else contextlib.nullcontext():
        with torch.inference_mode():
            for start in range(0,len(rows),4):
                part=rows[start:start+4];inputs=tokenizer([r['prepared_source'] for r in part],padding=True,return_tensors='pt').to('cuda')
                with torch.autocast('cuda',dtype=torch.bfloat16):
                    outputs=model.generate(**inputs,num_beams=4,max_new_tokens=160,do_sample=False,early_stopping=True,
                                           renormalize_logits=True,use_cache=True)
                translations=tokenizer.batch_decode(outputs,skip_special_tokens=True)
                result.extend(dict(id=r['id'],source=r['source'],prepared_source=r['prepared_source'],translation=t) for r,t in zip(part,translations))
    return result


def main():
    protocol=read(META/'protocol.json');assert torch.cuda.is_available(),'A usable CUDA build is required'
    assert shutil.disk_usage(OUT).free>4*1024**3
    torch.set_num_threads(2);random.seed(protocol['seed']);torch.manual_seed(protocol['seed']);torch.cuda.manual_seed_all(protocol['seed'])
    torch.cuda.set_per_process_memory_fraction(.82,0)
    tokenizer=MarianTokenizer.from_pretrained(OUT/'base-model',local_files_only=True)
    sets=validate_data(protocol,tokenizer)
    output=OUT/'lora-pilot';assert not output.exists(),'Never overwrite a trained candidate';output.mkdir()
    write(output/'run-input-proof.json',dict(protocol_sha256=sha(META/'protocol.json'),dataset_sha256=sha(META/'approved-pairs.json'),
        source_inventory_sha256=sha(META/'sources.json'),model_provenance_sha256=sha(OUT/'base-model-provenance.json'),
        execution_script_sha256=sha(__file__),counts={s:len(v) for s,v in sets.items()},gpu=torch.cuda.get_device_name(0),
        packages={n:importlib.metadata.version(n) for n in ['torch','transformers','peft','accelerate','safetensors','sentencepiece']},
        labels_used_for_backpropagation=['train'],heldout_targets_in_generation_input=False,application_modified=False))
    base=MarianMTModel.from_pretrained(OUT/'base-model',local_files_only=True,torch_dtype=torch.float32)
    model=get_peft_model(base,LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM,r=protocol['rank'],lora_alpha=protocol['alpha'],
        lora_dropout=protocol['dropout'],target_modules=protocol['target_modules'],bias='none')).to('cuda')
    before_hash=base_hash(model)
    trainable=sum(p.numel() for p in model.parameters() if p.requires_grad);total=sum(p.numel() for p in model.parameters())
    print(json.dumps(dict(state='loaded',trainable_parameters=trainable,total_parameters=total,counts={s:len(v) for s,v in sets.items()})),flush=True)
    baseline={s:generate(model,tokenizer,sets[s],disabled=True) for s in ['validation','test']}
    write(output/'baseline-heldout.json',baseline)
    model.config.use_cache=False;model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads()
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=protocol['learning_rate'],weight_decay=protocol['weight_decay'])
    training=list(sets['train']);order=[];cursor=0;log=[];started=time.monotonic();model.train()
    for step in range(protocol['optimizer_steps']):
        optimizer.zero_grad(set_to_none=True);loss_sum=0
        for micro in range(protocol['gradient_accumulation_steps']):
            selected=[]
            while len(selected)<protocol['micro_batch_size']:
                if cursor>=len(order):order=list(range(len(training)));random.shuffle(order);cursor=0
                selected.append(training[order[cursor]]);cursor+=1
            inputs=batch(tokenizer,selected,'cuda')
            with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**inputs).loss
            assert torch.isfinite(loss).item(),'Nonfinite training loss; candidate is invalid'
            loss_sum+=float(loss.detach());(loss/protocol['gradient_accumulation_steps']).backward()
        norm=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.0)
        assert torch.isfinite(norm).item()
        factor=min((step+1)/protocol['warmup_steps'],(protocol['optimizer_steps']-step)/(protocol['optimizer_steps']-protocol['warmup_steps']))
        for group in optimizer.param_groups:group['lr']=protocol['learning_rate']*factor
        optimizer.step();row=dict(step=step+1,training_loss=loss_sum/protocol['gradient_accumulation_steps'],lr=optimizer.param_groups[0]['lr'])
        log.append(row);print(json.dumps(dict(state='training',**row)),flush=True)
    model.gradient_checkpointing_disable();model.config.use_cache=True
    after_hash=base_hash(model);assert before_hash==after_hash,'Frozen base weights changed'
    model.save_pretrained(output/'adapter',safe_serialization=True)
    assert any('lora_B' in n and float(p.detach().abs().max())>0 for n,p in model.named_parameters())
    candidate={s:generate(model,tokenizer,sets[s]) for s in ['validation','test']}
    write(output/'candidate-heldout.json',candidate);write(output/'training-log.json',log)
    metric=CHRF(word_order=2);scores={}
    for split in ['validation','test']:
        references=[r['target'] for r in sets[split]];a=[r['translation'] for r in baseline[split]];b=[r['translation'] for r in candidate[split]]
        scores[split]=dict(pairs=len(a),baseline_chrfpp=metric.corpus_score(a,[references]).score,
                          candidate_chrfpp=metric.corpus_score(b,[references]).score,changed_outputs=sum(x!=y for x,y in zip(a,b)),
                          automatic_metric_not_semantic_error_rate=True)
    value=dict(actual_weight_training_completed=True,optimizer_steps=len(log),trainable_parameters=trainable,total_parameters=total,
               frozen_base_sha256_before=before_hash,frozen_base_sha256_after=after_hash,base_weights_unchanged=True,
               trained_adapter_sha256=sha(output/'adapter/adapter_model.safetensors'),training_seconds=round(time.monotonic()-started,2),
               peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),heldout_scores=scores,
               application_weights_modified=False,manual_heldout_meaning_review_complete=False,
               screen_attempt_failure_probability=None,target_achieved=False,ready_for_application=False)
    write(output/'summary.json',value);print(json.dumps(value),flush=True)


if __name__=='__main__':main()
