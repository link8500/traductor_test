#pragma once
#include "translation_tail_candidate.h"

namespace luma::tail {
using Parts=tail_candidate::Parts;
using Result=tail_candidate::Result;
using tail_candidate::Plan;

// Translating an isolated English "you" can lose the plural addressee that
// was established in the head. Reject that disagreement; never guess a new
// inflection or replace a model word to make the added sentence fit.
inline bool KeepsAddresseeNumber(const Parts& parts,const std::string& head,const std::string& extra) {
  const auto source=coverage::NormalizedWords(parts.tail);
  auto has=[](const auto& words,const std::set<std::u32string>& values) {
    return std::any_of(words.begin(),words.end(),[&](const auto& word){return values.count(word)!=0;});
  };
  if(!has(source,{U"you",U"your",U"yours"}))return true;
  const auto before=coverage::NormalizedWords(head),after=coverage::NormalizedWords(extra);
  const std::set<std::u32string> plural{U"ustedes",U"vosotros",U"vosotras"};
  const std::set<std::u32string> singular{U"contigo",U"ti",U"tu",U"tuyo",U"tuya",U"tuyos",U"tuyas"};
  return !has(before,plural)||!has(after,singular)||has(after,plural);
}
inline Result Recover(const Parts& parts,const std::string& whole,const std::string& head,const std::string& extra,
                      bool whole_retained=false,bool head_retained=false,bool tail_retained=false) {
  if(!KeepsAddresseeNumber(parts,head,extra))return {whole,false};
  return tail_candidate::Recover(parts,whole,head,extra,whole_retained,head_retained,tail_retained);
}
}
