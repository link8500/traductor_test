"""Pinned, local-only COMET-QE inference using its official implementation."""
import os

import torch

from tools.quality_resources import wait_for_inference_memory
from tools.experiments.stability8035.core import ROOT, read, sha
from .compatibility import CompatibleReferenceless

MODEL = ROOT / 'build/qe8038/model'
TOKENIZER = ROOT / 'build/qe8038/tokenizer'


class QualityEstimator:
    def __init__(self):
        provenance = read(ROOT / 'benchmarks/qe8038/model-provenance.json')
        path = ROOT / provenance['checkpoint']
        assert sha(path) == provenance['checkpoint_sha256']
        for entry in read(ROOT / 'benchmarks/qe8038/tokenizer-provenance.json')['files']:
            assert sha(ROOT / entry['path']) == entry['sha256']
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        wait_for_inference_memory(minimum_free_bytes=6 * 1024**3)
        torch.set_num_threads(2)
        torch.manual_seed(8038)
        torch.cuda.set_per_process_memory_fraction(.85)
        # torch>=2.6 uses weights_only=True by default in the official loader.
        self.model = CompatibleReferenceless.load_from_checkpoint(
            str(path), map_location='cpu', strict=True,
            load_pretrained_weights=False, pretrained_model=str(TOKENIZER), local_files_only=True)
        assert not self.model.requires_references()
        self.model.freeze()
        self.model.eval()
        assert not any(parameter.requires_grad for parameter in self.model.parameters())
        self.limit = self.model.encoder.max_positions - 2

    def score(self, samples):
        assert all(set(sample) == {'src', 'mt'} for sample in samples)
        tokenizer = self.model.encoder.tokenizer
        for sample in samples:
            for text in sample.values():
                size = len(tokenizer(text, truncation=False)['input_ids'])
                assert size <= self.limit, 'Do not silently truncate quality-estimator input'
        with torch.inference_mode():
            result = self.model.predict(samples, batch_size=4, gpus=1,
                                        progress_bar=False, num_workers=0, length_batching=False)
        values = [float(value) for value in result.scores]
        assert len(values) == len(samples)
        return values
