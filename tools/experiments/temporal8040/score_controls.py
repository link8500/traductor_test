"""Compute control inverse scores only after the new validation gate passes."""
import json
import os

from tools.experiments.stability8035.core import ROOT, read, sha, write_new, format_issues
from tools.experiments.qe8038.evaluate import key
from .route import META, OUT, verify


def main():
    verify()
    selection = read(META / 'selection.json')
    assert selection['eligible'] and selection['frozen_before_controls']
    assert selection['validation_review_sha256'] == sha(META / 'validation-review.json')
    assert selection['protocol_sha256'] == sha(META / 'protocol.json')
    for row in read(ROOT / 'benchmarks/roundtrip8039/model-provenance.json')['files']:
        assert sha(ROOT / row['path']) == row['sha256']
    requests = {}
    for pool in read(ROOT / 'build/qe8038/candidate-pools.json'):
        if pool['group'] == 'validation' or len({row['translation'] for row in pool['candidates']}) == 1:
            continue
        for candidate in pool['candidates']:
            if not format_issues(pool['source'], candidate['translation']):
                requests[key(pool['source'], candidate['translation'])] = dict(src=pool['source'], mt=candidate['translation'])
    write_new(OUT / 'controls-inverse-input.json', requests)
    write_new(OUT / 'controls-scoring-proof.json', dict(
        protocol_sha256=sha(META / 'protocol.json'), selection_sha256=sha(META / 'selection.json'),
        original_english_source_used_as_reverse_target=True, gold_spanish_reference_used=False,
        gradient_updates=0, new_blind_test_chapters_opened=0))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    from tools.quality_resources import wait_for_inference_memory
    from tools.experiments.roundtrip8039.score import score_pairs
    wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
    torch.set_num_threads(2)
    torch.cuda.set_per_process_memory_fraction(.85)
    directory = ROOT / 'build/roundtrip8039/model'
    tokenizer = MarianTokenizer.from_pretrained(directory, local_files_only=True)
    model = MarianMTModel.from_pretrained(directory, local_files_only=True, torch_dtype=torch.float32,
                                         use_safetensors=False).to('cuda').eval()
    model.requires_grad_(False)
    scores = score_pairs(list(requests.values()), model, tokenizer)
    write_new(OUT / 'controls-inverse-scores.json', dict(scores=dict(zip(requests, scores)),
                                                       original_source_not_reference_translation=True,
                                                       score_is_not_probability_of_correct_translation=True))
    print(json.dumps(dict(state='controls_inverse_scored', unique_pairs=len(scores))), flush=True)


if __name__ == '__main__':
    main()
