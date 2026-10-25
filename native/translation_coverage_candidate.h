#pragma once
#include <algorithm>
#include "translation_coverage.h"

// Isolated candidate, not enabled in the application. It consumes only the
// captured source and the model's own output. Pixel/reference judgments live
// outside the inference process.
namespace luma::coverage_candidate {
inline std::vector<std::string> Sentences(const std::string& source) {
  auto original=coverage::Sentences(source);
  if(!original.empty()||source.size()>1800)return original;
  static const std::regex boundary("[.!?]+\\s+(?=[\"']?[A-Z])");
  static const std::regex abbreviation("\\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|No|vs|etc)\\.$",std::regex::icase);
  static const std::regex initial("\\b[A-Z]\\.$");
  static const std::regex complete("[.!?][\"']?$");
  static const std::regex unfinished("(?:[A-Za-z]|,)[\"']?$");
  static const std::regex ellipsis("\\.{2,}[\"']?$");
  std::vector<std::string> result;size_t start=0;
  for(auto it=std::sregex_iterator(source.begin(),source.end(),boundary);it!=std::sregex_iterator();++it) {
    auto match=*it;if(coverage::Trim(match.str()).size()!=1)continue;
    auto prefix=source.substr(0,match.position()+1);
    if(std::regex_search(prefix,abbreviation)||std::regex_search(prefix,initial))continue;
    size_t end=match.position()+match.length();result.push_back(coverage::Trim(source.substr(start,end-start)));start=end;
  }
  result.push_back(coverage::Trim(source.substr(start)));
  if(result.size()<2||result.size()>4)return {};
  for(size_t i=0;i<result.size();++i) {
    const auto& part=result[i];auto words=coverage::Words(part);
    if(words<3||words>70||std::regex_search(part,ellipsis))return {};
    if(std::regex_search(part,complete))continue;
    // A screen may contain a complete sentence followed by a visible clause
    // whose punctuation is below the viewport. Translate only those words.
    if(i+1!=result.size()||words<5||!std::regex_search(part,unfinished))return {};
  }
  return result;
}
inline bool Retry(const std::string& source,const std::string& output,const std::vector<std::string>& parts) {
  if(coverage::Retry(source,output,parts))return true;
  if(parts.empty()||output.empty())return false;
  // In Spanish an interrogative can grow despite an omitted short question,
  // so the previous character-length ratio misses that omission.
  return std::count(source.begin(),source.end(),'?')>std::count(output.begin(),output.end(),'?');
}
}
