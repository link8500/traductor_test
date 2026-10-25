#pragma once
#include "translation_coverage.h"
#include <set>

namespace luma::punctuation {
inline bool Quoted(std::string text) {
  const std::string curly="\xE2\x80\x99";
  for(size_t at=text.find(curly);at!=std::string::npos;at=text.find(curly,at+1))text.replace(at,curly.size(),"'");
  if(text.find_first_of("\"[]()")!=std::string::npos||text.find("\xE2\x80\x9C")!=std::string::npos||text.find("\xE2\x80\x9D")!=std::string::npos||text.find("\xE2\x80\x98")!=std::string::npos)return true;
  auto letter=[](char c){return (c>='a'&&c<='z')||(c>='A'&&c<='Z');};
  for(size_t i=0;i<text.size();++i)if(text[i]=='\''&&(i==0||i+1==text.size()||!letter(text[i-1])||!letter(text[i+1])))return true;
  return false;
}
inline bool SingleQuestion(const std::string& text) {
  if(text.empty()||text.back()!='?'||std::count(text.begin(),text.end(),'?')!=1||
      text.find_first_of(".!:;|{}@#&")!=std::string::npos||Quoted(text))return false;
  auto words=coverage::NormalizedWords(text);
  if(words.size()<4||words.size()>70)return false;
  // An indirect question can correctly become a Spanish declarative clause.
  // Conservative exclusions keep reporting/thought passages out of this rule.
  static const std::set<std::u32string> reporting{U"ask",U"asks",U"asked",U"asking",U"wonder",U"wonders",U"wondered",U"wondering",
      U"say",U"says",U"said",U"saying",U"told",U"hear",U"heard",U"think",U"thinks",U"thought",U"believe",U"believes",U"believed",
      U"know",U"knows",U"knew",U"remember",U"remembers",U"remembered"};
  for(const auto& word:words)if(reporting.count(word))return false;
  return true;
}
struct Result {std::string text;bool restored=false;};
inline Result PreserveQuestion(const std::string& source,const std::string& target,bool retained_original=false) {
  Result result{target,false};auto input=coverage::Trim(source),output=coverage::Trim(target);
  if(retained_original||!SingleQuestion(input)||output.empty()||Quoted(output)||
      output.find_first_of("?!:;")!=std::string::npos||output.find("\xC2\xBF")!=std::string::npos||
      output.find("\xC2\xA1")!=std::string::npos||output.find("\xE2\x80\xA6")!=std::string::npos||
      coverage::Letters(input)==coverage::Letters(output))return result;
  if(output.back()=='.')output.pop_back();
  if(output.empty()||output.find('.')!=std::string::npos)return result;
  result.text="\xC2\xBF"+output+"?";result.restored=true;return result;
}
}
