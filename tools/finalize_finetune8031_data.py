"""Bind every reviewed transcription to its unchanged bilingual pixel proposal."""
import collections
import json
import re
import unicodedata
from prepare_finetune8031 import OUT,META,sha,save


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def identity(p):return (p['chapter'],p['split'],p['english_page'],p['spanish_page'],tuple(p['source_bounds']),tuple(p['reference_bounds']),p['source_ocr'],p['target_ocr'])
def normal(s):return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',s).casefold()))


def main():
    final=read(OUT/'review-selection.json');by_identity={identity(r):r for r in final};entries={};proofs=[]
    filenames=['curation-partial.json','curation-train-final.json','curation-test-partial.json','curation-validation.json']
    for filename in filenames:
        path=META/filename;decisions=read(path);selection=OUT.parent.parent/decisions['selection']
        # selection is project-relative, not relative to this output directory.
        from prepare_finetune8031 import ROOT
        selection=ROOT/decisions['selection'];proposals={r['id']:r for r in read(selection)}
        assert decisions['reviewer']=='assistant_visual_pixel_review'
        corrections={r['id']:r['note'] for r in decisions.get('target_faithfulness_corrections',[])}
        for ident,source,target in decisions['approved']:
            original=proposals[ident];r=by_identity[identity(original)];assert r['id'] not in entries
            assert r['id']==ident,'An id changed: require explicit verified mapping, never silently reuse a label'
            entries[ident]=dict(id=ident,chapter=r['chapter'],split=r['split'],source=source,target=target,approved=True,
                source_pixels_visually_verified=True,target_pixels_visually_verified=True,artwork_alignment_verified=True,
                complete_dialogue_meaning_verified=True,source_normalized_from_complete_photographed_balloon=True,
                target_faithfulness_correction=corrections.get(ident),review_file=filename,
                source_page_sha256=r['source_image']['sha256'],reference_page_sha256=r['reference_image']['sha256'])
        proofs.append(dict(path=filename,sha256=sha(path),selection_sha256=sha(selection)))
    for r in final:
        if r['id'] not in entries:entries[r['id']]=dict(id=r['id'],chapter=r['chapter'],split=r['split'],approved=False,reason='Excluded by pixel/meaning review; see curation records')
    seen={};duplicates=[]
    for r in entries.values():
        if not r['approved']:continue
        key=normal(r['source'])
        if key in seen:duplicates.append((r['id'],seen[key]))
        else:seen[key]=r['id']
    assert not duplicates,('Duplicate reviewed source across or within splits',duplicates)
    counts=collections.Counter(r['split'] for r in entries.values() if r['approved']);protocol=read(META/'protocol.json')
    for split,n in protocol['minimum_approved_pairs'].items():assert counts[split]>=n,(split,counts[split],n)
    value=dict(schema=1,reviewer='assistant_visual_pixel_review',review_selection_sha256=sha(OUT/'review-selection.json'),
        protocol_sha256=sha(META/'protocol.json'),curation_proofs=proofs,entries=sorted(entries.values(),key=lambda r:r['id']),
        approved_counts=dict(counts),excluded=len(final)-sum(counts.values()),source_duplicates=duplicates,
        all217_chapters_reviewed=False,reference_targets_may_include_documented_faithfulness_annotations=True,
        no_candidate_model_outputs_used_to_select_or_prepare_labels=True,test_targets_allowed_in_training=False)
    save(META/'approved-pairs.json',value)
    print(json.dumps(dict(approved=dict(counts),excluded=value['excluded'],duplicates=len(duplicates),production_modified=False)),flush=True)


if __name__=='__main__':main()
