#include "translation_punctuation.h"
#include "json.hpp"
#include <iostream>
#include <stdexcept>

int main(int argc,char** argv) {
  if(argc>1&&std::string(argv[1])=="--self-test") {
    size_t n=0;auto check=[&](bool ok){++n;if(!ok)throw std::runtime_error("Question guard "+std::to_string(n));};
    auto apply=luma::punctuation::PreserveQuestion;
    check(apply("IS THERE A BOX HERE?","Hay una caja aqui.",false).text=="\xC2\xBFHay una caja aqui?");
    check(!apply("IS THERE A BOX HERE?","\xC2\xBFHay una caja aqui?",false).restored);
    check(!apply("THERE IS A BOX HERE.","Hay una caja aqui.",false).restored);
    check(!apply("HE ASKED IF THE BOX WAS HERE?","Pregunto si la caja estaba aqui.",false).restored);
    check(!apply("I WONDER IF THE BOX IS HERE?","Me pregunto si la caja esta aqui.",false).restored);
    check(!apply("I DON'T THINK WE NEED A BOX?","No creo que necesitemos una caja.",false).restored);
    check(!apply("HE LEFT. IS THERE A BOX HERE?","Se fue. Hay una caja aqui.",false).restored);
    check(!apply("HE WROTE 'IS THERE A BOX HERE?'","Escribio si habia una caja.",false).restored);
    check(!apply("IS THERE A BOX HERE?","Una caja. Esta aqui.",false).restored);
    check(!apply("IS THERE A BOX HERE?","Hay una caja...",false).restored);
    check(!apply("IS THERE A BOX HERE?","Hay una caja aqui.",true).restored);
    check(!apply("IS THERE A BOX HERE?","IS THERE A BOX HERE?",false).restored);
    check(!apply("IS THERE A BOX HERE?!","Hay una caja aqui.",false).restored);
    check(!apply("IS THERE A BOX HERE?","Hay una caja aqui!",false).restored);
    check(!apply("IS THERE | A BOX HERE?","Hay una caja aqui.",false).restored);
    check(apply("IT ISN'T ALREADY READY?","No esta listo.",false).text=="\xC2\xBFNo esta listo?");
    check(apply("ARE THERE 12 GOLD COINS?","Hay 12 monedas de oro.",false).text=="\xC2\xBFHay 12 monedas de oro?");
    check(!apply("WHO IS IT?","Es el.",false).restored);
    check(!luma::punctuation::Quoted("IT ISN'T ALREADY READY?"));
    check(luma::punctuation::Quoted("'IS IT ALREADY READY?'"));
    std::cout<<nlohmann::json{{"success",true},{"guards",n},{"application_enabled",false}}.dump()<<std::endl;return 0;
  }
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=nlohmann::json::parse(line);std::string before=row.at("translation");
    auto result=luma::punctuation::PreserveQuestion(row.at("source"),before,row.value("retained_original",false));
    row["translation"]=result.text;row["question_restored"]=result.restored;
    if(luma::coverage::NormalizedWords(before)!=luma::coverage::NormalizedWords(result.text))throw std::runtime_error("Question restoration changed lexical content");
    std::cout<<row.dump()<<std::endl;
  }
}
