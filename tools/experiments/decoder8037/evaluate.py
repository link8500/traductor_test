"""Fixed decoding comparisons; no training, reference-conditioned inputs or swaps."""
import argparse
import contextlib
import json
import shutil
from pathlib import Path

import torch
from peft import PeftModel
from transformers import LogitsProcessorList, MarianMTModel, MarianTokenizer

from tools.quality_resources import wait_for_inference_memory
from tools.experiments.stability8035.core import (
    BASE, PRIOR, ROOT, format_issues, read, sha, source_only, text_outputs,
    validate_provenance, write_new)
from .opening import LexicalOpening

META = ROOT / 'benchmarks/decoder8037'
OUT = ROOT / 'build/decoder8037'


class Runtime:
    def __init__(self):
        wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
        torch.set_num_threads(2)
        torch.manual_seed(8032)
        torch.cuda.set_per_process_memory_fraction(.82)
        self.tokenizer = MarianTokenizer.from_pretrained(BASE, local_files_only=True)
        model = MarianMTModel.from_pretrained(BASE, local_files_only=True, torch_dtype=torch.float32)
        self.model = PeftModel.from_pretrained(model, PRIOR / 'adapter', is_trainable=False,
                                              local_files_only=True).to('cuda').eval()
        self.tokens = self.tokenizer.convert_ids_to_tokens(list(range(self.model.config.vocab_size)))
        assert not any(parameter.requires_grad for parameter in self.model.parameters())

    def generate(self, rows, variant, generation):
        outputs = []
        for start in range(0, len(rows), 4):
            part = rows[start:start + 4]
            assert all(set(row) == {'id', 'source', 'prepared_source'} for row in part)
            batch = self.tokenizer([row['prepared_source'] for row in part], padding=True,
                                    return_tensors='pt').to('cuda')
            guard = LexicalOpening(self.tokens, [row['prepared_source'] for row in part],
                                   beams=generation['num_beams'], eos=self.tokenizer.eos_token_id,
                                   pad=self.tokenizer.pad_token_id, unknown=self.tokenizer.unk_token_id)
            kwargs = dict(generation, early_stopping=variant['early_stopping'])
            if variant['lexical_opening']:
                kwargs['logits_processor'] = LogitsProcessorList([guard])
            context = self.model.disable_adapter() if variant['weights'] == 'base' else contextlib.nullcontext()
            with context, torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                ids = self.model.generate(**batch, **kwargs)
            translations = self.tokenizer.batch_decode(ids, skip_special_tokens=True)
            for index, (row, translation, sequence) in enumerate(zip(part, translations, ids)):
                generated = len(sequence[1:][sequence[1:] != self.tokenizer.pad_token_id])
                outputs.append(dict(row, translation=translation, generated_tokens=generated,
                                    generation_limit_reached=generated >= generation['max_new_tokens'],
                                    format_issues=format_issues(row['source'], translation),
                                    guard_steps=guard.blocked_steps[index],
                                    unresolved_all_masked_steps=guard.restore_all_masked[index]))
        return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    protocol = read(META / 'protocol.json')
    _, data = validate_provenance()
    for entry in protocol['immutable_inputs']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    assert shutil.disk_usage(ROOT).free > 4 * 1024**3
    scripts = list(Path(__file__).parent.glob('*.py'))
    write_new(OUT / f'{args.stage}-input-proof.json', dict(
        protocol_sha256=sha(META / 'protocol.json'),
        code_sha256={str(path.relative_to(ROOT)): sha(path) for path in scripts},
        source_only_generation=True, weights_modified=False, new_blind_test_chapters_opened=0))
    runtime = Runtime()
    inputs = source_only(data['validation'])
    for weights, name in [('base', 'baseline-validation.json'), ('adapter8034', 'candidate-validation.json')]:
        old = runtime.generate(inputs, dict(weights=weights, early_stopping=True, lexical_opening=False), protocol['generation'])
        assert text_outputs(old) == read(PRIOR / name), f'Historical parity failed: {weights}'
    write_new(OUT / f'{args.stage}-parity.json', dict(exact=True, inputs=25, baseline_and_adapter=True))
    names = ['validation'] if args.stage == 'validation' else ['regression-core', 'known-test', 'early-known-test']
    variants = protocol['variants'] if args.stage == 'validation' else [
        variant for variant in protocol['variants'] if variant['id'] in protocol['fixed_control_variants']]
    for name in names:
        rows = inputs if name == 'validation' else source_only(read(PRIOR / f'{name}-baseline.json'))
        write_new(OUT / f'{name}-source-only-input.json', rows)
        for variant in variants:
            result = runtime.generate(rows, variant, protocol['generation'])
            path = OUT / f"{name}-{variant['id']}.json"
            write_new(path, result)
            summary = dict(name=name, variant=variant['id'], rows=len(result), output_sha256=sha(path),
                           format_alerts=sum(bool(row['format_issues']) for row in result),
                           generation_limits_reached=sum(row['generation_limit_reached'] for row in result),
                           unresolved_guard_rows=sum(row['unresolved_all_masked_steps'] > 0 for row in result),
                           semantic_review_complete=False, app_failure_probability=None)
            write_new(OUT / f"{name}-{variant['id']}-summary.json", summary)
            print(json.dumps(dict(state='decoding_complete', **summary)), flush=True)


if __name__ == '__main__':
    main()
