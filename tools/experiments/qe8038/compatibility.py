"""Narrow legacy buffer compatibility; all learned parameters remain strict."""
import torch
from comet.models import str2model


class CompatibleReferenceless(str2model['referenceless_regression_metric']):
    def load_state_dict(self, state_dict, strict=True, assign=False):
        obsolete = 'encoder.model.embeddings.position_ids'
        if obsolete in state_dict:
            supplied = state_dict[obsolete]
            generated = self.encoder.model.embeddings.position_ids
            assert supplied.shape == generated.shape
            assert torch.equal(supplied.cpu(), generated.cpu()), 'Unexpected positional index values'
            state_dict = state_dict.copy()
            del state_dict[obsolete]
        # Never suppress a missing or unexpected learned parameter.
        return super().load_state_dict(state_dict, strict=True, assign=assign)
