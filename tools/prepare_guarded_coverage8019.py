"""Compile the exact recovery safeguards and apply them to pinned native candidates."""
import json
import subprocess
from audit_corpus_quality import ROOT, QA, atomic, digest, read, records


def main():
    out=ROOT/'build/coverage-guard8019';source=out/'source';source.mkdir(parents=True,exist_ok=True)
    atomic(source/'guard.cpp',r'''#include "translation_coverage.h"
#include "json.hpp"
#include <iostream>
int main(){std::string line;while(std::getline(std::cin,line)){
auto r=nlohmann::json::parse(line);std::string s=r.at("source"),t=r.at("translation");
bool accepted=true;std::string reason="unchanged native result";
if(r.value("sentence_recovered",false)){
  std::string whole=r.at("whole_translation");auto parts=luma::coverage::Sentences(s);
  if(!luma::coverage::LongClauseRetry(s,whole,parts)){
    accepted=luma::coverage::PreservesExistingWords(whole,t);reason=accepted?"preserved previous words":"changed too many previous words";
    const auto& translations=r.at("sentence_translations");if(translations.size()!=parts.size())return 2;
    for(size_t i=0;i<parts.size();++i)if(!luma::coverage::PreservesNegation(parts[i],translations[i])){accepted=false;reason="negation not preserved";}
  }
  if(!accepted)t=whole;
}
r["guarded_translation"]=t;r["recovery_accepted"]=accepted;r["guard_reason"]=reason;
std::cout<<r.dump()<<std::endl;}}
''')
    native=(ROOT/'native').as_posix()
    atomic(source/'CMakeLists.txt',f'''cmake_minimum_required(VERSION 3.18)
project(luma_guard8019 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(luma_guard guard.cpp)
target_include_directories(luma_guard PRIVATE "{native}" "{native}/third_party/json")
target_compile_options(luma_guard PRIVATE /utf-8 /EHsc)
''')
    cmake=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    subprocess.run([cmake,'-S',str(source),'-B',str(out/'compiled'),'-A','x64'],check=True)
    subprocess.run([cmake,'--build',str(out/'compiled'),'--config','Release','--parallel','2'],check=True)
    folder=QA/'full-corpus-coverage8019';folder.mkdir(exist_ok=True)
    old=QA/'full-corpus-coverage8018/paired-inferences.jsonl'
    rows=[r['result'] for r in records(old) if r['variant']=='after']
    manifest=folder/'guard-input.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in rows))
    binary=out/'compiled/Release/luma_guard.exe';target=folder/'guarded-candidates.jsonl'
    with manifest.open('rb') as src,target.open('wb') as dest:subprocess.run([str(binary)],stdin=src,stdout=dest,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    proof=dict(policy_sha256=digest(ROOT/'native/translation_coverage.h'),source_sha256=digest(source/'guard.cpp'),binary_sha256=digest(binary),
        native_trial_outputs_sha256=digest(old),manifest_sha256=digest(manifest),output_sha256=digest(target),
        native_translator_fresh_inference=False,reference_or_manual_answers_supplied=False)
    atomic(folder/'guard-provenance.json',json.dumps(proof,indent=2))
    print(json.dumps(dict(sources=len(rows),recoveries_blocked=sum(not r['recovery_accepted'] for r in records(target)),**proof)),flush=True)


if __name__=='__main__':main()
