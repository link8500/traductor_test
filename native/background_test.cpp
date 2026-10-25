#include "overlay_background.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
using Json=nlohmann::json;
int main(int argc,char** argv) {
  int count=0;auto check=[&](bool value){++count;if(!value)throw std::runtime_error("Background guard failed: "+std::to_string(count));};
  const int width=80,height=80;std::vector<uint8_t> pixels(width*height*4,255);
  auto set=[&](int x,int y,int r,int g,int b){auto at=(y*width+x)*4;pixels[at]=b;pixels[at+1]=g;pixels[at+2]=r;};
  auto sample=[&](){return luma::background::Dominant(pixels.data(),pixels.size(),width,height,width*4,0,0,width,height);};
  auto white=sample();check(white.confident&&white.red==255&&white.green==255&&white.blue==255);
  for(int y=0;y<height;++y)for(int x=0;x<width;++x)if((x<3&&y<3)||(x%19==0&&y%7==0))set(x,y,0,0,0);
  auto border=sample();check(border.confident&&border.red==255);
  for(int y=0;y<height;++y)for(int x=0;x<width;++x)set(x,y,0,0,0);
  for(int y=0;y<height;++y)for(int x=0;x<width;++x)if((x<3&&y<3)||(x%19==0&&y%7==0))set(x,y,255,255,255);
  auto dark=sample();check(dark.confident&&dark.red==0);
  for(int y=0;y<height;++y)for(int x=0;x<width;++x)set(x,y,200,224,176);
  auto color=sample();check(color.confident&&color.red==200&&color.green==224&&color.blue==176);
  for(int y=0;y<height;++y)for(int x=0;x<width;++x)set(x,y,x<40?0:255,x<40?0:255,x<40?0:255);
  check(!sample().confident);
  check(!luma::background::Dominant(pixels.data(),pixels.size(),width,height,width*4,0,0,4,4).confident);
  check(!luma::background::Dominant(pixels.data(),pixels.size(),width,height,width*4,100,100,120,120).confident);
  check(!luma::background::Dominant(nullptr,0,0,0,0,0,0,1,1).confident);
  check(!luma::background::Dominant(pixels.data(),3,width,height,width*4,0,0,width,height).confident);
  check(!luma::background::Dominant(pixels.data(),pixels.size(),width,height,1,0,0,width,height).confident);
  if(argc==3) {
    std::ifstream inputs(argv[1]);std::ofstream output(argv[2]);std::string line;
    while(std::getline(inputs,line)) {
      auto row=Json::parse(line);std::ifstream source(row.at("path").get<std::string>(),std::ios::binary);
      std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(source)),std::istreambuf_iterator<char>());
      auto b=row.at("bounds");int w=row.at("width"),h=row.at("height");
      auto value=luma::background::Dominant(bytes.data(),bytes.size(),w,h,w*4,b[0],b[1],b[2],b[3]);
      output<<Json{{"id",row.at("id")},{"confident",value.confident},{"color",{value.red,value.green,value.blue}},{"agreeing_samples",value.samples}}.dump()<<'\n';
    }
  }
  std::cout<<Json{{"success",true},{"guards",count},{"model_inference",false}}.dump()<<std::endl;
}
