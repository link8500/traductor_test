#pragma once
#include "ocr_recovery.h"
#include <cctype>

// Experimental, pixel-reader consensus. The policy has no chapter text,
// manual transcriptions or translation answers. It cannot remove/add words.
namespace luma::consensus_candidate {
struct Result {std::string text;size_t replacements=0;};
inline std::string Core(std::string part) {
  const std::string curly="\xE2\x80\x99";
  for(size_t at=part.find(curly);at!=std::string::npos;at=part.find(curly,at+1))part.replace(at,curly.size(),"'");
  auto first=part.find_first_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789");
  auto last=part.find_last_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789");
  if(first==std::string::npos)return {};
  part=part.substr(first,last-first+1);
  for(char& ch:part)if(ch>='a'&&ch<='z')ch=static_cast<char>(ch-'a'+'A');
  return part;
}
inline Result Select(const std::string& base,const std::string& first,const std::string& second,const recovery::Vocabulary& known) {
  auto parts=recovery::Parts(base),a=recovery::Words(base),b=recovery::Words(first),c=recovery::Words(second);
  auto firstParts=recovery::Parts(first),secondParts=recovery::Parts(second);std::vector<std::string> rendering(a.size());
  Result result{base,0};if(a.empty()||a.size()>150||b.size()>150||c.size()>150)return result;
  std::vector<int> left(a.size(),-1),right(a.size(),-1);
  for(auto [i,j]:recovery::Align(a,b).links)if(i>=0&&j>=0)left[i]=j;
  for(auto [i,j]:recovery::Align(a,c).links)if(i>=0&&j>=0)right[i]=j;
  auto proposed=a;
  for(size_t i=0;i<a.size();++i) {
    if(left[i]<0||right[i]<0)continue;
    const auto& word=b[left[i]];
    if(word!=c[right[i]]||word==a[i]||word.empty())continue;
    // Letter-only comparison conflates contractions with other words. Require
    // agreement on the actual internal apostrophe and retain it when replacing
    // letters. Existing apostrophes cannot disappear during recovery.
    auto evidence=Core(firstParts[left[i]]);
    if(evidence!=Core(secondParts[right[i]]))continue;
    if(evidence.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'")!=std::string::npos)continue;
    if(Core(parts[i]).find('\'')!=std::string::npos&&evidence.find('\'')==std::string::npos)continue;
    // Whole-token membership is a conservative guard, not a spelling guess.
    // A known original word is kept even if the other two readers disagree;
    // names and identifiers absent from the vocabulary cannot replace it.
    if(recovery::Known(a[i],known)||!recovery::Known(word,known))continue;
    auto numeric=[](const std::string& value){return std::any_of(value.begin(),value.end(),[](unsigned char ch){return ch>='0'&&ch<='9';});};
    if(numeric(a[i])||numeric(word))continue;
    if(recovery::Align(a[i],word).edits>std::max(1.0,.3*std::max(a[i].size(),word.size())))continue;
    proposed[i]=word;
    rendering[i]=evidence;
  }
  if(recovery::Negations(a)!=recovery::Negations(proposed))return result;
  std::string joined;
  for(size_t i=0;i<parts.size();++i) {
    if(i)joined+=' ';
    if(proposed[i]==a[i]){joined+=parts[i];continue;}
    auto part=parts[i];auto firstAlpha=part.find_first_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz");
    auto lastAlpha=part.find_last_of("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz");
    if(firstAlpha==std::string::npos||lastAlpha==std::string::npos){joined+=part;continue;}
    auto replacement=rendering[i];bool uppercase=true;
    for(unsigned char ch:part)if(ch>='a'&&ch<='z')uppercase=false;
    if(!uppercase)for(char& ch:replacement)ch=static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    if(!uppercase&&part[firstAlpha]>='A'&&part[firstAlpha]<='Z')replacement[0]=static_cast<char>(std::toupper(static_cast<unsigned char>(replacement[0])));
    joined+=part.substr(0,firstAlpha)+replacement+part.substr(lastAlpha+1);++result.replacements;
  }
  if(result.replacements)result.text=joined;
  return result;
}
}
