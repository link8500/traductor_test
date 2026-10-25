#pragma once
#include <array>
#include <string>

namespace luma::short_dialogue_candidate {
struct Reading {std::string text;float confidence;};

// A bare vertical stroke is unsafe: require an English pronoun followed by
// an ellipsis, independently stable in both recognizers and both crops.
inline bool SupportedPronoun(const std::array<Reading,4>& evidence,float detector_confidence) {
  if(detector_confidence<.90f)return false;
  for(const auto& read:evidence) {
    if(read.confidence<.95f)return false;
    std::string compact;
    for(size_t i=0;i<read.text.size();) {
      if(read.text.compare(i,3,"\xe2\x80\xa6")==0){compact+="...";i+=3;continue;}
      unsigned char c=read.text[i++];
      if(c==' '||c=='\t'||c=='\r'||c=='\n')continue;
      compact+=static_cast<char>(c);
    }
    if(compact.size()<3||compact.size()>5||compact.front()!='I')return false;
    if(compact.find_first_not_of('.',1)!=std::string::npos)return false;
  }
  return true;
}
}
