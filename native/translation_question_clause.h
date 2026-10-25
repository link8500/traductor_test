#pragma once
#include "translation_opening.h"

// Follow-up candidate: complete short English interrogative clauses only.
// Nominal fragments, quoted text and sounds remain outside this policy.
namespace luma::question_clause {
inline opening::Parts Split(const std::string& source) {
  const auto text=coverage::Trim(source);
  static const std::regex pattern("^([A-Za-z][A-Za-z' ]{1,63}\\?)\\s+(.+)$");
  static const std::set<std::string> first_words{"what","why","who","whom","where","when","how","which","whose",
      "are","is","was","were","do","does","did","can","could","will","would",
      "shall","should","may","might","have","has","had"};
  std::smatch match;
  if(text.size()>1800||!std::regex_match(text,match,pattern)||punctuation::Quoted(text)||
      text.find_first_of("|{}@#&")!=std::string::npos)return {};
  auto first=match[1].str(),rest=match[2].str();auto n=coverage::Words(first),m=coverage::Words(rest);
  auto key=coverage::Letters(first.substr(0,first.find(' ')));
  if(n<2||n>4||m<4||m>100||!first_words.count(key))return {};
  return {first,rest};
}
inline std::string ModelInput(const std::string& source) {
  return std::regex_replace(opening::ModelInput(source),std::regex("\\bi\\b"),"I");
}
}
