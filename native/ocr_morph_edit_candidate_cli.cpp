#include "ocr_morph_edit_candidate.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    int n=0;auto check=[&](bool value){++n;if(!value)throw std::runtime_error("Letter edit guard "+std::to_string(n));};
    std::set<std::string> vocabulary{"WE","ARE","HOME","WALK","DREAM","THIS","IS","FAIR","FOR","US","NOT","TAKE","12","17","GOLD","COINS"};
    auto known=[&](const std::string& w){return vocabulary.count(w)!=0;};
    auto apply=[&](const std::string& a,const std::string& b,const std::string& c){return luma::morph_edit_candidate::Select(a,b,c,known);};
    check(apply("WE ARE WALING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text=="WE ARE WALKING HOME.");
    check(apply("WE ARE DREAAMING HOME.","WE ARE DREAMING HOME.","WE ARE DREAMING HOME.").single_letter_recoveries==1);
    check(apply("THIS IS UNFAR FOR US.","THIS IS UNFAIR FOR US.","THIS IS UNFAIR FOR US.").single_letter_recoveries==1);
    check(apply("WE ARE WALING HOME.","WE ARE WALKING HOME.","WE ARE WALING HOME.").text=="WE ARE WALING HOME.");
    check(!apply("WE ARE MARIIANA HOME.","WE ARE MARIANA HOME.","WE ARE MARIANA HOME.").single_letter_recoveries);
    check(!apply("WE ARE WALKING HOME.","WE ARE WALING HOME.","WE ARE WALING HOME.").single_letter_recoveries);
    check(!apply("TAKE 12 WALING GOLD COINS.","TAKE 17 WALKING GOLD COINS.","TAKE 17 WALKING GOLD COINS.").single_letter_recoveries);
    check(!apply("WE ARE NOT WALING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").single_letter_recoveries);
    check(!apply("WE ARE WAAALING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").single_letter_recoveries);
    check(!apply("WE ARE WALING HOME.","THIS IS WALKING FOR US.","THIS IS WALKING FOR US.").single_letter_recoveries);
    check(apply("WE ARE WALING HOME!","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text=="WE ARE WALKING HOME!");
    check(apply("We are waling home.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text=="We are walking home.");
    std::cout<<nlohmann::json{{"success",true},{"guards",n},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  if(argc!=2)return 2;
  std::ifstream input(argv[1]);auto tokenizer=nlohmann::json::parse(input);std::set<std::string> known;
  const std::string start="\xE2\x96\x81";
  for(const auto& value:tokenizer.at("tokens")) {
    auto token=value.get<std::string>();if(token.compare(0,start.size(),start)==0)known.insert(luma::recovery::Key(token.substr(start.size())));
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);
    auto result=luma::morph_edit_candidate::Select(row.at("base"),row.at("first"),row.at("second"),[&](const std::string& word){return known.count(word)!=0;});
    row["selected"]=result.text;row["single_letter_recoveries"]=result.single_letter_recoveries;
    std::cout<<row.dump()<<std::endl;
  }
}
