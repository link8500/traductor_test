#include "ocr_coverage_candidate.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>

int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    std::set<std::string> words{"WE","MUST","LEAVE","WAIT","HERE","NOW","YOU","CAN","GO","DO","NOT","NO","TAKE","COINS","ILL","YOUVE","RETURN"};
    auto select=[&](const std::string& a,const std::string& b,const std::string& c){
      return luma::coverage_candidate::Select(a,b,c,[&](const std::string& word){return words.count(word)!=0;});};
    size_t count=0;auto check=[&](bool ok){++count;if(!ok)throw std::runtime_error("Coverage guard "+std::to_string(count));};
    check(select("WE LEAVE NOW.","WE MUST LEAVE NOW.","WE MUST LEAVE NOW.").text=="WE MUST LEAVE NOW.");
    check(select("CAN GO NOW.","YOU CAN GO NOW.","YOU CAN GO NOW.").text=="YOU CAN GO NOW.");
    check(select("YOU CAN GO.","YOU CAN GO NOW.","YOU CAN GO NOW.").text=="YOU CAN GO NOW.");
    check(select("WE LEAVE NOW.","WE MUST LEAVE NOW.","WE LEAVE NOW.").insertions==0);
    check(select("WE LEAVE NOW.","WE NOT LEAVE NOW.","WE NOT LEAVE NOW.").insertions==0);
    check(select("WE LEAVE NOW.","WE 7 LEAVE NOW.","WE 7 LEAVE NOW.").insertions==0);
    check(select("WE LEAVE NOW.","WE KORVAN LEAVE NOW.","WE KORVAN LEAVE NOW.").insertions==0);
    check(select("WE MUST LEAVE NOW.","WE LEAVE NOW.","WE LEAVE NOW.").text=="WE MUST LEAVE NOW.");
    check(select("WE LEAVE.","WE MUST LEAVE.","WE MUST LEAVE.").insertions==0);
    check(select("DO GO NOW.","DO NOT GO NOW.","DO NOT GO NOW.").text=="DO GO NOW.");
    check(select("TAKE 12 COINS.","TAKE 17 COINS.","TAKE 17 COINS.").text=="TAKE 12 COINS.");
    check(select("WE LEAVE NOW.","WE MUST WAIT HERE LEAVE NOW.","WE MUST WAIT HERE LEAVE NOW.").insertions==0);
    check(select("I'IL RETURN NOW.","ILL RETURN NOW.","ILL RETURN NOW.").text=="I'IL RETURN NOW.");
    check(select("I'IL RETURN NOW.","I'LL RETURN NOW.","I'LL RETURN NOW.").text=="I'LL RETURN NOW.");
    check(select("I'IL RETURN NOW.","I'LL RETURN NOW.","ILL RETURN NOW.").text=="I'IL RETURN NOW.");
    check(select("YOL'VE RETURN NOW.","YOU'VE RETURN NOW.","YOU'VE RETURN NOW.").text=="YOU'VE RETURN NOW.");
    check(select("I\xE2\x80\x99IL RETURN NOW.","I'LL RETURN NOW.","I'LL RETURN NOW.").text=="I'LL RETURN NOW.");
    std::cout<<"{\"guards\":"<<count<<",\"success\":true,\"application_enabled\":false}"<<std::endl;return 0;
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
    auto result=luma::coverage_candidate::Select(row.at("base"),row.at("first"),row.at("second"),[&](const std::string& word){return words.count(word)!=0;});
    row["selected"]=result.text;row["replacements"]=result.replacements;row["insertions"]=result.insertions;
    std::cout<<row.dump()<<std::endl;
  }
}
