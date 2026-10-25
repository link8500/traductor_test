"""Pin old/new source-only retry planning with the exact previous policy hash."""
import hashlib
import json
import subprocess
from audit_corpus_quality import ROOT,QA,atomic,digest,read


def main():
    out=ROOT/'build/coverage-plan8018';source=out/'source';source.mkdir(parents=True,exist_ok=True)
    current=(ROOT/'native/translation_coverage.h').read_text(encoding='utf-8')
    marker='\nnamespace luma::coverage {\ninline size_t RepeatedRun'
    assert current.count(marker)==1
    before=current.split(marker)[0].replace('words<2||words>70','words<3||words>70')
    start=before.index('  bool short_clause=');end=before.index('\n}',start)
    before=before[:start]+"  return short_output||std::count(source.begin(),source.end(),'?')>std::count(output.begin(),output.end(),'?');"+before[end:]
    expected=read(QA/'windows-engine801704.json')['source_sha256']['native/translation_coverage.h']
    candidates=[before,before.rstrip()+'\n',before.rstrip()+'\n\n']
    exact=next((data for s in candidates for data in [s.encode(),s.replace('\n','\r\n').encode()]
                if hashlib.sha256(data).hexdigest()==expected),None)
    assert exact is not None,'Reconstructed previous policy must match its frozen source exactly'
    path=source/'previous-policy.h';path.write_bytes(exact);assert digest(path)==expected
    atomic(source/'previous-namespace.h',exact.decode().replace('namespace luma::coverage {','namespace luma::coverage_before {'))
    atomic(source/'plan.cpp',r'''#include "previous-namespace.h"
#include "translation_coverage.h"
#include "json.hpp"
#include <iostream>
int main(){std::string line;while(std::getline(std::cin,line)){
auto r=nlohmann::json::parse(line);std::string s=r.at("source"),t=r.at("whole_translation");
auto a=luma::coverage_before::Sentences(s),b=luma::coverage::Sentences(s);
r["before_retry"]=luma::coverage_before::Retry(s,t,a);r["after_retry"]=luma::coverage::Retry(s,t,b);
r["selected"]=r["before_retry"].get<bool>()||r["after_retry"].get<bool>();
std::cout<<r.dump()<<std::endl;}}
''')
    native=(ROOT/'native').as_posix()
    atomic(source/'CMakeLists.txt',f'''cmake_minimum_required(VERSION 3.18)
project(luma_coverage_plan8018 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(luma_plan plan.cpp)
target_include_directories(luma_plan PRIVATE "{native}" "{native}/third_party/json")
target_compile_options(luma_plan PRIVATE /utf-8 /EHsc)
''')
    cmake=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    subprocess.run([cmake,'-S',str(source),'-B',str(out/'compiled'),'-A','x64'],check=True)
    subprocess.run([cmake,'--build',str(out/'compiled'),'--config','Release','--parallel','2'],check=True)
    proof=dict(before_policy_sha256=digest(path),after_policy_sha256=digest(ROOT/'native/translation_coverage.h'),
        binary_sha256=digest(out/'compiled/Release/luma_plan.exe'),source_sha256=digest(source/'plan.cpp'),reference_answers_used=False)
    atomic(out/'proof.json',json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
