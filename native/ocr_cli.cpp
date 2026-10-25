#include "local_translation.h"
#include "short_dialogue_candidate.h"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>

int main(int argc,char** argv) {
  if(argc==2&&std::string(argv[1])=="--short-dialogue-self-test") {
    using namespace luma::short_dialogue_candidate;
    std::array<Reading,4> good{{{"I..",.96f},{"I..",.97f},{"I...",.96f},{"I...",.99f}}};
    nlohmann::json checks=nlohmann::json::array();
    auto check=[&](const std::string& name,const std::array<Reading,4>& rows,float confidence,bool expected){
      checks.push_back({{"case",name},{"passed",SupportedPronoun(rows,confidence)==expected}});
    };
    check("four_independent_readings",good,.96f,true);
    auto candidate=good;candidate[3].text="l...";check("ambiguous_lowercase_l",candidate,.96f,false);
    candidate=good;candidate[1].confidence=.94f;check("weak_second_reader",candidate,.96f,false);
    candidate=good;candidate[0].text="I";check("bare_vertical_stroke",candidate,.96f,false);
    candidate=good;candidate[2].text="!";check("punctuation_only",candidate,.96f,false);
    candidate=good;candidate[2].text="I DON'T";check("ordinary_dialogue_not_replaced",candidate,.96f,false);
    check("weak_detector",good,.89f,false);
    candidate=good;candidate[2].text="I\xe2\x80\xa6";check("unicode_ellipsis",candidate,.96f,true);
    bool passed=std::all_of(checks.begin(),checks.end(),[](const auto& row){return row.at("passed").template get<bool>();});
    std::cout<<nlohmann::json({{"checks",checks},{"passed",passed}}).dump()<<std::endl;return passed?0:1;
  }
  if(argc<3)return 2;
  try {
    luma::LocalLineRecognizer reader(argv[1]);luma::LocalTextDetector detector(argv[2]);std::string line;
    while(std::getline(std::cin,line)) {
      auto value=nlohmann::json::parse(line);auto start=std::chrono::steady_clock::now();
      try {
        int width=value.at("width"),height=value.at("height");
        if(width<1||height<1||width>4096||height>4096)throw std::runtime_error("Invalid image shape");
        std::ifstream file(std::filesystem::u8path(value.at("path").get<std::string>()),std::ios::binary);
        std::vector<uint8_t> pixels((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
        if(pixels.size()!=static_cast<size_t>(width)*height*4)throw std::runtime_error("Invalid pixel buffer");
        value["lines"]=nlohmann::json::array();
        value["region_reads"]=nlohmann::json::array();
        if(value.contains("regions"))for(const auto& region:value["regions"]) {
          const auto& bounds=region.at("bounds");auto hint=region.value("hint",std::string());
          auto recognized=reader.ReadWithHint(pixels.data(),width,height,width*4,bounds[0],bounds[1],bounds[2],bounds[3],hint);
          value["region_reads"].push_back({{"text",recognized.text},{"confidence",recognized.confidence},{"system_agreement",recognized.system_agreement}});
        }
        value["quad_reads"]=nlohmann::json::array();
        if(value.contains("quads"))for(const auto& proposal:value["quads"]) {
          auto quad=proposal.at("quad").get<std::array<float,8>>();
          auto first=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,quad,false);
          auto second=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,quad,true);
          value["quad_reads"].push_back({{"id",proposal.at("id")},{"quad",quad},
              {"first_text",first.text},{"first_confidence",first.confidence},
              {"second_text",second.text},{"second_confidence",second.confidence}});
        }
        const auto boxes=value.value("skip_detection",false)?std::vector<luma::DetectedText>{}:detector.Detect(pixels.data(),width,height,width*4);
        for(auto& box:boxes) {
          auto recognized=reader.ReadQuad(pixels.data(),width,height,width*4,box.corners);
          nlohmann::json evidence={{"text",recognized.text},{"confidence",recognized.confidence},{"detector_confidence",box.confidence},{"quad",box.corners}};
          const auto letters=std::count_if(recognized.text.begin(),recognized.text.end(),[](unsigned char c){return std::isalpha(c)!=0;});
          if(value.value("include_short_evidence",false)&&letters<2) {
            auto first=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,box.corners,false);
            auto second=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,box.corners,true);
            evidence["first_text"]=first.text;evidence["first_confidence"]=first.confidence;
            evidence["second_text"]=second.text;evidence["second_confidence"]=second.confidence;
          }
          value["lines"].push_back(std::move(evidence));
        }
        value["milliseconds"]=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
      }catch(const std::exception& error){value["error"]=error.what();}
      std::cout<<value.dump()<<std::endl;
    }
  }catch(const std::exception& error){std::cerr<<error.what()<<std::endl;return 1;}
}
