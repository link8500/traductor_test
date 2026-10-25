#pragma once
#include "ocr_coverage_candidate.h"

// Isolated experiment: a complete replacement requires identical independent
// pixel readings, intact numeric/negative content and substantial old anchors.
// No transcripts, chapter IDs or translation answers are consulted.
namespace luma::full_consensus_candidate {
inline std::vector<std::string> Cores(const std::string& text) {
  auto parts=recovery::Parts(text);
  for(auto& part:parts)part=consensus_candidate::Core(part);
  return parts;
}
inline std::vector<std::string> WrittenNumbers(const std::vector<std::string>& words) {
  static const std::vector<std::string> numbers{
    "ZERO","ONE","TWO","THREE","FOUR","FIVE","SIX","SEVEN","EIGHT","NINE","TEN",
    "ELEVEN","TWELVE","THIRTEEN","FOURTEEN","FIFTEEN","SIXTEEN","SEVENTEEN","EIGHTEEN","NINETEEN",
    "TWENTY","THIRTY","FORTY","FIFTY","SIXTY","SEVENTY","EIGHTY","NINETY","HUNDRED","THOUSAND","MILLION",
    "FIRST","SECOND","THIRD","FOURTH","FIFTH","SIXTH","SEVENTH","EIGHTH","NINTH","TENTH"};
  std::vector<std::string> result;
  for(const auto& word:words)if(std::find(numbers.begin(),numbers.end(),word)!=numbers.end())result.push_back(word);
  return result;
}
inline bool CompleteAgreement(const std::string& base,const std::string& first,const std::string& second) {
  auto a=Cores(base),b=Cores(first),c=Cores(second);
  if(a.empty()||a.size()>150||b.size()<3||b.size()>150||b!=c||a==b)return false;
  auto aw=recovery::Words(base),bw=recovery::Words(first);
  if(recovery::ProtectedNumbers(aw)!=recovery::ProtectedNumbers(bw)||
      WrittenNumbers(aw)!=WrittenNumbers(bw)||recovery::Negations(aw)!=recovery::Negations(bw))return false;
  const auto old=recovery::Key(base),proposal=recovery::Key(first);
  if(old.empty()||proposal.empty()||recovery::Align(old,proposal).edits>
      std::max(2.0,.3*std::max(old.size(),proposal.size())))return false;
  size_t anchors=0;
  for(auto [i,j]:recovery::Align(a,b).links) {
    if(i>=0&&a[i].find('\'')!=std::string::npos&&
        (j<0||b[j].find('\'')==std::string::npos))return false;
    if(i>=0&&j>=0&&a[i]==b[j])++anchors;
  }
  return anchors>=2&&anchors*2>=std::min(a.size(),b.size());
}
inline bool UnresolvedLetterFragment(const std::string& text) {
  for(const auto& word:Cores(text))if(word.size()==1&&word[0]>='A'&&word[0]<='Z'&&word!="A"&&word!="I")return true;
  return false;
}
inline std::string PreserveIntactPunctuation(const std::string& old,const std::string& proposal) {
  auto a=Cores(old),b=Cores(proposal),original=recovery::Parts(old),parts=recovery::Parts(proposal);
  for(auto [i,j]:recovery::Align(a,b).links)if(i>=0&&j>=0&&a[i]==b[j])parts[j]=original[i];
  std::string result;
  for(const auto& part:parts){if(!result.empty())result+=' ';result+=part;}
  return result;
}
struct Result {std::string text;bool complete_agreement=false,partial_withheld=false;};
inline Result Select(const std::string& base,const std::string& first,const std::string& second,
                     const recovery::Vocabulary& known) {
  auto partial=coverage_candidate::Select(base,first,second,known);
  // Judge the full reading against the existing repaired result. Otherwise two
  // correlated readers can undo a valid spelling repair in the older policy.
  bool supported=true;auto a=recovery::Words(partial.text),b=recovery::Words(first);
  for(auto [i,j]:recovery::Align(a,b).links)
    if(j>=0&&(i<0||a[i]!=b[j])&&!recovery::Known(b[j],known))supported=false;
  if(supported&&!UnresolvedLetterFragment(first)&&CompleteAgreement(partial.text,first,second))
    return {PreserveIntactPunctuation(partial.text,first),true,false};
  return {partial.text,false,false};
}
}
