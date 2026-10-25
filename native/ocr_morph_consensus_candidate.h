#pragma once
#include "ocr_full_consensus_candidate.h"
#include <set>

// Pixel agreement can corroborate a productive inflection absent as a whole
// token from the translation vocabulary. Never invent a word from a stem:
// both readers must already supply the identical spelling at this location.
namespace luma::morph_consensus_candidate {
inline bool Letters(const std::string& word) {
  return !word.empty()&&std::all_of(word.begin(),word.end(),[](char c){return c>='A'&&c<='Z';});
}
inline bool SupportedRoot(const std::string& word,const recovery::Vocabulary& known) {
  if(word.size()<6||word.size()>30||!Letters(word))return false;
  auto root=[&](const std::string& value){return value.size()>=4&&known(value);};
  for(const auto* prefix:{"UN","RE","DIS","MIS","NON","PRE"}) {
    std::string affix(prefix);
    if(word.compare(0,affix.size(),affix)==0&&root(word.substr(affix.size())))return true;
  }
  for(const auto* suffix:{"ING","ED","LY","NESS","LESS","MENT"}) {
    std::string affix(suffix);
    if(word.size()<=affix.size()||word.compare(word.size()-affix.size(),affix.size(),affix)!=0)continue;
    auto stem=word.substr(0,word.size()-affix.size());
    if(root(stem))return true;
    if(affix=="ING"&&root(stem+"E"))return true;
    if((affix=="ING"||affix=="ED")&&stem.size()>4&&stem.back()==stem[stem.size()-2]&&root(stem.substr(0,stem.size()-1)))return true;
  }
  return false;
}
struct Result {std::string text;bool morphology_recovered=false;size_t corroborated_inflections=0;};
inline Result Select(const std::string& base,const std::string& first,const std::string& second,
                     const recovery::Vocabulary& known) {
  auto established=full_consensus_candidate::Select(base,first,second,known);
  Result result{established.text,false,0};
  auto a=full_consensus_candidate::Cores(result.text),b=full_consensus_candidate::Cores(first),c=full_consensus_candidate::Cores(second);
  if(a.empty()||a.size()>150||b.size()>150||c.size()>150)return result;
  auto protectedContent=[](const std::vector<std::string>& words){
    return std::make_tuple(recovery::ProtectedNumbers(words),full_consensus_candidate::WrittenNumbers(words),recovery::Negations(words));
  };
  if(protectedContent(a)!=protectedContent(b)||protectedContent(a)!=protectedContent(c))return result;
  std::vector<int> left(a.size(),-1),right(a.size(),-1);
  for(auto [i,j]:recovery::Align(a,b).links)if(i>=0&&j>=0)left[i]=j;
  for(auto [i,j]:recovery::Align(a,c).links)if(i>=0&&j>=0)right[i]=j;
  std::set<std::string> admitted;
  for(size_t i=0;i<a.size();++i) {
    if(left[i]<0||right[i]<0||known(a[i])||!Letters(a[i]))continue;
    const auto& proposal=b[left[i]];
    if(proposal!=c[right[i]]||proposal.size()!=a[i].size()||known(proposal)||!SupportedRoot(proposal,known))continue;
    size_t differences=0;
    for(size_t j=0;j<proposal.size();++j)differences+=proposal[j]!=a[i][j];
    if(differences==1)admitted.insert(proposal);
  }
  if(admitted.empty())return result;
  auto selected=full_consensus_candidate::Select(result.text,first,second,
      [&](const std::string& word){return known(word)||admitted.count(word)!=0;});
  if(selected.text!=result.text) {
    result.text=selected.text;result.morphology_recovered=true;result.corroborated_inflections=admitted.size();
  }
  return result;
}
}
