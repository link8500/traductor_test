#include "translation_opening.h"
#include "json.hpp"
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
  using namespace luma;
  if(argc>1&&std::string(argv[1])=="--self-test") {
    int n=0;auto check=[&](bool ok){++n;if(!ok)throw std::runtime_error("Opening guard "+std::to_string(n));};
    const auto parts=opening::Split("WHY? We planned a single afternoon.");
    check(!parts.first.empty());
    auto apply=[&](const std::string& a,const std::string& b,const std::string& c,bool x=false,bool y=false,bool z=false){return opening::Recover(parts,a,b,c,x,y,z);};
    check(apply("Planeamos una tarde.","Por que?","Planeamos una tarde.").recovered);
    check(apply("Planeamos una tarde.","Por que?","Planeamos una tarde.").text=="\xC2\xBF" "Por que? Planeamos una tarde.");
    check(!apply("Pensamos en una tarde.","Por que?","Planeamos una tarde.").recovered);
    check(!apply("Planeamos una tarde.","WHY?","Planeamos una tarde.").recovered);
    check(!apply("Planeamos una tarde.","Dias?","Planeamos una tarde.",true).recovered);
    check(!apply("Planeamos una tarde.","Dias?","Planeamos una tarde.",false,true).recovered);
    check(!apply("Planeamos una tarde.","Dias?","Planeamos una tarde.",false,false,true).recovered);
    check(!apply("Dias? Planeamos una tarde.","Dias?","Planeamos una tarde.").recovered);
    check(!apply("Dias planeados.","Dias?","Dias planeados.").recovered);
    check(!apply("No necesitamos 12 cajas.","Dias?","Necesitamos 12 cajas.").recovered);
    check(!apply("Necesitamos 12 cajas.","Dias?","Necesitamos 21 cajas.").recovered);
    check(!apply("Planeamos una tarde.","Una tarde. Dias?","Planeamos una tarde.").recovered);
    check(!apply("Planeamos una tarde.","Dias, por favor?","Planeamos una tarde.").recovered);
    check(opening::Split("Sniff. We planned a single afternoon.").first.empty());
    check(opening::Split("Dr. We planned a single afternoon.").first.empty());
    check(opening::Split("'DAYS?' We planned a single afternoon.").first.empty());
    check(opening::Split("DAYS? We | planned a single afternoon.").first.empty());
    check(opening::Split("DAYS? One day.").first.empty());
    check(!opening::Recover(opening::Split("SNIFF! We planned a single afternoon."),"Planeamos una tarde.","Sniff!","Planeamos una tarde.").recovered);
    check(opening::Recover(opening::Split("NO! We planned a single afternoon."),"Planeamos una tarde.","No!","Planeamos una tarde.").recovered);
    check(!opening::Recover(opening::Split("NO! We planned a single afternoon."),"Planeamos una tarde.","Si!","Planeamos una tarde.").recovered);
    check(opening::Split("DONE? We planned a single afternoon.").first.empty());
    check(opening::Split("MURDERED? We planned a single afternoon.").first.empty());
    check(opening::Split("ANGRY? We planned a single afternoon.").first.empty());
    check(opening::Split("HAHA! We planned a single afternoon.").first.empty());
    check(opening::ModelInput("WHAT?")=="What?");
    check(opening::ModelInput("WAIT!")=="Wait!");
    std::cout<<nlohmann::json{{"success",true},{"guards",n},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);auto p=opening::Split(row.at("source"));
    if(argc>1&&std::string(argv[1])=="--plan") {
      row["eligible"]=!p.first.empty();row["opening_source"]=p.first;row["rest_source"]=p.rest;
      std::cout<<row.dump()<<std::endl;continue;
    }
    auto result=opening::Recover(p,row.at("translation"),row.at("opening_translation"),row.at("rest_translation"),
      row.value("retained_original",false),row.value("opening_retained",false),row.value("rest_retained",false));
    row["candidate_translation"]=result.text;row["opening_recovered"]=result.recovered;
    if(result.recovered&&result.text.substr(result.text.size()-row.at("translation").get<std::string>().size())!=row.at("translation"))
      throw std::runtime_error("Existing translation changed");
    std::cout<<row.dump()<<std::endl;
  }
}
