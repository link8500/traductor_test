#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace luma::background {
struct Color {int red=0,green=0,blue=0,samples=0;bool confident=false;};
// Sample inside the recognized region. A border pixel alone must not invert
// a white balloon. Preserve the caller's fallback unless 3/4 of a fixed grid
// agree on one color family; artwork and gradients usually remain uncertain.
inline Color Dominant(const uint8_t* pixels,size_t bytes,int width,int height,int stride,
    int left,int top,int right,int bottom) {
  if(!pixels||width<1||height<1||stride<1||size_t(stride)<size_t(width)*4||bytes<size_t(stride)*height)return {};
  left=std::clamp(left,0,width);right=std::clamp(right,0,width);
  top=std::clamp(top,0,height);bottom=std::clamp(bottom,0,height);
  if(right-left<8||bottom-top<8)return {};
  std::array<int,512> counts{};std::vector<std::array<int,4>> samples;
  for(int row=0;row<13;++row)for(int column=0;column<17;++column) {
    int x=static_cast<int>(std::lround(left+(right-left-1)*(column+.5)/17));
    int y=static_cast<int>(std::lround(top+(bottom-top-1)*(row+.5)/13));
    const auto* p=pixels+size_t(y)*stride+size_t(x)*4;
    int key=(p[2]/32)*64+(p[1]/32)*8+p[0]/32;
    ++counts[key];samples.push_back({p[2],p[1],p[0],key});
  }
  int selected=static_cast<int>(std::max_element(counts.begin(),counts.end())-counts.begin());
  if(counts[selected]*4<static_cast<int>(samples.size())*3)return {};
  std::array<std::vector<int>,3> channels;
  for(const auto& sample:samples)if(sample[3]==selected)for(int c=0;c<3;++c)channels[c].push_back(sample[c]);
  std::array<int,3> median{};
  for(int c=0;c<3;++c){auto& values=channels[c];std::nth_element(values.begin(),values.begin()+values.size()/2,values.end());median[c]=values[values.size()/2];}
  return {median[0],median[1],median[2],counts[selected],true};
}
}
