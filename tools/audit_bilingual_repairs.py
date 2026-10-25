"""Audit every sampled input after tightening OCR repair boundaries.

Reuse an earlier inference only when the prepared input is byte-identical and
the decoder implementation, tokenizer and model weights are unchanged. Record
that reuse explicitly; a preprocessor replay is not another OCR pass.
"""
import hashlib,json,pathlib,subprocess

ROOT=pathlib.Path(__file__).resolve().parents[1]
QA=ROOT/'build/bilingual-quality'
code=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
decoder=code[code.index('  std::string Generate('):code.index('LocalTranslationModel::LocalTranslationModel')]
decoder_hash=hashlib.sha256(decoder.encode()).hexdigest()
assert decoder_hash==(QA/'decoder-code-before-guard.sha256').read_text().strip(),'Decoder changed; run fresh inference for the corpus'
manifest=(ROOT/'assets/models/opus-en-es/manifest.json').read_bytes()
engine=hashlib.sha256(manifest+code.encode()).hexdigest()
process=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),str(ROOT/'assets/models/opus-en-es')],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)


def call(value):
    process.stdin.write(json.dumps(value,ensure_ascii=False)+'\n');process.stdin.flush()
    line=process.stdout.readline()
    if not line:raise RuntimeError(process.stderr.read())
    result=json.loads(line)
    assert 'error' not in result,result
    return result


reports={}
try:
    for size in ['mobile','desktop']:
        baseline=[json.loads(line) for line in (QA/f'{size}-translations.jsonl').read_text(encoding='utf-8').splitlines()]
        previous=[json.loads(line) for line in (QA/f'corrected-{size}-translated-regions.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(baseline)==len(previous)
        final=[];fresh=0;changed=[]
        for before,old in zip(baseline,previous):
            assert before['chapter']==old['chapter'] and before['source']==old['source']
            prepared=call({'source':old['source'],'prepare':True})
            reused=prepared['prepared']==old['prepared']
            result={**old,'prepared':prepared['prepared'],'source_corrections':prepared['source_corrections'],
                'preprocess_milliseconds':prepared['milliseconds'],'engine':engine,'reused_identical_prepared_input':reused}
            if not reused:
                result.update(call({'source':old['source']}));fresh+=1
            if before.get('translation')!=result.get('translation'):
                changed.append({'chapter':old['chapter'],'source':old['source'],'before':before.get('translation'),
                    'after':result.get('translation'),'source_corrections':result['source_corrections']})
            final.append(result)
        (QA/f'final-{size}-translated-regions.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in final),encoding='utf-8')
        reports[size]={'inputs_audited':len(final),'fresh_inferences':fresh,'reused_identical_prepared_inputs':len(final)-fresh,
            'runtime_errors':sum('error' in row for row in final),'changed_translations_vs_original':changed,
            'repairs':[{'chapter':row['chapter'],'changes':row['source_corrections']} for row in final if row['source_corrections']]}
finally:
    process.stdin.close();process.wait()
summary={'engine':engine,'decoder_code_sha256':decoder_hash,'model_manifest_sha256':hashlib.sha256(manifest).hexdigest(),
    'replay_type':'Preprocessor audit over saved app OCR; inference reused only for byte-identical prepared input with unchanged decoder/model.',
    'reports':reports}
(QA/'repair-audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
