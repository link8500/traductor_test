#include "ocr_morph_consensus_candidate.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>

int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    size_t count=0;auto check=[&](bool ok){++count;if(!ok)throw std::runtime_error("Inflection guard "+std::to_string(count));};
    std::set<std::string> vocabulary{"WE","ARE","HOME","WALK","THIS","IS","FOR","US","FAIR","TAKE","GOLD","COINS","NOT","GO","NOW","REACH","THE","ROAD","BUILD","MAKE"};
    auto known=[&](const std::string& word){return vocabulary.count(word)!=0;};
    auto select=[&](const std::string& base,const std::string& a,const std::string& b){return luma::morph_consensus_candidate::Select(base,a,b,known);};
    check(select("WE ARE WALXING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text=="WE ARE WALKING HOME.");
    check(select("THIS IS UNFATR FOR US.","THIS IS UNFAIR FOR US.","THIS IS UNFAIR FOR US.").morphology_recovered);
    check(!select("WE ARE WALXING HOME.","WE ARE WALKING HOME.","WE ARE WALXING HOME.").morphology_recovered);
    check(select("WE ARE MARENA HOME.","WE ARE MARINA HOME.","WE ARE MARINA HOME.").text=="WE ARE MARENA HOME.");
    check(!select("WE ARE WALKING HOME.","WE ARE WALXING HOME.","WE ARE WALXING HOME.").morphology_recovered);
    check(select("TAKE 12 WALXING GOLD COINS.","TAKE 17 WALKING GOLD COINS.","TAKE 17 WALKING GOLD COINS.").text=="TAKE 12 WALXING GOLD COINS.");
    check(select("WE ARE NOT WALXING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text=="WE ARE NOT WALXING HOME.");
    check(select("WE ARE WALXING HOME.","WE ARE WALKING HOME.","WE ARE WALKING HOME.").text.find("WALXING")==std::string::npos);
    check(!luma::morph_consensus_candidate::SupportedRoot("WALK1NG",known));
    check(luma::morph_consensus_candidate::SupportedRoot("MAKING",known));
    check(!luma::morph_consensus_candidate::SupportedRoot("ABCDING",known));
    check(!luma::morph_consensus_candidate::SupportedRoot("FAIR",known));
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
    auto result=luma::morph_consensus_candidate::Select(row.at("base"),row.at("first"),row.at("second"),
        [&](const std::string& word){return words.count(word)!=0;});
    row["selected"]=result.text;row["morphology_recovered"]=result.morphology_recovered;
    row["corroborated_inflections"]=result.corroborated_inflections;
    std::cout<<row.dump()<<std::endl;
  }
}
