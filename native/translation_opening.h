#pragma once
#include "translation_punctuation.h"

// Candidate policy: the model must independently produce exactly the same
// remaining words before a short opening can be prepended. No transcript,
// chapter vocabulary or expected translation enters this policy.
namespace luma::opening {
struct Parts { std::string first, rest; };
inline bool SpeechFunction(const std::string& word) {
  // Closed speech functions avoid guessing the referent, number or gender of
  // an isolated noun/adjective. This is a general English lexicon, not a list
  // of comic terms or translated answers. Sounds/laughter are not admitted.
  static const std::set<std::string> words{"what","why","who","whom","where","when","how","which",
    "wait","stop","look","listen","help","hush","quiet","enough","please","sorry","thanks",
    "yes","no","okay","alright","good","exactly","hey","me","you","so","well"};
  return words.count(coverage::Letters(word))!=0;
}
inline std::string ModelInput(const std::string& first) {
  auto result=first;
  if(!result.empty()&&result[0]>='a'&&result[0]<='z')result[0]-=32;
  for(size_t i=1;i<result.size();++i)if(result[i]>='A'&&result[i]<='Z')result[i]+=32;
  return result;
}
inline Parts Split(const std::string& source) {
  const auto text=coverage::Trim(source);
  static const std::regex pattern("^([A-Za-z]{2,18}[!?])\\s+(.+)$");
  std::smatch match;
  if(!std::regex_match(text,match,pattern)||!SpeechFunction(match[1].str())||punctuation::Quoted(text)||
      text.find_first_of("|{}@#&")!=std::string::npos)return {};
  auto rest=match[2].str();auto count=coverage::Words(rest);
  if(count<4||count>100||text.size()>1800)return {};
  return {match[1].str(),rest};
}
struct Result { std::string text; bool recovered=false; };
inline Result Recover(const Parts& parts,const std::string& whole,const std::string& first,
                      const std::string& rest,bool whole_retained=false,bool first_retained=false,bool rest_retained=false) {
  Result result{whole,false};
  if(parts.first.empty()||whole_retained||first_retained||rest_retained)return result;
  const auto body=coverage::NormalizedWords(whole),remaining=coverage::NormalizedWords(rest);
  auto prefix=coverage::Trim(first);const auto prefix_words=coverage::NormalizedWords(prefix);
  const auto original_words=coverage::NormalizedWords(parts.first);
  if(body.empty()||body!=remaining||prefix_words.empty()||prefix_words.size()>5||prefix.size()>64||
      punctuation::Quoted(prefix)||prefix.find_first_of(",;:|{}@#&")!=std::string::npos||
      !coverage::PreservesNegation(parts.first,prefix))return result;
  // Unknown names and sound effects must not become invented dialogue.
  // "No" is a real negative utterance shared by both languages.
  if(prefix_words==original_words&&original_words!=std::vector<std::u32string>{U"no"})return result;
  if(body.size()>=prefix_words.size()&&std::equal(prefix_words.begin(),prefix_words.end(),body.begin()))return result;
  if(prefix.back()=='.'||prefix.back()=='!'||prefix.back()=='?')prefix.pop_back();
  if(prefix.rfind("\xC2\xBF",0)==0||prefix.rfind("\xC2\xA1",0)==0)prefix.erase(0,2);
  if(prefix.empty()||prefix.find_first_of(".!?")!=std::string::npos||prefix.find("\xC2\xBF")!=std::string::npos||
      prefix.find("\xC2\xA1")!=std::string::npos)return result;
  prefix=(parts.first.back()=='?'?"\xC2\xBF":"\xC2\xA1")+prefix+parts.first.back();
  result.text=prefix+" "+whole;result.recovered=true;return result;
}
}
