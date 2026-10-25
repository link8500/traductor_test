#include "screen_translator.h"
#include "utils.h"
#include "json.hpp"
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Graphics.Imaging.h>
#include <winrt/Windows.Storage.Streams.h>
#include <algorithm>
#include <cstring>
#include <filesystem>
#include <fstream>

// Replay saved model outputs through the production Windows text painter.
// This does not rerun recognition and does not represent a phone screenshot.
int ScreenTranslator::ReviewExport(const std::string& input,const std::string& output) {
  int code=1;
  std::thread worker([&] {
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    using namespace winrt::Windows::Graphics::Imaging;
    using namespace winrt::Windows::Storage::Streams;
    using Json=nlohmann::json;
    Json summary={{"images",0},{"blocks",0},{"renderer","production Windows PaintBlocks"},
      {"scope","Replay of recorded OCR/NMT outputs over original images; not a new device capture"}};
    try {
      std::ifstream manifest(input);std::string line;
      std::ofstream progress(output+".progress.txt");
      while(std::getline(manifest,line)) {
        auto item=Json::parse(line);
        progress<<item.at("output").get<std::string>()<<" decode\n"<<std::flush;
        std::ifstream image(std::filesystem::u8path(item.at("path").get<std::string>()),std::ios::binary);
        std::vector<uint8_t> encoded((std::istreambuf_iterator<char>(image)),std::istreambuf_iterator<char>());
        if(encoded.empty())throw std::runtime_error("Missing original review image");
        InMemoryRandomAccessStream source;DataWriter writer(source);
        writer.WriteBytes(winrt::array_view<const uint8_t>(encoded));writer.StoreAsync().get();writer.DetachStream();source.Seek(0);
        auto decoder=BitmapDecoder::CreateAsync(source).get();
        int width=static_cast<int>(decoder.PixelWidth()),height=static_cast<int>(decoder.PixelHeight());
        if(width<1||height<1||width>4096||height>60000)throw std::runtime_error("Review image too large");
        auto data=decoder.GetPixelDataAsync(BitmapPixelFormat::Bgra8,BitmapAlphaMode::Ignore,
          BitmapTransform(),ExifOrientationMode::IgnoreExifOrientation,ColorManagementMode::DoNotColorManage).get().DetachPixelData();
        progress<<"paint\n"<<std::flush;
        HDC dc=CreateCompatibleDC(nullptr);BITMAPINFO info{};info.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth=width;info.bmiHeader.biHeight=-height;info.bmiHeader.biPlanes=1;info.bmiHeader.biBitCount=32;
        void* bits=nullptr;HBITMAP dib=CreateDIBSection(dc,&info,DIB_RGB_COLORS,&bits,nullptr,0);
        if(!dib){DeleteDC(dc);throw std::runtime_error("Cannot allocate review bitmap");}
        auto old=SelectObject(dc,dib);std::memcpy(bits,data.data(),static_cast<size_t>(width)*height*4);
        std::vector<Block> blocks;
        for(const auto& row:item.at("rows")) {
          if(!row.contains("translation")||row.value("retained_original",false)||row.contains("error"))continue;
          auto bounds=row.at("bounds");Block block{};
          block.rect={bounds[0].get<LONG>(),bounds[1].get<LONG>(),bounds[2].get<LONG>(),bounds[3].get<LONG>()};
          auto text=row.at("translation").get<std::string>();
          int characters=MultiByteToWideChar(CP_UTF8,0,text.data(),static_cast<int>(text.size()),nullptr,0);
          block.text.resize(characters);MultiByteToWideChar(CP_UTF8,0,text.data(),static_cast<int>(text.size()),block.text.data(),characters);
          int x=std::clamp(static_cast<int>(block.rect.left)-2,0,width-1),y=std::clamp(static_cast<int>(block.rect.top)-2,0,height-1);
          const auto* pixel=data.data()+(static_cast<size_t>(y)*width+x)*4;
          block.background=OverlayBackground(data.data(),data.size(),width,height,width*4,block.rect,RGB(pixel[2],pixel[1],pixel[0]));block.centered=true;
          blocks.push_back(std::move(block));
        }
        PaintBlocks(dc,blocks);GdiFlush();
        progress<<"encode\n"<<std::flush;
        std::vector<uint8_t> painted(static_cast<uint8_t*>(bits),static_cast<uint8_t*>(bits)+static_cast<size_t>(width)*height*4);
        SelectObject(dc,old);DeleteObject(dib);DeleteDC(dc);
        InMemoryRandomAccessStream destination;
        auto encoder=BitmapEncoder::CreateAsync(BitmapEncoder::JpegEncoderId(),destination).get();
        encoder.SetPixelData(BitmapPixelFormat::Bgra8,BitmapAlphaMode::Ignore,width,height,96,96,painted);
        encoder.FlushAsync().get();destination.Seek(0);
        progress<<"save\n"<<std::flush;
        DataReader reader(destination);auto size=static_cast<uint32_t>(destination.Size());reader.LoadAsync(size).get();
        std::vector<uint8_t> result(size);reader.ReadBytes(result);
        std::ofstream target(std::filesystem::u8path(item.at("output").get<std::string>()),std::ios::binary);
        target.write(reinterpret_cast<const char*>(result.data()),result.size());
        if(!target)throw std::runtime_error("Cannot save review bitmap");
        progress<<"done\n"<<std::flush;
        summary["images"]=summary["images"].get<int>()+1;summary["blocks"]=summary["blocks"].get<int>()+static_cast<int>(blocks.size());
      }
      summary["success"]=true;code=0;
    }catch(const winrt::hresult_error& error){summary["error"]=winrt::to_string(error.message());}
    catch(const std::exception& error){summary["error"]=error.what();}
    std::ofstream report(output);report<<summary.dump(2);winrt::uninit_apartment();
  });worker.join();return code;
}
