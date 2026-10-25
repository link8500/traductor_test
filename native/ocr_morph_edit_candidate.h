#pragma once
#include "ocr_morph_consensus_candidate.h"

namespace luma::morph_edit_candidate {
struct Result {std::string text;size_t single_letter_recoveries=0;};
inline Result Select(const std::string& base,const std::string& first,const std::string& second,
                     const recovery::Vocabulary& known) {
  auto established=morph_consensus_candidate::Select(base,first,second,known);
  Result result{established.text,0};
  auto a=full_consensus_candidate::Cores(result.text),b=full_consensus_candidate::Cores(first),c=full_consensus_candidate::Cores(second);
  if(a.size()<3||a.size()>150||b.size()>150||c.size()>150)return result;
  auto protect=[](const auto& words){return std::make_tuple(recovery::ProtectedNumbers(words),
      full_consensus_candidate::WrittenNumbers(words),recovery::Negations(words));};
  if(protect(a)!=protect(b)||protect(a)!=protect(c))return result;
  std::vector<int> left(a.size(),-1),right(a.size(),-1);
  for(auto [i,j]:recovery::Align(a,b).links)if(i>=0&&j>=0)left[i]=j;
  for(auto [i,j]:recovery::Align(a,c).links)if(i>=0&&j>=0)right[i]=j;
  auto anchor=[&](size_t i){return left[i]>=0&&right[i]>=0&&b[left[i]]==a[i]&&c[right[i]]==a[i];};
  std::set<std::string> admitted;
  for(size_t i=0;i<a.size();++i) {
    if(left[i]<0||right[i]<0||known(a[i])||a[i].size()<4||!morph_consensus_candidate::Letters(a[i]))continue;
    const auto& word=b[left[i]];
    if(word!=c[right[i]]||known(word)||!morph_consensus_candidate::SupportedRoot(word,known))continue;
    if(std::max(word.size(),a[i].size())!=std::min(word.size(),a[i].size())+1||recovery::Align(a[i],word).edits!=1)continue;
    bool anchored=false;
    if(i>0&&i+1<a.size())anchored=anchor(i-1)&&anchor(i+1)&&left[i-1]+1==left[i]&&left[i]+1==left[i+1]&&right[i-1]+1==right[i]&&right[i]+1==right[i+1];
    else if(i==0)anchored=anchor(1)&&anchor(2)&&left[0]+1==left[1]&&left[1]+1==left[2]&&right[0]+1==right[1]&&right[1]+1==right[2];
    else anchored=anchor(i-1)&&anchor(i-2)&&left[i-2]+1==left[i-1]&&left[i-1]+1==left[i]&&right[i-2]+1==right[i-1]&&right[i-1]+1==right[i];
    if(anchored)admitted.insert(word);
  }
  if(admitted.empty())return result;
  auto selected=consensus_candidate::Select(result.text,first,second,[&](const std::string& word){return known(word)||admitted.count(word)!=0;});
  auto after=full_consensus_candidate::Cores(selected.text);
  if(after.size()!=a.size())return result;
  size_t changed=0;
  for(size_t i=0;i<a.size();++i)if(a[i]!=after[i]) {
    if(!admitted.count(after[i]))return result;
    ++changed;
  }
  if(changed){result.text=selected.text;result.single_letter_recoveries=changed;}
  return result;
}
}
