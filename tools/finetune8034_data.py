"""Build and validate reviewed expanded labels; never use evaluation answers in loss."""
import math
from transformers import MarianTokenizer
import finetune8032_guards as previous
from train_opus_lora8031 import ROOT,OUT as BASE,read,sha,write,normalized,prepare_source

META=ROOT/'benchmarks/finetune8034';OUT=ROOT/'build/finetune8034'


def known_evaluation_keys():
    old=read(ROOT/'benchmarks/finetune8031/approved-pairs.json')
    recent=read(ROOT/'benchmarks/finetune8032/fresh-test-labels.json')
    core=read(ROOT/'build/finetune8031/lora-pilot/regression-core-baseline.json')
    return {normalized(r['source']) for r in old['entries'] if r['approved'] and r['split']!='train'}|{normalized(r['source']) for r in recent['entries']+core}


def expected_originals(tokenizer):
    config=read(META/'data-protocol.json');protocol=read(META/'training-protocol.json')
    assert config['source_inventory_sha256']==sha(ROOT/'benchmarks/finetune8031/sources.json')
    assert config['previous_dataset_sha256']==sha(previous.META/'dataset.json')
    assert protocol['data_protocol_sha256']==sha(META/'data-protocol.json')
    old=read(previous.META/'dataset.json');previous.validate_dataset(old,tokenizer)
    selection=read(OUT/'review-selection.json');by={r['id']:r for r in selection};curation=read(META/'curation.json')
    assert curation['selection_sha256']==sha(OUT/'review-selection.json')
    assert curation['all_selected_proposals_reviewed'] and not curation['model_answers_used_for_annotation']
    approved_ids={r[0] for r in curation['approved']};rejected_ids={r['id'] for r in curation['excluded']}
    assert not approved_ids&rejected_ids and approved_ids|rejected_ids==set(by)
    training=[dict(r) for r in old['original_training']]
    validation=[dict(r,validation_group='known') for r in old['validation']]
    used={normalized(r['source']) for r in training+validation};blocked=known_evaluation_keys();excluded=[]
    for ident,source,target in curation['approved']:
        p=by[ident];split=p['split'];assert split in ['train','validation']
        assert p['chapter'] in config['selected_chapters'][split]
        assert source.strip() and target.strip()
        for key in ['source_image','reference_image']:assert sha(p[key]['path'])==p[key]['sha256']
        key=normalized(source)
        if key in used or key in blocked:
            excluded.append(dict(proposal_id=ident,reason='Source duplicates a previous reviewed label or known evaluation source; never move it into training'));continue
        prepared=prepare_source(source)
        assert len(tokenizer(prepared)['input_ids'])<=protocol['max_source_tokens']
        assert len(tokenizer(text_target=target)['input_ids'])<=protocol['max_target_tokens']
        used.add(key)
        row=dict(id=(200000 if split=='train' else 400000)+ident,proposal_id=ident,chapter=p['chapter'],split=split,source=source,target=target,
            prepared_source=prepared,origin='8034-pixel-reviewed',source_pixels_visually_verified=True,target_pixels_visually_verified=True,
            artwork_alignment_verified=True,complete_dialogue_meaning_verified=True,annotation_note=curation['annotation_notes'].get(str(ident)),
            source_page_sha256=p['source_image']['sha256'],reference_page_sha256=p['reference_image']['sha256'])
        if split=='train':training.append(row)
        else:validation.append(dict(row,validation_group='new'))
    assert len(training)-len(old['original_training'])>=protocol['minimum_new_pixel_reviewed_training_pairs']
    assert sum(r['validation_group']=='new' for r in validation)>=protocol['minimum_new_validation_pairs']
    assert not {r['chapter'] for r in training}&{r['chapter'] for r in validation}
    return training,validation,excluded


def packs(training,validation,tokenizer):
    protocol=read(META/'training-protocol.json');blocked=known_evaluation_keys()|{normalized(r['source']) for r in validation}
    used={normalized(r['source']) for r in training};result=[];oversized=[]
    for chapter in sorted({r['chapter'] for r in training}):
        group=[r for r in training if r['source'].rstrip().endswith(('.','!','?')) and not r['source'].rstrip().endswith('...')]
        for i in range(len(group)):
            for size,offset in [(2,3),(3,5)]:
                members=[group[(i+j*offset)%len(group)] for j in range(size)]
                if len({r['id'] for r in members})!=size:continue
                source=' '.join(r['source'] for r in members);target=' '.join(r['target'] for r in members);prepared=prepare_source(source)
                if len(tokenizer(prepared)['input_ids'])>protocol['max_source_tokens'] or len(tokenizer(text_target=target)['input_ids'])>protocol['max_target_tokens']:
                    oversized.append([r['id'] for r in members]);continue
                key=normalized(source)
                if key in used or key in blocked:continue
                used.add(key);result.append(dict(id=3000000+len(result),chapter=chapter,split='train',source=source,target=target,
                    prepared_source=prepared,origin='independent_complete_sentence_packing',member_ids=[r['id'] for r in members],assumes_same_speaker=False))
    return result,oversized


def validate_dataset(data,tokenizer):
    training,validation,excluded=expected_originals(tokenizer)
    assert data['original_training']==training and data['validation']==validation
    packed,oversized=packs(training,validation,tokenizer)
    assert data['packed_training']==packed and data['skipped_oversized_packs']==oversized
    assert data['excluded_duplicate_sources']==excluded
    assert data['proofs']==dict(previous_dataset_sha256=sha(previous.META/'dataset.json'),data_protocol_sha256=sha(META/'data-protocol.json'),
        training_protocol_sha256=sha(META/'training-protocol.json'),curation_sha256=sha(META/'curation.json'),selection_sha256=sha(OUT/'review-selection.json'))
    ids=[r['id'] for r in training+packed+validation];assert len(ids)==len(set(ids))
    assert all(r['split']=='train' for r in training+packed)
    assert not data['evaluation_examples_used_for_training'] and not data['new_blind_test_chapters_opened']
    assert data['optimizer_steps']==math.ceil(160*(len(training)+len(packed))/216/8)*8
    return training+packed,validation


def main():
    tokenizer=MarianTokenizer.from_pretrained(BASE/'base-model',local_files_only=True)
    training,validation,excluded=expected_originals(tokenizer);packed,oversized=packs(training,validation,tokenizer)
    value=dict(schema=1,original_training=training,packed_training=packed,validation=validation,
        excluded_duplicate_sources=excluded,skipped_oversized_packs=oversized,
        optimizer_steps=math.ceil(160*(len(training)+len(packed))/216/8)*8,
        proofs=dict(previous_dataset_sha256=sha(previous.META/'dataset.json'),data_protocol_sha256=sha(META/'data-protocol.json'),
            training_protocol_sha256=sha(META/'training-protocol.json'),curation_sha256=sha(META/'curation.json'),selection_sha256=sha(OUT/'review-selection.json')),
        counts=dict(original_training=len(training),new_original_training=len(training)-86,packed_training=len(packed),validation_known=14,
            validation_new=sum(r['validation_group']=='new' for r in validation)),evaluation_examples_used_for_training=False,new_blind_test_chapters_opened=0)
    validate_dataset(value,tokenizer);p=META/'dataset.json';assert not p.exists();write(p,value)
    import json
    print(json.dumps(dict(**value['counts'],optimizer_steps=value['optimizer_steps'],known_evaluation_leakage=False)),flush=True)


if __name__=='__main__':main()
