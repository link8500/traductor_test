#include "local_translation.h"
#include "json.hpp"
#include <chrono>
#include <fstream>
#include <iostream>
int main(int argc,char** argv) {
  if(argc<2)return 2;
  try {
    luma::LocalTranslationModel engine(argv[1]);std::string line;
    while(std::getline(std::cin,line)) {
      auto value=nlohmann::json::parse(line);auto started=std::chrono::steady_clock::now();
      try {
        std::string text=value.at("source");
        if(value.value("tokenize",false))value["tokens"]=engine.Tokenize(text);
        else if(value.value("prepare",false)) {auto prepared=engine.PrepareInput(text);value["prepared"]=prepared.prepared;value["source_corrections"]=prepared.source_corrections;}
        else {
          auto translated=engine.TranslateDetailed(text);
          value["prepared"]=translated.prepared;value["raw_model"]=translated.raw;value["translation"]=translated.text;
          value["terminology"]=translated.terminology;value["source_corrections"]=translated.source_corrections;
          value["retained_original"]=translated.retained_original;value["sentence_recovered"]=translated.sentence_recovered;
          value["question_recovered"]=translated.question_recovered;
          value["opening_recovered"]=translated.opening_recovered;
          value["opening_source"]=translated.opening_source;
          value["opening_translation"]=translated.opening_translation;
          value["tail_recovered"]=translated.tail_recovered;
          value["tail_source"]=translated.tail_source;
          value["tail_translation"]=translated.tail_translation;
          if(translated.retained_original)value["reason"]=translated.reason;
          if(translated.sentence_recovered) {
            value["whole_translation"]=translated.whole_translation;
            value["sentence_sources"]=translated.sentence_sources;value["sentence_translations"]=translated.sentence_translations;
          }
        }
        value["milliseconds"]=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-started).count();
      }catch(const std::exception& error){value["error"]=error.what();}
      std::cout<<value.dump()<<std::endl;
    }
  }catch(const std::exception& error){std::cerr<<error.what()<<std::endl;return 1;}
}
