"""Mask-normalized forward KL for supervised and free-running prefixes."""
import torch
import torch.nn.functional as F


def token_kl(student_logits, teacher_logits, mask):
    assert mask.dtype == torch.bool and mask.any()
    student = F.log_softmax(student_logits[mask].float(), dim=-1)
    teacher = F.log_softmax(teacher_logits[mask].detach().float(), dim=-1)
    return F.kl_div(student, teacher, reduction='sum', log_target=True) / mask.sum()


def decoder_prefixes(sequences, pad_token_id):
    assert sequences.ndim == 2 and sequences.shape[1] >= 2
    prefixes = sequences[:, :-1].detach()
    targets = sequences[:, 1:].detach()
    attention = prefixes.ne(pad_token_id).long()
    # Marian starts its decoder with PAD, which is an attended start token.
    attention[:, 0] = 1
    return prefixes, attention, targets.ne(pad_token_id)
