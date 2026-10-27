"""One new LoRA run with training-only self-generated prefix regularization."""
import hashlib
import json
import random
import shutil
import time
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from sacrebleu.metrics import CHRF
from transformers import MarianMTModel, MarianTokenizer

from tools.quality_resources import wait_for_inference_memory
from tools.train_opus_lora8031 import base_hash, batch, generate
from tools.experiments.stability8035.core import (
    BASE, ROOT, format_issues, read, sha, source_only, validate_provenance, write_new)
from .losses import decoder_prefixes, token_kl

META = ROOT / 'benchmarks/onpolicy8036'
OUT = ROOT / 'build/onpolicy8036'


def check_protocol():
    protocol = read(META / 'protocol.json')
    for entry in protocol['immutable_inputs']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    _, data = validate_provenance()
    training = data['original_training'] + data['packed_training']
    originals = data['original_training']
    validation = data['validation']
    assert len(training) == 417 and len(originals) == 163 and len(validation) == 25
    assert all(row['split'] == 'train' for row in training)
    assert not {row['id'] for row in training} & {row['id'] for row in validation}
    return protocol, training, originals, validation


def main():
    protocol, training, originals, validation = check_protocol()
    assert shutil.disk_usage(ROOT).free > 4 * 1024**3
    assert not OUT.exists(), 'Never overwrite a training run'
    OUT.mkdir(parents=True)
    wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
    torch.set_num_threads(2)
    torch.manual_seed(protocol['seed'])
    torch.cuda.manual_seed_all(protocol['seed'])
    rng = random.Random(protocol['seed'])
    torch.cuda.set_per_process_memory_fraction(.82)
    code = list(Path(__file__).parent.glob('*.py'))
    proof = dict(protocol_sha256=sha(META / 'protocol.json'),
                 code_sha256={str(path.relative_to(ROOT)): sha(path) for path in code},
                 training_ids=[row['id'] for row in training], rollout_ids=[row['id'] for row in originals],
                 validation_ids=[row['id'] for row in validation],
                 evaluation_inputs_used_for_gradients=False, new_blind_test_chapters_opened=0,
                 base_provenance_sha256=sha(ROOT / 'build/finetune8031/base-model-provenance.json'))
    write_new(OUT / 'run-input-proof.json', proof)
    tokenizer = MarianTokenizer.from_pretrained(BASE, local_files_only=True)
    base = MarianMTModel.from_pretrained(BASE, local_files_only=True, torch_dtype=torch.float32)
    model = get_peft_model(base, LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM, r=4, lora_alpha=8,
        lora_dropout=0, target_modules=['q_proj', 'v_proj'], bias='none')).to('cuda').eval()
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    assert sum(parameter.numel() for parameter in trainable) == 294912
    frozen_before = base_hash(model)
    baseline = generate(model, tokenizer, source_only(validation), disabled=True)
    assert baseline == read(ROOT / 'build/finetune8034/lora-pilot/baseline-validation.json')
    write_new(OUT / 'baseline-validation.json', baseline)
    optimizer = torch.optim.AdamW(trainable, lr=protocol['learning_rate'], weight_decay=.01)
    steps = protocol['optimizer_steps']
    order = []
    cursor = 0
    logs = []
    rollout_log = []
    checkpoints = []
    started = time.monotonic()
    model.config.use_cache = False
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True)
        ce_sum = kl_sum = 0.0
        training_ids = []
        for micro in range(4):
            selected = []
            while len(selected) < 2:
                if cursor >= len(order):
                    order = list(range(len(training)))
                    rng.shuffle(order)
                    cursor = 0
                selected.append(training[order[cursor]])
                cursor += 1
            training_ids.extend(row['id'] for row in selected)
            inputs = batch(tokenizer, selected, 'cuda')
            with torch.no_grad(), model.disable_adapter(), torch.autocast('cuda', dtype=torch.bfloat16):
                teacher = model(**inputs).logits.detach()
            with torch.autocast('cuda', dtype=torch.bfloat16):
                output = model(**inputs)
            kl = token_kl(output.logits, teacher, inputs['labels'].ne(-100))
            loss = output.loss + protocol['reference_kl_weight'] * kl
            assert torch.isfinite(loss).item()
            if step == 0 and micro == 0:
                assert abs(float(kl.detach())) < 1e-5
            ce_sum += float(output.loss.detach())
            kl_sum += float(kl.detach())
            (loss / 4).backward()
            del teacher, output, loss, kl

        # Cyclic, training-only sources. Reference targets never enter this generation.
        selected = [originals[(2 * step + offset) % len(originals)] for offset in range(2)]
        encoder = tokenizer([row['prepared_source'] for row in selected], padding=True,
                            return_tensors='pt').to('cuda')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            sequences = model.generate(**encoder, num_beams=1, do_sample=False,
                                       max_new_tokens=protocol['rollout_max_new_tokens'],
                                       renormalize_logits=True, use_cache=True)
        # Tensors created under inference_mode cannot be saved by autograd: clone outside it.
        prefixes, decoder_attention, mask = decoder_prefixes(sequences.clone(), tokenizer.pad_token_id)
        forward = dict(encoder, decoder_input_ids=prefixes,
                       decoder_attention_mask=decoder_attention, use_cache=False)
        with torch.no_grad(), model.disable_adapter(), torch.autocast('cuda', dtype=torch.bfloat16):
            teacher = model(**forward).logits.detach()
        with torch.autocast('cuda', dtype=torch.bfloat16):
            student = model(**forward).logits
        free_kl = token_kl(student, teacher, mask)
        assert torch.isfinite(free_kl).item() and float(free_kl.detach()) >= -1e-5
        (protocol['onpolicy_kl_weight'] * free_kl).backward()
        free_value = float(free_kl.detach())
        rollout_log.append(dict(step=step + 1, training_ids=[row['id'] for row in selected],
                                generated_token_ids=sequences.cpu().tolist(),
                                references_used_for_generation=False))
        del teacher, student, free_kl, forward, sequences, prefixes, decoder_attention, mask
        norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
        assert torch.isfinite(norm).item()
        factor = min((step + 1) / 8, (steps - step) / (steps - 8))
        for group in optimizer.param_groups:
            group['lr'] = protocol['learning_rate'] * factor
        optimizer.step()
        logs.append(dict(step=step + 1, cross_entropy=ce_sum / 4, reference_kl=kl_sum / 4,
                         onpolicy_kl=free_value, training_ids=training_ids))
        if (step + 1) % 16 == 0:
            print(json.dumps(dict(state='training', step=step + 1, total_steps=steps,
                                  cross_entropy=ce_sum / 4, onpolicy_kl=free_value)), flush=True)
        if step + 1 in protocol['checkpoint_steps']:
            name = f'step{step + 1:03d}'
            directory = OUT / name
            model.save_pretrained(directory / 'adapter', safe_serialization=True)
            model.config.use_cache = True
            candidate = generate(model, tokenizer, source_only(validation))
            model.config.use_cache = False
            write_new(directory / 'validation-candidate.json', candidate)
            metric = CHRF(word_order=2)
            score = metric.corpus_score([row['translation'] for row in candidate],
                                        [[row['target'] for row in validation]]).score
            record = dict(name=name, optimizer_step=step + 1, adapter_sha256=sha(directory / 'adapter/adapter_model.safetensors'),
                          output_sha256=sha(directory / 'validation-candidate.json'), validation_chrfpp=score,
                          format_alerts=sum(bool(format_issues(row['source'], row['translation'])) for row in candidate),
                          meaning_review_complete=False)
            checkpoints.append(record)
            print(json.dumps(dict(state='checkpoint_complete', **record)), flush=True)
    frozen_after = base_hash(model)
    assert frozen_before == frozen_after
    train_ids = set(proof['training_ids'])
    assert all(set(row['training_ids']) <= train_ids for row in logs + rollout_log)
    write_new(OUT / 'training-log.json', logs)
    write_new(OUT / 'rollout-log.json', rollout_log)
    write_new(OUT / 'summary.json', dict(
        actual_weight_training_completed=True, optimizer_steps=steps, trainable_parameters=294912,
        base_weights_unchanged=True, base_hash_before=frozen_before, base_hash_after=frozen_after,
        checkpoints=checkpoints, all_gradient_and_rollout_ids_are_training_only=True,
        training_seconds=round(time.monotonic() - started, 2),
        peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
        test_control_outputs_used_for_checkpoint_selection=False,
        application_weights_modified=False, app_failure_probability=None, target_achieved=False))


if __name__ == '__main__':
    main()
