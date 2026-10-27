"""Run exactly the validation-selected checkpoint on all known controls."""
import json
import shutil

import torch
from peft import PeftModel
from transformers import MarianMTModel, MarianTokenizer

from tools.quality_resources import wait_for_inference_memory
from tools.train_opus_lora8031 import generate
from tools.experiments.stability8035.core import BASE, PRIOR, ROOT, format_issues, read, sha, source_only, write_new
from .select_checkpoint import META, OUT, verified_run


def main():
    protocol, summary = verified_run()
    selection = read(META / 'selection.json')
    assert selection['all_selection_gates_passed'] and selection['selected_checkpoint']
    assert selection['protocol_sha256'] == sha(META / 'protocol.json')
    assert selection['review_sha256'] == sha(META / 'validation-review.json')
    assert selection['frozen_before_control_inference'] and not selection['controls_used_for_selection']
    assert shutil.disk_usage(ROOT).free > 4 * 1024**3
    checkpoint = OUT / selection['selected_checkpoint']
    write_new(OUT / 'controls-input-proof.json', dict(
        selection=selection, selection_sha256=sha(META / 'selection.json'),
        execution_script_sha256=sha(__file__), helper_sha256=sha(ROOT / 'tools/train_opus_lora8031.py'),
        no_checkpoint_reselection_from_controls=True, no_gradients=True,
        no_new_blind_test_chapters=True, application_weights_modified=False))
    wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
    torch.set_num_threads(2)
    torch.manual_seed(8032)
    torch.cuda.set_per_process_memory_fraction(.82)
    tokenizer = MarianTokenizer.from_pretrained(BASE, local_files_only=True)
    base = MarianMTModel.from_pretrained(BASE, local_files_only=True, torch_dtype=torch.float32)
    model = PeftModel.from_pretrained(base, checkpoint / 'adapter', is_trainable=False,
                                     local_files_only=True).to('cuda').eval()
    assert not any(parameter.requires_grad for parameter in model.parameters())
    data = read(ROOT / 'benchmarks/finetune8034/dataset.json')
    assert generate(model, tokenizer, source_only(data['validation'])) == read(checkpoint / 'validation-candidate.json')
    write_new(OUT / 'selected-checkpoint-reload-parity.json', dict(exact=True, rows=25,
               adapter_sha256=sha(checkpoint / 'adapter/adapter_model.safetensors')))
    for name in ['regression-core', 'known-test', 'early-known-test']:
        baseline = read(PRIOR / f'{name}-baseline.json')
        inputs = source_only(baseline)
        write_new(OUT / f'{name}-source-only-input.json', inputs)
        candidate = generate(model, tokenizer, inputs)
        write_new(OUT / f'{name}-candidate.json', candidate)
        result = dict(rows=len(inputs), changed_from_base=sum(
            before['translation'] != after['translation'] for before, after in zip(baseline, candidate)),
            format_alerts=sum(bool(format_issues(row['source'], row['translation'])) for row in candidate),
            output_sha256=sha(OUT / f'{name}-candidate.json'), baseline_sha256=sha(PRIOR / f'{name}-baseline.json'),
            selection_sha256=sha(META / 'selection.json'),
            source_only=True, no_fresh_ocr_or_capture=True, fresh_blind_test=False,
            semantic_review_complete=False, app_failure_probability=None)
        write_new(OUT / f'{name}-summary.json', result)
        print(json.dumps(dict(state='known_control_complete', name=name, **result)), flush=True)


if __name__ == '__main__':
    main()
