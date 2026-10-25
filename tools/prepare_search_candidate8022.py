"""Build an isolated wider-search variant; leave production sources unchanged."""
import difflib
import json
import shutil
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def main():
    folder=QA/'translation-search8022';source=folder/'source';source.mkdir(parents=True,exist_ok=True)
    assert shutil.disk_usage(ROOT).free>4*1024**3+100*1024**2
    snapshot=read(QA/'windows-engine802101.json')
    assert digest(ROOT/'native/local_translation.cpp')==snapshot['source_sha256']['native/local_translation.cpp']
    previous=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
    assert previous.count('constexpr size_t width=4;')==1
    old='return b.score/static_cast<double>(std::max<size_t>(1,b.tokens.size()));'
    assert previous.count(old)==1
    candidate=previous.replace('constexpr size_t width=4;','constexpr size_t width=6;').replace(old,
        'return b.score/std::pow(static_cast<double>(std::max<size_t>(1,b.tokens.size())),1.1);')
    atomic(source/'local_translation.cpp',candidate)
    atomic(folder/'source.diff',''.join(difflib.unified_diff(previous.splitlines(True),candidate.splitlines(True),fromfile='frozen802101',tofile='isolated-search6-penalty1.1')))
    for name in ['local_translation.h','translation_coverage.h','translate_cli.cpp']:
        shutil.copy2(ROOT/'native'/name,source/name)
    cmake='''cmake_minimum_required(VERSION 3.18)
project(luma_search8022 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(luma_translate_search translate_cli.cpp local_translation.cpp)
target_compile_definitions(luma_translate_search PRIVATE NOMINMAX)
target_compile_options(luma_translate_search PRIVATE /utf-8 /EHsc)
target_link_libraries(luma_translate_search PRIVATE normaliz)
'''
    cmake+=f'target_include_directories(luma_translate_search PRIVATE "{(ROOT/"native/third_party/json").as_posix()}" "{(ROOT/"native/third_party/onnxruntime/include").as_posix()}")\n'
    atomic(source/'CMakeLists.txt',cmake)
    cmake_binary=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    build=ROOT/'build/local-search8022'
    subprocess.run([cmake_binary,'-S',str(source),'-B',str(build),'-A','x64'],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    subprocess.run([cmake_binary,'--build',str(build),'--config','Release','--target','luma_translate_search','--parallel','2'],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    binary=build/'Release/luma_translate_search.exe'
    shutil.copy2(ROOT/'windows/third_party/onnxruntime/onnxruntime.dll',binary.parent/'onnxruntime.dll')
    proof=dict(binary_sha256=digest(binary),runtime_sha256=digest(binary.parent/'onnxruntime.dll'),
        frozen_baseline_snapshot_sha256=digest(QA/'windows-engine802101.json'),
        baseline_source_sha256=digest(ROOT/'native/local_translation.cpp'),candidate_source_sha256=digest(source/'local_translation.cpp'),
        source_diff_sha256=digest(folder/'source.diff'),beam_width=6,length_penalty=1.1,
        application_sources_modified=False,model_weights_changed=False,
        reference_or_manual_answers_supplied=False,
        model_assets={p:digest(ROOT/'assets/models/opus-en-es'/p) for p in ['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json']})
    target=folder/'build-provenance.json'
    if target.exists():assert read(target)==proof
    else:atomic(target,json.dumps(proof,indent=2))
    print(json.dumps(dict(built=True,application_modified=False,model_weights_changed=False)),flush=True)


if __name__=='__main__':main()
