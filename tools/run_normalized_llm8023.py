"""Compare the existing local LLM using exact production text preparation.

Model, prompt, sampling and raw OCR are unchanged from the prior recommended
trial. Only the user passages now pass through native PrepareInput first.
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
from run_local_llm8021 import SYSTEM, RECOMMENDED_SETTINGS

FOLDER=QA/'local-llm8023-normalized'
RUNTIME=ROOT/'build/llm-quality8023'
CACHE=ROOT/'build/llm-quality8021'


def request(path,body=None):
    token=(RUNTIME/'server-token.txt').read_text(encoding='utf-8').strip()
    req=urllib.request.Request('http://127.0.0.1:8766'+path,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=240) as response:return json.load(response)


def start_server():
    RUNTIME.mkdir(exist_ok=True)
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1',8766))!=0,'Port occupied; inspect existing process before starting another'
    proof=read(CACHE/'download-provenance.json');binary=CACHE/'runtime/llama-server.exe';model=CACHE/proof['model']['filename']
    assert digest(binary)==proof['server_binaries']['llama-server.exe']
    assert digest(model)==proof['model']['sha256']
    token=RUNTIME/'server-token.txt'
    if not token.exists():atomic(token,secrets.token_hex(32)+'\n')
    command=[str(binary),'--model',str(model),'--host','127.0.0.1','--port','8766',
        '--ctx-size','8192','--parallel','2','--gpu-layers','99','--threads','4',
        '--threads-batch','4','--flash-attn','on','--no-webui','--reasoning','off',
        '--api-key-file',str(token),'--cors-origins','http://127.0.0.1:8766']
    with (RUNTIME/'server.log').open('ab') as log:
        child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(RUNTIME/'server-process.json',json.dumps(dict(pid=child.pid,command=command,
        binary_sha256=digest(binary),model_sha256=digest(model),bound_to_loopback_only=True,
        authenticated_local_endpoint=True),indent=2))
    print(json.dumps(dict(server_pid=child.pid,port=8766,local_only=True)),flush=True)


def evaluate():
    pin=read(FOLDER/'prepare-provenance.json');raw_path=QA/'windows8021-full-viewports-full-agreement/output.jsonl'
    raw=records(raw_path);assert digest(raw_path)==pin['frozen_ocr_sha256']
    prepared={r['source']:r['prepared'] for r in records(FOLDER/'native-prepared.jsonl')}
    assert len(prepared)==215 and digest(FOLDER/'native-prepared.jsonl')==pin['native_prepared_sha256']
    assert all(s.casefold()==p.casefold() for s,p in prepared.items())
    old=read(QA/'local-llm8021-full-viewports-recommended/provenance.json')
    assert old['system']==SYSTEM and old['settings']==RECOMMENDED_SETTINGS
    server=read(RUNTIME/'server-process.json')
    assert server['model_sha256']==old['model_sha256'] and server['binary_sha256']==old['server_binary_sha256']
    props=request('/props');atomic(RUNTIME/'server-props.json',json.dumps(props,ensure_ascii=False,indent=2))
    proof=dict(model_sha256=server['model_sha256'],server_binary_sha256=server['binary_sha256'],
        system=SYSTEM,settings=RECOMMENDED_SETTINGS,prior_recommended_provenance_sha256=digest(QA/'local-llm8021-full-viewports-recommended/provenance.json'),
        prepare_provenance_sha256=digest(FOLDER/'prepare-provenance.json'),raw_ocr_sha256=digest(raw_path),
        preparation_only_changes_case=True,unique_sources_with_changed_case=sum(s!=p for s,p in prepared.items()),
        local_endpoint='http://127.0.0.1:8766',human_or_reference_text_supplied=False,
        original_images_supplied=False,model_weights_trained=False,application_modified=False,
        complete_live_app_uses=False)
    provenance=FOLDER/'provenance.json'
    if provenance.exists():assert read(provenance)==proof
    else:atomic(provenance,json.dumps(proof,indent=2))
    grouped={ident:[r for r in raw if r['image']==ident] for ident in range(1,125)}
    def run(ident):
        target=FOLDER/f'{ident:03d}.json';sources=[r['source'] for r in grouped[ident]]
        passages=[prepared[s] for s in sources]
        if target.exists():
            value=read(target);assert value['original_source_passages']==sources and value['source_passages']==passages
            return value
        count=len(passages)
        schema=dict(type='object',properties=dict(translations=dict(type='array',items=dict(type='string'),minItems=count,maxItems=count)),
            required=['translations'],additionalProperties=False)
        body=dict(RECOMMENDED_SETTINGS,messages=[dict(role='system',content=SYSTEM),
            dict(role='user',content=json.dumps(dict(passages=passages),ensure_ascii=False))],
            response_format=dict(type='json_object',schema=schema))
        started=time.monotonic();response=request('/v1/chat/completions',body)
        choice=response['choices'][0];translations=json.loads(choice['message']['content'])['translations']
        assert choice['finish_reason']=='stop' and len(translations)==count
        assert all(isinstance(s,str) and s.strip() for s in translations)
        value=dict(id=ident,original_source_passages=sources,source_passages=passages,translations=translations,
            response=response,elapsed_seconds=time.monotonic()-started,
            input_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest(),meanings_reviewed=False)
        atomic(target,json.dumps(value,ensure_ascii=False,indent=2));return value
    completed={};errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(run,i):i for i in grouped}
        for future in concurrent.futures.as_completed(jobs):
            try:
                value=future.result();completed[value['id']]=value
                print(json.dumps(dict(viewports_complete=len(completed),requested=124)),flush=True)
            except Exception as error:errors.append(dict(id=jobs[future],error=str(error)))
            summary=dict(requested=124,completed=len(completed),regions=sum(len(v['translations']) for v in completed.values()),
                errors=errors,all_meanings_reviewed=False,screen_attempt_failure_probability=None,target_achieved=False,ready_for_release=False)
            atomic(FOLDER/'summary.json',json.dumps(summary,indent=2))
    if errors:raise SystemExit('Incomplete normalized trial; inspect summary before resuming')
    output=[]
    for ident,rows in grouped.items():
        for original,text,source_text in zip(rows,completed[ident]['translations'],completed[ident]['source_passages']):
            row=dict(original,translation=text,prepared_model_input=source_text,
                experimental_translation_provider='local-Qwen3-4B-normalized',retained_original=False,sentence_recovered=False)
            for key in ['whole_translation','sentence_sources','sentence_translations','reason']:row.pop(key,None)
            output.append(row)
    atomic(FOLDER/'output.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in output))
    summary.update(output_sha256=digest(FOLDER/'output.jsonl'),provenance_sha256=digest(provenance))
    atomic(FOLDER/'summary.json',json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--start-server',action='store_true');args=parser.parse_args()
    if args.start_server:start_server()
    else:evaluate()
