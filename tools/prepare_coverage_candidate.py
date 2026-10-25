"""Build an isolated omission candidate without modifying the shipped engine."""
import json
import subprocess
from audit_corpus_quality import ROOT,QA,digest,atomic


def main():
    out=ROOT/'build/coverage8016';source=out/'source';source.mkdir(parents=True,exist_ok=True)
    pinned=out/'build.json'
    if pinned.exists():
        proof=json.loads(pinned.read_text(encoding='utf-8'))
        assert digest(out/'compiled/Release/luma_translate.exe')==proof['binary_sha256']
        assert digest(source/'local_translation.cpp')==proof['generated_source_sha256']
        print(json.dumps(dict(reused_immutable_candidate=True,**proof)),flush=True);return
    current=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
    trial=current.replace('#include "translation_coverage.h"','#include "translation_coverage_candidate.h"').replace('coverage::Sentences(text)','coverage_candidate::Sentences(text)').replace('coverage::Retry(text,result.text,parts)','coverage_candidate::Retry(text,result.text,parts)')
    assert trial!=current and trial.count('coverage_candidate::')==2
    atomic(source/'local_translation.cpp',trial)
    native=(ROOT/'native').as_posix();runtime=(ROOT/'windows/third_party/onnxruntime/onnxruntime.dll').as_posix()
    cmake=f'''cmake_minimum_required(VERSION 3.18)
project(luma_coverage_candidate LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(luma_translate "{native}/translate_cli.cpp" local_translation.cpp)
add_executable(luma_coverage_candidate_test "{native}/coverage_candidate_test.cpp")
target_include_directories(luma_translate PRIVATE "{native}" "{native}/third_party/json" "{native}/third_party/onnxruntime/include")
target_compile_definitions(luma_translate PRIVATE NOMINMAX)
target_compile_options(luma_translate PRIVATE /utf-8 /EHsc)
target_link_libraries(luma_translate PRIVATE normaliz)
add_custom_command(TARGET luma_translate POST_BUILD COMMAND ${{CMAKE_COMMAND}} -E copy_if_different "{runtime}" "$<TARGET_FILE_DIR:luma_translate>/onnxruntime.dll")
'''
    atomic(source/'CMakeLists.txt',cmake)
    executable=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    subprocess.run([executable,'-S',str(source),'-B',str(out/'compiled'),'-A','x64'],check=True)
    subprocess.run([executable,'--build',str(out/'compiled'),'--config','Release','--parallel','2'],check=True)
    binary=out/'compiled/Release/luma_translate.exe'
    guard=subprocess.run([str(binary.with_name('luma_coverage_candidate_test.exe'))],capture_output=True,text=True,check=True)
    value=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        base_source_sha256=digest(ROOT/'native/local_translation.cpp'),generated_source_sha256=digest(source/'local_translation.cpp'),
        candidate_policy_sha256=digest(ROOT/'native/translation_coverage_candidate.h'),base_policy_sha256=digest(ROOT/'native/translation_coverage.h'),
        guards=json.loads(guard.stdout),application_modified=False,reference_used_for_inference=False,translator_weights_changed=False)
    atomic(out/'build.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
