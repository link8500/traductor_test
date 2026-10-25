#include "ocr_consensus_candidate.h"
#include "json.hpp"
#include <iostream>
#include <fstream>
#include <set>
#include <stdexcept>
int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    size_t count=0;auto check=[&](bool ok){++count;if(!ok)throw std::runtime_error("Consensus guard "+std::to_string(count));};
    auto Select=[](const std::string& a,const std::string& b,const std::string& c) {
      const std::set<std::string> words{"WE","MUST","LEAVE","WAIT","HERE","NOW","TAKE","COINS","DO","NOT","GO","BECAUSE"};
      return luma::consensus_candidate::Select(a,b,c,[&](const std::string& word){return words.count(word)!=0;});
    };
    check(Select("WE MLST LEAVE.","WE MUST LEAVE.","WE MUST LEAVE.").text=="WE MUST LEAVE.");
    check(Select("WE MUST LEAVE.","WE LEAVE.","WE LEAVE.").text=="WE MUST LEAVE.");
    check(Select("WAIT HERE.","WAIT HERE NOW.","WAIT HERE NOW.").text=="WAIT HERE.");
    check(Select("TAKE 12 COINS.","TAKE 17 COINS.","TAKE 17 COINS.").text=="TAKE 12 COINS.");
    check(Select("DO NOT GO.","DO NOW GO.","DO NOW GO.").text=="DO NOT GO.");
    check(Select("We mlst leave!","WE MUST LEAVE.","WE MUST LEAVE.").text=="We must leave!");
    check(Select("WE MLST LEAVE.","WE MUST LEAVE.","WE JUST LEAVE.").text=="WE MLST LEAVE.");
    check(Select("", "ONE WORD", "ONE WORD").text.empty());
    check(Select("RADIO ID A17", "RADIO ID A11", "RADIO ID A11").text=="RADIO ID A17");
    check(Select("WE LEAVE BECAUSE WE MUST.","WE LEAVE BECALSE WE MUST.","WE LEAVE BECALSE WE MUST.").text=="WE LEAVE BECAUSE WE MUST.");
    check(Select("MY NAME IS KORVAN.","MY NAME IS KORBAN.","MY NAME IS KORBAN.").text=="MY NAME IS KORVAN.");
    std::cout<<"{\"guards\":"<<count<<",\"success\":true,\"application_enabled\":false}"<<std::endl;return 0;
  }
  if(argc!=2)return 2;
  std::ifstream vocabularyFile(argv[1]);auto tokenizer=nlohmann::json::parse(vocabularyFile);std::set<std::string> words;
  for(const auto& value:tokenizer.at("tokens")) {
    auto piece=value.get<std::string>();const std::string prefix="\xE2\x96\x81";
    if(piece.compare(0,prefix.size(),prefix)==0)words.insert(luma::recovery::Key(piece.substr(prefix.size())));
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);
    auto result=luma::consensus_candidate::Select(row.at("base"),row.at("first"),row.at("second"),[&](const std::string& word){return words.count(word)!=0;});
    row["selected"]=result.text;row["replacements"]=result.replacements;std::cout<<row.dump()<<std::endl;
  }
}
