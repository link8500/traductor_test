#include "translation_question_clause.h"
#include "json.hpp"
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
  using namespace luma;
  if(argc>1&&std::string(argv[1])=="--self-test") {
    int n=0;auto check=[&](bool value){++n;if(!value)throw std::runtime_error("Short question guard "+std::to_string(n));};
    auto parts=question_clause::Split("WHY NOW? We have five other tasks.");
    check(!parts.first.empty());
    check(!question_clause::Split("IS THAT TRUE? We have five other tasks.").first.empty());
    check(question_clause::Split("THE OLD MASTER? We have five other tasks.").first.empty());
    check(question_clause::Split("SNIFF SNIFF? We have five other tasks.").first.empty());
    check(question_clause::Split("WHY NOW? Two tasks.").first.empty());
    check(question_clause::Split("WHY DO YOU ASK NOW? We have five other tasks.").first.empty());
    check(question_clause::Split("'WHY NOW?' We have five other tasks.").first.empty());
    check(question_clause::Split("WHY NOW? We have | five other tasks.").first.empty());
    check(question_clause::ModelInput("HOW WOULD I KNOW?")=="How would I know?");
    auto apply=[&](const std::string& whole,const std::string& first,const std::string& rest){return opening::Recover(parts,whole,first,rest);};
    check(apply("Tenemos cinco tareas.","Por que ahora?","Tenemos cinco tareas.").recovered);
    check(!apply("Tenemos cinco tareas.","Por que ahora?","Tenemos cuatro tareas.").recovered);
    check(!apply("No tenemos tareas.","Por que ahora?","Tenemos tareas.").recovered);
    check(!opening::Recover(question_clause::Split("WHY NOT? We have five other tasks."),"Tenemos tareas.","Por que?","Tenemos tareas.").recovered);
    check(opening::Recover(question_clause::Split("WHY NOT? We have five other tasks."),"Tenemos tareas.","Por que no?","Tenemos tareas.").recovered);
    check(!apply("Tenemos cinco tareas.","WHY NOW?","Tenemos cinco tareas.").recovered);
    check(!apply("Por que ahora? Tenemos tareas.","Por que ahora?","Tenemos tareas.").recovered);
    check(!apply("Tenemos cinco tareas.","Por que? Ahora.","Tenemos cinco tareas.").recovered);
    std::cout<<nlohmann::json{{"success",true},{"guards",n},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);auto parts=question_clause::Split(row.at("source"));
    if(argc>1&&std::string(argv[1])=="--plan") {
      row["eligible"]=!parts.first.empty();row["opening_source"]=parts.first;row["rest_source"]=parts.rest;
    } else {
      auto result=opening::Recover(parts,row.at("translation"),row.at("opening_translation"),row.at("rest_translation"),
          row.value("retained_original",false),row.value("opening_retained",false),row.value("rest_retained",false));
      row["candidate_translation"]=result.text;row["opening_recovered"]=result.recovered;
      if(result.recovered&&!result.text.empty()) {
        auto old=row.at("translation").get<std::string>();
        if(result.text.substr(result.text.size()-old.size())!=old)throw std::runtime_error("Existing body changed");
      }
    }
    std::cout<<row.dump()<<std::endl;
  }
}
