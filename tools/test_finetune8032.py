"""Leakage and provenance guards for the second trained adapter."""
import copy
import unittest
from safetensors import safe_open
from transformers import MarianTokenizer
import finetune8032_guards as g


class Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=g.read(g.META/'dataset.json')
        cls.tokenizer=MarianTokenizer.from_pretrained(g.OLD_OUT/'base-model',local_files_only=True)

    def rejects(self,change):
        data=copy.deepcopy(self.data);change(data)
        with self.assertRaises(AssertionError):g.validate_dataset(data,self.tokenizer)

    def test_original_and_packed_examples_have_verified_provenance(self):
        training,val=g.validate_dataset(self.data,self.tokenizer)
        self.assertEqual((len(training),len(val)),(216,14))

    def test_validation_cannot_be_used_for_gradients(self):
        self.rejects(lambda d:d['original_training'].__setitem__(0,dict(d['validation'][0],split='train')))

    def test_invented_reference_cannot_replace_a_pixel_label(self):
        self.rejects(lambda d:d['original_training'][0].update(target='A plausible but invented reference.'))

    def test_unverified_pixels_cannot_be_accepted(self):
        self.rejects(lambda d:d['original_training'][0].update(source_pixels_visually_verified=False))

    def test_packs_cannot_invent_or_drop_a_word(self):
        self.rejects(lambda d:d['packed_training'][0].update(target=d['packed_training'][0]['target']+' Inventado.'))

    def test_packs_cannot_mention_validation_members(self):
        self.rejects(lambda d:d['packed_training'][0]['member_ids'].__setitem__(0,d['validation'][0]['id']))

    def test_packs_cannot_assume_one_speaker(self):
        self.rejects(lambda d:d['packed_training'][0].update(assumes_same_speaker=True))

    def test_oversized_input_cannot_be_silently_truncated(self):
        self.rejects(lambda d:d['packed_training'][0].update(source='Too long. '*1000))

    def test_duplicate_sources_cannot_inflate_the_dataset(self):
        self.rejects(lambda d:d['packed_training'].__setitem__(1,copy.deepcopy(d['packed_training'][0])))

    def test_checkpoint_proves_only_training_ids_received_gradients(self):
        self.assertEqual(g.validate_checkpoint()['optimizer_steps'],160)

    def test_adapter_contains_finite_learned_weights(self):
        count=0;nonzero=0
        with safe_open(g.OUT/'lora-pilot/adapter/adapter_model.safetensors',framework='pt',device='cpu') as f:
            for name in f.keys():
                self.assertIn('lora_',name);t=f.get_tensor(name);count+=t.numel()
                self.assertTrue(t.isfinite().all().item())
                if 'lora_B' in name:nonzero+=int(t.abs().max().item()>0)
        self.assertEqual(count,294912);self.assertGreater(nonzero,0)

    def test_validation_fixes_are_content_and_not_app_accuracy(self):
        d=g.read(g.META/'validation-meaning-decisions.json');rows=d['entries']
        self.assertEqual(sum(r['before'] in ['incorrect','incomplete'] and r['after']=='acceptable' for r in rows),2)
        self.assertEqual(sum(r['before']=='acceptable' and r['after'] in ['incorrect','incomplete'] for r in rows),0)
        self.assertIsNone(d['screen_attempt_failure_probability']);self.assertFalse(d['ready_for_application'])

    def test_new_test_was_frozen_for_the_specific_adapter(self):
        p=g.read(g.META/'fresh-test-protocol.json');summary=g.validate_checkpoint()
        self.assertEqual(p['adapter_sha256'],summary['adapter_sha256'])
        self.assertFalse(p['training_allowed']);self.assertTrue(p['model_frozen_before_test'])
        self.assertFalse(set(p['selected_chapters'])&set(self.data['training_chapters']))

    def test_test_references_never_entered_generation_requests(self):
        folder=g.OUT/'lora-pilot';proof=g.read(folder/'fresh-test-summary.json')
        labels=g.read(g.META/'fresh-test-labels.json')
        self.assertEqual(proof['labels_sha256'],g.sha(g.META/'fresh-test-labels.json'))
        self.assertEqual(len(labels['entries']),16)
        self.assertFalse(labels['training_allowed']);self.assertFalse(labels['model_answers_used_for_annotation'])
        import json
        requests=[json.loads(s) for s in (folder/'fresh-test-input.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertTrue(all(set(r)=={'id','source','prepared_source'} for r in requests))
        self.assertFalse({g.normalized(r['source']) for r in labels['entries']}&{g.normalized(r['source']) for r in self.data['original_training']+self.data['packed_training']})

    def test_meaning_review_covers_every_changed_old_core_output(self):
        changed=g.read(g.OUT/'lora-pilot/regression-core-changes.json')
        review=g.read(g.META/'regression-core-meaning-decisions.json')
        self.assertEqual({r['input']['id'] for r in changed},{r['id'] for r in review['entries']})
        self.assertEqual(g.sha(g.OUT/'lora-pilot/regression-core-changes.json'),review['changes_sha256'])
        self.assertEqual(sum(r['before'] in ['incorrect','incomplete'] and r['after']=='acceptable' for r in review['entries']),12)
        self.assertEqual(sum(r['before']=='acceptable' and r['after'] in ['incorrect','incomplete'] for r in review['entries']),3)

    def test_partial_greeting_recovery_is_not_a_complete_usable_fix(self):
        d=g.read(g.META/'fresh-test-meaning-decisions.json')
        self.assertEqual(next(r for r in d['entries'] if r['id']==5)['after'],'quality_defect')
        self.assertEqual(d['complete_usable_dialogue_corrections'],1)
        self.assertEqual(d['partial_content_recoveries_without_complete_approval'],1)
        self.assertFalse(d['app_modified']);self.assertIsNone(d['screen_attempt_failure_probability'])


if __name__=='__main__':unittest.main()
