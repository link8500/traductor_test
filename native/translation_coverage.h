#pragma once
#include <algorithm>
#include <regex>
#include <string>
#include <vector>

// This policy consumes only the actual source and the model's own output.
// It contains no comic transcripts or expected translations.
namespace luma::coverage {
inline std::string Trim(const std::string& value) {
  auto first=value.find_first_not_of(" \t\r\n");
  if(first==std::string::npos)return {};
  return value.substr(first,value.find_last_not_of(" \t\r\n")-first+1);
}
inline size_t Words(const std::string& value) {
  static const std::regex word("[A-Za-z]+(?:'[A-Za-z]+)?");
  return std::distance(std::sregex_iterator(value.begin(),value.end(),word),std::sregex_iterator());
}
inline std::vector<std::string> Sentences(const std::string& source) {
  if(source.size()>1800)return {};
  static const std::regex boundary("[.!?]+\\s+(?=[\"']?[A-Z])");
  static const std::regex abbreviation("\\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|No|vs|etc)\\.$",std::regex::icase);
  static const std::regex initial("\\b[A-Z]\\.$");
  static const std::regex complete("[.!?][\"']?$");
  static const std::regex ellipsis("\\.{2,}[\"']?$");
  static const std::regex visible_clause("(?:[A-Za-z]|,)[\"']?$");
  std::vector<std::string> result;size_t start=0;
  for(auto it=std::sregex_iterator(source.begin(),source.end(),boundary);it!=std::sregex_iterator();++it) {
    auto match=*it;auto punctuation=Trim(match.str());
    if(punctuation.size()!=1)continue;
    auto prefix=source.substr(0,match.position()+1);
    if(std::regex_search(prefix,abbreviation)||std::regex_search(prefix,initial))continue;
    size_t end=match.position()+match.length();result.push_back(Trim(source.substr(start,end-start)));start=end;
  }
  result.push_back(Trim(source.substr(start)));
  if(result.size()<2||result.size()>4)return {};
  for(size_t i=0;i<result.size();++i) {
    const auto& part=result[i];auto words=Words(part);
    if(words<2||words>70||std::regex_search(part,ellipsis))return {};
    if(std::regex_search(part,complete))continue;
    // A visible final clause may continue beyond the screen. The retry
    // translates only its captured words; it does not invent a completion.
    if(i+1!=result.size()||words<5||!std::regex_search(part,visible_clause))return {};
  }
  return result;
}
inline size_t Clauses(const std::string& text) {
  size_t count=0;
  for(size_t i=0;i<text.size();++i) {
    if(std::string(",;:.!?").find(text[i])==std::string::npos)continue;
    size_t end=i+1;
    while(end<text.size()&&std::string(",;:.!?\"'").find(text[end])!=std::string::npos)++end;
    if(end==text.size()||std::string(" \t\r\n").find(text[end])!=std::string::npos)++count;
    i=end-1;
  }
  return count;
}
inline bool Retry(const std::string& source,const std::string& output,const std::vector<std::string>& parts) {
  // Commas also count: a fluent paraphrase may combine complete sentences.
  auto characters=[](const std::string& text){size_t n=0;for(unsigned char c:text)if((c&0xc0)!=0x80)++n;return n;};
  if(parts.empty()||output.empty())return false;
  bool short_output=characters(output)<.70*characters(source)&&Clauses(output)<parts.size();
  // Short questions can disappear while the remaining Spanish grows past
  // the length cutoff. Contrast actual question ends as a separate signal.
  bool short_clause=std::any_of(parts.begin(),parts.end(),[](const auto& part){return Words(part)<=3;});
  size_t sentence_ends=0;
  for(size_t i=0;i<output.size();++i)if(std::string(".!?").find(output[i])!=std::string::npos) {
    while(i+1<output.size()&&std::string(".!?").find(output[i+1])!=std::string::npos)++i;
    ++sentence_ends;
  }
  bool shortened_sentence=characters(output)<.70*characters(source)&&sentence_ends<parts.size();
  return short_output||shortened_sentence||(short_clause&&Clauses(output)<parts.size())||
      std::count(source.begin(),source.end(),'?')>std::count(output.begin(),output.end(),'?');
}
inline std::string Letters(std::string text) {
  std::string out;
  for(unsigned char c:text)if(c>='A'&&c<='Z')out+=static_cast<char>(c+32);else if(c>='a'&&c<='z')out+=static_cast<char>(c);
  return out;
}
}

namespace luma::coverage {
inline size_t RepeatedRun(const std::string& text) {
  static const std::regex word("[A-Za-z]+(?:'[A-Za-z]+)?");
  std::vector<std::string> values;
  for(auto it=std::sregex_iterator(text.begin(),text.end(),word);it!=std::sregex_iterator();++it)values.push_back(Letters(it->str()));
  size_t maximum=0;
  for(size_t width=1;width<=3;++width)for(size_t start=0;start+width<=values.size();++start) {
    size_t repeats=1,next=start+width;
    while(next+width<=values.size()&&std::equal(values.begin()+start,values.begin()+start+width,values.begin()+next)){++repeats;next+=width;}
    maximum=std::max(maximum,repeats);
  }
  return maximum;
}
inline bool Plausible(const std::string& source,const std::string& output) {
  auto repeated=RepeatedRun(output);return repeated<4||repeated<=RepeatedRun(source)+1;
}
// The established retry handles longer clauses with a length or question
// deficit. Newly admitted short/merged clauses need additional safeguards:
// punctuation and length alone cannot distinguish an omission from a fluent
// paraphrase. These checks do not establish semantic correctness.
inline bool LongClauseRetry(const std::string& source,const std::string& output,const std::vector<std::string>& parts) {
  if(parts.empty()||output.empty()||std::any_of(parts.begin(),parts.end(),[](const auto& part){return Words(part)<3;}))return false;
  auto characters=[](const std::string& text){size_t n=0;for(unsigned char c:text)if((c&0xc0)!=0x80)++n;return n;};
  return (characters(output)<.70*characters(source)&&Clauses(output)<parts.size())||
      std::count(source.begin(),source.end(),'?')>std::count(output.begin(),output.end(),'?');
}
inline std::vector<std::u32string> NormalizedWords(const std::string& text) {
  std::vector<std::u32string> words;std::u32string word;
  auto flush=[&](){if(!word.empty()){words.push_back(word);word.clear();}};
  for(size_t i=0;i<text.size();) {
    unsigned char first=text[i++];char32_t code=first;size_t continuation=0;
    if(first>=0xc2&&first<=0xdf){code=first&31;continuation=1;}
    else if(first>=0xe0&&first<=0xef){code=first&15;continuation=2;}
    else if(first>=0xf0&&first<=0xf4){code=first&7;continuation=3;}
    else if(first>=0x80){flush();continue;}
    bool valid=i+continuation<=text.size();
    for(size_t n=0;valid&&n<continuation;++n){unsigned char c=text[i++];if((c&0xc0)!=0x80)valid=false;else code=(code<<6)|(c&63);}
    if(!valid){flush();continue;}
    if(code>=U'A'&&code<=U'Z')code+=32;
    if(code>=0xc0&&code<=0xde&&code!=0xd7)code+=32;
    if(code==0x2019)code=U'\'';
    bool letter=(code>=U'a'&&code<=U'z')||(code>=U'0'&&code<=U'9')||
        (code>=0xc0&&code<=0xff&&code!=0xd7&&code!=0xf7);
    if(letter||(code==U'\''&&!word.empty()))word+=code;else flush();
  }
  flush();return words;
}
inline bool PreservesExistingWords(const std::string& whole,const std::string& joined) {
  auto before=NormalizedWords(whole),after=NormalizedWords(joined);
  if(before.empty())return false;
  std::sort(before.begin(),before.end());std::sort(after.begin(),after.end());
  size_t matched=0,i=0,j=0;
  while(i<before.size()&&j<after.size()) {
    if(before[i]==after[j]){++matched;++i;++j;}
    else if(before[i]<after[j])++i;else ++j;
  }
  return matched*5>=before.size()*4;
}
inline bool PreservesNegation(const std::string& source,const std::string& output) {
  auto words=NormalizedWords(source);bool negative=false;
  for(const auto& word:words)if(word==U"no"||word==U"not"||word==U"never"||word==U"without"||word==U"neither"||word==U"nor"||
      (word.size()>3&&word.substr(word.size()-3)==U"n't")){negative=true;break;}
  if(!negative)return true;
  for(const auto& word:NormalizedWords(output))if(word==U"no"||word==U"nunca"||word==U"jamás"||word==U"sin"||word==U"ni"||
      word==U"nadie"||word==U"nada"||word==U"ningún"||word==U"ninguno"||word==U"ninguna"||word==U"tampoco")return true;
  return false;
}
}
