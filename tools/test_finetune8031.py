"""Data-leakage, label-provenance and actual trained-artifact guards."""
import copy
import json
import math
import pathlib
import unittest
from unittest.mock import patch
from safetensors import safe_open
from transformers import MarianTokenizer
import train_opus_lora8031 as pilot


class PilotGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol=pilot.read(pilot.META/'protocol.json')
        cls.data=pilot.read(pilot.META/'approved-pairs.json')
        cls.tokenizer=MarianTokenizer.from_pretrained(pilot.OUT/'base-model',local_files_only=True)

    def validate_mutation(self,fn):
        value=copy.deepcopy(self.data);fn(value);original=pilot.read
        def fake(p):return value if pathlib.Path(p).name=='approved-pairs.json' else original(p)
        with patch.object(pilot,'read',side_effect=fake):
            with self.assertRaises(AssertionError):pilot.validate_data(self.protocol,self.tokenizer)

    def test_approved_data_has_disjoint_chapters_and_sources(self):
        sets=pilot.validate_data(self.protocol,self.tokenizer)
        self.assertEqual({k:len(v) for k,v in sets.items()},{'train':35,'validation':14,'test':13})
        self.assertFalse({r['chapter'] for r in sets['train']}&{r['chapter'] for r in sets['test']+sets['validation']})
        self.assertEqual(len({pilot.normalized(r['source']) for rs in sets.values() for r in rs}),62)

    def test_test_pair_cannot_be_moved_into_training(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==50).update(split='train'))

    def test_wrong_chapter_cannot_reuse_an_approved_label(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==5).update(chapter=8))

    def test_unverified_reference_is_rejected(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==5).update(target_pixels_visually_verified=False))

    def test_duplicate_source_cannot_cross_splits(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==50).update(source=next(r['source'] for r in d['entries'] if r['id']==5)))

    def test_missing_target_is_rejected(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==5).update(target=''))

    def test_long_source_is_rejected_instead_of_silently_truncated(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==5).update(source='This text exceeds the length. '*500))

    def test_long_target_is_rejected_instead_of_silently_truncated(self):
        self.validate_mutation(lambda d:next(r for r in d['entries'] if r['id']==5).update(target='Este texto supera el límite. '*500))

    def test_changed_image_pixels_invalidate_the_review(self):
        original=pilot.sha
        with patch.object(pilot,'sha',side_effect=lambda p:'0'*64 if pathlib.Path(p).suffix in ['.jpg','.webp'] else original(p)):
            with self.assertRaises(AssertionError):pilot.validate_data(self.protocol,self.tokenizer)

    def test_curation_sources_are_pinned_and_faithfulness_edits_are_explicit(self):
        for proof in self.data['curation_proofs']:
            self.assertEqual(pilot.sha(pilot.META/proof['path']),proof['sha256'])
        corrected={r['id'] for r in self.data['entries'] if r.get('target_faithfulness_correction')}
        self.assertEqual(corrected,{114,119,121,124,149})

    def test_actual_adapter_contains_learned_finite_lora_weights(self):
        folder=pilot.OUT/'lora-pilot';summary=pilot.read(folder/'summary.json')
        path=folder/'adapter/adapter_model.safetensors'
        self.assertEqual(pilot.sha(path),summary['trained_adapter_sha256'])
        count=0;nonzero_b=0
        with safe_open(path,framework='pt',device='cpu') as tensors:
            for name in tensors.keys():
                self.assertIn('lora_',name);tensor=tensors.get_tensor(name);count+=tensor.numel()
                self.assertTrue(tensor.isfinite().all().item())
                if 'lora_B' in name:nonzero_b+=int(tensor.abs().max().item()>0)
        self.assertEqual(count,294912);self.assertGreater(nonzero_b,0)
        self.assertEqual(summary['frozen_base_sha256_before'],summary['frozen_base_sha256_after'])
        self.assertFalse(summary['application_weights_modified'])

    def test_training_run_pins_data_protocol_and_executed_script(self):
        proof=pilot.read(pilot.OUT/'lora-pilot/run-input-proof.json')
        self.assertEqual(proof['dataset_sha256'],pilot.sha(pilot.META/'approved-pairs.json'))
        self.assertEqual(proof['protocol_sha256'],pilot.sha(pilot.META/'protocol.json'))
        self.assertEqual(proof['execution_script_sha256'],pilot.sha(pilot.__file__))
        self.assertEqual(proof['labels_used_for_backpropagation'],['train'])
        log=pilot.read(pilot.OUT/'lora-pilot/training-log.json')
        self.assertEqual([r['step'] for r in log],list(range(1,41)))
        self.assertTrue(all(math.isfinite(r['training_loss']) for r in log))

    def test_heldout_outputs_have_only_source_generation_fields(self):
        folder=pilot.OUT/'lora-pilot'
        for name in ['baseline-heldout.json','candidate-heldout.json']:
            outputs=pilot.read(folder/name)
            for split in ['validation','test']:
                expected={r['id'] for r in self.data['entries'] if r['approved'] and r['split']==split}
                self.assertEqual({r['id'] for r in outputs[split]},expected)
                self.assertTrue(all(set(r)=={'id','source','prepared_source','translation'} for r in outputs[split]))

    def test_meaning_scores_do_not_count_filler_as_a_fix(self):
        decisions=pilot.read(pilot.META/'heldout-meaning-decisions.json');a=decisions['validation']+decisions['test']
        corrected=sum(r['before']!='acceptable' and r['after']=='acceptable' for r in a)
        lost=sum(r['before']=='acceptable' and r['after']!='acceptable' for r in a)
        self.assertEqual((corrected,lost),(0,1))
        self.assertEqual(decisions['complete_content_corrections'],corrected)
        self.assertEqual(decisions['new_content_losses'],lost)
        self.assertFalse(decisions['pilot_supports_replacing_the_app_model'])
        self.assertIsNone(decisions['screen_attempt_failure_probability'])

    def test_old_core_diagnostic_cannot_be_presented_as_production_app_accuracy(self):
        folder=pilot.OUT/'lora-pilot';value=pilot.read(folder/'regression-core-summary.json')
        self.assertEqual((value['regression_regions'],value['regression_saved_views']),(229,124))
        self.assertTrue(value['adapter_reload_exact_output_parity'])
        self.assertFalse(value['production_app_error_rate_comparable'])
        changes=pilot.read(folder/'regression-core-changes.json');decisions=pilot.read(pilot.META/'regression-core-meaning-decisions.json')
        self.assertEqual({r['input']['id'] for r in changes},{r['id'] for r in decisions['entries']})
        self.assertEqual(len(changes),22)
        self.assertEqual(sum(r['before']!='acceptable' and r['after']=='acceptable' for r in decisions['entries']),5)
        self.assertEqual(sum(r['before']=='acceptable' and r['after']!='acceptable' for r in decisions['entries']),2)


if __name__=='__main__':unittest.main()
