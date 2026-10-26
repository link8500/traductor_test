"""Check regularization mathematics and the actual trained artifact's isolation."""
import math
import unittest
import torch
from safetensors import safe_open
from train_opus_lora8033 import token_kl,META,OUT
import finetune8032_guards as g


class RegularizationGuards(unittest.TestCase):
    def test_equal_distributions_have_zero_kl(self):
        logits=torch.tensor([[[1.,2.,3.],[3.,2.,1.]]])
        self.assertAlmostEqual(token_kl(logits,logits,torch.tensor([[1,2]])).item(),0,places=6)

    def test_padding_does_not_change_kl_or_its_denominator(self):
        student=torch.tensor([[[2.,0.],[0.,2.]]]);teacher=torch.tensor([[[0.,2.],[2.,0.]]])
        expected=token_kl(student[:,:1],teacher[:,:1],torch.tensor([[1]]))
        self.assertAlmostEqual(token_kl(student,teacher,torch.tensor([[1,-100]])).item(),expected.item(),places=6)
        changed=teacher.clone();changed[:,1]=1000
        self.assertAlmostEqual(token_kl(student,changed,torch.tensor([[1,-100]])).item(),expected.item(),places=6)

    def test_kl_is_base_to_candidate_and_not_divided_by_vocabulary(self):
        p=torch.tensor([.8,.2]);q=torch.tensor([.3,.7])
        expected=(p*(p.log()-q.log())).sum().item()
        self.assertAlmostEqual(token_kl(q.log().reshape(1,1,2),p.log().reshape(1,1,2),torch.tensor([[1]])).item(),expected,places=6)

    def test_teacher_is_detached_and_only_candidate_receives_gradient(self):
        student=torch.tensor([[[2.,0.]]],requires_grad=True);teacher=torch.tensor([[[0.,2.]]],requires_grad=True)
        token_kl(student,teacher,torch.tensor([[1]])).backward()
        self.assertIsNone(teacher.grad);self.assertGreater(student.grad.abs().sum().item(),0)

    def test_actual_execution_pins_dataset_protocol_and_code(self):
        folder=OUT/'lora-pilot';proof=g.read(folder/'run-input-proof.json');summary=g.read(folder/'summary.json')
        self.assertEqual(proof['protocol_sha256'],g.sha(META/'protocol.json'))
        self.assertEqual(proof['dataset_sha256'],g.sha(g.META/'dataset.json'))
        self.assertEqual(proof['execution_script_sha256'],g.sha(g.ROOT/'tools/train_opus_lora8033.py'))
        self.assertEqual(proof['validation_guards_sha256'],g.sha(g.ROOT/'tools/finetune8032_guards.py'))
        self.assertEqual(summary['initial_token_kl'],0)
        self.assertEqual(summary['frozen_base_sha256_before'],summary['frozen_base_sha256_after'])
        self.assertFalse(proof['test_sources_or_targets_loaded_for_training'])
        self.assertFalse(summary['application_weights_modified'])
        log=g.read(folder/'training-log.json')
        self.assertEqual([r['step'] for r in log],list(range(1,161)))
        self.assertTrue(all(set(r['training_sample_ids'])<=set(proof['training_ids']) for r in log))
        self.assertTrue(all(math.isfinite(r['token_kl']) and r['token_kl']>=-1e-5 for r in log))
        self.assertFalse(set(proof['training_ids'])&set(proof['validation_ids']))

    def test_actual_regularized_adapter_contains_finite_learned_parameters(self):
        folder=OUT/'lora-pilot';summary=g.read(folder/'summary.json');path=folder/'adapter/adapter_model.safetensors'
        self.assertEqual(g.sha(path),summary['adapter_sha256'])
        count=0;trained=0
        with safe_open(path,framework='pt',device='cpu') as tensors:
            for key in tensors.keys():
                self.assertIn('lora_',key);t=tensors.get_tensor(key);count+=t.numel()
                self.assertTrue(t.isfinite().all().item())
                if 'lora_B' in key:trained+=int(t.abs().max().item()>0)
        self.assertEqual(count,294912);self.assertGreater(trained,0)

    def test_known_control_inference_contains_only_sources(self):
        import json
        folder=OUT/'lora-pilot'
        for prefix in ['regression-core','fresh-test']:
            rows=[json.loads(s) for s in (folder/(prefix+'-input.jsonl')).read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(set(r)=={'id','source','prepared_source'} for r in rows))
            self.assertTrue(g.read(folder/(prefix+'-summary.json'))['adapter_reload_exact_output_parity'])
        self.assertTrue(g.read(folder/'fresh-test-summary.json')['test_already_inspected_not_blind'])

    def test_every_changed_core_verdict_has_output_identity_or_an_explicit_review(self):
        folder=OUT/'lora-pilot';review=g.read(META/'regression-core-meaning-decisions.json')
        changes=g.read(folder/'regression-core-changes.json')
        previous={r['id']:r for r in g.read(g.OUT/'lora-pilot/regression-core-candidate.json')}
        self.assertEqual({r['input']['id'] for r in changes},{r['id'] for r in review['entries']})
        self.assertEqual(review['changes_sha256'],g.sha(folder/'regression-core-changes.json'))
        changed={r['input']['id']:r for r in changes}
        for r in review['entries']:
            if r['reused_verdict_by_exact_output_identity']:
                self.assertEqual(changed[r['id']]['candidate'],previous[r['id']]['translation'])
                self.assertEqual(changed[r['id']]['input']['source'],previous[r['id']]['source'])
        self.assertEqual(sum(r['before'] in ['incorrect','incomplete'] and r['after']=='acceptable' for r in review['entries']),9)
        self.assertEqual(sum(r['before']=='acceptable' and r['after'] in ['incorrect','incomplete'] for r in review['entries']),2)

    def test_validation_scores_are_bound_to_reviewed_outputs_and_not_app_accuracy(self):
        folder=OUT/'lora-pilot';review=g.read(META/'validation-meaning-decisions.json')
        self.assertEqual(review['candidate_outputs_sha256'],g.sha(folder/'candidate-validation.json'))
        self.assertEqual((review['baseline_confirmed_content_errors'],review['candidate_confirmed_content_errors']),(5,3))
        self.assertFalse(review['ready_for_application']);self.assertIsNone(review['screen_attempt_failure_probability'])

    def test_original_and_test_pixel_proofs_still_match_the_saved_images(self):
        old=g.read(g.OLD_META/'approved-pairs.json');proposals={r['id']:r for r in g.read(g.OLD_OUT/'review-selection.json')}
        current=g.read(g.META/'fresh-test-labels.json');new={r['id']:r for r in g.read(g.OUT/'fresh-test/review-selection.json')}
        for labels,selection in [(old['entries'],proposals),(current['entries'],new)]:
            for r in labels:
                if not r.get('approved',True):continue
                p=selection[r['id']]
                for key in ['source_image','reference_image']:self.assertEqual(g.sha(p[key]['path']),p[key]['sha256'])
        self.assertEqual(current['test_protocol_sha256'],g.sha(g.META/'fresh-test-protocol.json'))
        self.assertEqual(current['selection_sha256'],g.sha(g.OUT/'fresh-test/review-selection.json'))


if __name__=='__main__':unittest.main()
