"""Keep one running control and one memory-gated current Windows traversal."""
import datetime
import json
import subprocess
import sys
import threading
import time
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def powershell(script):
    return subprocess.check_output(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script],
                                   creationflags=subprocess.CREATE_NO_WINDOW,text=True)


def own_jobs(report,build,include_old_coordinator=False,stop=False):
    root=str(ROOT).replace("'","''")
    # Select only QA command lines from this workspace. Recheck identity before
    # terminating the obsolete stage; user applications never match this set.
    script=r'''
$root='ROOT_LITERAL'
$venv=Join-Path $root 'build\quality-venv\Scripts\python.exe'
$system=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'
$native=Join-Path $root 'build\full-comics\frozen-windowsBUILD_LITERAL\traductor.exe'
$jobs=@(Get-CimInstance Win32_Process | Where-Object {
  $stageJob=($_.CommandLine -match 'run_full_comics\.py' -and $_.CommandLine -match '--report-name\s+REPORT_LITERAL(?:\s|$)')
  $coordinatorJob=COORDINATOR_CLAUSE
  $pythonJob=($_.Name -eq 'python.exe') -and ($_.ExecutablePath -in @($venv,$system)) -and ($stageJob -or $coordinatorJob)
  $nativeJob=($_.ExecutablePath -eq $native) -and ($_.CommandLine -match '--comic-benchmark')
  $pythonJob -or $nativeJob
})
STOP_CLAUSE
ConvertTo-Json -InputObject @($jobs | ForEach-Object { $_.ProcessId }) -Compress
'''.replace('ROOT_LITERAL',root).replace('BUILD_LITERAL',build).replace('REPORT_LITERAL',report)
    script=script.replace('COORDINATOR_CLAUSE',"($_.CommandLine -match 'tools[\\/]run_full_quality8025\\.py\\b')" if include_old_coordinator else '$false')
    script=script.replace('STOP_CLAUSE',r'''
foreach($job in ($jobs | Sort-Object @{Expression={if($_.Name -eq 'traductor.exe'){0}else{1}}})) {
  $current=Get-CimInstance Win32_Process -Filter ("ProcessId="+$job.ProcessId)
  if($current -and $current.CreationDate -eq $job.CreationDate -and $current.CommandLine -eq $job.CommandLine) {
    Stop-Process -Id $job.ProcessId -ErrorAction SilentlyContinue
  }
}
''' if stop else '')
    return json.loads(powershell(script))


def main():
    report_path=ROOT/'benchmarks/full-comics/windows8026-inflection-full-viewports-semantic-review.json'
    review=read(report_path)
    assert review['normal_worker_inflection_support_enabled'] and not review['target_achieved']
    assert read(QA/'windows8026-inflection-full-viewports/summary.json')['identical_to_reviewed_experiment_viewports']==list(range(1,125))
    status_path=QA/'full-quality8026-status.json'
    def publish(stage,build,pid=None,complete=False,waiting=False):
        rows=[read(path) for path in (QA/stage).glob('*.done.json')]
        engine=read(QA/f'windows-engine{build}.json')['engine']
        assert all(r['engine']==engine for r in rows)
        value=dict(updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage=stage,build=build,pid=pid,
                   complete=complete,waiting_for_previous_control=waiting,chapters_complete=len(rows),chapters_expected=124,
                   regions=sum(r['regions'] for r in rows),runtime_errors=sum(r['runtime_errors'] for r in rows),
                   workers=1,review_sha256=digest(report_path),word_review_complete=False,
                   semantic_accuracy=None,screen_attempt_failure_probability=None,target_achieved=False)
        value['maximum_current_workers']=1;value['maximum_control_workers']=1
        value['memory_gate_before_each_native_job_bytes']=3*1024**3
        path=QA/'full-quality8026-adopted-control-status.json' if build=='801704' else status_path
        atomic(path,json.dumps(value,indent=2))
    def run_stage(build,folder):
        command=[sys.executable,'-u',str(ROOT/'tools/run_full_comics.py'),'--language','en','--series','absolute-regression',
                 '--workers','1','--report-name',folder,'--binary',str(QA/f'frozen-windows{build}/traductor.exe'),
                 '--engine-snapshot',str(QA/f'windows-engine{build}.json')]
        with (QA/'full-quality8026-child.log').open('ab') as log:
            process=subprocess.Popen(command,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdout=log,stderr=log)
            while process.poll() is None:
                publish(folder,build,process.pid)
                time.sleep(20)
        if process.returncode:raise SystemExit(f'Traversal stopped with code {process.returncode}; partial evidence preserved.')
        result=read(QA/folder/'summary.json')
        assert result['all_requested_files_traversed'] and result['chapters_completed']==124 and not result['runtime_errors']
        publish(folder,build,complete=True)
    control='translated-en8017-geometry'
    def control_complete():
        path=QA/control/'summary.json'
        if not path.exists():return False
        state=read(path)
        return state.get('all_requested_files_traversed') and state.get('chapters_completed')==124 and not state.get('runtime_errors')
    def preserve_control():
        while not control_complete():
            publish(control,'801704',waiting=True)
            if not own_jobs(control,'801704',include_old_coordinator=True):
                run_stage('801704',control)
            else:time.sleep(20)
        # Retire only the obsolete next stage after the control's cleanup.
        while own_jobs(control,'801704'):
            publish(control,'801704',complete=True,waiting=True)
            time.sleep(20)
        retired=[]
        for attempt in range(3):
            found=own_jobs('translated-en8025-packaged','802501',include_old_coordinator=True,stop=True)
            retired.extend(found)
            if not found:break
            time.sleep(1)
        assert not own_jobs('translated-en8025-packaged','802501',include_old_coordinator=True),'Obsolete own stage still running; do not start a duplicate traversal'
        publish(control,'801704',complete=True)
        print(json.dumps(dict(retired_obsolete_own_processes=retired,control_chapters_complete=124)),flush=True)
    control_thread=threading.Thread(target=preserve_control,name='preserve-existing-control',daemon=True)
    control_thread.start()
    run_stage('802601','translated-en8026-inflection')
    control_thread.join()


if __name__=='__main__':main()
