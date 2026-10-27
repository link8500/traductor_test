"""Compute inverse likelihood with known source text as target, without gradients."""
import argparse
import json
import os
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import MarianMTModel, MarianTokenizer

from tools.quality_resources import wait_for_inference_memory
from tools.train_opus_lora8031 import prepare_source
from tools.experiments.stability8035.core import ROOT, read, sha, write_new, format_issues
from tools.experiments.qe8038.evaluate import key

OUT = ROOT / 'build/roundtrip8039'
META = ROOT / 'benchmarks/roundtrip8039'


def score_pairs(samples, model, tokenizer):
    values = []
    for start in range(0, len(samples), 8):
        part = samples[start:start + 8]
        assert all(set(row) == {'src', 'mt'} for row in part)
        spanish = tokenizer([row['mt'] for row in part], padding=True, return_tensors='pt').to('cuda')
        english = tokenizer(text_target=[prepare_source(row['src']) for row in part], padding=True,
                            return_tensors='pt')['input_ids'].to('cuda')
        assert spanish['input_ids'].shape[1] <= 512 and english.shape[1] <= 512
        mask = english.ne(tokenizer.pad_token_id)
        labels = english.masked_fill(~mask, -100)
        with torch.inference_mode():
            logits = model(**spanish, labels=labels, use_cache=False).logits
            logp = F.log_softmax(logits.float(), dim=-1).gather(-1, english.unsqueeze(-1)).squeeze(-1)
            means = (logp * mask).sum(-1) / mask.sum(-1)
        for index, row in enumerate(part):
            tokens = english[index][mask[index]].cpu().tolist()
            values.append(dict(mean_log_probability=float(means[index]),
                               english_token_ids=tokens,
                               english_token_logprobs=logp[index][mask[index]].cpu().tolist(),
                               unknown_english_tokens=tokens.count(tokenizer.unk_token_id)))
        print(json.dumps(dict(state='inverse_likelihood_scored', completed=len(values), total=len(samples))), flush=True)
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['validation', 'controls'])
    args = parser.parse_args()
    protocol = read(META / 'protocol.json')
    for entry in protocol['immutable_inputs']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    model_provenance = read(META / 'model-provenance.json')
    for entry in model_provenance['files']:
        assert sha(ROOT / entry['path']) == entry['sha256']
    if args.stage == 'controls':
        selection = read(META / 'selection.json')
        assert selection['eligible'] and selection['frozen_before_controls']
    pools = read(ROOT / 'build/qe8038/candidate-pools.json')
    pools = [row for row in pools if (row['group'] == 'validation') == (args.stage == 'validation')]
    requests = {}
    for pool in pools:
        if len({row['translation'] for row in pool['candidates']}) == 1:
            continue
        for candidate in pool['candidates']:
            if not format_issues(pool['source'], candidate['translation']):
                requests[key(pool['source'], candidate['translation'])] = dict(src=pool['source'], mt=candidate['translation'])
    write_new(OUT / f'{args.stage}-input-proof.json', dict(
        protocol_sha256=sha(META / 'protocol.json'), model_provenance_sha256=sha(META / 'model-provenance.json'),
        code_sha256={str(path.relative_to(ROOT)): sha(path) for path in Path(__file__).parent.glob('*.py')},
        original_english_source_used_as_reverse_target=True, gold_spanish_reference_used=False,
        gradient_updates=0, new_blind_test_chapters_opened=0))
    write_new(OUT / f'{args.stage}-inverse-input.json', requests)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(.85)
    directory = OUT / 'model'
    tokenizer = MarianTokenizer.from_pretrained(directory, local_files_only=True)
    model = MarianMTModel.from_pretrained(directory, local_files_only=True,
                                         torch_dtype=torch.float32, use_safetensors=False).to('cuda').eval()
    model.requires_grad_(False)
    values = score_pairs(list(requests.values()), model, tokenizer)
    write_new(OUT / f'{args.stage}-inverse-scores.json', dict(
        scores=dict(zip(requests, values)), original_source_not_reference_translation=True,
        score_is_not_probability_of_correct_translation=True))


if __name__ == '__main__':
    main()
