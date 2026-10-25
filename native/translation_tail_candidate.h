#pragma once
#include "translation_punctuation.h"

// Candidate recovery consumes only captured source and actual model outputs.
// A tail may be appended only if the independent head reproduces the entire
// existing output. Existing translated words can never be replaced or removed.
namespace luma::tail_candidate {
struct Parts {std::string head,tail;};
inline size_t Ends(const std::string& text) {
  size_t n=0;
  for(size_t i=0;i<text.size();++i)if(text[i]=='.'||text[i]=='!'||text[i]=='?') {
    while(i+1<text.size()&&(text[i+1]=='.'||text[i+1]=='!'||text[i+1]=='?'))++i;
    ++n;
  }
  return n;
}
inline bool ShortQuestion(const std::string& text) {
  auto words=coverage::NormalizedWords(text);
  static const std::set<std::u32string> first{U"what",U"why",U"who",U"whom",U"whose",U"how",U"where",U"when",U"which",
    U"is",U"are",U"was",U"were",U"do",U"does",U"did",U"can",U"could",U"would",U"will",U"shall",U"should",U"may",U"might",U"have",U"has",U"had"};
  return !text.empty()&&text.back()=='?'&&!words.empty()&&first.count(words.front())!=0;
}
inline Parts Plan(const std::string& source,const std::string& whole,bool retained=false) {
  if(retained||whole.empty()||punctuation::Quoted(source)||source.find_first_of("|{}@#&")!=std::string::npos)return {};
  const auto parts=coverage::Sentences(coverage::Trim(source));
  if(parts.size()<2)return {};
  const auto& tail=parts.back();
  if(tail.empty()||std::string(".!?").find(tail.back())==std::string::npos)return {};
  auto tail_words=coverage::Words(tail);
  if(tail_words<4&&!ShortQuestion(tail))return {};
  const auto source_words=coverage::Words(source),target_words=coverage::NormalizedWords(whole).size();
  const bool question_gap=std::count(source.begin(),source.end(),'?')>std::count(whole.begin(),whole.end(),'?');
  const bool short_output=Ends(whole)<parts.size()&&target_words*5<source_words*4;
  if(!question_gap&&!short_output)return {};
  std::string head;
  for(size_t i=0;i+1<parts.size();++i){if(!head.empty())head+=' ';head+=parts[i];}
  if(coverage::Words(head)<3)return {};
  return {head,tail};
}
inline std::vector<std::string> Digits(const std::string& text) {
  static const std::regex digits("[0-9]+");std::vector<std::string> result;
  for(auto i=std::sregex_iterator(text.begin(),text.end(),digits);i!=std::sregex_iterator();++i)result.push_back(i->str());
  return result;
}
struct Result {std::string text;bool recovered=false;};
inline Result Recover(const Parts& parts,const std::string& whole,const std::string& head,const std::string& tail,
                      bool whole_retained=false,bool head_retained=false,bool tail_retained=false) {
  Result result{whole,false};
  if(parts.head.empty()||whole_retained||head_retained||tail_retained)return result;
  auto a=coverage::NormalizedWords(whole),b=coverage::NormalizedWords(head),extra=coverage::NormalizedWords(tail);
  if(a.empty()||a!=b||extra.empty()||extra.size()>70||coverage::Letters(parts.tail)==coverage::Letters(tail)||
      punctuation::Quoted(tail)||!coverage::Plausible(parts.tail,tail)||
      !coverage::PreservesNegation(parts.tail,tail)||Digits(parts.tail)!=Digits(tail))return result;
  if(std::search(a.begin(),a.end(),extra.begin(),extra.end())!=a.end())return result;
  auto actual=coverage::Trim(tail);
  if(actual.empty())return result;
  const bool ended=!whole.empty()&&std::string(".!?").find(whole.back())!=std::string::npos;
  result.text=whole+(ended?" ":". ")+actual;result.recovered=true;return result;
}
}
