"""Traverse the saved control and current Windows release sequentially."""
import datetime
import json
import subprocess
import sys
import time
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    review_path=ROOT/'benchmarks/full-comics/windows8025-packaged-full-viewports-semantic-review.json'
    review=read(review_path)
    assert review['normal_worker_consensus_enabled']
    assert review['all124_meaning_judgments_reused_only_for_identical_full_location_outputs']
    assert not review['target_achieved']
    assert read(QA/'windows8025-packaged-full-viewports/summary.json')['identical_to_reviewed_experiment_viewports']==list(range(1,125))
    stages=[('801704','translated-en8017-geometry'),('802501','translated-en8025-packaged')]
    status_path=QA/'full-quality8025-status.json'
    for build,folder in stages:
        snapshot=QA/f'windows-engine{build}.json'
        command=[sys.executable,'-u',str(ROOT/'tools/run_full_comics.py'),'--language','en',
                 '--series','absolute-regression','--workers','1','--report-name',folder,
                 '--binary',str(QA/f'frozen-windows{build}/traductor.exe'),'--engine-snapshot',str(snapshot)]
        process=subprocess.Popen(command,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        def publish(complete=False):
            rows=[read(path) for path in (QA/folder).glob('*.done.json')]
            assert all(row['engine']==read(snapshot)['engine'] for row in rows)
            state=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       stage=folder,build=build,pid=process.pid,complete=complete,
                       chapters_complete=len(rows),chapters_expected=124,
                       regions=sum(row['regions'] for row in rows),runtime_errors=sum(row['runtime_errors'] for row in rows),
                       workers=1,stages_run_sequentially=True,review_sha256=digest(review_path),
                       word_review_complete=False,semantic_accuracy=None,screen_attempt_failure_probability=None,
                       target_achieved=False)
            atomic(status_path,json.dumps(state,indent=2))
        publish()
        while process.poll() is None:
            time.sleep(20)
            publish()
        if process.returncode:
            raise SystemExit(f'Full traversal stopped with code {process.returncode}; partial evidence preserved.')
        summary=read(QA/folder/'summary.json')
        assert summary['all_requested_files_traversed'] and summary['chapters_completed']==124
        assert summary['runtime_errors']==0
        publish(True)


if __name__=='__main__':main()
