#ifdef LUMA_PRODUCTION_TAIL
#include "translation_tail.h"
namespace tail_policy=luma::tail;
#else
#include "translation_tail_candidate.h"
namespace tail_policy=luma::tail_candidate;
#endif
#include "json.hpp"
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
  using namespace luma;
  if(argc>1&&std::string(argv[1])=="--self-test") {
    int n=0;auto check=[&](bool ok){++n;if(!ok)throw std::runtime_error("Tail guard "+std::to_string(n));};
    auto parts=tail_policy::Plan("WE HAVE A MAP. WE MUST CHECK THE RIVER.","Tenemos un mapa.");
    check(!parts.head.empty());
    auto apply=[&](const std::string& whole,const std::string& head,const std::string& tail){return tail_policy::Recover(parts,whole,head,tail);};
    check(apply("Tenemos un mapa.","Tenemos un mapa.","Debemos revisar el rio.").text=="Tenemos un mapa. Debemos revisar el rio.");
    check(!apply("Tenemos un mapa nuevo.","Tenemos un mapa.","Debemos revisar el rio.").recovered);
    check(!apply("Tenemos un mapa.","Tenemos un mapa.","WE MUST CHECK THE RIVER.").recovered);
    check(!tail_policy::Recover(parts,"Tenemos un mapa.","Tenemos un mapa.","Debemos revisar el rio.",false,false,true).recovered);
    check(tail_policy::Plan("WE HAVE A MAP. SNIFF SNIFF.","Tenemos un mapa.").head.empty());
    check(tail_policy::Plan("WE HAVE A MAP. WE MUST CHECK THE RIVER...","Tenemos un mapa.").head.empty());
    check(tail_policy::Plan("WE HAVE A MAP. WE MUST CHECK THE","Tenemos un mapa.").head.empty());
    check(tail_policy::Plan("WE HAVE A MAP. 'WE MUST CHECK THE RIVER.'","Tenemos un mapa.").head.empty());
    check(!tail_policy::Plan("WE HAVE A MAP. DO YOU UNDERSTAND?","Tenemos un mapa.").head.empty());
    check(!tail_policy::Recover({"WE HAVE A MAP.","DO NOT CROSS THAT RIVER."},"Tenemos un mapa.","Tenemos un mapa.","Cruza ese rio.").recovered);
    check(!tail_policy::Recover({"WE HAVE A MAP.","WE NEED 12 GOLD COINS."},"Tenemos un mapa.","Tenemos un mapa.","Necesitamos 21 monedas de oro.").recovered);
    check(!tail_policy::Recover({"WE HAVE A MAP.","WE NEED A MAP."},"Necesitamos un mapa.","Necesitamos un mapa.","Necesitamos un mapa.").recovered);
    check(tail_policy::Plan("WE HAVE A MAP. WE MUST CHECK THE RIVER.","Tenemos un mapa. Debemos revisar el rio.").head.empty());
    check(!tail_policy::Recover(parts,"Tenemos un mapa.","Tenemos un mapa.","Necesitamos necesitamos necesitamos necesitamos necesitamos.").recovered);
#ifdef LUMA_PRODUCTION_TAIL
    tail_policy::Parts plural{"ALL OF YOU SHOULD WAIT.","I WILL WAIT FOR YOU."};
    check(!tail_policy::Recover(plural,"Ustedes deben esperar.","Ustedes deben esperar.","Esperare por ti.").recovered);
    check(tail_policy::Recover(plural,"Ustedes deben esperar.","Ustedes deben esperar.","Esperare por ustedes.").recovered);
    check(tail_policy::Recover({"YOU SHOULD WAIT.","I WILL WAIT FOR YOU."},"Debes esperar.","Debes esperar.","Esperare por ti.").recovered);
#endif
    std::cout<<nlohmann::json{{"success",true},{"guards",n},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);auto p=tail_policy::Plan(row.at("source"),row.at("translation"),row.value("retained_original",false));
    if(argc>1&&std::string(argv[1])=="--plan") {
      row["eligible"]=!p.head.empty();row["head_source"]=p.head;row["tail_source"]=p.tail;
    } else {
      auto result=tail_policy::Recover(p,row.at("translation"),row.at("head_translation"),row.at("tail_translation"),
          row.value("retained_original",false),row.value("head_retained",false),row.value("tail_retained",false));
      row["candidate_translation"]=result.text;row["tail_recovered"]=result.recovered;
      auto old=row.at("translation").get<std::string>();
      if(result.recovered&&result.text.compare(0,old.size(),old)!=0)throw std::runtime_error("Existing output changed");
    }
    std::cout<<row.dump()<<std::endl;
  }
}
