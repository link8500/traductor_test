#include "translation_coverage_candidate.h"
#include "json.hpp"
#include <iostream>
int main() {
  std::string line;
  while(std::getline(std::cin,line)) {
    try {
      auto row=nlohmann::json::parse(line);std::string source=row.at("source"),output=row.at("translation");
      auto parts=luma::coverage_candidate::Sentences(source);
      row["candidate_parts"]=parts;row["retry"]=luma::coverage_candidate::Retry(source,output,parts);
      std::cout<<row.dump()<<std::endl;
    }catch(const std::exception& error){std::cerr<<error.what()<<std::endl;return 1;}
  }
}
