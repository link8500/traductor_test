#ifndef RUNNER_SCREEN_TRANSLATOR_H_
#define RUNNER_SCREEN_TRANSLATOR_H_

#include <windows.h>
#include <flutter/method_channel.h>
#include <flutter/standard_method_codec.h>
#include <atomic>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
namespace luma {class LocalLineRecognizer;class LocalTextDetector;}

class ScreenTranslator {
 public:
  ScreenTranslator(HWND owner, flutter::BinaryMessenger* messenger);
  ~ScreenTranslator();
  static int SelfTest(const std::string& output);
  static int ToolbarTest(const std::string& output);
  static int ComicBenchmark(const std::string& input,const std::string& output);
  static int TranslationReplay(const std::string& input,const std::string& output);
  static int ReviewExport(const std::string& input,const std::string& output);
  static int LayoutTest(const std::string& output);
  static int RecoveryTest(const std::string& output);

 private:
  struct Options {
    std::wstring source = L"en", target = L"es";
    std::wstring provider = L"local", endpoint, api_key;
    double opacity = .8;
  };
  struct Block { RECT rect; std::wstring text; COLORREF background; bool centered = false; std::wstring raw_text;
    std::vector<std::pair<RECT,std::wstring>> words;bool additional_detection=false;bool paragraph_recovered=false;bool line_completed=false;
    std::wstring before_consensus,first_reader,second_reader;bool consensus_recovered=false;bool short_dialogue_recovered=false; };
  struct Frame { int width, height; RECT desktop; double scale; std::vector<uint8_t> pixels; };
  struct CaptureResult {
    int generation = 0;
    bool complete = true;
    RECT desktop{};
    std::vector<Block> blocks;
    std::vector<RECT> text_regions;
    std::wstring error;
  };

  static LRESULT CALLBACK WindowProc(HWND, UINT, WPARAM, LPARAM);
  void HandleMethod(const flutter::MethodCall<flutter::EncodableValue>&,
      std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>>);
  void CreateWindows();
  void Start(const flutter::EncodableMap& args);
  void Stop(bool restore);
  void Request();
  Frame CaptureFrame();
  void PlaceToolbar(const RECT& desktop,const std::vector<RECT>& text);
  void SetWorking(bool);
  void DismissTranslation();
  void MonitorScreen();
  static std::vector<int> MotionSample(RECT& desktop);
  void Worker();
  void Notify(const std::wstring& message, bool error = false);
  flutter::EncodableMap Status() const;
  void PaintToolbar(HDC);
  void PaintOverlay(HDC);
  static void PaintBlocks(HDC,const std::vector<Block>&);
  static std::vector<RECT> PaintTextRects(const std::vector<Block>&);
  static COLORREF OverlayBackground(const uint8_t*,size_t,int,int,int,const RECT&,COLORREF);
  static Frame CaptureDesktop();
  static std::vector<Block> Recognize(const Frame&, const std::wstring& source, luma::LocalLineRecognizer* letters = nullptr,
      luma::LocalTextDetector* detector = nullptr,const std::function<bool()>& cancelled = {},bool recover_paragraphs = true,bool complete_lines = true,bool recover_short_dialogue = true);
  static std::vector<Block> MergeTextLines(std::vector<Block> lines,bool allow_row_overlap=true);
  static std::vector<Block> PreserveGroupReadings(const std::vector<Block>& baseline,std::vector<Block> proposed);
  static void RecoverParagraphs(const Frame&,std::vector<Block>&,luma::LocalLineRecognizer&,luma::LocalTextDetector&,const std::function<bool()>& cancelled);
  static void RecoverReaderConsensus(const Frame&,std::vector<Block>&,luma::LocalLineRecognizer&,
      luma::LocalLineRecognizer&,luma::LocalTextDetector&,const std::function<bool()>& cancelled = {});
  static std::wstring Translate(const std::wstring&, const Options&);

  HWND owner_, toolbar_ = nullptr, overlay_ = nullptr;
  std::unique_ptr<flutter::MethodChannel<flutter::EncodableValue>> channel_;
  std::thread worker_;
  std::mutex mutex_;
  std::condition_variable wake_;
  std::atomic<bool> exiting_{false}, active_{false}, busy_{false};
  std::atomic<int> generation_{0};
  bool requested_ = false, original_ = false;
  std::unique_ptr<Frame> requested_frame_;
  bool animating_ = false, watch_motion_ = false, toolbar_dragging_ = false;
  std::vector<int> motion_reference_;
  RECT motion_desktop_{}, motion_toolbar_{};
  bool exclusion_ = false;
  Options options_;
  std::vector<Block> blocks_;
  std::wstring message_ = L"Listo para activar la barra flotante";
  bool error_ = false;
  std::unordered_map<std::wstring, std::wstring> cache_;
};
#endif
