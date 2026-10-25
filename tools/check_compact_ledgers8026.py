"""Round-trip all124 existing word ledgers without writing duplicate corpora."""
import json
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from compare_full_comics import compact_ledger_row


def main():
    chapters=0;words=0;before_bytes=0;after_bytes=0;proofs=[]
    for number in range(1,125):
        chapter=f'absolute-regression-{number:02d}'
        meta=QA/'comparison'/(chapter+'.json');ledger=meta.with_name(chapter+'.words.jsonl')
        state=read(meta);old=records(ledger)
        english_path=QA/state['english_report_directory']/(chapter+'-en.jsonl')
        spanish_path=QA/'ocr-es'/(chapter+'-es.jsonl')
        english=records(english_path);spanish=records(spanish_path)
        compact=[compact_ledger_row(r) for r in old]
        for original,row in zip(old,compact):
            reference=spanish[row['reference_region']];index=row['luma_region'];source=english[index] if index is not None else None
            restored=dict(row,reference_image=reference['image'],reference_bounds=reference['bounds'],
                reference_text=reference['source'],reference_native_text=reference['native_source'],
                reference_reading_human_verified=False,artwork_alignment_human_verified=False,
                luma_image=source['image'] if source else None,luma_bounds=source['bounds'] if source else None,
                source=source['source'] if source else None,translation=source.get('translation') if source else None)
            assert original==restored,(chapter,row['reference_region'],row['word_index'])
        chapters+=1;words+=len(old);before_bytes+=ledger.stat().st_size
        after_bytes+=sum(len((json.dumps(r,ensure_ascii=False)+'\n').encode('utf-8')) for r in compact)
        proofs.append(dict(chapter=chapter,ledger_sha256=digest(ledger),english_sha256=digest(english_path),spanish_sha256=digest(spanish_path)))
    result=dict(chapters=chapters,reference_words=words,roundtrip_mismatches=0,words_dropped=0,
                explicit_ledger_bytes=before_bytes,compact_ledger_bytes=after_bytes,
                projected_bytes_avoided_per_equivalent_pass=before_bytes-after_bytes,
                projected_reduction_percent=100*(before_bytes-after_bytes)/before_bytes,
                existing_evidence_deleted=False,already_freed_disk_bytes=0,proofs=proofs,
                script_sha256=digest(ROOT/'tools/check_compact_ledgers8026.py'),writer_sha256=digest(ROOT/'tools/compare_full_comics.py'),
                semantic_accuracy=None,all_words_visually_reviewed=False)
    assert chapters==124
    atomic(QA/'compact-ledger8026-validation.json',json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='proofs'}),flush=True)


if __name__=='__main__':main()
