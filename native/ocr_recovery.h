#pragma once
#include <algorithm>
#include <functional>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

// Pixel-derived OCR proposals only. This policy has no comic transcripts,
// translations, chapter identifiers or expected answers.
namespace luma::recovery {
inline std::string Key(const std::string& value) {
  std::string out;
  for(unsigned char c:value) {
    if(c>='a'&&c<='z')out+=static_cast<char>(c-'a'+'A');
    else if((c>='A'&&c<='Z')||(c>='0'&&c<='9'))out+=static_cast<char>(c);
  }
  return out;
}
inline std::vector<std::string> Parts(const std::string& text) {
  std::istringstream stream(text);std::vector<std::string> out;std::string word;
  while(stream>>word)if(!Key(word).empty())out.push_back(word);
  return out;
}
inline std::vector<std::string> Words(const std::string& text) {
  auto out=Parts(text);for(auto& word:out)word=Key(word);return out;
}
struct Alignment {size_t edits=0;std::vector<std::pair<int,int>> links;};
template<class Sequence> Alignment Align(const Sequence& a,const Sequence& b) {
  const size_t rows=a.size()+1,cols=b.size()+1;
  std::vector<size_t> cost(rows*cols);auto at=[&](size_t i,size_t j)->size_t&{return cost[i*cols+j];};
  for(size_t i=0;i<rows;++i)at(i,0)=i;for(size_t j=0;j<cols;++j)at(0,j)=j;
  for(size_t i=1;i<rows;++i)for(size_t j=1;j<cols;++j)
    at(i,j)=std::min({at(i-1,j)+1,at(i,j-1)+1,at(i-1,j-1)+(a[i-1]!=b[j-1])});
  Alignment result;result.edits=at(a.size(),b.size());size_t i=a.size(),j=b.size();
  while(i||j) {
    if(i&&j&&at(i,j)==at(i-1,j-1)+(a[i-1]!=b[j-1])){result.links.push_back({static_cast<int>(i-1),static_cast<int>(j-1)});--i;--j;}
    else if(i&&at(i,j)==at(i-1,j)+1){result.links.push_back({static_cast<int>(i-1),-1});--i;}
    else {result.links.push_back({-1,static_cast<int>(j-1)});--j;}
  }
  std::reverse(result.links.begin(),result.links.end());return result;
}
inline std::vector<bool> Agreed(const std::vector<std::string>& words,const std::vector<std::string>& evidence) {
  std::vector<bool> result(words.size(),false);
  for(auto [i,j]:Align(words,evidence).links)if(i>=0&&j>=0&&words[i]==evidence[j])result[i]=true;
  return result;
}
inline std::vector<std::string> ProtectedNumbers(const std::vector<std::string>& values) {
  std::vector<std::string> out;
  for(const auto& value:values) {
    size_t letters=0,digits=0;bool embedded=true;
    auto alpha=[](char c){return c>='A'&&c<='Z';};
    for(size_t i=0;i<value.size();++i) {
      char c=value[i];if(alpha(c))++letters;
      else if(c>='0'&&c<='9') {++digits;
        if(std::string("0158").find(c)==std::string::npos||i==0||i+1==value.size()||!alpha(value[i-1])||!alpha(value[i+1]))embedded=false;}
    }
    if(digits&&!(embedded&&letters>=3))out.push_back(value);
  }
  return out;
}
inline std::vector<std::string> Negations(const std::vector<std::string>& words) {
  static const std::vector<std::string> negatives{"NO","NOT","NEVER","NONE","NOTHING","NOBODY","WITHOUT","CANNOT","CANT","DONT","DOESNT","DIDNT","ISNT","ARENT","WASNT","WERENT","WONT","WOULDNT","COULDNT","SHOULDNT","HASNT","HAVENT","HADNT"};
  std::vector<std::string> out;for(const auto& word:words)if(std::find(negatives.begin(),negatives.end(),word)!=negatives.end())out.push_back(word);
  std::sort(out.begin(),out.end());return out;
}
using Vocabulary = std::function<bool(const std::string&)>;
inline bool Known(const std::string& word,const Vocabulary& known) {
  return known(word)&&(word.size()>1||word=="A"||word=="I");
}
inline bool Accept(const std::string& old,const std::string& old_native,
    const std::string& close_text,const std::string& near_support,const std::string& context,
    const std::string& context_support,const Vocabulary& known) {
  auto before=Key(old),after=Key(close_text);
  if(after!=Key(context)||before==after)return false;
  auto a=Words(old),b=Words(close_text);
  if(a.empty()||b.empty()||a.size()>150||b.size()>150)return false;
  if(Align(before,after).edits>std::max(2.0,.35*std::max(before.size(),after.size())))return false;
  if(ProtectedNumbers(a)!=ProtectedNumbers(b)||Negations(a)!=Negations(b))return false;
  auto original=Agreed(a,Words(old_native)),close=Agreed(b,Words(near_support)),wide=Agreed(b,Words(context_support));
  for(auto [i,j]:Align(a,b).links) {
    if(j<0)return false;
    if(i>=0&&a[i]==b[j])continue;
    if(!close[j]||!wide[j]||!Known(b[j],known))return false;
    if(i>=0&&Known(a[i],known)&&original[i])return false;
  }
  return true;
}
struct Ensemble {std::string text,support;};
inline bool CompleteLine(const std::string& old,const std::string& primary,const std::string& alternate,const Vocabulary& known) {
  auto a=Words(old),b=Words(primary);
  auto before=Key(old),after=Key(primary);
  if(b!=Words(alternate)||a.empty()||a.size()>40||b.size()>40||b.size()<a.size())return false;
  if(before.size()<6||after.size()<before.size()+2||after.size()>before.size()*3+6||after.find(before)==std::string::npos)return false;
  if(ProtectedNumbers(a)!=ProtectedNumbers(b)||Negations(a)!=Negations(b))return false;
  // Retain a contiguous word span. Edit-distance ties can align a clipped
  // final word with a newly added word rather than its actual completion.
  for(size_t start=0;start+a.size()<=b.size();++start) {
    bool valid=true;
    for(size_t j=0;j<b.size();++j) {
      if(j<start||j>=start+a.size()){if(!Known(b[j],known))valid=false;continue;}
      size_t i=j-start;if(a[i]==b[j])continue;
      if(!Known(b[j],known)){valid=false;break;}
      // Only a clipped edge word can grow. Interior words cannot be rewritten.
      bool prefix=i==a.size()-1&&a[i].size()>=3&&b[j].size()>=a[i].size()+2&&b[j].find(a[i])==0;
      bool suffix=i==0&&a[i].size()>=3&&b[j].size()>=a[i].size()+2&&b[j].compare(b[j].size()-a[i].size(),a[i].size(),a[i])==0;
      if(!prefix&&!suffix){valid=false;break;}
    }
    if(valid)return true;
  }
  return false;
}
inline Ensemble Combine(const std::string& primary,const std::string& alternate,float alternate_confidence,const Vocabulary& known) {
  auto parts=Parts(primary),others=Parts(alternate);auto a=Words(primary),b=Words(alternate);
  std::vector<bool> supported(parts.size(),false);
  for(auto [i,j]:Align(a,b).links) {
    if(i<0||j<0)continue;
    if(a[i]==b[j]&&alternate_confidence>=.65f)supported[i]=true;
    else if(!Known(a[i],known)&&Known(b[j],known)&&alternate_confidence>=.85f&&
        Align(a[i],b[j]).edits<=std::max(1.0,.3*std::max(a[i].size(),b[j].size()))) {
      bool uppercase=true,letters=false;for(unsigned char c:parts[i])if((c>='A'&&c<='Z')||(c>='a'&&c<='z')){letters=true;if(c>='a'&&c<='z')uppercase=false;}
      parts[i]=others[j];if(letters&&uppercase)for(char& c:parts[i])if(c>='a'&&c<='z')c=static_cast<char>(c-'a'+'A');
      supported[i]=true;
    }
  }
  Ensemble result;
  for(size_t i=0;i<parts.size();++i){if(i){result.text+=' ';result.support+=' ';}result.text+=parts[i];result.support+=supported[i]?parts[i]:"UNSUPPORTEDWORD"+std::to_string(i);}
  return result;
}
}
