"""Exercise actual frozen Windows8017 lifecycle and geometry checks."""
import argparse
import json
import subprocess
from audit_corpus_quality import QA,atomic,digest,read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',choices=['801701','801702','801703','801704','801801','801901','802001','802101','802401','802402','802501','802601','802701','802801','802901','803001'],default='801701')
    args=parser.parse_args();prefix={'801701':'windows8017','801702':'windows8017-preserve','801703':'windows8017-final','801704':'windows8017-render','801801':'windows8018','801901':'windows8019','802001':'windows8020','802101':'windows8021','802401':'windows8024-short','802402':'windows8024-default','802501':'windows8025-packaged','802601':'windows8026-inflection','802701':'windows8027-question','802801':'windows8028-opening','802901':'windows8029-refinement','803001':'windows8030-tail'}[args.build]
    binary=QA/f'frozen-windows{args.build}/traductor.exe'
    snapshot=read(QA/f'windows-engine{args.build}.json')
    assert digest(binary)==snapshot['binary_sha256']
    results={}
    for name,flag in [('recovery','--ocr-recovery-test'),('layout','--comic-layout-test'),
                      ('overlay','--overlay-self-test'),('toolbar','--overlay-toolbar-test')]:
        path=QA/f'{prefix}-{name}-test.json'
        subprocess.run([str(binary),flag,str(path)],check=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
        value=read(path)
        assert value.get('success',all(v for v in value.values() if isinstance(v,bool)))
        results[name]=dict(path=str(path),sha256=digest(path),result=value)
    report=dict(binary_sha256=digest(binary),tests=results,success=True,
        geometry_tests=len(results['layout']['result']['cases']),experimental_reader_models_used=False)
    atomic(QA/f'{prefix}-runtime-checks.json',json.dumps(report,indent=2))
    print(json.dumps(dict(success=True,geometry_tests=report['geometry_tests'],checks=list(results))),flush=True)


if __name__=='__main__':main()
