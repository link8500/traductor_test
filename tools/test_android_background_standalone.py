"""Test the real Android pure Kotlin policy using the cached compiler/JUnit.

No Gradle networking, emulator or device permissions are needed. This does
not claim that the complete Android application has been built or installed.
"""
import json
import os
import pathlib
import subprocess
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    cache=pathlib.Path('C:/Users/MSI THIN/.gradle/caches/modules-2/files-2.1')
    def jar(group,name,version):
        paths=list((cache/group/name/version).glob('*/'+name+'-'+version+'.jar'));assert len(paths)==1,(name,version)
        return paths[0]
    stdlib=jar('org.jetbrains.kotlin','kotlin-stdlib','2.3.20')
    junit=jar('junit','junit','4.13.2');hamcrest=jar('org.hamcrest','hamcrest-core','1.3');annotations=jar('org.jetbrains','annotations','13.0')
    compiler=[jar('org.jetbrains.kotlin','kotlin-compiler-embeddable','2.3.20'),stdlib,
        jar('org.jetbrains.kotlin','kotlin-script-runtime','2.3.20'),jar('org.jetbrains.kotlin','kotlin-reflect','1.6.10'),
        jar('org.jetbrains.kotlin','kotlin-daemon-embeddable','2.3.20'),jar('org.jetbrains.kotlinx','kotlinx-coroutines-core-jvm','1.8.0'),annotations]
    java=pathlib.Path('C:/Program Files/Android/Android Studio/jbr/bin/java.exe')
    folder=QA/'background8015/android-standalone';folder.mkdir(exist_ok=True);classes=folder/'classes';classes.mkdir(exist_ok=True)
    production=ROOT/'android/app/src/main/kotlin/com/example/traductor/OverlayBackground.kt'
    test=ROOT/'android/app/src/test/kotlin/com/example/traductor/OverlayBackgroundTest.kt';probe=ROOT/'tools/OverlayBackgroundProbe.kt'
    cp=lambda paths:os.pathsep.join(map(str,paths))
    args=[str(java),'-Xmx768m','-cp',cp(compiler),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect',
        '-jvm-target','17','-classpath',cp([stdlib,junit,hamcrest,annotations]),'-d',str(classes),str(production),str(test),str(probe)]
    result=subprocess.run(args,text=True,capture_output=True,encoding='utf-8',timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(folder/'compiler.log',result.stdout+result.stderr);assert result.returncode==0,result.stderr
    runtime=cp([classes,stdlib,junit,hamcrest,annotations])
    unit=subprocess.run([str(java),'-cp',runtime,'org.junit.runner.JUnitCore','com.example.traductor.OverlayBackgroundTest'],text=True,capture_output=True,encoding='utf-8',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic(folder/'junit.log',unit.stdout+unit.stderr);assert unit.returncode==0 and 'OK (6 tests)' in unit.stdout,unit.stdout+unit.stderr
    inputs=records(QA/'background8015/input.jsonl');manifest=folder/'input.tsv';output=folder/'output.tsv'
    atomic(manifest,''.join('\t'.join(map(str,[r['id'],r['path'],r['width'],r['height'],*r['bounds']]))+'\n' for r in inputs))
    subprocess.run([str(java),'-cp',runtime,'com.example.traductor.OverlayBackgroundProbeKt',str(manifest),str(output)],check=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    native={r['id']:r for r in records(QA/'background8015/output.jsonl')};checked=0
    for line in output.read_text().splitlines():
        index,color=line.split('\t');expected=native[int(index)]
        if expected['confident']:
            assert color!='none';rgb=expected['color'];assert int(color,16)&0xffffff==(rgb[0]<<16)|(rgb[1]<<8)|rgb[2]
        else:assert color=='none'
        checked+=1
    assert checked==8
    value=dict(kotlin_unit_tests=6,native_pixel_probe_parity_cases=8,kotlin_source_sha256=digest(production),test_sha256=digest(test),
        kotlin_compiler_sha256=digest(compiler[0]),junit_output_sha256=digest(folder/'junit.log'),pixel_output_sha256=digest(output),
        full_android_application_built=False,emulator_or_phone_used=False,gradle_issue='Java NIO loopback connection fails before Android compilation')
    atomic(folder/'summary.json',json.dumps(value,indent=2));print(json.dumps(value))


if __name__=='__main__':main()
