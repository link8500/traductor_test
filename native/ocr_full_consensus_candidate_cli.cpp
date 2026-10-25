#include "ocr_full_consensus_candidate.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>

int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    size_t count=0;auto check=[&](bool ok){++count;if(!ok)throw std::runtime_error("Full consensus guard "+std::to_string(count));};
    auto agree=luma::full_consensus_candidate::CompleteAgreement;
    check(agree("KEEP THE LIP CLEAN.","KEEP THE CUP CLEAN.","KEEP THE CUP CLEAN."));
    check(!agree("KEEP THE LIP CLEAN.","KEEP THE CUP CLEAN.","KEEP THE LIP CLEAN."));
    check(!agree("WE CAN GO HOME.","WE CANNOT GO HOME.","WE CANNOT GO HOME."));
    check(!agree("TAKE 12 GOLD COINS.","TAKE 17 GOLD COINS.","TAKE 17 GOLD COINS."));
    check(!agree("TAKE FOUR GOLD COINS.","TAKE FIVE GOLD COINS.","TAKE FIVE GOLD COINS."));
    check(!agree("WE GO HOME NOW.","THEY STAY AT WORK.","THEY STAY AT WORK."));
    check(!agree("I'LL GO HOME NOW.","ILL GO HOME NOW.","I'LL GO HOME NOW."));
    check(!agree("I'LL GO HOME NOW.","ILL GO HOME NOW.","ILL GO HOME NOW."));
    check(agree("I'IL GO HOME NOW.","I'LL GO HOME NOW.","I'LL GO HOME NOW."));
    check(!agree("GO HOME.","GO HOME NOW.","GO HOME NOW."));
    check(!agree("TAKE SECOND ROAD HOME.","TAKE THIRD ROAD HOME.","TAKE THIRD ROAD HOME."));
    check(luma::full_consensus_candidate::UnresolvedLetterFragment("IT IS Q IN THE BOX."));
    check(!luma::full_consensus_candidate::UnresolvedLetterFragment("I HAVE A BOX."));
    check(!agree("WE DON'T GO HOME.","WE DO GO HOME.","WE DO GO HOME."));
    auto known=[](const std::string& word){return word!="BECALSE";};
    check(luma::full_consensus_candidate::Select("WE LEFT BECAUSE IT RAINED.","WE LEFT BECALSE IT RAINED.","WE LEFT BECALSE IT RAINED.",known).text=="WE LEFT BECAUSE IT RAINED.");
    check(luma::full_consensus_candidate::Select("WE LEFT BECAUSE IT RAINED.","WE LEFT H BECAUSE IT RAINED.","WE LEFT H BECAUSE IT RAINED.",known).text=="WE LEFT BECAUSE IT RAINED.");
    check(luma::full_consensus_candidate::PreserveIntactPunctuation("YOU GO, MOW.","YOU GO NOW.")=="YOU GO, NOW.");
    std::cout<<nlohmann::json{{"guards",count},{"success",true},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  if(argc!=2)return 2;
  std::ifstream file(argv[1]);auto tokenizer=nlohmann::json::parse(file);std::set<std::string> words;
  const std::string prefix="\xE2\x96\x81";
  for(const auto& value:tokenizer.at("tokens")) {
    auto piece=value.get<std::string>();if(piece.compare(0,prefix.size(),prefix)==0)words.insert(luma::recovery::Key(piece.substr(prefix.size())));
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);
    auto result=luma::full_consensus_candidate::Select(row.at("base"),row.at("first"),row.at("second"),
        [&](const std::string& word){return words.count(word)!=0;});
    row["selected"]=result.text;row["complete_agreement"]=result.complete_agreement;row["partial_withheld"]=result.partial_withheld;
    std::cout<<row.dump()<<std::endl;
  }
}
