"""Validate real label provenance, packing, split isolation and frozen execution."""
from train_opus_lora8031 import ROOT,OUT as OLD_OUT,META as OLD_META,read,sha,normalized,prepare_source

META=ROOT/'benchmarks/finetune8032'
OUT=ROOT/'build/finetune8032'


def validate_dataset(data,tokenizer):
    protocol=read(META/'protocol.json');old=read(OLD_META/'approved-pairs.json')
    inventory=read(OLD_META/'sources.json');curation=read(OLD_META/'expansion-curation.json')
    proposals={r['id']:r for r in read(OLD_OUT/'expansion-v1/review-selection.json')}
    assert data['proofs']==dict(previous_approved_sha256=sha(OLD_META/'approved-pairs.json'),
        expansion_selection_sha256=sha(OLD_OUT/'expansion-v1/review-selection.json'),
        expansion_curation_sha256=sha(OLD_META/'expansion-curation.json'),protocol_sha256=sha(META/'protocol.json'))
    expected={r['id']:dict(r,origin='8031-pixel-reviewed-original',prepared_source=prepare_source(r['source']))
              for r in old['entries'] if r['approved'] and r['split']=='train'}
    for ident,source,target in curation['approved']:
        p=proposals[ident]
        assert p['split']=='train' and p['chapter'] in inventory['assignments']['train']
        for key in ['source_image','reference_image']:assert sha(p[key]['path'])==p[key]['sha256']
        expected[10000+ident]=dict(id=10000+ident,proposal_id=ident,origin='8031-expansion-v1-pixel-reviewed',chapter=p['chapter'],split='train',
            source=source,target=target,prepared_source=prepare_source(source),approved=True,source_pixels_visually_verified=True,
            target_pixels_visually_verified=True,artwork_alignment_verified=True,complete_dialogue_meaning_verified=True,
            annotation_note=curation['annotation_notes'].get(str(ident)),source_page_sha256=p['source_image']['sha256'],reference_page_sha256=p['reference_image']['sha256'])
    originals=data['original_training'];packs=data['packed_training'];validation=data['validation']
    assert len(originals)==len(expected)==86
    assert {r['id']:r for r in originals}==expected
    expected_validation=[dict(r,origin='8031-fixed-validation',prepared_source=prepare_source(r['source']))
                         for r in old['entries'] if r['approved'] and r['split']=='validation']
    assert validation==expected_validation
    assert not data['test_rows_present'] and not data['validation_targets_used_in_training']
    heldout={normalized(r['source']) for r in old['entries'] if r['approved'] and r['split']!='train'}
    all_ids=set();sources=set()
    for r in originals+packs:
        assert r['split']=='train' and r['chapter'] in inventory['assignments']['train']
        assert r['id'] not in all_ids;all_ids.add(r['id'])
        key=normalized(r['source']);assert key not in heldout and key not in sources;sources.add(key)
        assert r['source'].strip() and r['target'].strip() and r['prepared_source']==prepare_source(r['source'])
        assert len(tokenizer(r['prepared_source'])['input_ids'])<=protocol['max_source_tokens']
        assert len(tokenizer(text_target=r['target'])['input_ids'])<=protocol['max_target_tokens']
    for r in packs:
        ids=r['member_ids'];assert len(ids) in [2,3] and len(set(ids))==len(ids) and all(i in expected for i in ids)
        members=[expected[i] for i in ids]
        assert {m['chapter'] for m in members}=={r['chapter']}
        assert all(m['source'].rstrip().endswith(('.','!','?')) and not m['source'].rstrip().endswith('...') for m in members)
        assert r['source']==' '.join(m['source'] for m in members)
        assert r['target']==' '.join(m['target'] for m in members)
        assert r['assumes_same_speaker'] is False and r['source_and_target_are_exact_ordered_concatenations'] is True
    assert data['counts']==dict(original_training=86,packed_training=len(packs),total_training=86+len(packs),validation=14)
    assert not {r['chapter'] for r in originals}&{r['chapter'] for r in validation}
    return originals+packs,validation


def validate_checkpoint():
    folder=OUT/'lora-pilot';proof=read(folder/'run-input-proof.json');summary=read(folder/'summary.json')
    assert proof['dataset_sha256']==sha(META/'dataset.json')
    assert proof['protocol_sha256']==sha(META/'protocol.json')
    assert proof['execution_script_sha256']==sha(ROOT/'tools/train_opus_lora8032.py')
    assert proof['shared_training_helpers_sha256']==sha(ROOT/'tools/train_opus_lora8031.py')
    assert proof['base_provenance_sha256']==sha(OLD_OUT/'base-model-provenance.json')
    assert summary['frozen_base_sha256_before']==summary['frozen_base_sha256_after']
    assert summary['adapter_sha256']==sha(folder/'adapter/adapter_model.safetensors')
    assert summary['actual_weight_training_completed'] and not summary['application_weights_modified']
    assert not summary['test_evaluation_performed'] and not proof['test_answers_loaded']
    log=read(folder/'training-log.json');protocol=read(META/'protocol.json')
    assert [r['step'] for r in log]==list(range(1,protocol['optimizer_steps']+1))
    assert all(set(r['training_sample_ids'])<=set(proof['train_ids']) for r in log)
    assert not set(proof['train_ids'])&set(proof['validation_ids'])
    return summary
