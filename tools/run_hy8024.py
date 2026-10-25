"""Isolated local specialist: same 228 OCR regions, vendor translation prompt.

This evaluates HY-MT itself. Generated text is not used to train other models.
No application defaults, weights or original/reference inventories are edited.
"""
import argparse
import concurrent.futures
import hashlib
import json
import secrets
import socket
import subprocess
import time
import urllib.request
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records

CACHE=ROOT/'build/llm-hy8024'
FOLDER=QA/'hy8024-full-viewports'
TEMPLATE='Translate the following segment into Spanish, without additional explanation.\n\n{source}'
SETTINGS=dict(temperature=.7,top_p=.6,top_k=20,min_p=0,repeat_penalty=1.05,
    presence_penalty=0,seed=8024,max_tokens=768)


def request(path,body=None):
    token=(CACHE/'server-token.txt').read_text(encoding='utf-8').strip()
    req=urllib.request.Request('http://127.0.0.1:8767'+path,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=240) as response:return json.load(response)


def start_server():
    proof=read(CACHE/'download-provenance.json');model=CACHE/proof['filename']
    assert model.stat().st_size==proof['bytes'] and digest(model)==proof['sha256']
    binary=ROOT/'build/llm-quality8021/runtime/llama-server.exe'
    expected=read(ROOT/'build/llm-quality8021/download-provenance.json')['server_binaries']['llama-server.exe']
    assert digest(binary)==expected
    with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',8767))!=0,'Inspect existing server before creating another'
    token=CACHE/'server-token.txt'
    if not token.exists():atomic(token,secrets.token_hex(32)+'\n')
    command=[str(binary),'--model',str(model),'--host','127.0.0.1','--port','8767',
        '--ctx-size','4096','--parallel','2','--gpu-layers','99','--threads','4',
        '--threads-batch','4','--flash-attn','on','--no-webui',
        '--api-key-file',str(token),'--cors-origins','http://127.0.0.1:8767']
    with (CACHE/'server.log').open('ab') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(CACHE/'server-process.json',json.dumps(dict(pid=child.pid,command=command,
        binary_sha256=expected,model_sha256=proof['sha256'],local_only=True,authenticated=True),indent=2))
    print(json.dumps(dict(server_pid=child.pid,port=8767,local_only=True)),flush=True)


def evaluate():
    FOLDER.mkdir(exist_ok=True);prepared_path=QA/'local-llm8023-normalized/native-prepared.jsonl'
    prepared=records(prepared_path);assert len(prepared)==215 and all(r['source'].casefold()==r['prepared'].casefold() for r in prepared)
    raw_path=QA/'windows8021-full-viewports-full-agreement/output.jsonl';rows=records(raw_path)
    assert len(rows)==228 and len({r['image'] for r in rows})==124
    server=read(CACHE/'server-process.json');model=read(CACHE/'download-provenance.json')
    assert server['model_sha256']==model['sha256']
    props=request('/props');atomic(CACHE/'server-props.json',json.dumps(props,ensure_ascii=False,indent=2))
    pin=FOLDER/'provenance.json'
    proof=dict(model_sha256=model['sha256'],download_provenance_sha256=digest(CACHE/'download-provenance.json'),
        server_binary_sha256=server['binary_sha256'],raw_ocr_sha256=digest(raw_path),
        native_prepared_sha256=digest(prepared_path),prompt_template=TEMPLATE,settings=SETTINGS,
        independent_source_calls=True,unique_sources=215,regions=228,viewports=124,
        model_card='https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF',
        local_only=True,human_or_reference_text_supplied=False,model_weights_trained=False,
        outputs_not_used_to_train_other_models=True,application_modified=False,distribution_approved=False)
    if pin.exists():assert read(pin)==proof
    else:atomic(pin,json.dumps(proof,indent=2))

    def run(item):
        ident=item['id'];target=FOLDER/f'source-{ident:03d}.json'
        if target.exists():
            saved=read(target);assert saved['source']==item['source'] and saved['prepared']==item['prepared'];return saved
        body=dict(SETTINGS,messages=[dict(role='user',content=TEMPLATE.format(source=item['prepared']))])
        started=time.monotonic();response=request('/v1/chat/completions',body)
        choice=response['choices'][0];text=choice['message']['content']
        assert choice['finish_reason']=='stop' and isinstance(text,str) and text.strip()
        value=dict(id=ident,source=item['source'],prepared=item['prepared'],translation=text.strip(),response=response,
            elapsed_seconds=time.monotonic()-started,
            request_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(),meaning_reviewed=False)
        atomic(target,json.dumps(value,ensure_ascii=False,indent=2));return value

    completed={};errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(run,item):item['id'] for item in prepared}
        for future in concurrent.futures.as_completed(futures):
            try:
                result=future.result();completed[result['source']]=result
                print(json.dumps(dict(sources_complete=len(completed),requested=215)),flush=True)
            except Exception as error:
                errors.append(dict(id=futures[future],error=str(error)));print(json.dumps(dict(runtime_errors=len(errors))),flush=True)
            summary=dict(requested_viewports=124,unique_sources_requested=215,sources_completed=len(completed),errors=errors,
                all_meanings_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
            atomic(FOLDER/'summary.json',json.dumps(summary,indent=2))
    if errors:raise SystemExit('Incomplete specialist experiment; inspect errors before resuming')
    output=[]
    for original in rows:
        result=completed[original['source']]
        row=dict(original,translation=result['translation'],prepared_model_input=result['prepared'],
            experimental_translation_provider='local-HY-MT1.5-1.8B-Q8_0',retained_original=False,sentence_recovered=False)
        for key in ['whole_translation','sentence_sources','sentence_translations','reason']:row.pop(key,None)
        output.append(row)
    atomic(FOLDER/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output))
    summary.update(viewports=124,regions=228,output_sha256=digest(FOLDER/'output.jsonl'),provenance_sha256=digest(pin))
    atomic(FOLDER/'summary.json',json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--start-server',action='store_true');args=parser.parse_args()
    if args.start_server:start_server()
    else:evaluate()
