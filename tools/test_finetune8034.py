"""Guard expanded-data provenance, actual checkpoint integrity and evaluation isolation."""
import copy
import json
import math
import unittest
from unittest.mock import patch
from safetensors import safe_open
from transformers import MarianTokenizer
import finetune8034_data as data
from evaluate_opus_lora8034 import checkpoint


class ExpandedDataGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value=data.read(data.META/'dataset.json')
        cls.tokenizer=MarianTokenizer.from_pretrained(data.BASE/'base-model',local_files_only=True)

    def reject(self,fn):
        value=copy.deepcopy(self.value);fn(value)
        with self.assertRaises(AssertionError):data.validate_dataset(value,self.tokenizer)

    def test_expansion_has_real_new_training_and_validation_labels(self):
        train,val=data.validate_dataset(self.value,self.tokenizer)
        self.assertGreaterEqual(self.value['counts']['new_original_training'],40)
        self.assertGreaterEqual(self.value['counts']['validation_new'],10)
        self.assertFalse({r['chapter'] for r in train}&{r['chapter'] for r in val})

    def test_validation_cannot_be_moved_into_training(self):
        self.reject(lambda d:d['original_training'].__setitem__(0,dict(d['validation'][-1],split='train')))

    def test_plausible_invented_target_cannot_replace_approved_pixels(self):
        self.reject(lambda d:d['original_training'][-1].update(target='Una respuesta inventada y plausible.'))

    def test_unreviewed_english_cannot_be_accepted(self):
        self.reject(lambda d:d['original_training'][-1].update(source_pixels_visually_verified=False))

    def test_packing_cannot_reorder_target_sentences(self):
        self.reject(lambda d:d['packed_training'][0].update(target='This is not the exact reviewed ordered concatenation.'))

    def test_packs_cannot_assume_one_speaker(self):
        self.reject(lambda d:d['packed_training'][0].update(assumes_same_speaker=True))

    def test_duplicate_examples_cannot_inflate_counts(self):
        self.reject(lambda d:d['original_training'].append(copy.deepcopy(d['original_training'][0])))

    def test_mutated_image_bytes_invalidate_label_provenance(self):
        real=data.sha
        with patch.object(data,'sha',side_effect=lambda p:'0'*64 if str(p).lower().endswith(('.jpg','.webp')) else real(p)):
            with self.assertRaises(AssertionError):data.validate_dataset(self.value,self.tokenizer)

    def test_no_test_chapters_were_opened_for_this_expansion(self):
        p=data.read(data.META/'data-protocol.json');images=data.read(data.OUT/'images.json')
        inventory=data.read(data.ROOT/'benchmarks/finetune8031/sources.json')
        self.assertEqual(p['selected_chapters']['test'],[])
        self.assertFalse({r['chapter'] for r in images}&set(inventory['assignments']['test']))
        self.assertEqual(p['uninspected_test_chapters_remaining'],41)

    def test_training_step_rule_preserves_documented_exposure(self):
        n=len(self.value['original_training'])+len(self.value['packed_training'])
        self.assertEqual(self.value['optimizer_steps'],math.ceil(160*n/216/8)*8)

    def test_actual_checkpoint_received_only_training_gradients(self):
        folder,summary=checkpoint();proof=data.read(folder/'run-input-proof.json');logs=data.read(folder/'training-log.json')
        self.assertFalse(set(proof['training_ids'])&set(proof['validation_ids']))
        self.assertEqual([r['step'] for r in logs],list(range(1,self.value['optimizer_steps']+1)))
        self.assertTrue(all(set(r['training_sample_ids'])<=set(proof['training_ids']) for r in logs))
        self.assertTrue(all(math.isfinite(r['token_kl']) and r['token_kl']>=-1e-5 for r in logs))
        self.assertEqual(summary['initial_token_kl'],0)
        self.assertFalse(proof['evaluation_sources_and_targets_used_for_gradients'])

    def test_actual_saved_adapter_has_learned_finite_tensors(self):
        folder,summary=checkpoint();n=0;trained=0
        with safe_open(folder/'adapter/adapter_model.safetensors',framework='pt',device='cpu') as tensors:
            for key in tensors.keys():
                self.assertIn('lora_',key);t=tensors.get_tensor(key);n+=t.numel();self.assertTrue(t.isfinite().all().item())
                if 'lora_B' in key:trained+=int(t.abs().max().item()>0)
        self.assertEqual(n,294912);self.assertGreater(trained,0)

    def test_evaluation_generation_requests_contain_no_reference_answers(self):
        folder,_=checkpoint()
        for name in ['validation-source-only','regression-core','known-test','early-known-test']:
            rows=[json.loads(s) for s in (folder/(name+'-input.jsonl')).read_text(encoding='utf-8').splitlines()]
            self.assertTrue(all(set(r)=={'id','source','prepared_source'} for r in rows))

    def test_model_assets_installed_in_the_app_still_match_the_frozen_control(self):
        path=data.ROOT/'assets/models/opus-en-es/manifest.json';manifest=data.read(path)
        self.assertEqual(data.sha(path),data.read(data.ROOT/'build/full-comics/windows-engine803001.json')['manifest_sha256'])
        for name in ['encoder.onnx','decoder.onnx']:self.assertEqual(data.sha(path.parent/name),manifest['files'][name])

    def test_generation_collapse_is_detected_without_rejecting_valid_letters(self):
        from audit_generation8034 import issues
        self.assertIn('no_alphabetic_content_for_alphabetic_source',issues('A meaningful sentence.','¡'*160))
        self.assertIn('same_character_run_at_least32',issues('A meaningful sentence.','¡'*160))
        self.assertEqual(issues('HAHAHAHA!','¡Jajaja!'),[])
        self.assertEqual(issues('...','...'),[])

    def test_failed_generation_is_preserved_and_not_hidden_by_float32_diagnostic(self):
        folder,_=checkpoint();audit=data.read(folder/'generation-format-audit.json');diag=data.read(folder/'precision-diagnostic.json')
        self.assertEqual(len(audit['alerts']),1)
        self.assertTrue(diag['bfloat16_exact_reproduction']);self.assertTrue(diag['official_benchmark_outputs_unchanged'])
        self.assertFalse(any(c.isalpha() for c in diag['outputs']['original_bfloat16'][2]['translation']))
        self.assertFalse(any(c.isalpha() for c in diag['outputs']['diagnostic_float32'][2]['translation']))

    def test_semantic_review_covers_all_changed_core_outputs(self):
        folder,_=checkpoint();review=data.read(data.META/'regression-core-meaning-decisions.json')
        changes=data.read(folder/'regression-core-changes.json')
        self.assertEqual({r['input']['id'] for r in changes},{r['id'] for r in review['entries']})
        self.assertEqual(review['changes_sha256'],data.sha(folder/'regression-core-changes.json'))
        self.assertEqual(sum(r['before'] in ['incorrect','incomplete'] and r['after']=='acceptable' for r in review['entries']),11)

    def test_better_similarity_cannot_override_failed_quality_gates(self):
        from finetune8034_gates import assess
        protocol=data.read(data.META/'training-protocol.json');v=data.read(data.META/'validation-meaning-decisions.json')
        c=data.read(data.META/'regression-core-meaning-decisions.json');a=data.read(data.OUT/'lora-pilot/generation-format-audit.json')
        result=assess(protocol,v,c,a)
        self.assertFalse(result['all_predeclared_quality_gates_passed'])
        self.assertFalse(result['predeclared_checks']['new_validation_no_regressions'])
        self.assertFalse(result['ready_for_native_parity']);self.assertFalse(result['ready_for_installation'])
        self.assertIsNone(result['app_failure_probability'])


if __name__=='__main__':unittest.main()
