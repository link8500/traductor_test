"""Expand supervised labels and pack only reviewed independent train sentences."""
import collections
import hashlib
import json
import pathlib
import re
from transformers import MarianTokenizer
from train_opus_lora8031 import ROOT,OUT as PREVIOUS,META as OLD_META,read,sha,write,normalized,prepare_source

OUT=ROOT/'build/finetune8032';META=ROOT/'benchmarks/finetune8032'


def main():
    OUT.mkdir(exist_ok=True);protocol=read(META/'protocol.json')
    tokenizer=MarianTokenizer.from_pretrained(PREVIOUS/'base-model',local_files_only=True)
    old=read(OLD_META/'approved-pairs.json');selection=PREVIOUS/'expansion-v1/review-selection.json'
    proposed={r['id']:r for r in read(selection)};curation=read(OLD_META/'expansion-curation.json')
    assert len(proposed)==60 and len(curation['approved'])+len(curation['excluded'])==60
    training=[dict(r,origin='8031-pixel-reviewed-original') for r in old['entries'] if r['approved'] and r['split']=='train']
    validation=[dict(r,origin='8031-fixed-validation') for r in old['entries'] if r['approved'] and r['split']=='validation']
    source_inventory=read(OLD_META/'sources.json');train_chapters=set(source_inventory['assignments']['train'])
    for ident,source,target in curation['approved']:
        p=proposed[ident];assert p['split']=='train' and p['chapter'] in train_chapters
        assert sha(p['source_image']['path'])==p['source_image']['sha256'] and sha(p['reference_image']['path'])==p['reference_image']['sha256']
        training.append(dict(id=10000+ident,proposal_id=ident,origin='8031-expansion-v1-pixel-reviewed',chapter=p['chapter'],split='train',
            source=source,target=target,approved=True,source_pixels_visually_verified=True,target_pixels_visually_verified=True,
            artwork_alignment_verified=True,complete_dialogue_meaning_verified=True,annotation_note=curation['annotation_notes'].get(str(ident)),
            source_page_sha256=p['source_image']['sha256'],reference_page_sha256=p['reference_image']['sha256']))
    assert len(training)==86 and len(validation)==14
    keys=set();heldout={normalized(r['source']) for r in validation}
    for r in training:
        key=normalized(r['source']);assert key not in keys and key not in heldout;keys.add(key)
        r['prepared_source']=prepare_source(r['source'])
        assert len(tokenizer(r['prepared_source'])['input_ids'])<=192 and len(tokenizer(text_target=r['target'])['input_ids'])<=192
    for r in validation:r['prepared_source']=prepare_source(r['source'])
    packed=[];skipped=[]
    def complete(r):return r['source'].rstrip().endswith(('.','!','?')) and not r['source'].rstrip().endswith('...')
    for chapter in sorted({r['chapter'] for r in training}):
        group=[r for r in training if r['chapter']==chapter and complete(r)]
        for i,first in enumerate(group):
            for size,offset in [(2,3),(3,5)]:
                members=[group[(i+j*offset)%len(group)] for j in range(size)]
                if len({r['id'] for r in members})!=size:continue
                source=' '.join(r['source'] for r in members);target=' '.join(r['target'] for r in members);prepared=prepare_source(source)
                if len(tokenizer(prepared)['input_ids'])>192 or len(tokenizer(text_target=target)['input_ids'])>192:
                    skipped.append(dict(member_ids=[r['id'] for r in members],reason='Full sequence exceeds token budget; never truncate'));continue
                key=normalized(source)
                if key in keys or key in heldout:continue
                keys.add(key);packed.append(dict(id=1000000+len(packed),chapter=chapter,split='train',origin='documented_independent_sentence_packing',
                    source=source,target=target,prepared_source=prepared,member_ids=[r['id'] for r in members],
                    assumes_same_speaker=False,source_and_target_are_exact_ordered_concatenations=True))
    value=dict(schema=1,reviewer='assistant_visual_pixel_review',original_training=training,packed_training=packed,validation=validation,
        proofs=dict(previous_approved_sha256=sha(OLD_META/'approved-pairs.json'),expansion_selection_sha256=sha(selection),
            expansion_curation_sha256=sha(OLD_META/'expansion-curation.json'),protocol_sha256=sha(META/'protocol.json')),
        counts=dict(original_training=len(training),packed_training=len(packed),total_training=len(training)+len(packed),validation=len(validation)),
        skipped_oversized_packs=skipped,training_chapters=sorted({r['chapter'] for r in training}),
        test_rows_present=False,validation_targets_used_in_training=False,all217_chapters_reviewed=False)
    path=META/'dataset.json';assert not path.exists(),'Do not overwrite a frozen dataset';write(path,value)
    print(json.dumps(dict(**value['counts'],heldout_leakage=False,all_source_duplicates_removed=True)),flush=True)


if __name__=='__main__':main()
