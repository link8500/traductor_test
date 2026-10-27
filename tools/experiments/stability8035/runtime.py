"""Local-only PEFT adapter loading and exact multiplicative LoRA scaling."""
import json
import time

import torch
from peft import PeftModel
from peft.tuners.lora.layer import Linear
from transformers import MarianMTModel, MarianTokenizer

from tools.quality_resources import wait_for_inference_memory
from .core import BASE, PRIOR, format_issues


class Runtime:
    def __init__(self, generation):
        wait_for_inference_memory(minimum_free_bytes=3 * 1024**3)
        assert torch.cuda.is_available()
        torch.set_num_threads(2)
        torch.manual_seed(8032)
        torch.cuda.set_per_process_memory_fraction(.82)
        self.tokenizer = MarianTokenizer.from_pretrained(BASE, local_files_only=True)
        base = MarianMTModel.from_pretrained(BASE, local_files_only=True, torch_dtype=torch.float32)
        self.model = PeftModel.from_pretrained(
            base, PRIOR / 'adapter', is_trainable=False, local_files_only=True).to('cuda').eval()
        self.generation = generation
        assert not any(parameter.requires_grad for parameter in self.model.parameters())
        self.layers = [module for module in self.model.modules() if isinstance(module, Linear)]
        assert self.layers

    def set_strength(self, strength):
        assert 0 <= strength <= 1
        for layer in self.layers:
            layer.set_scale('default', strength)
            assert layer.scaling['default'] == strength * layer.lora_alpha['default'] / layer.r['default']

    def generate(self, rows, strength):
        self.set_strength(strength)
        results = []
        for start in range(0, len(rows), 4):
            part = rows[start:start + 4]
            assert all(set(row) == {'id', 'source', 'prepared_source'} for row in part)
            inputs = self.tokenizer([row['prepared_source'] for row in part],
                                    padding=True, return_tensors='pt').to('cuda')
            started = time.monotonic()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                ids = self.model.generate(**inputs, **self.generation)
            texts = self.tokenizer.batch_decode(ids, skip_special_tokens=True)
            for row, text, sequence in zip(part, texts, ids):
                generated = len(sequence[1:][sequence[1:] != self.tokenizer.pad_token_id])
                results.append(dict(row, translation=text,
                                    generated_tokens=generated,
                                    generation_limit_reached=generated >= self.generation['max_new_tokens'],
                                    format_issues=format_issues(row['source'], text)))
            print(json.dumps(dict(state='inference', strength=strength, completed=len(results),
                                  total=len(rows), batch_seconds=round(time.monotonic() - started, 3))), flush=True)
        return results
