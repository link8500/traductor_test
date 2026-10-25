"""Build an isolated translation candidate for missing short clauses."""
import argparse
import json
import subprocess
from audit_corpus_quality import ROOT,atomic,digest,read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guard-repetitions',action='store_true')
    args=parser.parse_args()
    out=ROOT/('build/coverage8017-guarded' if args.guard_repetitions else 'build/coverage8017');source=out/'source';source.mkdir(parents=True,exist_ok=True)
    pinned=out/'build.json'
    if pinned.exists():
        proof=read(pinned);assert digest(out/'compiled/Release/luma_translate.exe')==proof['binary_sha256']
        print(json.dumps(proof),flush=True);return
    base=ROOT/'native/translation_coverage.h';policy=base.read_text(encoding='utf-8')
    policy=policy.replace('#pragma once','#pragma once\n#include "translation_coverage.h"').replace('namespace luma::coverage {','namespace luma::coverage8017 {')
    assert policy.count('words<3||words>70')==1
    policy=policy.replace('words<3||words>70','words<2||words>70')
    marker='return short_output||std::count(source.begin(),source.end(),\'?\')>std::count(output.begin(),output.end(),\'?\');'
    assert marker in policy
    policy=policy.replace(marker,'''bool short_clause=std::any_of(parts.begin(),parts.end(),[](const auto& part){return Words(part)<=3;});
  size_t sentence_ends=0;
  for(size_t i=0;i<output.size();++i)if(std::string(".!?").find(output[i])!=std::string::npos) {
    while(i+1<output.size()&&std::string(".!?").find(output[i+1])!=std::string::npos)++i;
    ++sentence_ends;
  }
  bool shortened_sentence=characters(output)<.70*characters(source)&&sentence_ends<parts.size();
  return short_output||shortened_sentence||(short_clause&&Clauses(output)<parts.size())||
      std::count(source.begin(),source.end(),'?')>std::count(output.begin(),output.end(),'?');''')
    atomic(source/'translation_coverage8017_candidate.h',policy)
    current=(ROOT/'native/local_translation.cpp').read_text(encoding='utf-8')
    trial=current.replace('#include "translation_coverage.h"','#include "translation_coverage8017_candidate.h"').replace('coverage::Sentences(text)','coverage8017::Sentences(text)').replace('coverage::Retry(text,result.text,parts)','coverage8017::Retry(text,result.text,parts)')
    if args.guard_repetitions:
        guard=r'''
namespace luma::coverage8017 {
inline size_t RepeatedRun(const std::string& text) {
  static const std::regex word("[A-Za-z]+(?:'[A-Za-z]+)?");
  std::vector<std::string> values;
  for(auto it=std::sregex_iterator(text.begin(),text.end(),word);it!=std::sregex_iterator();++it)values.push_back(Letters(it->str()));
  size_t maximum=0;
  for(size_t width=1;width<=3;++width)for(size_t start=0;start+width<=values.size();++start) {
    size_t repeats=1,next=start+width;
    while(next+width<=values.size()&&std::equal(values.begin()+start,values.begin()+start+width,values.begin()+next)){++repeats;next+=width;}
    maximum=std::max(maximum,repeats);
  }
  return maximum;
}
inline bool Plausible(const std::string& source,const std::string& output) {
  auto repeated=RepeatedRun(output);return repeated<4||repeated<=RepeatedRun(source)+1;
}
}
'''
        policy+=guard;atomic(source/'translation_coverage8017_candidate.h',policy)
        marker='if(translated.retained_original||translated.text.empty()||coverage::Letters(translated.text)==coverage::Letters(part))return result;'
        assert marker in trial
        trial=trial.replace(marker,'if(!coverage8017::Plausible(part,translated.text))return result;\n    '+marker)
    atomic(source/'local_translation.cpp',trial)
    atomic(source/'guards.cpp',r'''#include "translation_coverage8017_candidate.h"
#include <iostream>
#include <stdexcept>
int main(){size_t n=0;auto check=[&](bool ok){++n;if(!ok)throw std::runtime_error("Short clause guard "+std::to_string(n));};using namespace luma::coverage8017;
check(Sentences("COME NOW? WE WILL WAIT FOR YOU.").size()==2);
check(Sentences("WE AGREE. WE WILL WAIT FOR YOU.").size()==2);
check(Sentences("NO. WE WILL WAIT FOR YOU.").empty());
check(Sentences("PLEASE STOP HERE... WE WILL WAIT FOR YOU.").empty());
check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU...").empty());
check(Sentences("WE SAW MR. GREEN AT HOME. WE WILL WAIT FOR YOU.").size()==2);
check(Sentences("WE SAW A. GREEN AT HOME. WE WILL WAIT FOR YOU.").size()==2);
check(Sentences("PLEASE STOP HERE. WAIT FOR ME").empty());
check(Sentences("PLEASE STOP HERE. WE WILL WAIT FOR YOU").size()==2);
auto s="COME NOW? WE WILL WAIT FOR YOU.";check(Retry(s,"Te esperamos en este lugar.",Sentences(s)));
check(!Retry(s,"Ven ahora. Te esperamos en este lugar?",Sentences(s)));
auto t="WE MUST DEPART NOW. IF WE STAY HERE, WE WILL LOSE.";check(Retry(t,"Si seguimos, perderemos.",Sentences(t)));
std::cout<<"{\"success\":true,\"guards\":"<<n<<"}"<<std::endl;}
''')
    if args.guard_repetitions:
        path=source/'guards.cpp';tests=path.read_text(encoding='utf-8')
        tests=tests.replace('std::cout<<',r'''check(!Plausible("ONE SHORT EXPRESSION.","Ay, ay, ay, ay, ay, ay, ay."));
check(Plausible("HA HA HA HA HA!", "Ha, ha, ha, ha, ha!"));
check(Plausible("WE MUST LEAVE.","Tenemos que irnos."));
std::cout<<''')
        atomic(path,tests)
    atomic(source/'plan.cpp',r'''#include "translation_coverage8017_candidate.h"
#include "json.hpp"
#include <iostream>
int main(){std::string line;while(std::getline(std::cin,line)){auto r=nlohmann::json::parse(line);std::string s=r.at("source"),t=r.at("translation");
auto a=luma::coverage::Sentences(s),b=luma::coverage8017::Sentences(s);
r["before_retry"]=luma::coverage::Retry(s,t,a);r["candidate_retry"]=luma::coverage8017::Retry(s,t,b);r["parts"]=b;
r["policy_changed"]=(a!=b||r["before_retry"]!=r["candidate_retry"]);std::cout<<r.dump()<<std::endl;}}
''')
    native=(ROOT/'native').as_posix();runtime=(ROOT/'windows/third_party/onnxruntime/onnxruntime.dll').as_posix()
    atomic(source/'CMakeLists.txt',f'''cmake_minimum_required(VERSION 3.18)
project(luma_short_clause_candidate LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
add_executable(luma_translate "{native}/translate_cli.cpp" local_translation.cpp)
add_executable(luma_short_clause_test guards.cpp)
add_executable(luma_short_clause_plan plan.cpp)
foreach(target luma_translate luma_short_clause_test luma_short_clause_plan)
target_include_directories(${{target}} PRIVATE "{native}" "{native}/third_party/json" "{native}/third_party/onnxruntime/include")
target_compile_options(${{target}} PRIVATE /utf-8 /EHsc)
endforeach()
target_compile_definitions(luma_translate PRIVATE NOMINMAX)
target_link_libraries(luma_translate PRIVATE normaliz)
add_custom_command(TARGET luma_translate POST_BUILD COMMAND ${{CMAKE_COMMAND}} -E copy_if_different "{runtime}" "$<TARGET_FILE_DIR:luma_translate>/onnxruntime.dll")
''')
    cmake=r'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    subprocess.run([cmake,'-S',str(source),'-B',str(out/'compiled'),'-A','x64'],check=True)
    subprocess.run([cmake,'--build',str(out/'compiled'),'--config','Release','--parallel','2'],check=True)
    binary=out/'compiled/Release/luma_translate.exe'
    guards=json.loads(subprocess.check_output([str(binary.with_name('luma_short_clause_test.exe'))],text=True))
    proof=dict(binary_sha256=digest(binary),policy_sha256=digest(source/'translation_coverage8017_candidate.h'),
        base_policy_sha256=digest(base),generated_source_sha256=digest(source/'local_translation.cpp'),
        plan_binary_sha256=digest(binary.with_name('luma_short_clause_plan.exe')),guards=guards,
        runtime_sha256=digest(binary.parent/'onnxruntime.dll'),application_modified=False,
        reference_or_transcriptions_supplied=False,weights_changed=False,repeated_fragment_rejected=args.guard_repetitions)
    atomic(pinned,json.dumps(proof,indent=2));print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
