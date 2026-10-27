"""A decoding validity constraint, without word substitutions or reference text."""
import torch
from transformers import LogitsProcessor


def token_shape(text):
    text = text.replace('▁', ' ')
    leading = 0
    lexical = False
    for char in text:
        if char.isalnum():
            lexical = True
            break
        if not char.isspace():
            leading += 1
    return lexical, leading


class LexicalOpening(LogitsProcessor):
    """Require lexical content before EOS for lexical sources, bounding punctuation.

    After the first letter/number, logits are unchanged. Punctuation-only sources
    are unchanged. No minimum translated-word count or target phrase is imposed.
    """
    def __init__(self, tokens, sources, *, beams, eos, pad, unknown, minimum_budget=3):
        shapes = [token_shape(token) for token in tokens]
        for ident in [eos, pad, unknown]:
            shapes[ident] = (False, 0)
        self.lexical = torch.tensor([item[0] for item in shapes])
        self.leading = torch.tensor([item[1] for item in shapes])
        self.active = torch.tensor([any(char.isalnum() for char in source) for source in sources])
        self.budgets = torch.tensor([max(minimum_budget, token_shape(source)[1] + 2) for source in sources])
        self.beams = beams
        self.special = [eos, pad, unknown]
        self.blocked_steps = [0] * len(sources)
        self.restore_all_masked = [0] * len(sources)

    def __call__(self, input_ids, scores):
        device = input_ids.device
        lexical = self.lexical.to(device)
        leading = self.leading.to(device)
        active = self.active.to(device).repeat_interleave(self.beams)
        budgets = self.budgets.to(device).repeat_interleave(self.beams)
        assert len(active) == len(input_ids)
        needs_word = active & ~lexical[input_ids].any(dim=1)
        if not needs_word.any():
            return scores
        indices = needs_word.nonzero(as_tuple=True)[0]
        spent = leading[input_ids[indices]].sum(dim=1)
        remaining = budgets[indices] - spent
        blocked = leading.unsqueeze(0) > remaining.unsqueeze(1)
        blocked[:, self.special] = True
        original = scores[indices].clone()
        constrained = original.masked_fill(blocked, -torch.inf)
        finite = torch.isfinite(constrained).any(dim=1)
        # A forced-EOS step can leave no lexical token available. Preserve a
        # finite termination and record the unresolved case rather than NaNs.
        constrained[~finite] = original[~finite]
        output = scores.clone()
        output[indices] = constrained
        for index, valid in zip(indices.tolist(), finite.tolist()):
            batch = index // self.beams
            self.blocked_steps[batch] += 1
            if not valid:
                self.restore_all_masked[batch] += 1
        return output
