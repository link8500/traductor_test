#pragma once
#include "ocr_consensus_candidate.h"

// Isolated follow-up experiment. Insertions need the same pixel-derived word
// sequence from both independent readers and unchanged surrounding anchors.
// No original token can disappear, change its identity, or move position.
namespace luma::coverage_candidate {
struct Result {std::string text;size_t replacements=0,insertions=0;};
struct Gap {std::vector<std::string> words;bool valid=false;};
inline std::vector<Gap> Insertions(const std::vector<std::string>& original,
    const std::vector<std::string>& evidence) {
  std::vector<Gap> gaps(original.size()+1);std::vector<int> mapping(original.size(),-1);
  for(auto [i,j]:recovery::Align(original,evidence).links)
    if(i>=0&&j>=0&&original[i]==evidence[j])mapping[i]=j;
  for(size_t at=0;at<=original.size();++at) {
    bool left=at==0||(mapping[at-1]>=0),right=at==original.size()||mapping[at]>=0;
    if(!left||!right)continue;
    size_t begin=at==0?0:static_cast<size_t>(mapping[at-1]+1);
    size_t end=at==original.size()?evidence.size():static_cast<size_t>(mapping[at]);
    if(end<=begin||end-begin>2)continue;
    // Two intact neighbouring words are mandatory. At a boundary, both must
    // be on the available side. Interior gaps have one anchor on each side.
    if(at==0&&(original.size()<2||mapping[1]!=mapping[0]+1))continue;
    if(at==original.size()&&(original.size()<2||mapping[at-2]<0||mapping[at-2]+1!=mapping[at-1]))continue;
    gaps[at].words.assign(evidence.begin()+begin,evidence.begin()+end);gaps[at].valid=true;
  }
  return gaps;
}
inline Result Select(const std::string& base,const std::string& first,
    const std::string& second,const recovery::Vocabulary& known) {
  auto replaced=consensus_candidate::Select(base,first,second,known);
  Result result{replaced.text,replaced.replacements,0};
  auto a=recovery::Words(result.text),b=recovery::Words(first),c=recovery::Words(second);
  if(a.size()<3||a.size()>150||b.size()>150||c.size()>150)return result;
  auto left=Insertions(a,b),right=Insertions(a,c);auto parts=recovery::Parts(result.text);
  std::vector<std::vector<std::string>> additions(a.size()+1);
  for(size_t at=0;at<=a.size();++at) {
    if(!left[at].valid||!right[at].valid||left[at].words!=right[at].words)continue;
    bool allowed=true;
    for(const auto& word:left[at].words) {
      if(!recovery::Known(word,known)||
          !std::all_of(word.begin(),word.end(),[](char ch){return ch>='A'&&ch<='Z';}))allowed=false;
    }
    if(!allowed||!recovery::Negations(left[at].words).empty())continue;
    additions[at]=left[at].words;
  }
  std::string terminal;
  if(!additions.back().empty()) {
    while(!parts.back().empty()&&std::string(".!?,;:").find(parts.back().back())!=std::string::npos) {
      terminal.insert(terminal.begin(),parts.back().back());parts.back().pop_back();
    }
  }
  std::string joined;bool uppercase=true;
  for(unsigned char ch:result.text)if(ch>='a'&&ch<='z')uppercase=false;
  auto append=[&](std::string part){if(!joined.empty())joined+=' ';joined+=part;};
  for(size_t at=0;at<=parts.size();++at) {
    for(auto word:additions[at]) {
      if(!uppercase)for(char& ch:word)ch=static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
      append(word);++result.insertions;
    }
    if(at<parts.size())append(parts[at]);
  }
  if(result.insertions)result.text=joined+terminal;
  return result;
}
}
