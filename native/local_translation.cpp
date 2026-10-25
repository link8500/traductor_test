#include "local_translation.h"
#include "translation_coverage.h"
#include "translation_punctuation.h"
#include "translation_opening.h"
#include "translation_question_clause.h"
#include "translation_tail.h"
#define ORT_API_MANUAL_INIT
#include "onnxruntime_cxx_api.h"
#include "json.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <mutex>
#include <numeric>
#include <regex>
#include <stdexcept>
#include <unordered_map>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace luma {
namespace {
void InitializeRuntime() {
  static std::once_flag once;
  std::call_once(once,[] {
#ifdef _WIN32
    wchar_t filename[32768]{}; GetModuleFileNameW(nullptr,filename,32768);
    auto path=std::filesystem::path(filename).parent_path()/L"onnxruntime.dll";
    auto library=LoadLibraryExW(path.c_str(),nullptr,LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!library) throw std::runtime_error("No se pudo cargar el motor local de traduccion.");
    auto getApi=reinterpret_cast<const OrtApiBase*(ORT_API_CALL*)()>(GetProcAddress(library,"OrtGetApiBase"));
#else
    auto library=dlopen("libonnxruntime.so",RTLD_NOW|RTLD_LOCAL);
    if (!library) throw std::runtime_error("No se pudo cargar el motor local de traduccion.");
    auto getApi=reinterpret_cast<const OrtApiBase*(ORT_API_CALL*)()>(dlsym(library,"OrtGetApiBase"));
#endif
    if (!getApi) throw std::runtime_error("Runtime local incompatible.");
    Ort::InitApi(getApi()->GetApi(ORT_API_VERSION));
  });
}
size_t CharacterSize(unsigned char c) { return c<0x80?1:(c<0xE0?2:(c<0xF0?3:4)); }
std::string Trim(std::string s) {
  auto begin=s.find_first_not_of(" \t\r\n");
  return begin==std::string::npos?std::string():s.substr(begin,s.find_last_not_of(" \t\r\n")-begin+1);
}
std::string Nfkc(const std::string& input) {
#ifdef _WIN32
  int size=MultiByteToWideChar(CP_UTF8,0,input.data(),static_cast<int>(input.size()),nullptr,0);
  std::wstring wide(size,L'\0');MultiByteToWideChar(CP_UTF8,0,input.data(),static_cast<int>(input.size()),wide.data(),size);
  int required=NormalizeString(NormalizationKC,wide.data(),size,nullptr,0);
  if(required<=0)return input;
  std::wstring normalized(required,L'\0');int count=NormalizeString(NormalizationKC,wide.data(),size,normalized.data(),required);
  if(count<=0)return input;
  int bytes=WideCharToMultiByte(CP_UTF8,0,normalized.data(),count,nullptr,0,nullptr,nullptr);
  std::string output(bytes,'\0');WideCharToMultiByte(CP_UTF8,0,normalized.data(),count,output.data(),bytes,nullptr,nullptr);return output;
#else
  // Android applies java.text.Normalizer.NFKC before crossing JNI.
  return input;
#endif
}
struct PieceNode {
  std::vector<std::pair<unsigned char,size_t>> children;
  int id=-1; double score=0;
};
struct Tokenizer {
  std::vector<PieceNode> trie{1}; std::vector<std::string> tokens;
  std::unordered_map<std::string,int> vocabulary;
  double unknownScore=-30;
  int eos=0,unknown=1,pad=65000,heads=8,headSize=64;
  explicit Tokenizer(const std::filesystem::path& path) {
    std::ifstream file(path); if (!file) throw std::runtime_error("Falta el tokenizador del modelo local.");
    auto data=nlohmann::json::parse(file); tokens=data.at("tokens").get<std::vector<std::string>>();
    eos=data.at("eos").get<int>();unknown=data.at("unk").get<int>();pad=data.at("pad").get<int>();
    heads=data.value("heads",8);headSize=data.value("head_size",64);
    for(size_t i=0;i<tokens.size();++i)vocabulary[tokens[i]]=static_cast<int>(i);
    double minimum=0;
    for (auto& item:data.at("pieces")) {
      auto piece=item.at(0).get<std::string>(); auto score=item.at(1).get<double>(); int id=item.at(2).get<int>();
      size_t node=0;
      for (unsigned char c:piece) {
        size_t next=trie.size(); bool found=false;
        for (auto edge:trie[node].children) if (edge.first==c) {next=edge.second;found=true;break;}
        if (!found) {trie[node].children.push_back({c,next});trie.emplace_back();}
        node=next;
      }
      trie[node].id=id;trie[node].score=score;minimum=std::min(minimum,score);
    }
    unknownScore=minimum-10;
  }
  std::vector<int64_t> Encode(const std::string& input) const {
    std::string normalized; bool space=true;
    auto source=Nfkc(input);
    for (size_t i=0;i<source.size();) {
      unsigned char c=source[i]; size_t length=std::min(CharacterSize(c),source.size()-i);
      if (c<=0x20) space=true;
      else {if(space)normalized+="\xE2\x96\x81";normalized.append(source,i,length);space=false;}
      i+=length;
    }
    size_t n=normalized.size(); std::vector<double> scores(n+1,-std::numeric_limits<double>::infinity());
    std::vector<size_t> previous(n+1,0);std::vector<int> ids(n+1,unknown);scores[0]=0;
    for (size_t i=0;i<n;++i) {
      if (!std::isfinite(scores[i])) continue;
      size_t node=0;bool single=false;size_t charEnd=std::min(n,i+CharacterSize(static_cast<unsigned char>(normalized[i])));
      for (size_t j=i;j<n;++j) {
        bool found=false;for(auto edge:trie[node].children)if(edge.first==static_cast<unsigned char>(normalized[j])) {node=edge.second;found=true;break;}
        if(!found)break;
        if(trie[node].id>=0) {
          if(j+1==charEnd)single=true;
          double score=scores[i]+trie[node].score;
          if(score>scores[j+1]) {scores[j+1]=score;previous[j+1]=i;ids[j+1]=trie[node].id;}
        }
      }
      if(!single && scores[i]+unknownScore>scores[charEnd]) {scores[charEnd]=scores[i]+unknownScore;previous[charEnd]=i;ids[charEnd]=unknown;}
    }
    std::vector<std::pair<int64_t,std::string>> reversed;
    for(size_t at=n;at>0;) {size_t before=previous[at];if(before>=at)throw std::runtime_error("Texto no tokenizable.");reversed.push_back({ids[at],normalized.substr(before,at-before)});at=before;}
    std::reverse(reversed.begin(),reversed.end());std::vector<int64_t> output;
    for(size_t i=0;i<reversed.size();++i) {
      if(reversed[i].first!=unknown)output.push_back(reversed[i].first);
      else {
        auto surface=reversed[i].second;
        while(i+1<reversed.size()&&reversed[i+1].first==unknown)surface+=reversed[++i].second;
        auto found=vocabulary.find(surface);output.push_back(found==vocabulary.end()?unknown:found->second);
      }
    }
    output.push_back(eos);return output;
  }
  std::string Decode(const std::vector<int64_t>& ids) const {
    std::string output;for(auto id:ids)if(id>=0&&id!=unknown&&id!=pad&&id!=eos)output+=tokens.at(static_cast<size_t>(id));
    const std::string space="\xE2\x96\x81";size_t at=0;
    while((at=output.find(space,at))!=std::string::npos) {output.replace(at,space.size()," ");++at;}
    output=std::regex_replace(output,std::regex(" +([,.!?;:])"),"$1");return Trim(output);
  }
};
struct Decoded { std::vector<Ort::Value> values; };
struct Beam {std::vector<int64_t> tokens;double score=0;std::shared_ptr<Decoded> past,cross;};
struct Candidate {Beam beam;int64_t token;};
struct IncompleteTranslation : std::runtime_error {using std::runtime_error::runtime_error;};
}

struct LocalTextDetector::Impl {
  Ort::Env env;Ort::SessionOptions options;Ort::Session session{nullptr};
  Ort::MemoryInfo memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
  std::string input,output;std::mutex mutex;
  Impl(const std::filesystem::path& directory,const void* bytes,size_t size):env(ORT_LOGGING_LEVEL_ERROR,"LumaTextDetector") {
    options.SetIntraOpNumThreads(2);options.SetInterOpNumThreads(1);options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    session=bytes?Ort::Session(env,bytes,size,options):Ort::Session(env,(directory/"text-detector.onnx").c_str(),options);
    Ort::AllocatorWithDefaultOptions allocator;input=session.GetInputNameAllocated(0,allocator).get();output=session.GetOutputNameAllocated(0,allocator).get();
  }
};
LocalTextDetector::LocalTextDetector(const std::string& directory,const void* bytes,size_t size) {InitializeRuntime();impl_=std::make_unique<Impl>(std::filesystem::u8path(directory),bytes,size);}
LocalTextDetector::~LocalTextDetector()=default;
std::vector<DetectedText> LocalTextDetector::Detect(const uint8_t* pixels,int width,int height,int stride,const std::function<bool()>& cancelled) {
  if(width<1||height<1||width>4096||height>4096||stride<width*4)throw std::runtime_error("Invalid detector image size");
  std::lock_guard<std::mutex> guard(impl_->mutex);
  auto stopped=[&]{return cancelled&&cancelled();};
  double scale=std::min(1.5,1280.0/std::max(width,height));
  int w=std::max(32,static_cast<int>(std::round(width*scale/32))*32),h=std::max(32,static_cast<int>(std::round(height*scale/32))*32);
  std::vector<float> input(static_cast<size_t>(3)*w*h);
  const float mean[]{.485f,.456f,.406f},stddev[]{.229f,.224f,.225f};
  for(int y=0;y<h;++y) {
    if(stopped())return {};
    double sy=(y+.5)*height/h-.5;int y0=std::clamp(static_cast<int>(std::floor(sy)),0,height-1),y1=std::min(y0+1,height-1);double fy=std::clamp(sy-y0,0.0,1.0);
    for(int x=0;x<w;++x) {
      double sx=(x+.5)*width/w-.5;int x0=std::clamp(static_cast<int>(std::floor(sx)),0,width-1),x1=std::min(x0+1,width-1);double fx=std::clamp(sx-x0,0.0,1.0);
      for(int c=0;c<3;++c) {
        auto at=[&](int a,int b){return pixels[static_cast<size_t>(b)*stride+a*4+c];};
        double value=at(x0,y0)*(1-fx)*(1-fy)+at(x1,y0)*fx*(1-fy)+at(x0,y1)*(1-fx)*fy+at(x1,y1)*fx*fy;
        input[(static_cast<size_t>(c)*h+y)*w+x]=static_cast<float>((value/255-mean[c])/stddev[c]);
      }
    }
  }
  std::array<int64_t,4> shape{1,3,h,w};auto tensor=Ort::Value::CreateTensor<float>(impl_->memory,input.data(),input.size(),shape.data(),shape.size());
  const char* in=impl_->input.c_str();const char* out=impl_->output.c_str();Ort::RunOptions run;
  auto result=impl_->session.Run(run,&in,&tensor,1,&out,1);
  if(stopped())return {};
  auto dims=result[0].GetTensorTypeAndShapeInfo().GetShape();
  if(dims.size()!=4||dims[0]!=1||dims[1]!=1||dims[2]<1||dims[3]<1||dims[2]*dims[3]>4096*4096)throw std::runtime_error("Invalid detector output");
  int mh=static_cast<int>(dims[2]),mw=static_cast<int>(dims[3]);const float* map=result[0].GetTensorData<float>();
  std::vector<uint8_t> visited(static_cast<size_t>(mw)*mh,0);std::vector<int> queue;std::vector<DetectedText> boxes;
  for(int start=0;start<mw*mh;++start) {
    if(visited[start]||map[start]<.3f)continue;
    if(stopped())return {};
    queue.clear();queue.push_back(start);visited[start]=1;
    double sumx=0,sumy=0,xx=0,yy=0,xy=0,score=0;
    for(size_t i=0;i<queue.size();++i) {
      int p=queue[i],x=p%mw,y=p/mw;sumx+=x;sumy+=y;xx+=x*x;yy+=y*y;xy+=x*y;score+=map[p];
      for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx) {
        int nx=x+dx,ny=y+dy;if(nx<0||nx>=mw||ny<0||ny>=mh)continue;
        int next=ny*mw+nx;if(!visited[next]&&map[next]>=.3f){visited[next]=1;queue.push_back(next);}
      }
    }
    double count=static_cast<double>(queue.size());if(count<6||score/count<.55)continue;
    double angle=.5*std::atan2(2*(xy-sumx*sumy/count),xx-yy-(sumx*sumx-sumy*sumy)/count);
    // A principal axis gives a stable affine rectification for slanted lines.
    // Very steep text remains a proposal; the recognizer must still read it.
    double cs=std::cos(angle),sn=std::sin(angle),a=1e9,b=1e9,c=-1e9,d=-1e9;
    for(int p:queue) {double x=p%mw,y=p/mw,u=x*cs+y*sn,v=-x*sn+y*cs;a=std::min(a,u);c=std::max(c,u);b=std::min(b,v);d=std::max(d,v);}
    double bw=c-a+1,bh=d-b+1;if(bw<3||bh<2)continue;
    double pad=bw*bh*1.5/(2*(bw+bh));a-=pad;b-=pad;c+=pad;d+=pad;
    DetectedText box;box.confidence=static_cast<float>(score/count);
    std::array<std::pair<double,double>,4> corners{{{a,b},{c,b},{c,d},{a,d}}};
    for(size_t i=0;i<4;++i) {auto [u,v]=corners[i];box.corners[i*2]=static_cast<float>(std::clamp((u*cs-v*sn)*width/mw,0.0,static_cast<double>(width-1)));
      box.corners[i*2+1]=static_cast<float>(std::clamp((u*sn+v*cs)*height/mh,0.0,static_cast<double>(height-1)));}
    boxes.push_back(box);if(boxes.size()>=1000)break;
  }
  std::sort(boxes.begin(),boxes.end(),[](const DetectedText& a,const DetectedText& b){return a.corners[1]<b.corners[1];});return boxes;
}

struct LocalLineRecognizer::Impl {
  Ort::Env env;Ort::SessionOptions options;Ort::Session session{nullptr};
  Ort::MemoryInfo memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
  std::vector<std::string> characters;std::string input,output;std::mutex mutex;
  std::filesystem::path directory;const void* fallback_bytes=nullptr;size_t fallback_size=0;
  bool fallback_available=false;std::unique_ptr<Impl> fallback;
  RecognizedLine Run(const uint8_t*,int,int,int,int,int,int,int);
  Impl(const std::filesystem::path& path,const void* bytes,size_t size,bool secondary=false,const void* alternate=nullptr,size_t alternate_size=0)
      :env(ORT_LOGGING_LEVEL_ERROR,"LumaLetters"),directory(path),fallback_bytes(alternate),fallback_size(alternate_size) {
    options.SetIntraOpNumThreads(2);options.SetInterOpNumThreads(1);options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    session=bytes?Ort::Session(env,bytes,size,options):Ort::Session(env,(directory/(secondary?"english-ocr-fallback.onnx":"english-ocr.onnx")).c_str(),options);
    std::ifstream dictionary(directory/(secondary?"ocr-characters-fallback.json":"ocr-characters.json"));characters=nlohmann::json::parse(dictionary).get<std::vector<std::string>>();
    fallback_available=!secondary&&((alternate&&alternate_size)||std::filesystem::exists(directory/"english-ocr-fallback.onnx"));
    Ort::AllocatorWithDefaultOptions allocator;input=session.GetInputNameAllocated(0,allocator).get();output=session.GetOutputNameAllocated(0,allocator).get();
  }
};
LocalLineRecognizer::LocalLineRecognizer(const std::string& directory,const void* bytes,size_t size,const void* alternate,size_t alternate_size) {
  InitializeRuntime();impl_=std::make_unique<Impl>(std::filesystem::u8path(directory),bytes,size,false,alternate,alternate_size);
}
LocalLineRecognizer::~LocalLineRecognizer()=default;
RecognizedLine LocalLineRecognizer::ReadQuad(const uint8_t* pixels,int width,int height,int stride,const std::array<float,8>& q,const std::string& system_text) {
  double horizontal=std::hypot(q[2]-q[0],q[3]-q[1]),vertical=std::hypot(q[6]-q[0],q[7]-q[1]);
  if(horizontal<2||vertical<2)return {};
  int w=std::clamp(static_cast<int>(std::ceil(48*horizontal/vertical)),8,2048);
  std::vector<uint8_t> rectified(static_cast<size_t>(w)*48*4,255);
  for(int y=0;y<48;++y)for(int x=0;x<w;++x) {
    double u=(x+.5)/w,v=(y+.5)/48;
    double sx=(1-v)*((1-u)*q[0]+u*q[2])+v*((1-u)*q[6]+u*q[4]);
    double sy=(1-v)*((1-u)*q[1]+u*q[3])+v*((1-u)*q[7]+u*q[5]);
    int x0=std::clamp(static_cast<int>(sx),0,width-1),y0=std::clamp(static_cast<int>(sy),0,height-1),x1=std::min(x0+1,width-1),y1=std::min(y0+1,height-1);
    double fx=std::clamp(sx-x0,0.0,1.0),fy=std::clamp(sy-y0,0.0,1.0);
    for(int c=0;c<3;++c){auto at=[&](int a,int b){return pixels[static_cast<size_t>(b)*stride+a*4+c];};
      rectified[(static_cast<size_t>(y)*w+x)*4+c]=static_cast<uint8_t>(at(x0,y0)*(1-fx)*(1-fy)+at(x1,y0)*fx*(1-fy)+at(x0,y1)*(1-fx)*fy+at(x1,y1)*fx*fy);}
  }
  return system_text.empty()?Read(rectified.data(),w,48,w*4,0,0,w,48):ReadWithHint(rectified.data(),w,48,w*4,0,0,w,48,system_text);
}
RecognizedLine LocalLineRecognizer::Impl::Run(const uint8_t* pixels,int width,int height,int stride,int left,int top,int right,int bottom) {
  left=std::clamp(left,0,width-1);right=std::clamp(right,left+1,width);top=std::clamp(top,0,height-1);bottom=std::clamp(bottom,top+1,height);
  int roiWidth=right-left,roiHeight=bottom-top;
  int resizedWidth=std::clamp(static_cast<int>(std::ceil(48.0*roiWidth/roiHeight)),8,2048),targetWidth=std::max(320,resizedWidth);
  std::vector<float> data(static_cast<size_t>(3)*48*targetWidth,0);
  auto pixel=[&](int x,int y,int channel) {return pixels[static_cast<size_t>(y)*stride+static_cast<size_t>(x)*4+channel];};
  int dark=0;for(auto point:std::array<std::pair<int,int>,4>{{{left,top},{right-1,top},{left,bottom-1},{right-1,bottom-1}}})
    if(pixel(point.first,point.second,0)+pixel(point.first,point.second,1)+pixel(point.first,point.second,2)<330)++dark;
  for(int y=0;y<48;++y)for(int x=0;x<resizedWidth;++x) {
    double sourceX=left+(x+.5)*roiWidth/resizedWidth-.5,sourceY=top+(y+.5)*roiHeight/48-.5;
    int x0=std::clamp(static_cast<int>(std::floor(sourceX)),left,right-1),y0=std::clamp(static_cast<int>(std::floor(sourceY)),top,bottom-1);
    int x1=std::min(x0+1,right-1),y1=std::min(y0+1,bottom-1);
    double fx=std::clamp(sourceX-x0,0.0,1.0),fy=std::clamp(sourceY-y0,0.0,1.0);
    for(int channel=0;channel<3;++channel) {
      int sourceChannel=2-channel;
      double value=pixel(x0,y0,sourceChannel)*(1-fx)*(1-fy)+pixel(x1,y0,sourceChannel)*fx*(1-fy)+pixel(x0,y1,sourceChannel)*(1-fx)*fy+pixel(x1,y1,sourceChannel)*fx*fy;
      if(dark>=3)value=255-value;
      data[(static_cast<size_t>(channel)*48+y)*targetWidth+x]=static_cast<float>(value/127.5-1);
    }
  }
  std::array<int64_t,4> shape{1,3,48,targetWidth};
  auto tensor=Ort::Value::CreateTensor<float>(memory,data.data(),data.size(),shape.data(),shape.size());
  const char* in=input.c_str();const char* out=output.c_str();Ort::RunOptions run;
  auto result=session.Run(run,&in,&tensor,1,&out,1);
  auto dimensions=result[0].GetTensorTypeAndShapeInfo().GetShape();
  if(dimensions.size()!=3||dimensions[2]!=static_cast<int64_t>(characters.size()))throw std::runtime_error("Diccionario OCR incompatible.");
  const float* probabilities=result[0].GetTensorData<float>();RecognizedLine recognized;double total=0;int count=0,previous=-1;int64_t firstStep=-1,lastStep=0;
  for(int64_t step=0;step<dimensions[1];++step) {
    auto row=probabilities+step*dimensions[2];int id=static_cast<int>(std::max_element(row,row+dimensions[2])-row);
    if(id!=0&&id!=previous) {recognized.text+=characters[id];total+=row[id];++count;
      if(characters[id]!=" "){if(firstStep<0)firstStep=step;lastStep=step;}}
    previous=id;
  }
  recognized.text=Trim(std::regex_replace(recognized.text,std::regex(" +")," "));
  recognized.confidence=count?static_cast<float>(total/count):0;
  double scale=static_cast<double>(targetWidth)*roiWidth/(static_cast<double>(dimensions[1])*resizedWidth);
  recognized.left=std::clamp(left+static_cast<int>((static_cast<double>(firstStep)+.5)*scale-roiHeight*.35),left,right-1);
  recognized.right=std::clamp(left+static_cast<int>((static_cast<double>(lastStep)+.5)*scale+roiHeight*.35),recognized.left+1,right);
  return recognized;
}

RecognizedLine LocalLineRecognizer::Read(const uint8_t* pixels,int width,int height,int stride,int left,int top,int right,int bottom) {
  std::lock_guard<std::mutex> guard(impl_->mutex);
  left=std::clamp(left,0,width-1);right=std::clamp(right,left+1,width);top=std::clamp(top,0,height-1);bottom=std::clamp(bottom,top+1,height);
  auto primary=impl_->Run(pixels,width,height,stride,left,top,right,bottom);
  if(primary.confidence>=.90f||!impl_->fallback_available)return primary;
  if(!impl_->fallback)impl_->fallback=std::make_unique<Impl>(impl_->directory,impl_->fallback_bytes,impl_->fallback_size,true);
  auto alternate=impl_->fallback->Run(pixels,width,height,stride,left,top,right,bottom);
  auto key=[](const std::string& text){std::string value;for(unsigned char c:text) {
    if(c==' '||c=='\n'||c=='\r'||c=='\t')continue;
    value+=static_cast<char>(c>='a'&&c<='z'?c-'a'+'A':c);
  }return value;};
  // Preserve the specialist's proven decorative-word reading. Tighten only
  // vertical padding, retain the whole word width, and require agreement.
  if(alternate.confidence>=.75f&&alternate.confidence<.90f&&right-left<(bottom-top)*8) {
    auto original=key(alternate.text);
    for(float factor:{.95f,.9f,.85f,.8f}) {
      int margin=static_cast<int>(std::round((bottom-top)*(1-factor)*.5f));
      if(margin<1||bottom-top-margin*2<8)continue;
      auto retry=impl_->fallback->Run(pixels,width,height,stride,left,top+margin,right,bottom-margin);
      if(retry.confidence>=.90f&&retry.confidence>alternate.confidence+.025f&&key(retry.text)==original){alternate=std::move(retry);break;}
    }
  }
  auto a=key(primary.text),b=key(alternate.text);
  if(alternate.confidence>=.90f&&alternate.confidence>primary.confidence+.025f&&
      (a.empty()||(b.size()>=a.size()*.65&&b.size()<=a.size()*1.75+4)))return alternate;
  return primary;
}

RecognizedLine LocalLineRecognizer::ReadWithHint(const uint8_t* pixels,int width,int height,int stride,int left,int top,int right,int bottom,const std::string& system_text) {
  auto primary=Read(pixels,width,height,stride,left,top,right,bottom);
  auto key=[](const std::string& text){std::string result;for(unsigned char c:text) {
    if((c>='A'&&c<='Z')||(c>='0'&&c<='9')||c>=128)result+=static_cast<char>(c);
    else if(c>='a'&&c<='z')result+=static_cast<char>(c-'a'+'A');
  }return result;};
  auto expected=key(system_text),actual=key(primary.text);
  if(expected.size()<2||expected.size()>512)return primary;
  if(expected==actual){primary.system_agreement=true;return primary;}
  if(!impl_->fallback_available||actual.size()>512)return primary;
  // Confidence from different OCR families is not calibrated. Consult the
  // independent English reader only for a small disagreement, and require
  // exact agreement with the system reader. Keep its actual confidence.
  std::vector<size_t> distance(expected.size()+1);for(size_t j=0;j<distance.size();++j)distance[j]=j;
  for(size_t i=0;i<actual.size();++i){size_t previous=distance[0];distance[0]=i+1;
    for(size_t j=0;j<expected.size();++j){size_t old=distance[j+1];distance[j+1]=std::min({distance[j+1]+1,distance[j]+1,previous+(actual[i]!=expected[j])});previous=old;}}
  if(distance.back()>std::max<size_t>(1,expected.size()/6))return primary;
  std::lock_guard<std::mutex> guard(impl_->mutex);
  if(!impl_->fallback)impl_->fallback=std::make_unique<Impl>(impl_->directory,impl_->fallback_bytes,impl_->fallback_size,true);
  auto alternate=impl_->fallback->Run(pixels,width,height,stride,left,top,right,bottom);
  if(alternate.confidence>=.75f&&key(alternate.text)==expected){alternate.system_agreement=true;return alternate;}
  // A few pixels of extra vertical padding can change a stylized U into L
  // even at high confidence. Retry only a small disagreement, preserving
  // the entire line width. Accept actual pixels only when a high-confidence
  // local retry agrees with the independent system reader, never a spelling
  // guess or a vocabulary replacement.
  for(int margin:{2,3,4,5}) {
    if(bottom-top-margin*2<16)continue;
    auto retry=impl_->Run(pixels,width,height,stride,left,top+margin,right,bottom-margin);
    if(retry.confidence>=.90f&&key(retry.text)==expected){retry.system_agreement=true;return retry;}
    auto fallbackRetry=impl_->fallback->Run(pixels,width,height,stride,left,top+margin,right,bottom-margin);
    if(fallbackRetry.confidence>=.90f&&key(fallbackRetry.text)==expected){fallbackRetry.system_agreement=true;return fallbackRetry;}
  }
  return primary;
}

RecognizedLine LocalLineRecognizer::ReadFamilyQuad(const uint8_t* pixels,int width,int height,int stride,const std::array<float,8>& q,bool secondary) {
  double horizontal=std::hypot(q[2]-q[0],q[3]-q[1]),vertical=std::hypot(q[6]-q[0],q[7]-q[1]);
  if(horizontal<2||vertical<2)return {};
  int w=std::clamp(static_cast<int>(std::ceil(48*horizontal/vertical)),8,2048);
  std::vector<uint8_t> rectified(static_cast<size_t>(w)*48*4,255);
  for(int y=0;y<48;++y)for(int x=0;x<w;++x) {
    double u=(x+.5)/w,v=(y+.5)/48;
    double sx=(1-v)*((1-u)*q[0]+u*q[2])+v*((1-u)*q[6]+u*q[4]);
    double sy=(1-v)*((1-u)*q[1]+u*q[3])+v*((1-u)*q[7]+u*q[5]);
    int x0=std::clamp(static_cast<int>(sx),0,width-1),y0=std::clamp(static_cast<int>(sy),0,height-1),x1=std::min(x0+1,width-1),y1=std::min(y0+1,height-1);
    double fx=std::clamp(sx-x0,0.0,1.0),fy=std::clamp(sy-y0,0.0,1.0);
    for(int c=0;c<3;++c){auto at=[&](int a,int b){return pixels[static_cast<size_t>(b)*stride+a*4+c];};
      rectified[(static_cast<size_t>(y)*w+x)*4+c]=static_cast<uint8_t>(at(x0,y0)*(1-fx)*(1-fy)+at(x1,y0)*fx*(1-fy)+at(x0,y1)*(1-fx)*fy+at(x1,y1)*fx*fy);}
  }
  std::lock_guard<std::mutex> guard(impl_->mutex);
  if(!secondary)return impl_->Run(rectified.data(),w,48,w*4,0,0,w,48);
  if(!impl_->fallback_available)return {};
  if(!impl_->fallback)impl_->fallback=std::make_unique<Impl>(impl_->directory,impl_->fallback_bytes,impl_->fallback_size,true);
  return impl_->fallback->Run(rectified.data(),w,48,w*4,0,0,w,48);
}

struct LocalTranslationModel::Impl {
  Ort::Env env;Ort::SessionOptions options;Ort::Session encoder{nullptr},decoder{nullptr};
  Ort::MemoryInfo memory=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
  Tokenizer tokenizer;
  std::vector<std::string> inputNames,outputNames;
  std::vector<const char*> inputPointers,outputPointers;
  std::mutex mutex;std::atomic<uint64_t> cancellation{0};
  struct TermRule {std::regex source,pattern;std::string replacement;};
  std::vector<TermRule> terminology;
  std::vector<TermRule> sourceRules;
  explicit Impl(const std::filesystem::path& directory,ModelBytes bytes):env(ORT_LOGGING_LEVEL_ERROR,"LumaLocal"),tokenizer(directory/"tokenizer.json") {
    options.SetIntraOpNumThreads(2);options.SetInterOpNumThreads(1);options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
    encoder=bytes.encoder?Ort::Session(env,bytes.encoder,bytes.encoder_size,options):Ort::Session(env,(directory/"encoder.onnx").c_str(),options);
    decoder=bytes.decoder?Ort::Session(env,bytes.decoder,bytes.decoder_size,options):Ort::Session(env,(directory/"decoder.onnx").c_str(),options);
    Ort::AllocatorWithDefaultOptions allocator;
    for(size_t i=0;i<decoder.GetInputCount();++i)inputNames.emplace_back(decoder.GetInputNameAllocated(i,allocator).get());
    for(size_t i=0;i<decoder.GetOutputCount();++i)outputNames.emplace_back(decoder.GetOutputNameAllocated(i,allocator).get());
    for(auto& n:inputNames)inputPointers.push_back(n.c_str());for(auto& n:outputNames)outputPointers.push_back(n.c_str());
    std::ifstream glossary(directory/"terminology.json");
    if(glossary) {
      auto entries=nlohmann::json::parse(glossary);
      auto read=[](const nlohmann::json& rules,std::vector<TermRule>& target) {for(auto& rule:rules)target.push_back({std::regex(rule.at("source").get<std::string>(),std::regex::icase),std::regex(rule.at("pattern").get<std::string>(),std::regex::icase),rule.at("replacement").get<std::string>()});};
      read(entries.at("rules"),terminology);if(entries.contains("source_rules"))read(entries.at("source_rules"),sourceRules);
    }
  }
  std::string RepairOcr(const std::string& input,std::vector<std::string>& changes) const {
    auto protectedToken=[](const std::string& text,size_t start,size_t end) {
      while(start>0&&static_cast<unsigned char>(text[start-1])>32)--start;
      while(end<text.size()&&static_cast<unsigned char>(text[end])>32)++end;
      auto token=text.substr(start,end-start);
      if(token.find('/')!=std::string::npos||token.find('\\')!=std::string::npos||
          token.find('@')!=std::string::npos||token.find('_')!=std::string::npos)return true;
      for(size_t i=1;i+1<token.size();++i)if(token[i]=='.'&&
          ((token[i-1]>='A'&&token[i-1]<='Z')||(token[i-1]>='a'&&token[i-1]<='z')||(token[i-1]>='0'&&token[i-1]<='9'))&&
          ((token[i+1]>='A'&&token[i+1]<='Z')||(token[i+1]>='a'&&token[i+1]<='z')))return true;
      return false;
    };
    // Comic lettering confuses O/0 in measurements. Limit this correction to
    // an existing numeric prefix followed by a known unit, preserving values
    // such as 10 minutes, model numbers and character names.
    static const std::regex measurement("\\b([0-9]+)([oO]+)([ ]*(?:mm|cm|km|mg|kg|ml|m|g|l))\\b",std::regex::icase);
    std::string measured;size_t previous=0;
    for(std::sregex_iterator it(input.begin(),input.end(),measurement),end;it!=end;++it) {
      auto& match=*it;measured.append(input,previous,match.position()-previous);
      auto replacement=match.str();
      if(!protectedToken(input,match.position(),match.position()+match.length())) {
        replacement=match[1].str()+std::string(match[2].length(),'0')+match[3].str();
        changes.push_back(match.str()+" -> "+replacement);
      }
      measured+=replacement;previous=match.position()+match.length();
    }
    measured.append(input,previous,std::string::npos);
    std::string output;
    auto alpha=[](char c){return (c>='A'&&c<='Z')||(c>='a'&&c<='z');};
    auto digit=[](char c){return c>='0'&&c<='9';};
    for(size_t at=0;at<measured.size();) {
      if(!alpha(measured[at])&&!digit(measured[at])) {output+=measured[at++];continue;}
      size_t begin=at,end=at;while(end<measured.size()&&(alpha(measured[end])||digit(measured[end])))++end;
      auto word=measured.substr(at,end-at);at=end;
      // A slash may be a misread stroke inside one word (QUE5T/ON), not a
      // boundary after a complete word (QUEST). Preserve fragments, addresses
      // and file paths instead of turning them into a different valid word.
      bool dotted=(end+1<measured.size()&&measured[end]=='.'&&alpha(measured[end+1]))||
          (begin>1&&measured[begin-1]=='.'&&alpha(measured[begin-2]));
      if(protectedToken(measured,begin,end)||dotted){output+=word;continue;}
      int letters=0,digits=0;bool internal=false,uppercase=true,supported=true;
      for(size_t i=0;i<word.size();++i) {
        char c=word[i];if(alpha(c)){++letters;if(c>='a'&&c<='z')uppercase=false;}
        else {++digits;if(i>0&&i+1<word.size()&&alpha(word[i-1])&&alpha(word[i+1]))internal=true;
          if(c!='0'&&c!='1'&&c!='5'&&c!='8')supported=false;}
      }
      // An isolated number, suffix (PlayStation5/Windows11), code (RTX5080)
      // or ambiguous short token is never repaired by the word vocabulary.
      if(letters<4||digits<1||digits>2||!internal||!supported){output+=word;continue;}
      std::vector<std::string> candidates{std::string()};
      for(char c:word) {
        if(alpha(c)){for(auto& candidate:candidates)candidate+=c>='A'&&c<='Z'?static_cast<char>(c+32):c;}
        else if(c=='1') {auto alternate=candidates;for(auto& candidate:candidates)candidate+='i';for(auto& candidate:alternate)candidate+='l';candidates.insert(candidates.end(),alternate.begin(),alternate.end());}
        else {char letter=c=='0'?'o':c=='5'?'s':'b';for(auto& candidate:candidates)candidate+=letter;}
      }
      std::string selected;int valid=0;
      for(auto& candidate:candidates)if(tokenizer.vocabulary.count("\xE2\x96\x81"+candidate)){selected=candidate;++valid;}
      if(valid!=1){output+=word;continue;}
      auto repaired=word;
      for(size_t i=0;i<word.size();++i)if(digit(word[i]))repaired[i]=uppercase?static_cast<char>(selected[i]-32):selected[i];
      output+=repaired;changes.push_back(word+" -> "+repaired);
    }
    return output;
  }
  std::string Generate(const std::string& source,const std::function<bool()>& cancelled,uint64_t generation) {
    auto check=[&] {if(cancellation!=generation||(cancelled&&cancelled()))throw std::runtime_error("Traduccion cancelada por movimiento.");};
    check();auto ids=tokenizer.Encode(source);
    if(ids.size()>450) {
      size_t middle=source.size()/2;size_t split=source.find_last_of(".!?;",middle);
      if(split==std::string::npos||split<source.size()/5)split=source.find_last_of(' ',middle);
      if(split==std::string::npos)throw std::runtime_error("El bloque de texto es demasiado largo para traducirlo completo.");
      return Generate(source.substr(0,split+1),cancelled,generation)+" "+Generate(source.substr(split+1),cancelled,generation);
    }
    std::vector<int64_t> attention(ids.size(),1);std::array<int64_t,2> shape{1,static_cast<int64_t>(ids.size())};
    auto sourceTensor=Ort::Value::CreateTensor<int64_t>(memory,ids.data(),ids.size(),shape.data(),2);
    auto attentionTensor=Ort::Value::CreateTensor<int64_t>(memory,attention.data(),attention.size(),shape.data(),2);
    const char* encoderNames[]{"input_ids","attention_mask"};const char* encoderOutputs[]{"last_hidden_state"};
    std::array<const OrtValue*,2> encoderInput{sourceTensor,attentionTensor};OrtValue* hiddenRaw=nullptr;Ort::RunOptions run;
    Ort::ThrowOnError(Ort::GetApi().Run(encoder,run,encoderNames,encoderInput.data(),2,encoderOutputs,1,&hiddenRaw));
    Ort::Value hidden{hiddenRaw};float dummy=0;std::array<int64_t,4> emptyShape{1,tokenizer.heads,0,tokenizer.headSize};
    auto empty=Ort::Value::CreateTensor<float>(memory,&dummy,0,emptyShape.data(),4);
    std::vector<Beam> beams{{{tokenizer.pad},0,nullptr,nullptr}},finished;
    constexpr size_t width=4;size_t maxSteps=std::min<size_t>(480,std::max<size_t>(64,ids.size()*3));
    for(size_t step=0;step<maxSteps;++step) {
      check();std::vector<Candidate> candidates;
      for(auto& beam:beams) {
        check();int64_t last=beam.tokens.back();std::array<int64_t,2> tokenShape{1,1};bool cached=beam.past!=nullptr;std::array<int64_t,1> flagShape{1};
        auto token=Ort::Value::CreateTensor<int64_t>(memory,&last,1,tokenShape.data(),2);
        auto flag=Ort::Value::CreateTensor<bool>(memory,&cached,1,flagShape.data(),1);
        std::vector<const OrtValue*> inputs;
        for(auto& name:inputNames) {
          if(name=="input_ids")inputs.push_back(token);
          else if(name=="encoder_attention_mask")inputs.push_back(attentionTensor);
          else if(name=="encoder_hidden_states")inputs.push_back(hidden);
          else if(name=="use_cache_branch")inputs.push_back(flag);
          else {
            int layer=std::stoi(name.substr(16));bool cross=name.find(".encoder.")!=std::string::npos;
            int index=1+layer*4+(cross?2:0)+(name.find(".value")!=std::string::npos?1:0);
            auto cache=cross?beam.cross:beam.past;inputs.push_back(cache?cache->values.at(index):empty);
          }
        }
        std::vector<OrtValue*> raw(outputNames.size(),nullptr);
        Ort::ThrowOnError(Ort::GetApi().Run(decoder,run,inputPointers.data(),inputs.data(),inputs.size(),outputPointers.data(),raw.size(),raw.data()));
        auto decoded=std::make_shared<Decoded>();for(auto value:raw)decoded->values.emplace_back(value);
        const float* logits=decoded->values[0].GetTensorData<float>();
        std::array<std::pair<float,int>,8> top;for(auto& item:top)item={-std::numeric_limits<float>::infinity(),0};
        int vocabSize=static_cast<int>(tokenizer.tokens.size());
        for(int id=0;id<vocabSize;++id)if(id!=tokenizer.pad&&id!=tokenizer.unknown&&logits[id]>top.back().first) {
          size_t at=top.size()-1;while(at>0&&logits[id]>top[at-1].first) {top[at]=top[at-1];--at;}top[at]={logits[id],id};
        }
        double sum=0;for(int id=0;id<vocabSize;++id)if(id!=tokenizer.pad&&id!=tokenizer.unknown)sum+=std::exp(static_cast<double>(logits[id])-top[0].first);
        double normalizer=top[0].first+std::log(sum);
        for(auto item:top) {Beam child=beam;child.score+=item.first-normalizer;child.past=decoded;child.cross=beam.cross?beam.cross:decoded;candidates.push_back({std::move(child),item.second});}
      }
      std::stable_sort(candidates.begin(),candidates.end(),[](const Candidate& a,const Candidate& b){return a.beam.score>b.beam.score;});
      beams.clear();size_t rank=0;
      for(auto& candidate:candidates) {
        if(candidate.token==tokenizer.eos) {if(rank<width)finished.push_back(std::move(candidate.beam));}
        else if(beams.size()<width) {candidate.beam.tokens.push_back(candidate.token);beams.push_back(std::move(candidate.beam));}
        ++rank;if(beams.size()==width&&rank>=width*2)break;
      }
      auto score=[](const Beam& b){return b.score/static_cast<double>(std::max<size_t>(1,b.tokens.size()));};
      std::stable_sort(finished.begin(),finished.end(),[&](const Beam& a,const Beam& b){return score(a)>score(b);});
      if(finished.size()>width)finished.resize(width);
      if(beams.empty()||(finished.size()==width&&score(finished.back())>=score(beams.front())))break;
    }
    check();if(finished.empty())throw IncompleteTranslation("El modelo no completo la frase; se conserva el original.");
    auto result=tokenizer.Decode(finished.front().tokens);
    return result;
  }
};

LocalTranslationModel::LocalTranslationModel(const std::string& directory,ModelBytes bytes) {InitializeRuntime();impl_=std::make_unique<Impl>(std::filesystem::u8path(directory),bytes);}
LocalTranslationModel::~LocalTranslationModel()=default;
void LocalTranslationModel::Cancel(){++impl_->cancellation;}
std::vector<int64_t> LocalTranslationModel::Tokenize(const std::string& text) const {return impl_->tokenizer.Encode(text);}
std::string LocalTranslationModel::PrepareSource(const std::string& text) {
  std::string result=std::regex_replace(text,std::regex("[\\t\\r\\n ]+")," ");result=Trim(result);
  size_t letters=0,lower=0;for(unsigned char c:result) {if(c>='A'&&c<='Z')++letters;else if(c>='a'&&c<='z'){++letters;++lower;}}
  // Short all-capital labels are fragmented very differently by SentencePiece
  // (e.g. a common word can become unrelated single-letter pieces). Use the
  // same sentence casing as longer OCR paragraphs. Keep codes, addresses,
  // hashtags, numeric identifiers and common protocol/encoding acronyms.
  bool shortLabel=letters>=5&&lower==0&&result.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZ ,.!?;:'\"()-")==std::string::npos;
  for(const char* acronym:{"ASCII","HTTPS","HTTP","JSON","HTML","ONNX","CUDA","RGBA","ARGB"})if(result==acronym)shortLabel=false;
  if((letters>12&&lower==0&&std::count(result.begin(),result.end(),' ')>=2)||shortLabel) {
    bool initial=true;
    for(char& c:result) {if(c>='A'&&c<='Z'){if(!initial)c=static_cast<char>(c+32);initial=false;}else if(c=='.'||c=='!'||c=='?')initial=true;}
    result=std::regex_replace(result,std::regex("\\bi\\b"),"I");
  }
  return result;
}
std::string LocalTranslationModel::Translate(const std::string& text,const std::function<bool()>& cancelled) {
  return TranslateDetailed(text,cancelled).text;
}
TranslationResult LocalTranslationModel::PrepareInput(const std::string& text) const {
  TranslationResult result;result.prepared=PrepareSource(impl_->RepairOcr(Nfkc(text),result.source_corrections));
  for(auto& rule:impl_->sourceRules)if(std::regex_search(result.prepared,rule.source)&&std::regex_search(result.prepared,rule.pattern)) {
    auto corrected=std::regex_replace(result.prepared,rule.pattern,rule.replacement);
    if(corrected!=result.prepared){result.prepared=corrected;result.source_corrections.push_back(rule.replacement);}
  }
  return result;
}
TranslationResult LocalTranslationModel::TranslateCoreDetailed(const std::string& text,const std::function<bool()>& cancelled) {
  std::lock_guard<std::mutex> lock(impl_->mutex);auto generation=impl_->cancellation.load();
  auto translate_one=[&](const std::string& input) {
    TranslationResult result=PrepareInput(input);
    // Scanlation role credits contain names/handles, not dialogue. Inference
    // can invent a sentence for an unrecognized handle; keep these verbatim.
    if(std::regex_match(result.prepared,std::regex("(?:TS|TL|PR|RD|QC|CL) [A-Za-z0-9_-]{3,}"))) {
      result.text=input;result.retained_original=true;result.reason="Credito o identificador: se conserva el nombre original.";return result;
    }
    auto generate=[&]() {
      try {result.raw=impl_->Generate(result.prepared,cancelled,generation);result.text=result.raw;return true;}
      catch(const IncompleteTranslation& error) {
        // A truncated OCR fragment must not discard the other translated
        // balloons. Preserve it explicitly, without publishing a partial guess.
        result.text=input;result.retained_original=true;result.reason=error.what();return false;
      }
    };
    if(!generate())return result;
    if(result.raw.empty()) {
      result.text=input;result.retained_original=true;result.reason="El modelo no produjo texto; se conserva esta region original.";return result;
    }
    auto folded=[](std::string value){for(char& c:value)if(c>='A'&&c<='Z')c=static_cast<char>(c+32);return value;};
    // An unpunctuated UI label can be mistaken for a copied title. Retry only
    // unchanged multiword text; preserve genuinely unchanged names afterwards.
    if(folded(result.raw)==folded(result.prepared)&&result.prepared.find(' ')!=std::string::npos&&
        result.prepared.find("http")==std::string::npos&&!result.prepared.empty()&&
        result.prepared.back()!='.'&&result.prepared.back()!='!'&&result.prepared.back()!='?'&&result.prepared.back()!=',') {
      result.prepared+='.';if(!generate())return result;
      if(result.raw.empty()) {result.text=input;result.retained_original=true;result.reason="El modelo no produjo texto al reintentar; se conserva el original.";return result;}
      if(!result.text.empty()&&result.text.back()=='.')result.text.pop_back();
    }
    for(auto& rule:impl_->terminology)if(std::regex_search(result.prepared,rule.source)&&std::regex_search(result.text,rule.pattern)) {
      result.text=std::regex_replace(result.text,rule.pattern,rule.replacement);result.terminology.push_back(rule.replacement);
    }
    return result;
  };
  auto result=translate_one(text);
  auto parts=coverage::Sentences(text);
  if(result.retained_original||!coverage::Retry(text,result.text,parts))return result;
  const bool conservative=!coverage::LongClauseRetry(text,result.text,parts);
  std::vector<TranslationResult> sentences;std::string joined;
  for(const auto& part:parts) {
    auto translated=translate_one(part);
    if(!coverage::Plausible(part,translated.text))return result;
    if(conservative&&!coverage::PreservesNegation(part,translated.text))return result;
    if(translated.retained_original||translated.text.empty()||coverage::Letters(translated.text)==coverage::Letters(part))return result;
    if(!joined.empty())joined+=' ';joined+=translated.text;
    sentences.push_back(std::move(translated));
  }
  if(joined.size()<1.15*result.text.size()||coverage::Clauses(joined)<parts.size())return result;
  if(conservative&&!coverage::PreservesExistingWords(result.text,joined))return result;
  result.whole_translation=result.text;result.text=joined;result.sentence_recovered=true;
  for(auto& sentence:sentences) {
    result.sentence_sources.push_back(sentence.prepared);result.sentence_translations.push_back(sentence.text);
    result.terminology.insert(result.terminology.end(),sentence.terminology.begin(),sentence.terminology.end());
    result.source_corrections.insert(result.source_corrections.end(),sentence.source_corrections.begin(),sentence.source_corrections.end());
  }
  return result;
}
TranslationResult LocalTranslationModel::TranslateBaseDetailed(const std::string& text,const std::function<bool()>& stopped) {
  auto result=TranslateCoreDetailed(text,stopped);
  auto question=punctuation::PreserveQuestion(text,result.text,result.retained_original);
  result.text=std::move(question.text);result.question_recovered=question.restored;
  auto parts=opening::Split(text);
  bool shortQuestion=false;
  if(parts.first.empty()){parts=question_clause::Split(text);shortQuestion=!parts.first.empty();}
  if(!parts.first.empty()&&!result.retained_original) {
    // The additional inferences use only captured source text. Every existing
    // output word must also occur, in order, in the independent remainder.
    auto first=TranslateCoreDetailed(shortQuestion?question_clause::ModelInput(parts.first):opening::ModelInput(parts.first),stopped);
    auto rest=TranslateCoreDetailed(parts.rest,stopped);
    auto recovered=opening::Recover(parts,result.text,first.text,rest.text,result.retained_original,
                                    first.retained_original,rest.retained_original);
    if(recovered.recovered) {
      if(result.whole_translation.empty())result.whole_translation=result.text;
      result.text=std::move(recovered.text);result.opening_recovered=true;
      result.opening_source=parts.first;result.opening_translation=first.text;
    }
  }
  return result;
}
TranslationResult LocalTranslationModel::TranslateDetailed(const std::string& text,const std::function<bool()>& cancelled) {
  const auto generation=impl_->cancellation.load();
  auto stopped=[&]{return impl_->cancellation.load()!=generation||(cancelled&&cancelled());};
  auto result=TranslateBaseDetailed(text,stopped);
  const auto parts=tail::Plan(text,result.text,result.retained_original);
  if(!parts.head.empty()&&!stopped()) {
    const auto head=TranslateBaseDetailed(parts.head,stopped);
    // Do not decode an extra sentence unless the independent head accounts
    // exactly for the existing translation. The prefix is immutable.
    if(!head.retained_original&&coverage::NormalizedWords(head.text)==coverage::NormalizedWords(result.text)&&!stopped()) {
      const auto extra=TranslateBaseDetailed(parts.tail,stopped);
      auto recovered=tail::Recover(parts,result.text,head.text,extra.text,result.retained_original,
                                   head.retained_original,extra.retained_original);
      if(recovered.recovered&&!stopped()) {
        if(result.whole_translation.empty())result.whole_translation=result.text;
        result.text=std::move(recovered.text);result.tail_recovered=true;
        result.tail_source=parts.tail;result.tail_translation=extra.text;
      }
    }
  }
  return result;
}
}
