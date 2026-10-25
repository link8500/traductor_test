#include "screen_translator.h"
#include "../../native/overlay_background.h"
#include "utils.h"
#include "local_translation.h"
#include "ocr_recovery.h"
#include "ocr_coverage_candidate.h"
#include "ocr_full_consensus_candidate.h"
#include "ocr_morph_consensus_candidate.h"
#include "ocr_morph_edit_candidate.h"
#include "short_dialogue_candidate.h"
#include "json.hpp"
#include <dwmapi.h>
#include <windowsx.h>
#include <winhttp.h>
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Globalization.h>
#include <winrt/Windows.Graphics.Imaging.h>
#include <winrt/Windows.Media.Ocr.h>
#include <winrt/Windows.Storage.Streams.h>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <filesystem>
#include <sstream>
#include <stdexcept>

namespace {
constexpr UINT kCompleted = WM_APP + 71;
constexpr int kHotkey = 710;
constexpr int kAnimationTimer = 72, kMotionTimer = 73;
const wchar_t* kClass = L"LumaFloatingTranslator";
bool ToolbarPosition(const RECT& current,const RECT& content,const std::vector<RECT>& text,RECT& result) {
  LONG width=current.right-current.left,height=current.bottom-current.top;
  if(width<=0||height<=0||width>content.right-content.left||height>content.bottom-content.top)return false;
  auto clear=[&](const RECT& box){
    if(box.left<content.left||box.top<content.top||box.right>content.right||box.bottom>content.bottom)return false;
    for(auto obstacle:text){InflateRect(&obstacle,10,10);RECT overlap;if(IntersectRect(&overlap,&box,&obstacle))return false;}return true;
  };
  if(clear(current)){result=current;return true;}
  std::vector<POINT> points;
  auto add=[&](LONG x,LONG y){points.push_back({std::clamp(x,content.left,content.right-width),std::clamp(y,content.top,content.bottom-height)});};
  for(int i=0;i<=10;++i)for(int j=0;j<=14;++j)add(content.left+(content.right-content.left-width)*i/10,content.top+(content.bottom-content.top-height)*j/14);
  for(auto box:text){InflateRect(&box,10,10);for(LONG x:{current.left,box.left-width,box.right})for(LONG y:{current.top,box.top-height,box.bottom})add(x,y);}
  bool found=false;long long best=0;
  for(auto p:points){RECT box{p.x,p.y,p.x+width,p.y+height};if(!clear(box))continue;
    long long dx=static_cast<long long>(p.x)-current.left,dy=static_cast<long long>(p.y)-current.top,score=dx*dx+dy*dy;
    if(!found||score<best){found=true;best=score;result=box;}}
  return found;
}
std::wstring Wide(const std::string& text) {
  if (text.empty()) return {};
  int n = MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
  std::wstring out(n, L'\0');
  MultiByteToWideChar(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), out.data(), n);
  return out;
}
std::string LocalModelDirectory() {
  wchar_t executable[32768]{}; GetModuleFileNameW(nullptr,executable,32768);
  return (std::filesystem::path(executable).parent_path()/L"data/flutter_assets/assets/models/opus-en-es").u8string();
}
std::string PackagedReaderDirectory(const char* name) {
  wchar_t executable[32768]{};GetModuleFileNameW(nullptr,executable,32768);
  auto folder=std::filesystem::path(executable).parent_path()/L"ocr-readers"/name;
  for(const auto* part:{"english-ocr.onnx","ocr-characters.json","english-ocr-fallback.onnx","ocr-characters-fallback.json"})
    if(!std::filesystem::is_regular_file(folder/part))return {};
  return folder.u8string();
}
const std::unordered_map<std::string,bool>& RecoveryWords() {
  static const auto words=[] {
    std::ifstream input(std::filesystem::u8path(LocalModelDirectory())/"tokenizer.json");
    auto data=nlohmann::json::parse(input);std::unordered_map<std::string,bool> result;
    const std::string prefix="\xE2\x96\x81";
    for(const auto& value:data.at("tokens")) {
      auto piece=value.get<std::string>();
      if(piece.compare(0,prefix.size(),prefix)==0)result[luma::recovery::Key(piece.substr(prefix.size()))]=true;
    }
    return result;
  }();
  return words;
}
std::wstring StringArg(const flutter::EncodableMap& map, const char* key, const wchar_t* fallback) {
  auto it = map.find(flutter::EncodableValue(key));
  if (it != map.end()) if (auto s = std::get_if<std::string>(&it->second)) return Wide(*s);
  return fallback;
}
std::wstring Encode(const std::wstring& value) {
  std::string bytes = Utf8FromUtf16(value.c_str());
  const wchar_t* hex = L"0123456789ABCDEF";
  std::wstring output;
  for (unsigned char c : bytes) {
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~') output += static_cast<wchar_t>(c);
    else { output += L'%'; output += hex[c >> 4]; output += hex[c & 15]; }
  }
  return output;
}
class InternetHandle {
 public:
  explicit InternetHandle(HINTERNET h) : handle(h) { if (!h) throw std::runtime_error("No se pudo abrir la conexion de traduccion."); }
  ~InternetHandle() { WinHttpCloseHandle(handle); }
  HINTERNET handle;
};
std::wstring Http(const std::wstring& url, const std::wstring& body = {}) {
  URL_COMPONENTS components{};
  components.dwStructSize = sizeof(components);
  components.dwHostNameLength = components.dwUrlPathLength = components.dwExtraInfoLength = static_cast<DWORD>(-1);
  if (!WinHttpCrackUrl(url.c_str(), 0, 0, &components)) throw std::runtime_error("URL de traduccion no valida.");
  std::wstring host(components.lpszHostName, components.dwHostNameLength);
  std::wstring path(components.lpszUrlPath, components.dwUrlPathLength);
  if (components.dwExtraInfoLength) path.append(components.lpszExtraInfo, components.dwExtraInfoLength);
  if (path.empty()) path = L"/";
  InternetHandle session(WinHttpOpen(L"Luma/1.0", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0));
  WinHttpSetTimeouts(session.handle, 8000, 8000, 10000, 10000);
  InternetHandle connection(WinHttpConnect(session.handle, host.c_str(), components.nPort, 0));
  InternetHandle request(WinHttpOpenRequest(connection.handle, body.empty() ? L"GET" : L"POST", path.c_str(), nullptr,
      WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, components.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0));
  std::string payload = Utf8FromUtf16(body.c_str());
  if (!WinHttpSendRequest(request.handle, body.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : L"Content-Type: application/json\r\n", static_cast<DWORD>(-1),
      payload.empty() ? WINHTTP_NO_REQUEST_DATA : payload.data(), static_cast<DWORD>(payload.size()), static_cast<DWORD>(payload.size()), 0)
      || !WinHttpReceiveResponse(request.handle, nullptr)) throw std::runtime_error("No hay respuesta del traductor. Comprueba Internet o la URL del servidor.");
  DWORD status = 0, status_size = sizeof(status);
  WinHttpQueryHeaders(request.handle, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX, &status, &status_size, WINHTTP_NO_HEADER_INDEX);
  if (status == 429) throw std::runtime_error("El proveedor alcanzo su limite de traduccion. Usa otro proveedor o espera.");
  if (status != 200) throw std::runtime_error("El proveedor rechazo la traduccion (HTTP " + std::to_string(status) + ").");
  std::string response;
  DWORD available = 0;
  while (WinHttpQueryDataAvailable(request.handle, &available) && available) {
    if (response.size() + available > 1024 * 1024) throw std::runtime_error("Respuesta de traduccion demasiado grande.");
    std::string buffer(available, '\0'); DWORD read = 0;
    if (!WinHttpReadData(request.handle, buffer.data(), available, &read)) throw std::runtime_error("La conexion de traduccion se interrumpio.");
    response.append(buffer.data(), read);
  }
  return Wide(response);
}
void Text(HDC dc, const std::wstring& text, RECT rect, int size, COLORREF color, UINT flags = DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_END_ELLIPSIS) {
  HFONT font = CreateFontW(-size, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
  auto old = SelectObject(dc, font); SetBkMode(dc, TRANSPARENT); SetTextColor(dc, color);
  DrawTextW(dc, text.c_str(), static_cast<int>(text.size()), &rect, flags);
  SelectObject(dc, old); DeleteObject(font);
}
COLORREF Sample(const std::vector<uint8_t>& pixels, int width, int height, int x, int y) {
  x = std::clamp(x, 0, width-1); y = std::clamp(y, 0, height-1);
  const auto* p = &pixels[(static_cast<size_t>(y)*width+x)*4];
  return RGB(p[2], p[1], p[0]);
}
}

ScreenTranslator::ScreenTranslator(HWND owner, flutter::BinaryMessenger* messenger) : owner_(owner) {
  if (messenger) {
    channel_ = std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(messenger, "luma/screen_translator", &flutter::StandardMethodCodec::GetInstance());
    channel_->SetMethodCallHandler([this](const auto& call, auto result) { HandleMethod(call, std::move(result)); });
  }
  CreateWindows();
  worker_ = std::thread([this] { Worker(); });
}

COLORREF ScreenTranslator::OverlayBackground(const uint8_t* pixels,size_t bytes,int width,int height,int stride,const RECT& rect,COLORREF fallback) {
  auto color=luma::background::Dominant(pixels,bytes,width,height,stride,rect.left,rect.top,rect.right,rect.bottom);
  return color.confident?RGB(color.red,color.green,color.blue):fallback;
}

ScreenTranslator::~ScreenTranslator() {
  active_ = false; exiting_ = true; ++generation_; wake_.notify_one();
  if (worker_.joinable()) worker_.join();
  KillTimer(toolbar_, kAnimationTimer); KillTimer(toolbar_, kMotionTimer); UnregisterHotKey(toolbar_, kHotkey);
  MSG message;
  while (PeekMessage(&message, toolbar_, kCompleted, kCompleted, PM_REMOVE)) delete reinterpret_cast<CaptureResult*>(message.lParam);
  DestroyWindow(overlay_); DestroyWindow(toolbar_);
  if (channel_) channel_->SetMethodCallHandler(nullptr);
}

void ScreenTranslator::CreateWindows() {
  WNDCLASSW wc{}; wc.lpfnWndProc = WindowProc; wc.hInstance = GetModuleHandle(nullptr);
  wc.lpszClassName = kClass; wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
  RegisterClassW(&wc);
  toolbar_ = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, kClass,
      L"Luma - Barra flotante", WS_POPUP, 50, 90, 184, 76, nullptr, nullptr, wc.hInstance, this);
  overlay_ = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED,
      kClass, L"Luma - Traducciones", WS_POPUP, 0, 0, 1, 1, nullptr, nullptr, wc.hInstance, this);
  if (!toolbar_ || !overlay_) throw std::runtime_error("No se pudo crear la barra flotante.");
  SetLayeredWindowAttributes(overlay_, RGB(255, 0, 255), 255, LWA_COLORKEY | LWA_ALPHA);
  exclusion_ = SetWindowDisplayAffinity(overlay_, 0x00000011) != FALSE;
  SetWindowDisplayAffinity(toolbar_, 0x00000011);
  int rounded = 2; DwmSetWindowAttribute(toolbar_, 33, &rounded, sizeof(rounded));
}

flutter::EncodableMap ScreenTranslator::Status() const {
  return {{flutter::EncodableValue("running"), flutter::EncodableValue(active_.load())},
    {flutter::EncodableValue("original"), flutter::EncodableValue(original_)},
    {flutter::EncodableValue("message"), flutter::EncodableValue(Utf8FromUtf16(message_.c_str()))},
    {flutter::EncodableValue("error"), error_ ? flutter::EncodableValue(Utf8FromUtf16(message_.c_str())) : flutter::EncodableValue()}};
}

void ScreenTranslator::Notify(const std::wstring& message, bool error) {
  message_ = message; error_ = error;
  InvalidateRect(toolbar_, nullptr, FALSE);
  if (channel_) channel_->InvokeMethod("status", std::make_unique<flutter::EncodableValue>(Status()));
}

void ScreenTranslator::HandleMethod(const flutter::MethodCall<flutter::EncodableValue>& call,
    std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>> result) {
  try {
    if (call.method_name() == "status") { result->Success(flutter::EncodableValue(Status())); return; }
    if (call.method_name() == "start") {
      const auto* args = call.arguments() ? std::get_if<flutter::EncodableMap>(call.arguments()) : nullptr;
      if (!args) { result->Error("arguments", "Faltan los idiomas de la captura."); return; }
      Start(*args);
    } else if (call.method_name() == "stop") Stop(true);
    else if (call.method_name() == "translate") Request();
    else { result->NotImplemented(); return; }
    result->Success();
  } catch (const std::exception& e) { result->Error("overlay", e.what()); }
  catch (const winrt::hresult_error& e) { result->Error("overlay", winrt::to_string(e.message())); }
}

void ScreenTranslator::Start(const flutter::EncodableMap& args) {
  if (active_) throw std::runtime_error("Deten la captura antes de cambiar sus idiomas.");
  {
    std::lock_guard<std::mutex> lock(mutex_);
    options_.source = StringArg(args, "source", L"en"); options_.target = StringArg(args, "target", L"es");
    if (options_.source == options_.target) throw std::runtime_error("Elige dos idiomas diferentes.");
    options_.provider = StringArg(args, "provider", L"local");
    if (options_.provider == L"local" && (options_.source != L"en" || options_.target != L"es"))
      throw std::runtime_error("El modelo local incluido traduce de ingles a espanol. Selecciona esos idiomas.");
    options_.endpoint = StringArg(args, "endpoint", L""); options_.api_key = StringArg(args, "apiKey", L"");
    auto opacity = args.find(flutter::EncodableValue("opacity"));
    if (opacity != args.end()) if (const auto* v = std::get_if<double>(&opacity->second)) options_.opacity = std::clamp(*v, .4, 1.0);
  }
  original_ = false; active_ = true; ++generation_; blocks_.clear();
  SetLayeredWindowAttributes(overlay_, RGB(255,0,255), static_cast<BYTE>(options_.opacity * 255), LWA_COLORKEY | LWA_ALPHA);
  ShowWindow(owner_, SW_MINIMIZE); ShowWindow(toolbar_, SW_SHOWNOACTIVATE);
  SetWindowPos(toolbar_, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);
  RegisterHotKey(toolbar_, kHotkey, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 'L');
  watch_motion_ = false; SetWorking(false);
  Notify(L"Toca el icono · Ctrl + Shift + L");
}

void ScreenTranslator::Stop(bool restore) {
  active_ = false; ++generation_;
  watch_motion_ = false; motion_reference_.clear(); SetWorking(false);
  { std::lock_guard<std::mutex> lock(mutex_); requested_ = false; requested_frame_.reset(); }
  KillTimer(toolbar_, kMotionTimer); UnregisterHotKey(toolbar_, kHotkey);
  blocks_.clear(); ShowWindow(overlay_, SW_HIDE); ShowWindow(toolbar_, SW_HIDE);
  if (restore) { ShowWindow(owner_, SW_RESTORE); SetForegroundWindow(owner_); }
  Notify(L"Captura detenida · Barra cerrada");
}

void ScreenTranslator::Request() {
  if (!active_ || busy_.exchange(true)) return;
  original_ = false;
  blocks_.clear();
  std::unique_ptr<Frame> frame;
  try { frame=std::make_unique<Frame>(CaptureFrame()); }
  catch(const std::exception& e){busy_=false;watch_motion_=false;KillTimer(toolbar_,kMotionTimer);SetWorking(false);Notify(Wide(e.what()),true);return;}
  SetWorking(true);
  GetWindowRect(toolbar_, &motion_toolbar_);
  motion_reference_ = MotionSample(motion_desktop_); watch_motion_ = true;
  SetTimer(toolbar_, kMotionTimer, 150, nullptr);
  Notify(L"Reconociendo y traduciendo pantalla…");
  { std::lock_guard<std::mutex> lock(mutex_); requested_frame_=std::move(frame);requested_ = true; }
  wake_.notify_one();
}

ScreenTranslator::Frame ScreenTranslator::CaptureFrame() {
  ShowWindow(overlay_,SW_HIDE);ShowWindow(toolbar_,SW_HIDE);DwmFlush();
  try {
    auto frame=CaptureDesktop();ShowWindow(toolbar_,SW_SHOWNOACTIVATE);return frame;
  }catch(...){ShowWindow(toolbar_,SW_SHOWNOACTIVATE);throw;}
}

void ScreenTranslator::PlaceToolbar(const RECT& desktop,const std::vector<RECT>& text) {
  if(toolbar_dragging_||text.empty())return;
  RECT current{};GetWindowRect(toolbar_,&current);
  MONITORINFO monitor{};monitor.cbSize=sizeof(monitor);
  if(!GetMonitorInfo(MonitorFromWindow(toolbar_,MONITOR_DEFAULTTONEAREST),&monitor))return;
  std::vector<RECT> obstacles=text;for(auto& rect:obstacles)OffsetRect(&rect,desktop.left,desktop.top);
  RECT next{};if(!ToolbarPosition(current,monitor.rcWork,obstacles,next)||EqualRect(&current,&next))return;
  SetWindowPos(toolbar_,HWND_TOPMOST,next.left,next.top,0,0,SWP_NOSIZE|SWP_NOACTIVATE);DwmFlush();
  motion_reference_=MotionSample(motion_desktop_);GetWindowRect(toolbar_,&motion_toolbar_);
}

void ScreenTranslator::SetWorking(bool value) {
  animating_ = value;
  if (value) SetTimer(toolbar_, kAnimationTimer, 33, nullptr);
  else KillTimer(toolbar_, kAnimationTimer);
  InvalidateRect(toolbar_, nullptr, FALSE);
}

void ScreenTranslator::DismissTranslation() {
  if (!watch_motion_) return;
  ++generation_; watch_motion_ = false; motion_reference_.clear();
  KillTimer(toolbar_, kMotionTimer); SetWorking(false);
  blocks_.clear(); original_ = true; ShowWindow(overlay_, SW_HIDE);
  Notify(L"Pantalla cambiada · Toca el icono");
}

std::vector<int> ScreenTranslator::MotionSample(RECT& desktop) {
  desktop = {GetSystemMetrics(SM_XVIRTUALSCREEN), GetSystemMetrics(SM_YVIRTUALSCREEN), 0, 0};
  desktop.right = desktop.left + GetSystemMetrics(SM_CXVIRTUALSCREEN);
  desktop.bottom = desktop.top + GetSystemMetrics(SM_CYVIRTUALSCREEN);
  HDC screen = GetDC(nullptr), dc = CreateCompatibleDC(screen);
  BITMAPINFO info{}; info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  info.bmiHeader.biWidth = 96; info.bmiHeader.biHeight = -64; info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32;
  void* data = nullptr; HBITMAP bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &data, nullptr, 0);
  std::vector<int> sample;
  if (bitmap) {
    auto old = SelectObject(dc, bitmap); SetStretchBltMode(dc, HALFTONE);
    if (StretchBlt(dc,0,0,96,64,screen,desktop.left,desktop.top,desktop.right-desktop.left,desktop.bottom-desktop.top,SRCCOPY|CAPTUREBLT)) {
      GdiFlush(); auto pixels = static_cast<uint8_t*>(data); sample.resize(96*64);
      for (int i=0; i<96*64; ++i) sample[i] = (pixels[i*4+2]*77+pixels[i*4+1]*150+pixels[i*4]*29)>>8;
    }
    SelectObject(dc, old); DeleteObject(bitmap);
  }
  DeleteDC(dc); ReleaseDC(nullptr,screen); return sample;
}

void ScreenTranslator::MonitorScreen() {
  if (!active_ || !watch_motion_ || toolbar_dragging_) return;
  RECT bar{}; GetWindowRect(toolbar_, &bar);
  RECT desktop{}; auto sample = MotionSample(desktop);
  if (!EqualRect(&desktop,&motion_desktop_)) { DismissTranslation(); return; }
  if (sample.size() != motion_reference_.size() || sample.empty()) return;
  int valid=0, changed=0;
  for (int i=0;i<96*64;++i) {
    POINT point{desktop.left+(i%96*2+1)*(desktop.right-desktop.left)/192,
      desktop.top+(i/96*2+1)*(desktop.bottom-desktop.top)/128};
    if (i/96<3 || i/96>60 || PtInRect(&bar,point) || PtInRect(&motion_toolbar_,point)) continue;
    POINT local{point.x-desktop.left,point.y-desktop.top}; bool masked=false;
    for (auto& block: blocks_) { RECT rect=block.rect; InflateRect(&rect,12,12); if (PtInRect(&rect,local)) { masked=true; break; } }
    if (masked) continue;
    ++valid; if (std::abs(sample[i]-motion_reference_[i])>28) ++changed;
  }
  if (valid>100 && changed>=std::max(18,static_cast<int>(valid*.025))) DismissTranslation();
}

void ScreenTranslator::Worker() {
  winrt::init_apartment(winrt::apartment_type::multi_threaded);
  std::unique_ptr<luma::LocalTranslationModel> localModel;
  std::unique_ptr<luma::LocalLineRecognizer> letterModel;
  std::unique_ptr<luma::LocalTextDetector> textDetector;
  std::unique_ptr<luma::LocalLineRecognizer> consensusFirst,consensusSecond;
  while (!exiting_) {
    Options options; int generation;std::unique_ptr<Frame> captured;
    {
      std::unique_lock<std::mutex> lock(mutex_);
      wake_.wait(lock, [this] { return exiting_ || requested_; });
      if (exiting_) break;
      requested_ = false; options = options_; generation = generation_;captured=std::move(requested_frame_);
    }
    auto result = std::make_unique<CaptureResult>(); result->generation = generation;
    try {
      if(!captured)throw std::runtime_error("No llego una captura limpia de pantalla.");
      auto& frame=*captured; result->desktop = frame.desktop;
      if(options.source==L"en"&&!letterModel)letterModel=std::make_unique<luma::LocalLineRecognizer>(LocalModelDirectory());
      if(options.source==L"en"&&!textDetector)textDetector=std::make_unique<luma::LocalTextDetector>(LocalModelDirectory());
      auto blocks = Recognize(frame, options.source, options.source==L"en"?letterModel.get():nullptr,
          options.source==L"en"?textDetector.get():nullptr,[&]{return !active_||generation!=generation_||exiting_;});
      if(options.source==L"en") {
        auto first=PackagedReaderDirectory("english-v5"),second=PackagedReaderDirectory("multilingual-v6-small");
        if(!first.empty()&&!second.empty()) {
          if(!consensusFirst)consensusFirst=std::make_unique<luma::LocalLineRecognizer>(first);
          if(!consensusSecond)consensusSecond=std::make_unique<luma::LocalLineRecognizer>(second);
          RecoverReaderConsensus(frame,blocks,*consensusFirst,*consensusSecond,*textDetector,
              [&]{return !active_||generation!=generation_||exiting_;});
        }
      }
      for(const auto& block:blocks)result->text_regions.push_back(block.rect);
      for (auto& block : blocks) {
        if (!active_ || generation != generation_ || exiting_) break;
        auto key = options.provider + L"|" + options.endpoint + L"|" + options.source + L"|" + options.target + L"|" + block.text;
        auto cached = cache_.find(key);
        std::wstring translated;
        if (cached != cache_.end()) translated = cached->second;
        else {
          if (options.provider == L"local") {
            if (!localModel) {
              localModel = std::make_unique<luma::LocalTranslationModel>(LocalModelDirectory());
            }
            translated = Wide(localModel->Translate(Utf8FromUtf16(block.text.c_str()),[&] { return !active_ || generation != generation_ || exiting_; }));
          } else translated = Translate(block.text, options);
          if (cache_.size() >= 600) cache_.clear(); cache_[key] = translated;
        }
        if (translated != block.text && !translated.empty()) {
          bool hasLetter=false,allCaps=true;for(wchar_t c:block.text)if(iswalpha(c)){hasLetter=true;if(!iswupper(c))allCaps=false;}
          if(hasLetter&&allCaps)CharUpperBuffW(translated.data(),static_cast<DWORD>(translated.size()));
          block.text = translated;
          // Color is selected only after recognition and translation. It must
          // never affect line grouping, recovery, or the model's source text.
          RECT sample{static_cast<LONG>(std::floor(block.rect.left*frame.scale)),static_cast<LONG>(std::floor(block.rect.top*frame.scale)),
            static_cast<LONG>(std::ceil(block.rect.right*frame.scale)),static_cast<LONG>(std::ceil(block.rect.bottom*frame.scale))};
          block.background=OverlayBackground(frame.pixels.data(),frame.pixels.size(),frame.width,frame.height,frame.width*4,sample,block.background);
          result->blocks.push_back(std::move(block));
          if (result->blocks.size() % 5 == 0) {
            auto partial = std::make_unique<CaptureResult>(*result); partial->complete = false;
            if (PostMessage(toolbar_, kCompleted, 0, reinterpret_cast<LPARAM>(partial.get()))) partial.release();
          }
        }
      }
    } catch (const winrt::hresult_error& e) { result->error = L"OCR de Windows: " + std::wstring(e.message()); }
    catch (const std::exception& e) { result->error = Wide(e.what()); }
    if (!PostMessage(toolbar_, kCompleted, 0, reinterpret_cast<LPARAM>(result.get()))) busy_ = false;
    else result.release();
  }
  winrt::uninit_apartment();
}

ScreenTranslator::Frame ScreenTranslator::CaptureDesktop() {
  Frame frame{};
  frame.desktop = {GetSystemMetrics(SM_XVIRTUALSCREEN), GetSystemMetrics(SM_YVIRTUALSCREEN), 0, 0};
  int width = GetSystemMetrics(SM_CXVIRTUALSCREEN), height = GetSystemMetrics(SM_CYVIRTUALSCREEN);
  frame.desktop.right = frame.desktop.left + width; frame.desktop.bottom = frame.desktop.top + height;
  if (width <= 0 || height <= 0) throw std::runtime_error("No se encontro una pantalla para capturar.");
  auto max = static_cast<int>(winrt::Windows::Media::Ocr::OcrEngine::MaxImageDimension());
  frame.scale = std::min(1.0, static_cast<double>(max) / std::max(width, height));
  frame.width = static_cast<int>(width * frame.scale); frame.height = static_cast<int>(height * frame.scale);
  HDC screen = GetDC(nullptr), dc = CreateCompatibleDC(screen);
  BITMAPINFO info{}; info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER); info.bmiHeader.biWidth = frame.width;
  info.bmiHeader.biHeight = -frame.height; info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32; info.bmiHeader.biCompression = BI_RGB;
  void* pixels = nullptr;
  HBITMAP bitmap = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &pixels, nullptr, 0);
  if (!bitmap) { DeleteDC(dc); ReleaseDC(nullptr, screen); throw std::runtime_error("No se pudo reservar la captura de pantalla."); }
  auto old = SelectObject(dc, bitmap); SetStretchBltMode(dc, HALFTONE);
  BOOL captured = StretchBlt(dc, 0, 0, frame.width, frame.height, screen, frame.desktop.left, frame.desktop.top, width, height, SRCCOPY | CAPTUREBLT);
  GdiFlush();
  if (captured) frame.pixels.assign(static_cast<uint8_t*>(pixels), static_cast<uint8_t*>(pixels) + static_cast<size_t>(frame.width)*frame.height*4);
  SelectObject(dc, old); DeleteObject(bitmap); DeleteDC(dc); ReleaseDC(nullptr, screen);
  if (!captured) throw std::runtime_error("Windows no permitio capturar esta pantalla.");
  return frame;
}

std::vector<ScreenTranslator::Block> ScreenTranslator::Recognize(const Frame& frame, const std::wstring& source, luma::LocalLineRecognizer* letters,
    luma::LocalTextDetector* detector,const std::function<bool()>& cancelled,bool recover_paragraphs,bool complete_lines,bool recover_short_dialogue) {
  using namespace winrt::Windows;
  auto engine = Media::Ocr::OcrEngine::TryCreateFromLanguage(Globalization::Language(source));
  if (!engine) throw std::runtime_error("Instala el reconocimiento de texto del idioma de origen en Configuracion > Hora e idioma de Windows.");
  Storage::Streams::DataWriter writer;
  writer.WriteBytes(winrt::array_view<const uint8_t>(frame.pixels));
  auto bitmap = Graphics::Imaging::SoftwareBitmap::CreateCopyFromBuffer(writer.DetachBuffer(), Graphics::Imaging::BitmapPixelFormat::Bgra8, frame.width, frame.height, Graphics::Imaging::BitmapAlphaMode::Ignore);
  auto recognized = engine.RecognizeAsync(bitmap).get();
  // Windows reports word boxes in its deskewed coordinate system. Map them
  // back around the image centre before cropping pixels or placing overlays.
  double angle=recognized.TextAngle()?recognized.TextAngle().Value()*3.141592653589793/180:0;
  auto imageQuad=[&](const RECT& rect) {
    std::array<float,8> q{};std::array<std::pair<double,double>,4> points{{{rect.left,rect.top},{rect.right,rect.top},{rect.right,rect.bottom},{rect.left,rect.bottom}}};
    for(size_t i=0;i<4;++i){double x=points[i].first-frame.width*.5,y=points[i].second-frame.height*.5;
      q[i*2]=static_cast<float>(std::clamp(x*std::cos(angle)-y*std::sin(angle)+frame.width*.5,0.0,static_cast<double>(frame.width-1)));
      q[i*2+1]=static_cast<float>(std::clamp(x*std::sin(angle)+y*std::cos(angle)+frame.height*.5,0.0,static_cast<double>(frame.height-1)));}
    return q;
  };
  auto imageRect=[&](const RECT& rect) {auto q=imageQuad(rect);RECT box{LONG_MAX,LONG_MAX,0,0};for(int i=0;i<4;++i){
    box.left=std::min(box.left,static_cast<LONG>(std::floor(q[i*2]/frame.scale)));box.top=std::min(box.top,static_cast<LONG>(std::floor(q[i*2+1]/frame.scale)));
    box.right=std::max(box.right,static_cast<LONG>(std::ceil(q[i*2]/frame.scale)));box.bottom=std::max(box.bottom,static_cast<LONG>(std::ceil(q[i*2+1]/frame.scale)));}return box;};
  std::vector<Block> lines;
  for (const auto& line : recognized.Lines()) {
    if(cancelled&&cancelled())return {};
    std::wstring text(line.Text());
    if (text.empty() || !std::any_of(text.begin(), text.end(), [](wchar_t c) { return iswalpha(c) != 0; })) continue;
    RECT rect{LONG_MAX, LONG_MAX, 0, 0};
    std::vector<std::pair<RECT,std::wstring>> words;
    for (const auto& word : line.Words()) {
      auto r = word.BoundingRect();
      RECT wordRect{static_cast<LONG>(r.X),static_cast<LONG>(r.Y),static_cast<LONG>(std::ceil(r.X+r.Width)),static_cast<LONG>(std::ceil(r.Y+r.Height))};
      words.push_back({imageRect(wordRect),std::wstring(word.Text())});
      rect.left = std::min(rect.left, static_cast<LONG>(r.X)); rect.top = std::min(rect.top, static_cast<LONG>(r.Y));
      rect.right = std::max(rect.right, static_cast<LONG>(std::ceil(r.X + r.Width))); rect.bottom = std::max(rect.bottom, static_cast<LONG>(std::ceil(r.Y + r.Height)));
    }
    if (rect.left == LONG_MAX || rect.bottom <= rect.top) continue;
    auto raw=text;
    auto mapped=imageRect(rect);
    COLORREF bg = Sample(frame.pixels, frame.width, frame.height, static_cast<int>(mapped.left*frame.scale)-2,static_cast<int>(mapped.top*frame.scale)-2);
    if(letters) {
      LONG height=rect.bottom-rect.top;
      RECT expanded{std::max<LONG>(0,rect.left-height*3/2),std::max<LONG>(0,rect.top-3),std::min<LONG>(frame.width,rect.right+height*3/2),std::min<LONG>(frame.height,rect.bottom+3)};
      auto hint=Utf8FromUtf16(text.c_str());
      auto recognizedLine=std::abs(angle)>.001?letters->ReadQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,imageQuad(expanded),hint):
          letters->ReadWithHint(frame.pixels.data(),frame.width,frame.height,frame.width*4,expanded.left,expanded.top,expanded.right,expanded.bottom,hint);
      if((recognizedLine.confidence>=.85f||(recognizedLine.system_agreement&&recognizedLine.confidence>=.75f))&&recognizedLine.text.size()>=hint.size()*.65&&recognizedLine.text.size()<=hint.size()*2.5+8) {
        text=Wide(recognizedLine.text);
        int upper=0,count=0;for(wchar_t c:raw)if(iswalpha(c)){++count;if(iswupper(c))++upper;}
        if(count>=3&&upper>=count*.75)CharUpperBuffW(text.data(),static_cast<DWORD>(text.size()));
        if(std::abs(angle)<=.001){rect.left=recognizedLine.left;rect.right=recognizedLine.right;}
      }
    }
    rect=imageRect(rect);
    lines.push_back({rect,text,bg,false,raw,std::move(words)});
  }
  if(detector&&letters)for(const auto& box:detector->Detect(frame.pixels.data(),frame.width,frame.height,frame.width*4,cancelled)) {
    if(cancelled&&cancelled())return {};
    RECT rect{LONG_MAX,LONG_MAX,0,0};
    for(int i=0;i<4;++i){rect.left=std::min(rect.left,static_cast<LONG>(std::floor(box.corners[i*2]/frame.scale)));
      rect.top=std::min(rect.top,static_cast<LONG>(std::floor(box.corners[i*2+1]/frame.scale)));
      rect.right=std::max(rect.right,static_cast<LONG>(std::ceil(box.corners[i*2]/frame.scale)));
      rect.bottom=std::max(rect.bottom,static_cast<LONG>(std::ceil(box.corners[i*2+1]/frame.scale)));}
    if(rect.right<=rect.left||rect.bottom<=rect.top)continue;
    std::vector<size_t> covered;
    for(size_t index=0;index<lines.size();++index){const auto& old=lines[index];RECT overlap;if(IntersectRect(&overlap,&old.rect,&rect)&&
        static_cast<double>((overlap.right-overlap.left)*(overlap.bottom-overlap.top))>.5*std::min(
          (old.rect.right-old.rect.left)*(old.rect.bottom-old.rect.top),(rect.right-rect.left)*(rect.bottom-rect.top)))covered.push_back(index);}
    if(!covered.empty()) {
      // A small Windows fragment does not cover an entire detector line.
      // Replace only a contained, same-baseline fragment independently read
      // by both bundled recognizers; preserve its native evidence for audits.
      if(complete_lines&&source==L"en"&&covered.size()==1) {
        auto& old=lines[covered.front()];const auto& r=old.rect;
        double oldArea=static_cast<double>(r.right-r.left)*(r.bottom-r.top);
        double newArea=static_cast<double>(rect.right-rect.left)*(rect.bottom-rect.top);
        int height=std::min(r.bottom-r.top,rect.bottom-rect.top);RECT intersection{};
        RECT evidence=r;
        if(!old.words.empty()) {
          evidence=old.words.front().first;
          for(const auto& word:old.words)UnionRect(&evidence,&evidence,&word.first);
        }
        // Local rereading can expand a clipped system box into the balloon
        // border. Containment must use the original system word coordinates.
        double evidenceArea=static_cast<double>(evidence.right-evidence.left)*(evidence.bottom-evidence.top);
        bool contained=IntersectRect(&intersection,&evidence,&rect)&&
            static_cast<double>((intersection.right-intersection.left)*(intersection.bottom-intersection.top))>=evidenceArea*.85;
        if(height>0&&contained&&newArea>=oldArea*1.25&&newArea<=oldArea*4&&
            std::max(r.bottom-r.top,rect.bottom-rect.top)<=height*1.5&&
            std::abs((r.top+r.bottom-rect.top-rect.bottom)*.5)<=height*.35) {
          auto primary=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,box.corners,false);
          if(primary.confidence>=.90f) {
            auto secondary=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,box.corners,true);
            const auto& vocabulary=RecoveryWords();
            luma::recovery::Vocabulary known=[&](const std::string& word){return vocabulary.count(word)!=0;};
            if(secondary.confidence>=.90f&&luma::recovery::CompleteLine(Utf8FromUtf16(old.text.c_str()),primary.text,secondary.text,known)) {
              old.text=Wide(primary.text);UnionRect(&old.rect,&old.rect,&rect);old.line_completed=true;
            }
          }
        }
      }
      continue;
    }
    auto read=letters->ReadQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,box.corners);
    auto text=Wide(read.text);int alphabetic=0;for(auto c:text)if(iswalpha(c))++alphabetic;
    bool shortRecovered=false;
    if(recover_short_dialogue&&source==L"en"&&alphabetic<2&&box.confidence>=.90f) {
      // A principal-axis crop can rotate a short serif glyph away from its
      // actual baseline. Require corroboration in upright crops, without
      // touching any existing line or accepting bare strokes from the art.
      float left=box.corners[0],right=left,top=box.corners[1],bottom=top;
      for(size_t i=0;i<8;i+=2){left=std::min(left,box.corners[i]);right=std::max(right,box.corners[i]);top=std::min(top,box.corners[i+1]);bottom=std::max(bottom,box.corners[i+1]);}
      float paddedRight=std::min(static_cast<float>(frame.width-1),right+(bottom-top)*.25f);
      RECT expanded=rect;expanded.right=static_cast<LONG>(std::ceil(paddedRight/frame.scale));
      bool touchesExisting=false;for(const auto& old:lines){RECT overlap{};if(IntersectRect(&overlap,&expanded,&old.rect)){touchesExisting=true;break;}}
      if(!touchesExisting) {
        std::array<float,8> upright{left,top,right,top,right,bottom,left,bottom};
        std::array<float,8> padded{left,top,paddedRight,top,paddedRight,bottom,left,bottom};
        auto a=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,upright,false);
        auto b=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,upright,true);
        auto c=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,padded,false);
        auto d=letters->ReadFamilyQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,padded,true);
        std::array<luma::short_dialogue_candidate::Reading,4> evidence{{{a.text,a.confidence},{b.text,b.confidence},{c.text,c.confidence},{d.text,d.confidence}}};
        if(luma::short_dialogue_candidate::SupportedPronoun(evidence,box.confidence)) {
          read=c;text=Wide(c.text);rect=expanded;shortRecovered=true;
        }
      }
    }
    if(read.confidence<.87f||(alphabetic<2&&!shortRecovered))continue;
    auto background=Sample(frame.pixels,frame.width,frame.height,static_cast<int>(rect.left*frame.scale)-2,static_cast<int>(rect.top*frame.scale)-2);
    lines.push_back({rect,text,background,false,text,{},true});
    lines.back().short_dialogue_recovered=shortRecovered;
  }
  // Correct original groups before changing paragraph geometry. A larger
  // paragraph crop can otherwise discard a previously corroborated reading.
  auto blocks=MergeTextLines(lines,false);
  if(recover_paragraphs&&source==L"en"&&letters&&detector)RecoverParagraphs(frame,blocks,*letters,*detector,cancelled);
  if(cancelled&&cancelled())return {};
  return PreserveGroupReadings(blocks,MergeTextLines(std::move(lines)));
}

void ScreenTranslator::RecoverReaderConsensus(const Frame& frame,std::vector<Block>& blocks,
    luma::LocalLineRecognizer& first,luma::LocalLineRecognizer& second,luma::LocalTextDetector& detector,
    const std::function<bool()>& cancelled) {
  struct Evidence {std::string text;float left,top,height;};
  std::vector<std::vector<Evidence>> a(blocks.size()),b(blocks.size());
  auto area=[](const RECT& r){return static_cast<double>(std::max<LONG>(0,r.right-r.left))*std::max<LONG>(0,r.bottom-r.top);};
  for(const auto& box:detector.Detect(frame.pixels.data(),frame.width,frame.height,frame.width*4,cancelled)) {
    if(cancelled&&cancelled())return;
    float left=box.corners[0],right=left,top=box.corners[1],bottom=top;
    for(size_t i=0;i<8;i+=2){left=std::min(left,box.corners[i]);right=std::max(right,box.corners[i]);top=std::min(top,box.corners[i+1]);bottom=std::max(bottom,box.corners[i+1]);}
    RECT rect{static_cast<LONG>(std::floor(left)),static_cast<LONG>(std::floor(top)),static_cast<LONG>(std::ceil(right)),static_cast<LONG>(std::ceil(bottom))};
    if(area(rect)<=0)continue;int owner=-1;
    for(size_t i=0;i<blocks.size();++i) {
      const auto& r=blocks[i].rect;RECT group{static_cast<LONG>(std::floor(r.left*frame.scale)),static_cast<LONG>(std::floor(r.top*frame.scale)),
        static_cast<LONG>(std::ceil(r.right*frame.scale)),static_cast<LONG>(std::ceil(r.bottom*frame.scale))};
      InflateRect(&group,3,3);RECT overlap{};
      if(IntersectRect(&overlap,&group,&rect)&&area(overlap)>=.90*area(rect)) {
        if(owner>=0){owner=-2;break;}owner=static_cast<int>(i);
      }
    }
    // Ambiguous/straddling detections cannot mix separate balloons. This
    // experiment changes only text supported inside one existing block.
    if(owner<0)continue;
    auto one=first.ReadQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,box.corners);
    auto two=second.ReadQuad(frame.pixels.data(),frame.width,frame.height,frame.width*4,box.corners);
    if(one.confidence>=.8f)a[owner].push_back({one.text,left,top,std::max(1.f,bottom-top)});
    if(two.confidence>=.8f)b[owner].push_back({two.text,left,top,std::max(1.f,bottom-top)});
  }
  auto join=[](std::vector<Evidence> lines) {
    std::stable_sort(lines.begin(),lines.end(),[](const auto& x,const auto& y){return x.top<y.top;});
    struct Row {float top,height;std::vector<Evidence> lines;};std::vector<Row> rows;
    for(auto& line:lines) {
      auto match=std::find_if(rows.begin(),rows.end(),[&](const auto& row){return std::abs(row.top-line.top)<.35*std::max(row.height,line.height);});
      if(match==rows.end())rows.push_back({line.top,line.height,{line}});else match->lines.push_back(line);
    }
    std::string result;
    for(auto& row:rows) {
      std::stable_sort(row.lines.begin(),row.lines.end(),[](const auto& x,const auto& y){return x.left<y.left;});
      for(auto& line:row.lines){if(!result.empty())result+=' ';result+=line.text;}
    }
    return result;
  };
  const auto& vocabulary=RecoveryWords();luma::recovery::Vocabulary known=[&](const std::string& word){return vocabulary.count(word)!=0;};
  for(size_t i=0;i<blocks.size();++i) {
    auto& block=blocks[i];auto base=Utf8FromUtf16(block.text.c_str()),one=join(a[i]),two=join(b[i]);
    auto selected=luma::morph_edit_candidate::Select(base,one,two,known);
    block.before_consensus=block.text;block.first_reader=Wide(one);block.second_reader=Wide(two);
    if(selected.text!=base){block.text=Wide(selected.text);block.consensus_recovered=true;}
  }
}

void ScreenTranslator::RecoverParagraphs(const Frame& frame,std::vector<Block>& blocks,luma::LocalLineRecognizer& reader,
    luma::LocalTextDetector& detector,const std::function<bool()>& cancelled) {
  const auto& vocabulary=RecoveryWords();
  luma::recovery::Vocabulary known=[&](const std::string& word){return vocabulary.count(word)!=0;};
  auto area=[](const RECT& box){return static_cast<double>(std::max<LONG>(0,box.right-box.left))*std::max<LONG>(0,box.bottom-box.top);};
  struct Paragraph {std::string text,support;RECT bounds{};bool valid=false;};
  for(auto& block:blocks) {
    if(cancelled&&cancelled())return;
    auto original=Utf8FromUtf16(block.text.c_str());auto tokens=luma::recovery::Words(original);
    if(tokens.size()<3||tokens.size()>150)continue;
    std::string native;
    for(const auto& word:block.words){if(!native.empty())native+=' ';native+=Utf8FromUtf16(word.second.c_str());}
    bool allKnown=std::all_of(tokens.begin(),tokens.end(),[&](const std::string& word){return luma::recovery::Known(word,known);});
    if(allKnown&&luma::recovery::Key(original)==luma::recovery::Key(native))continue;
    RECT target{static_cast<LONG>(std::floor(block.rect.left*frame.scale)),static_cast<LONG>(std::floor(block.rect.top*frame.scale)),
      static_cast<LONG>(std::ceil(block.rect.right*frame.scale)),static_cast<LONG>(std::ceil(block.rect.bottom*frame.scale))};
    auto reread=[&](int padX,int padY) {
      Paragraph result;
      RECT crop{std::max<LONG>(0,target.left-padX),std::max<LONG>(0,target.top-padY),
        std::min<LONG>(frame.width,target.right+padX),std::min<LONG>(frame.height,target.bottom+padY)};
      int width=crop.right-crop.left,height=crop.bottom-crop.top;
      if(width<2||height<2||width>4096||height>4096)return result;
      std::vector<uint8_t> pixels(static_cast<size_t>(width)*height*4);
      for(int y=0;y<height;++y)std::copy_n(frame.pixels.data()+(static_cast<size_t>(y+crop.top)*frame.width+crop.left)*4,
        static_cast<size_t>(width)*4,pixels.data()+static_cast<size_t>(y)*width*4);
      struct Part {double left,top,bottom,height;luma::recovery::Ensemble value;};
      std::vector<Part> parts;RECT total{LONG_MAX,LONG_MAX,0,0};
      for(const auto& detected:detector.Detect(pixels.data(),width,height,width*4,cancelled)) {
        if(cancelled&&cancelled())return result;
        double left=detected.corners[0],right=left,top=detected.corners[1],bottom=top;
        for(int i=1;i<4;++i){left=std::min(left,static_cast<double>(detected.corners[i*2]));right=std::max(right,static_cast<double>(detected.corners[i*2]));
          top=std::min(top,static_cast<double>(detected.corners[i*2+1]));bottom=std::max(bottom,static_cast<double>(detected.corners[i*2+1]));}
        double gx=left+crop.left,gy=top+crop.top,gr=right+crop.left,gb=bottom+crop.top;
        double intersection=std::max(0.0,std::min<double>(gr,target.right)-std::max<double>(gx,target.left))*
          std::max(0.0,std::min<double>(gb,target.bottom)-std::max<double>(gy,target.top));
        if(intersection<=.5*std::min(area(target),std::max(0.0,right-left)*std::max(0.0,bottom-top)))continue;
        auto primary=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,detected.corners,false);
        if(primary.confidence<.65f)continue;
        auto alternate=reader.ReadFamilyQuad(pixels.data(),width,height,width*4,detected.corners,true);
        auto combined=luma::recovery::Combine(primary.text,alternate.text,alternate.confidence,known);
        if(combined.text.empty())continue;
        parts.push_back({left,top,bottom,bottom-top,std::move(combined)});
        total.left=std::min(total.left,static_cast<LONG>(std::floor(gx)));total.top=std::min(total.top,static_cast<LONG>(std::floor(gy)));
        total.right=std::max(total.right,static_cast<LONG>(std::ceil(gr)));total.bottom=std::max(total.bottom,static_cast<LONG>(std::ceil(gb)));
      }
      if(parts.empty()||area(total)<area(target)*.5||area(total)>area(target)*1.8)return result;
      std::stable_sort(parts.begin(),parts.end(),[](const Part& a,const Part& b){return a.top<b.top;});
      struct Row {double top,bottom,height;std::vector<std::pair<double,luma::recovery::Ensemble>> parts;};
      std::vector<Row> rows;
      for(auto& part:parts) {
        auto found=std::find_if(rows.begin(),rows.end(),[&](const Row& row){return std::min(row.bottom,part.bottom)-std::max(row.top,part.top)>.6*std::min(row.height,part.height);});
        if(found==rows.end()){rows.push_back({part.top,part.bottom,part.height,{}});found=rows.end()-1;}
        found->parts.push_back({part.left,std::move(part.value)});
      }
      for(auto& row:rows) {
        std::stable_sort(row.parts.begin(),row.parts.end(),[](const auto& a,const auto& b){return a.first<b.first;});
        for(const auto& part:row.parts){if(!result.text.empty()){result.text+=' ';result.support+=' ';}result.text+=part.second.text;result.support+=part.second.support;}
      }
      result.bounds=total;result.valid=true;return result;
    };
    auto closeReading=reread(30,24);if(!closeReading.valid)continue;
    // The wide read can only add a second agreement requirement. Rejecting
    // the same proposal against its own support is therefore a necessary
    // precondition and avoids a second detector pass that cannot be accepted.
    if(!luma::recovery::Accept(original,native,closeReading.text,closeReading.support,closeReading.text,closeReading.support,known))continue;
    auto context=reread(80,80);if(!context.valid)continue;
    if(!luma::recovery::Accept(original,native,closeReading.text,closeReading.support,context.text,context.support,known))continue;
    block.text=Wide(closeReading.text);
    int uppercase=0,letters=0;for(wchar_t c:Wide(original))if(iswalpha(c)){++letters;if(iswupper(c))++uppercase;}
    if(letters>=3&&uppercase>=letters*.75)CharUpperBuffW(block.text.data(),static_cast<DWORD>(block.text.size()));
    RECT updated{static_cast<LONG>(std::floor(closeReading.bounds.left/frame.scale)),static_cast<LONG>(std::floor(closeReading.bounds.top/frame.scale)),
      static_cast<LONG>(std::ceil(closeReading.bounds.right/frame.scale)),static_cast<LONG>(std::ceil(closeReading.bounds.bottom/frame.scale))};
    UnionRect(&block.rect,&block.rect,&updated);block.paragraph_recovered=true;
  }
}

std::vector<ScreenTranslator::Block> ScreenTranslator::PreserveGroupReadings(const std::vector<Block>& baseline,std::vector<Block> proposed) {
  size_t cursor=0;
  for(auto& group:proposed) {
    auto expected=luma::recovery::Key(Utf8FromUtf16(group.raw_text.c_str()));
    if(expected.empty())return baseline;
    std::string actual;std::wstring text,raw;std::vector<std::pair<RECT,std::wstring>> words;
    bool recovered=false,completed=false,additional=false,shortRecovered=false;
    while(cursor<baseline.size()&&actual.size()<expected.size()) {
      const auto& original=baseline[cursor++];
      actual+=luma::recovery::Key(Utf8FromUtf16(original.raw_text.c_str()));
      if(!text.empty())text+=L" ";text+=original.text;
      if(!raw.empty())raw+=L" ";raw+=original.raw_text;
      words.insert(words.end(),original.words.begin(),original.words.end());
      recovered|=original.paragraph_recovered;completed|=original.line_completed;
      shortRecovered|=original.short_dialogue_recovered;
      additional|=original.additional_detection;UnionRect(&group.rect,&group.rect,&original.rect);
    }
    // A proposed grouping may only join complete, ordered original groups.
    // Ambiguous partitions retain the baseline, including all its words.
    if(actual!=expected)return baseline;
    group.text=std::move(text);group.raw_text=std::move(raw);group.words=std::move(words);
    group.paragraph_recovered=recovered;group.line_completed=completed;group.additional_detection=additional;
    group.short_dialogue_recovered=shortRecovered;
  }
  return cursor==baseline.size()?proposed:baseline;
}

std::vector<ScreenTranslator::Block> ScreenTranslator::MergeTextLines(std::vector<Block> lines,bool allow_row_overlap) {
  auto order=[](const Block& a,const Block& b){return a.rect.top==b.rect.top?a.rect.left<b.rect.left:a.rect.top<b.rect.top;};
  std::stable_sort(lines.begin(),lines.end(),order);
  // Same-baseline fragments must be in reading order before paragraphs merge.
  // Geometry only: this does not consult expected dialogue or translations.
  for(size_t i=0;i<lines.size();++i) {
    for(size_t j=i+1;j<lines.size();) {
      const auto& a=lines[i].rect;const auto& b=lines[j].rect;
      int ah=a.bottom-a.top,bh=b.bottom-b.top,height=std::min(ah,bh);
      int overlap=std::min(a.bottom,b.bottom)-std::max(a.top,b.top);
      int gap=std::max(a.left,b.left)-std::min(a.right,b.right);
      int colorDifference=std::abs(GetRValue(lines[i].background)-GetRValue(lines[j].background))+
          std::abs(GetGValue(lines[i].background)-GetGValue(lines[j].background))+
          std::abs(GetBValue(lines[i].background)-GetBValue(lines[j].background));
      if(height<=0 || std::max(ah,bh)>height*1.6 || overlap<height*.6 ||
          std::abs((a.top+a.bottom-b.top-b.bottom)*.5)>height*.4 || gap<0 || gap>height*.65 ||
          colorDifference>=60 || lines[i].text.size()+lines[j].text.size()>=1500) {++j;continue;}
      Block left=std::move(lines[i]),right=std::move(lines[j]);
      if(left.rect.left>right.rect.left)std::swap(left,right);
      left.text+=L" "+right.text;left.raw_text+=L" "+right.raw_text;
      UnionRect(&left.rect,&left.rect,&right.rect);
      left.words.insert(left.words.end(),right.words.begin(),right.words.end());
      left.additional_detection|=right.additional_detection;
      left.line_completed|=right.line_completed;
      left.short_dialogue_recovered|=right.short_dialogue_recovered;
      lines[i]=std::move(left);lines.erase(lines.begin()+j);j=i+1;
    }
  }
  std::stable_sort(lines.begin(),lines.end(),order);
  std::vector<Block> blocks;int previousLineHeight=0;
  for(auto& line:lines) {
    auto rect=line.rect;const auto& text=line.text;const auto& raw=line.raw_text;auto bg=line.background;
    int height = rect.bottom-rect.top;
    bool joined = false;
    if (!blocks.empty()) {
      auto& previous=blocks.back(); int gap=rect.top-previous.rect.bottom;
      int width=rect.right-rect.left, previousWidth=previous.rect.right-previous.rect.left;
      int overlap=std::min(rect.right,previous.rect.right)-std::max(rect.left,previous.rect.left);
      bool centered=std::abs((rect.left+rect.right)-(previous.rect.left+previous.rect.right))<std::max(width,previousWidth)*.20;
      bool leftAligned=std::abs(rect.left-previous.rect.left)<height*.45;
      int colorDifference=std::abs(GetRValue(bg)-GetRValue(previous.background))+std::abs(GetGValue(bg)-GetGValue(previous.background))+std::abs(GetBValue(bg)-GetBValue(previous.background));
      // Italic glyphs and detector padding can overlap between adjacent text
      // rows. A small overlap is still a vertical continuation; same-baseline
      // boxes overlap much more and remain separate. Use the preceding row's
      // height, not the growing paragraph height, at every display scale.
      if (gap>=(allow_row_overlap?-std::min(height,previousLineHeight)*.35:0) && gap<height*.7 && height>previousLineHeight*.65 && height<previousLineHeight*1.55 &&
          overlap>std::min(width,previousWidth)*.55 && (centered||leftAligned) && colorDifference<60 && previous.text.size()+text.size()<1500) {
        previous.text+=L" "+text;previous.raw_text+=L" "+raw; UnionRect(&previous.rect,&previous.rect,&rect);
        previous.words.insert(previous.words.end(),line.words.begin(),line.words.end());previous.additional_detection|=line.additional_detection;
        previous.line_completed|=line.line_completed;
        previous.short_dialogue_recovered|=line.short_dialogue_recovered;
        previous.centered=centered&&!leftAligned; joined=true;
      }
    }
    if (!joined) blocks.push_back(std::move(line));
    previousLineHeight=height;
    if (blocks.size() >= 120) break;
  }
  return blocks;
}

int ScreenTranslator::LayoutTest(const std::string& output) {
  using namespace winrt::Windows::Data::Json;
  JsonObject result;bool passed=true;JsonArray cases;
  auto check=[&](const wchar_t* name,std::vector<Block> input,size_t expected,const std::wstring& text=L"") {
    auto actual=MergeTextLines(std::move(input));
    bool ok=actual.size()==expected&&(text.empty()||(!actual.empty()&&actual.front().text==text));
    JsonObject row;row.Insert(L"case",JsonValue::CreateStringValue(name));row.Insert(L"passed",JsonValue::CreateBooleanValue(ok));
    row.Insert(L"regions",JsonValue::CreateNumberValue(static_cast<double>(actual.size())));
    JsonArray texts;for(const auto& block:actual)texts.Append(JsonValue::CreateStringValue(block.text));row.Insert(L"texts",texts);
    cases.Append(row);passed&=ok;
  };
  for(int scale:{1,2,3}) {
    auto block=[&](RECT box,const wchar_t* text){box.left*=scale;box.top*=scale;box.right*=scale;box.bottom*=scale;
      return Block{box,text,RGB(255,255,255),false,text,{},true};};
    check(L"skewed_same_baseline_and_balloon",{
      block({416,3174,591,3236},L"THEN"),block({582,3244,713,3310},L"ME."),block({295,3248,577,3305},L"FOLLOW")},1,L"THEN FOLLOW ME.");
    check(L"separate_columns",{block({0,0,80,30},L"LEFT"),block({120,0,200,30},L"RIGHT")},2);
    check(L"overlapping_detection",{block({0,0,100,30},L"SAME"),block({50,0,150,30},L"SAME")},2);
    check(L"different_font_sizes",{block({0,0,100,60},L"LARGE"),block({105,20,140,40},L"small")},2);
    check(L"separate_balloons",{block({0,0,100,30},L"FIRST."),block({0,100,100,130},L"SECOND.")},2);
    check(L"italic_rows_with_overlapping_padding",{
      block({45,10,180,55},L"WE WILL"),block({10,49,215,98},L"WAIT FOR YOU"),block({55,91,175,138},L"RIGHT HERE.")},1,L"WE WILL WAIT FOR YOU RIGHT HERE.");
    check(L"italic_padding_at_one_third_row_height",{
      block({30,10,260,90},L"WE WILL"),block({10,64,280,144},L"WAIT FOR YOU"),block({45,118,245,198},L"RIGHT HERE.")},1,L"WE WILL WAIT FOR YOU RIGHT HERE.");
    check(L"same_baseline_overlaps_are_not_paragraph_rows",{
      block({0,0,100,40},L"LEFT"),block({45,4,145,44},L"RIGHT")},2);
    check(L"large_vertical_overlap_is_not_a_new_row",{
      block({0,0,150,60},L"FIRST"),block({0,20,150,80},L"SECOND")},2);
  }
  auto preservedCheck=[&](const wchar_t* name,std::vector<Block> baseline,std::vector<Block> proposal,const std::vector<std::wstring>& expected,bool recovered) {
    auto actual=PreserveGroupReadings(baseline,std::move(proposal));bool ok=actual.size()==expected.size();
    for(size_t i=0;ok&&i<actual.size();++i)ok=actual[i].text==expected[i];
    if(recovered)ok=ok&&!actual.empty()&&actual.front().paragraph_recovered;
    JsonObject row;row.Insert(L"case",JsonValue::CreateStringValue(name));row.Insert(L"passed",JsonValue::CreateBooleanValue(ok));
    cases.Append(row);passed&=ok;
  };
  Block corrected{{0,0,120,40},L"WE MUST",RGB(255,255,255),false,L"WE MLST"};corrected.paragraph_recovered=true;
  Block continuation{{0,35,120,75},L"LEAVE NOW.",RGB(255,255,255),false,L"LEAVE NOW."};
  Block joined{{0,0,120,75},L"WE MLST LEAVE NOW.",RGB(255,255,255),false,L"WE MLST LEAVE NOW."};
  preservedCheck(L"grouping_preserves_corroborated_reading",{corrected,continuation},{joined},{L"WE MUST LEAVE NOW."},true);
  auto unrelated=joined;unrelated.raw_text=L"DIFFERENT WORDS";
  preservedCheck(L"ambiguous_grouping_keeps_all_original_words",{corrected,continuation},{unrelated},{L"WE MUST",L"LEAVE NOW."},true);
  preservedCheck(L"missing_proposed_group_keeps_originals",{corrected,continuation},{corrected},{L"WE MUST",L"LEAVE NOW."},true);
  preservedCheck(L"duplicate_proposal_cannot_duplicate_words",{corrected,continuation},{joined,joined},{L"WE MUST",L"LEAVE NOW."},true);
  for(int scale:{1,2,3}) {
    auto box=[&](RECT r){r.left*=scale;r.right*=scale;r.top*=scale;r.bottom*=scale;return Block{r,L"TEXT",RGB(255,255,255)};};
    auto paintCheck=[&](const wchar_t* name,const std::vector<Block>& input,bool shouldSeparate) {
      auto rects=PaintTextRects(input);RECT intersection{};
      bool ok=rects.size()==input.size()&&(!shouldSeparate||!IntersectRect(&intersection,&rects[0],&rects[1]));
      for(const auto& r:rects)ok&=r.bottom>r.top&&r.right>r.left;
      JsonObject row;row.Insert(L"case",JsonValue::CreateStringValue(name));row.Insert(L"passed",JsonValue::CreateBooleanValue(ok));
      cases.Append(row);passed&=ok;
    };
    paintCheck(L"adjacent_padded_text_does_not_overlap",{box({10,10,270,140}),box({15,118,265,200})},true);
    auto columns=std::vector<Block>{box({10,10,110,70}),box({140,10,240,70})};
    auto unchanged=PaintTextRects(columns);RECT original=columns[0].rect;InflateRect(&original,3,2);
    bool ok=EqualRect(&unchanged[0],&original)!=0;
    JsonObject row;row.Insert(L"case",JsonValue::CreateStringValue(L"paint_separate_columns_keep_their_space"));
    row.Insert(L"passed",JsonValue::CreateBooleanValue(ok));cases.Append(row);passed&=ok;
  }
  try {
    luma::LocalTranslationModel model(LocalModelDirectory());auto translated=model.TranslateDetailed("THEN FOLLOW ME.");
    result.Insert(L"source",JsonValue::CreateStringValue(L"THEN FOLLOW ME."));
    result.Insert(L"prepared",JsonValue::CreateStringValue(Wide(translated.prepared)));
    result.Insert(L"translation",JsonValue::CreateStringValue(Wide(translated.text)));
    passed&=!translated.text.empty()&&!translated.retained_original;
  }catch(const std::exception& error){passed=false;result.Insert(L"error",JsonValue::CreateStringValue(Wide(error.what())));}
  result.Insert(L"cases",cases);result.Insert(L"success",JsonValue::CreateBooleanValue(passed));
  std::ofstream file(output);file<<winrt::to_string(result.Stringify());return passed?0:1;
}

int ScreenTranslator::RecoveryTest(const std::string& output) {
  nlohmann::json results=nlohmann::json::array();bool success=true;
  const auto& vocabulary=RecoveryWords();luma::recovery::Vocabulary known=[&](const std::string& word){return vocabulary.count(word)!=0;};
  auto check=[&](const char* name,const std::string& old,const std::string& oldNative,const std::string& closeText,const std::string& support,
      const std::string& context,const std::string& contextSupport,bool expected) {
    bool actual=luma::recovery::Accept(old,oldNative,closeText,support,context,contextSupport,known);
    bool passed=actual==expected;success&=passed;results.push_back({{"case",name},{"passed",passed},{"accepted",actual}});
  };
  check("corrupt_embedded_glyph","THE DOOR IS BR0KEN","THE DOOR IS BR0KEN","THE DOOR IS BROKEN","THE DOOR IS BROKEN","THE DOOR IS BROKEN","THE DOOR IS BROKEN",true);
  check("independent_reading_required","THE DOOR IS BR0KEN","THE DOOR IS BR0KEN","THE DOOR IS BROKEN","THE DOOR IS BR0KEN","THE DOOR IS BROKEN","THE DOOR IS BR0KEN",false);
  check("different_crops","THE DOOR IS BR0KEN","","THE DOOR IS BROKEN","THE DOOR IS BROKEN","THE DOOR IS OPEN","THE DOOR IS OPEN",false);
  check("negation_preserved","DO NOT OPEN THE DOOR","DO NOT OPEN THE DOOR","DO OPEN THE DOOR","DO OPEN THE DOOR","DO OPEN THE DOOR","DO OPEN THE DOOR",false);
  check("content_preserved","THE RED BIRD CAN FLY","THE RED BIRD CAN FLY","THE BIRD CAN FLY","THE BIRD CAN FLY","THE BIRD CAN FLY","THE BIRD CAN FLY",false);
  check("numbers_preserved","IT WAS IN 2040","IT WAS IN 2040","IT WAS IN 2041","IT WAS IN 2041","IT WAS IN 2041","IT WAS IN 2041",false);
  check("identifiers_preserved","THE CODE IS RX2040","THE CODE IS RX2040","THE CODE IS RX2041","THE CODE IS RX2041","THE CODE IS RX2041","THE CODE IS RX2041",false);
  check("known_corroborated_word","THE BIRD IS RED","THE BIRD IS RED","THE BIRD IS BLUE","THE BIRD IS BLUE","THE BIRD IS BLUE","THE BIRD IS BLUE",false);
  check("new_nonword_rejected","THE DOOR IS XQZJ","THE DOOR IS XQZJ","THE DOOR IS XQZK","THE DOOR IS XQZK","THE DOOR IS XQZK","THE DOOR IS XQZK",false);
  check("formatting_unchanged","Open the door.","","OPEN THE DOOR!","","open the door","",false);
  auto combined=luma::recovery::Combine("THE DOOR IS BR0KEN","the door is broken",.99f,known);
  bool style=combined.text=="THE DOOR IS BROKEN";success&=style;results.push_back({{"case","reader_casing_preserved"},{"passed",style}});
  auto completion=[&](const char* name,const std::string& old,const std::string& primary,const std::string& secondary,bool expected) {
    bool actual=luma::recovery::CompleteLine(old,primary,secondary,known),passed=actual==expected;
    success&=passed;results.push_back({{"case",name},{"passed",passed},{"accepted",actual}});
  };
  completion("clipped_edge_completion","PLEASE STA","PLEASE STAND HERE","please stand here",true);
  completion("additional_known_words","THEY WORK","THEY WORK HERE","THEY WORK HERE",true);
  completion("different_readers_cannot_complete","PLEASE STA","PLEASE STAND HERE","PLEASE STAY HERE",false);
  completion("interior_word_cannot_change","THE RED BIRD","THE BLUE BIRD IS HERE","THE BLUE BIRD IS HERE",false);
  completion("new_unknown_word_rejected","PLEASE STA","PLEASE STAXQ HERE","PLEASE STAXQ HERE",false);
  completion("short_fragment_not_evidence","ST","STAND HERE","STAND HERE",false);
  completion("completion_cannot_remove_words","THEY WORK HERE","THEY WORK","THEY WORK",false);
  completion("completion_cannot_add_negation","THEY WORK","THEY DO NOT WORK","THEY DO NOT WORK",false);
  completion("completion_cannot_change_number","ROOM 2040","ROOM 2041 IS HERE","ROOM 2041 IS HERE",false);
  completion("word_boundaries_must_agree","THEY WORK","THEY WORK HERE","THEY WORKHERE",false);
  std::ofstream file(output);file<<nlohmann::json({{"success",success},{"cases",results},{"model_inference_test",false}}).dump(2);
  return success?0:1;
}

std::wstring ScreenTranslator::Translate(const std::wstring& text, const Options& options) {
  if (options.provider == L"local") throw std::runtime_error("El modelo local debe ejecutarse en el trabajador de traduccion.");
  using namespace winrt::Windows::Data::Json;
  if (options.provider == L"libre") {
    JsonObject body; body.Insert(L"q", JsonValue::CreateStringValue(text)); body.Insert(L"source", JsonValue::CreateStringValue(options.source));
    body.Insert(L"target", JsonValue::CreateStringValue(options.target)); body.Insert(L"format", JsonValue::CreateStringValue(L"text"));
    if (!options.api_key.empty()) body.Insert(L"api_key", JsonValue::CreateStringValue(options.api_key));
    auto response = JsonObject::Parse(Http(options.endpoint, std::wstring(body.Stringify())));
    if (response.HasKey(L"error")) throw std::runtime_error(winrt::to_string(response.GetNamedString(L"error")));
    return std::wstring(response.GetNamedString(L"translatedText"));
  }
  // MyMemory limits each segment to 500 UTF-8 bytes, independently of URL size.
  std::vector<std::wstring> segments; std::wstring segment;
  for (wchar_t c : text) {
    if (Utf8FromUtf16((segment + c).c_str()).size() > 450) {
      auto split=segment.find_last_of(L" \t\n");
      if (split==std::wstring::npos) { segments.push_back(segment); segment.clear(); }
      else { segments.push_back(segment.substr(0,split)); segment=segment.substr(split+1); }
    }
    segment += c;
  }
  if (!segment.empty()) segments.push_back(segment);
  std::wstring result;
  for (const auto& part : segments) {
    auto response = JsonObject::Parse(Http(L"https://api.mymemory.translated.net/get?q=" + Encode(part) + L"&langpair=" + options.source + L"%7C" + options.target));
    if (response.GetNamedNumber(L"responseStatus", 0) != 200) throw std::runtime_error("MyMemory no pudo traducir o alcanzo su cuota. Puedes configurar LibreTranslate.");
    if (!result.empty()) result += L" ";
    result += response.GetNamedObject(L"responseData").GetNamedString(L"translatedText");
  }
  for (auto pair : {std::pair{L"&quot;", L"\""}, std::pair{L"&#39;", L"'"}, std::pair{L"&amp;", L"&"}, std::pair{L"&lt;", L"<"}, std::pair{L"&gt;", L">"}}) {
    size_t at = 0; while ((at = result.find(pair.first, at)) != std::wstring::npos) { result.replace(at, wcslen(pair.first), pair.second); at += wcslen(pair.second); }
  }
  return result;
}

void ScreenTranslator::PaintToolbar(HDC dc) {
  RECT area{0,0,184,76}; HBRUSH brush = CreateSolidBrush(RGB(35,49,42)); FillRect(dc, &area, brush); DeleteObject(brush);
  Text(dc, L"⠿ Luma", {10, 0, 80, 47}, 15, RGB(221,236,210));
  HBRUSH action = CreateSolidBrush(RGB(213,239,157));
  auto oldBrush = SelectObject(dc, action); auto oldPen = SelectObject(dc, GetStockObject(NULL_PEN));
  Ellipse(dc, 87, 3, 133, 49);
  SelectObject(dc, oldPen); SelectObject(dc, oldBrush); DeleteObject(action);
  Text(dc, L"A", {96,9,114,30}, 18, RGB(35,49,42), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
  Text(dc, L"文", {108,20,126,41}, 16, RGB(35,49,42), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
  if (animating_) {
    double angle=(GetTickCount64()%900)*6.283185307/900.0;
    HPEN pen=CreatePen(PS_SOLID,3,RGB(66,101,74)); auto before=SelectObject(dc,pen);
    SetArcDirection(dc,AD_CLOCKWISE);
    Arc(dc,91,7,129,45,110+static_cast<int>(19*cos(angle)),26+static_cast<int>(19*sin(angle)),
      110+static_cast<int>(19*cos(angle+4.54)),26+static_cast<int>(19*sin(angle+4.54)));
    SelectObject(dc,before); DeleteObject(pen);
  }
  Text(dc, L"×", {146,0,178,47}, 22, RGB(230,237,226), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
  Text(dc, message_, {12,49,174,71}, 10, error_ ? RGB(255,183,156) : RGB(171,194,165));
}

void ScreenTranslator::PaintOverlay(HDC dc) {
  RECT area; GetClientRect(overlay_, &area); HBRUSH clear = CreateSolidBrush(RGB(255,0,255)); FillRect(dc, &area, clear); DeleteObject(clear);
  PaintBlocks(dc,blocks_);
}

std::vector<RECT> ScreenTranslator::PaintTextRects(const std::vector<Block>& blocks) {
  std::vector<RECT> original,rects;
  for(const auto& block:blocks){RECT r=block.rect;InflateRect(&r,3,2);original.push_back(r);}
  rects=original;
  for(size_t i=0;i<original.size();++i)for(size_t j=i+1;j<original.size();++j) {
    size_t above=i,below=j;
    if(original[above].top+original[above].bottom>original[below].top+original[below].bottom)std::swap(above,below);
    const auto& a=original[above];const auto& b=original[below];
    LONG height=std::min(a.bottom-a.top,b.bottom-b.top),width=std::min(a.right-a.left,b.right-b.left);
    LONG overlap=a.bottom-b.top,horizontal=std::min(a.right,b.right)-std::max(a.left,b.left);
    // Detector padding may intersect between consecutive rows. Keep each
    // translation in its own share instead of painting over its neighbour.
    if(overlap>0&&overlap<height*.45&&horizontal>width*.55) {
      LONG boundary=(a.bottom+b.top)/2;
      rects[above].bottom=std::min(rects[above].bottom,boundary);
      rects[below].top=std::max(rects[below].top,boundary);
    }
  }
  return rects;
}

void ScreenTranslator::PaintBlocks(HDC dc,const std::vector<Block>& blocks) {
  // Erase all source text before drawing any translated glyphs. Otherwise
  // a following background rectangle can erase an earlier translation.
  for(const auto& block:blocks) {
    RECT rect = block.rect; InflateRect(&rect, 3, 2);
    HBRUSH brush = CreateSolidBrush(block.background); FillRect(dc, &rect, brush); DeleteObject(brush);
  }
  auto rects=PaintTextRects(blocks);
  for(size_t index=0;index<blocks.size();++index) {
    const auto& block=blocks[index];RECT rect=rects[index];
    int light = (GetRValue(block.background)*299 + GetGValue(block.background)*587 + GetBValue(block.background)*114)/1000;
    int size = std::max(static_cast<int>((rect.bottom-rect.top)*.9),9);
    // Shrink within the original text box; never cover unrelated controls.
    for (; size > 8; --size) {
      RECT measured = rect;
      HFONT font = CreateFontW(-size,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,CLEARTYPE_QUALITY,DEFAULT_PITCH,L"Segoe UI");
      auto old = SelectObject(dc, font);
      DrawTextW(dc, block.text.c_str(), static_cast<int>(block.text.size()), &measured, DT_CALCRECT | DT_WORDBREAK | DT_NOPREFIX);
      SelectObject(dc, old); DeleteObject(font);
      if (measured.bottom-measured.top <= rect.bottom-rect.top && measured.right-measured.left <= rect.right-rect.left) break;
    }
    SaveDC(dc); IntersectClipRect(dc, rect.left, rect.top, rect.right, rect.bottom);
    Text(dc, block.text, rect, size, light > 140 ? RGB(25,34,29) : RGB(255,255,255), (block.centered ? DT_CENTER : DT_LEFT) | DT_WORDBREAK | DT_NOPREFIX | DT_END_ELLIPSIS);
    RestoreDC(dc, -1);
  }
}

LRESULT CALLBACK ScreenTranslator::WindowProc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
  auto self = reinterpret_cast<ScreenTranslator*>(GetWindowLongPtr(window, GWLP_USERDATA));
  if (message == WM_NCCREATE) {
    self = static_cast<ScreenTranslator*>(reinterpret_cast<CREATESTRUCT*>(lparam)->lpCreateParams);
    SetWindowLongPtr(window, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(self));
  }
  if (!self) return DefWindowProc(window,message,wparam,lparam);
  if (message == WM_MOUSEACTIVATE) return MA_NOACTIVATE;
  if (message == WM_NCHITTEST && window == self->toolbar_) {
    POINT p{GET_X_LPARAM(lparam), GET_Y_LPARAM(lparam)}; ScreenToClient(window, &p);
    return p.x < 80 ? HTCAPTION : HTCLIENT;
  }
  if (message == WM_PAINT) {
    PAINTSTRUCT ps; HDC dc = BeginPaint(window, &ps);
    if (window == self->toolbar_) self->PaintToolbar(dc); else self->PaintOverlay(dc);
    EndPaint(window, &ps); return 0;
  }
  if (message == WM_ERASEBKGND) return 1;
  if (window == self->toolbar_ && message == WM_ENTERSIZEMOVE) self->toolbar_dragging_=true;
  if (window == self->toolbar_ && message == WM_EXITSIZEMOVE) {
    self->toolbar_dragging_=false;
    if (self->watch_motion_) {
      DwmFlush();
      self->motion_reference_=MotionSample(self->motion_desktop_);
      GetWindowRect(window,&self->motion_toolbar_);
    }
  }
  // These timers animate the task or dismiss stale text; they never request OCR.
  if (message == WM_TIMER && window == self->toolbar_) {
    if (wparam==kAnimationTimer) InvalidateRect(window,nullptr,FALSE);
    else if (wparam==kMotionTimer) self->MonitorScreen();
    return 0;
  }
  if (message == WM_HOTKEY) { self->Request(); return 0; }
  if (message == WM_LBUTTONUP && window == self->toolbar_) {
    if (GET_Y_LPARAM(lparam) < 7 || GET_Y_LPARAM(lparam) > 44) return 0;
    int x = GET_X_LPARAM(lparam);
    if (x >= 146 && x <= 178) self->Stop(true);
    else if (x >= 87 && x <= 133) self->Request();
    InvalidateRect(window,nullptr,FALSE); return 0;
  }
  if (message == kCompleted) {
    std::unique_ptr<CaptureResult> result(reinterpret_cast<CaptureResult*>(lparam));
    if (result->complete) { self->busy_ = false; self->SetWorking(false); }
    if (!self->active_ || result->generation != self->generation_) return 0;
    if (!result->error.empty()) {
      if (result->blocks.empty()) { self->watch_motion_=false; KillTimer(window,kMotionTimer); ShowWindow(self->overlay_, SW_HIDE); self->Notify(result->error, true); return 0; }
    }
    self->blocks_ = std::move(result->blocks);
    self->PlaceToolbar(result->desktop,result->text_regions);
    if (result->complete && self->blocks_.empty()) { self->watch_motion_=false; KillTimer(window,kMotionTimer); }
    SetWindowPos(self->overlay_, HWND_TOPMOST, result->desktop.left, result->desktop.top, result->desktop.right-result->desktop.left, result->desktop.bottom-result->desktop.top, SWP_NOACTIVATE);
    InvalidateRect(self->overlay_,nullptr,FALSE);
    if (!self->original_) ShowWindow(self->overlay_, SW_SHOWNOACTIVATE);
    SetWindowPos(self->toolbar_,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);
    if (!result->error.empty()) self->Notify(L"Traducción parcial · " + result->error, true);
    else self->Notify(std::to_wstring(self->blocks_.size()) + (result->complete ? L" textos · Desplaza para ver original" : L" textos listos; traduciendo…"));
    return 0;
  }
  if (message == WM_DISPLAYCHANGE && self->active_) self->DismissTranslation();
  return DefWindowProc(window,message,wparam,lparam);
}

int ScreenTranslator::SelfTest(const std::string& output) {
  int exit_code = 1;
  std::thread test([&] {
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    using namespace winrt::Windows::Data::Json;
    JsonObject report;
    try {
      Frame frame{}; frame.width = 900; frame.height = 180; frame.scale = 1; frame.desktop = {0,0,900,180};
      HDC dc = CreateCompatibleDC(nullptr); BITMAPINFO info{}; info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
      info.bmiHeader.biWidth=900; info.bmiHeader.biHeight=-180; info.bmiHeader.biPlanes=1; info.bmiHeader.biBitCount=32;
      void* pixels = nullptr; HBITMAP bitmap = CreateDIBSection(dc,&info,DIB_RGB_COLORS,&pixels,nullptr,0);
      auto old = SelectObject(dc,bitmap); RECT rect{0,0,900,180}; FillRect(dc,&rect,static_cast<HBRUSH>(GetStockObject(WHITE_BRUSH)));
      Text(dc,L"Hello world",{25,25,800,120},44,RGB(0,0,0)); GdiFlush();
      frame.pixels.assign(static_cast<uint8_t*>(pixels),static_cast<uint8_t*>(pixels)+900*180*4);
      SelectObject(dc,old); DeleteObject(bitmap); DeleteDC(dc);
      luma::LocalLineRecognizer letters(LocalModelDirectory());
      auto blocks = Recognize(frame,L"en",&letters);
      if (blocks.empty()) throw std::runtime_error("OCR did not recognize the generated fixture.");
      luma::LocalTranslationModel model(LocalModelDirectory());
      auto translated = Wide(model.Translate(Utf8FromUtf16(blocks.front().text.c_str())));
      report.Insert(L"offline",JsonValue::CreateBooleanValue(true));
      if (translated != L"Hola mundo" && translated != L"Hola mundo.") throw std::runtime_error("The offline model did not translate the greeting correctly.");
      report.Insert(L"recognized",JsonValue::CreateStringValue(blocks.front().text));
      report.Insert(L"translated",JsonValue::CreateStringValue(translated));
      report.Insert(L"positioned",JsonValue::CreateBooleanValue(blocks.front().rect.right > blocks.front().rect.left));
      report.Insert(L"success",JsonValue::CreateBooleanValue(true)); exit_code = 0;
    } catch (const winrt::hresult_error& e) { report.Insert(L"error",JsonValue::CreateStringValue(e.message())); }
    catch (const std::exception& e) { report.Insert(L"error",JsonValue::CreateStringValue(Wide(e.what()))); }
    std::ofstream file(output); file << winrt::to_string(report.Stringify());
    winrt::uninit_apartment();
  });
  test.join(); return exit_code;
}

// Native lifecycle smoke test. It never reads or transmits desktop content.
int ScreenTranslator::TranslationReplay(const std::string& input,const std::string& output) {
  size_t regions=0,failures=0,recovered=0;
  try {
    std::ifstream manifest(std::filesystem::u8path(input));
    std::ofstream report(std::filesystem::u8path(output));
    if(!manifest||!report)throw std::runtime_error("No se pudo abrir la repeticion de traduccion.");
    luma::LocalTranslationModel model(LocalModelDirectory());
    std::unordered_map<std::string,luma::TranslationResult> cache;
    std::string line;
    while(std::getline(manifest,line)) {
      if(line.empty())continue;
      auto row=nlohmann::json::parse(line);
      if(row.contains("translation")||row.contains("reference")||row.contains("expected"))throw std::runtime_error("La repeticion nativa recibe solo las fuentes reconocidas.");
      try {
        std::string source=row.at("source");auto found=cache.find(source);
        luma::TranslationResult translated=found==cache.end()?model.TranslateDetailed(source):found->second;
        if(found==cache.end())cache[source]=translated;
        row["translation"]=translated.text;row["prepared"]=translated.prepared;row["raw_model"]=translated.raw;
        row["retained_original"]=translated.retained_original;row["sentence_recovered"]=translated.sentence_recovered;
        row["question_recovered"]=translated.question_recovered;recovered+=translated.question_recovered;
        row["opening_recovered"]=translated.opening_recovered;
        row["opening_source"]=translated.opening_source;
        row["opening_translation"]=translated.opening_translation;
        row["tail_recovered"]=translated.tail_recovered;
        row["tail_source"]=translated.tail_source;
        row["tail_translation"]=translated.tail_translation;
      } catch(const std::exception& error) {row["error"]=error.what();++failures;}
      report<<row.dump()<<'\n';++regions;
    }
    nlohmann::json summary{{"mode","native_translation_replay"},{"regions",regions},{"runtime_errors",failures},
      {"questions_recovered",recovered},{"new_ocr_inferences",0},{"fresh_screen_capture",false}};
    std::ofstream meta(std::filesystem::u8path(output+".summary.json"));meta<<summary.dump(2);
    return failures?1:0;
  } catch(const std::exception& error) {
    std::ofstream failure(std::filesystem::u8path(output+".error.txt"));failure<<error.what();return 1;
  }
}

int ScreenTranslator::ComicBenchmark(const std::string& input,const std::string& output) {
  int exitCode=1;
  std::thread test([&] {
    using namespace winrt::Windows::Data::Json;
    using namespace winrt::Windows::Graphics::Imaging;
    using namespace winrt::Windows::Storage::Streams;
    winrt::init_apartment(winrt::apartment_type::multi_threaded);
    std::ofstream report(output);int images=0,viewports=0,regions=0,failures=0;
    try {
      std::unique_ptr<luma::LocalTranslationModel> model;
      luma::LocalLineRecognizer letters(LocalModelDirectory());
      luma::LocalTextDetector detector(LocalModelDirectory());
      std::unique_ptr<luma::LocalLineRecognizer> referenceLetters;std::string referenceDirectory;
      std::unique_ptr<luma::LocalLineRecognizer> consensusFirst,consensusSecond;std::string consensusFirstPath,consensusSecondPath;
      std::unordered_map<std::wstring,luma::TranslationResult> cache;
      std::ifstream manifest(input);std::string line;
      while(std::getline(manifest,line)) {
        auto item=JsonObject::Parse(Wide(line));
        bool ocrOnly=item.GetNamedBoolean(L"ocr_only",false),augment=item.GetNamedBoolean(L"augment_detection",true);
        bool allCandidates=item.GetNamedBoolean(L"all_candidates",false);
        bool recoverParagraphs=item.GetNamedBoolean(L"recover_paragraphs",true);
        bool completeLines=item.GetNamedBoolean(L"complete_lines",true);
        bool recoverShort=item.GetNamedBoolean(L"recover_short_dialogue",true);
        std::wstring language(item.GetNamedString(L"language",L"en"));
        auto recognizerDirectory=winrt::to_string(item.GetNamedString(L"recognizer_directory",L""));
        auto firstPath=winrt::to_string(item.GetNamedString(L"consensus_first_directory",L""));
        auto secondPath=winrt::to_string(item.GetNamedString(L"consensus_second_directory",L""));
        if(language==L"en"&&firstPath.empty()&&secondPath.empty()&&item.GetNamedBoolean(L"reader_consensus",true)) {
          firstPath=PackagedReaderDirectory("english-v5");secondPath=PackagedReaderDirectory("multilingual-v6-small");
        }
        bool consensus=language==L"en"&&!firstPath.empty()&&!secondPath.empty();
        if(consensus) {
          if(firstPath!=consensusFirstPath){consensusFirst=std::make_unique<luma::LocalLineRecognizer>(firstPath);consensusFirstPath=firstPath;}
          if(secondPath!=consensusSecondPath){consensusSecond=std::make_unique<luma::LocalLineRecognizer>(secondPath);consensusSecondPath=secondPath;}
        }
        if(!recognizerDirectory.empty()&&recognizerDirectory!=referenceDirectory) {
          referenceLetters=std::make_unique<luma::LocalLineRecognizer>(recognizerDirectory);referenceDirectory=recognizerDirectory;
        }
        std::ifstream file(std::filesystem::path(item.GetNamedString(L"path").c_str()),std::ios::binary);
        std::vector<uint8_t> encoded((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
        if(encoded.empty())throw std::runtime_error("No se pudo leer una imagen del corpus.");
        InMemoryRandomAccessStream stream;DataWriter writer(stream);
        writer.WriteBytes(winrt::array_view<const uint8_t>(encoded));writer.StoreAsync().get();writer.DetachStream();stream.Seek(0);
        auto decoder=BitmapDecoder::CreateAsync(stream).get();
        int width=static_cast<int>(decoder.PixelWidth()),height=static_cast<int>(decoder.PixelHeight());
        std::vector<std::pair<RECT,std::wstring>> previous;
        for(int top=0;top<height;top+=1300) {
          int bottom=std::min(top+2000,height);BitmapTransform transform;
          transform.Bounds({0,static_cast<uint32_t>(top),static_cast<uint32_t>(width),static_cast<uint32_t>(bottom-top)});
          auto pixels=decoder.GetPixelDataAsync(BitmapPixelFormat::Bgra8,BitmapAlphaMode::Ignore,transform,
              ExifOrientationMode::IgnoreExifOrientation,ColorManagementMode::DoNotColorManage).get().DetachPixelData();
          Frame frame{};frame.width=width;frame.height=bottom-top;frame.scale=1;frame.desktop={0,0,width,bottom-top};
          frame.pixels.assign(pixels.begin(),pixels.end());
          auto recognized=Recognize(frame,language,language==L"en"?&letters:referenceLetters.get(),augment?&detector:nullptr,{},recoverParagraphs,completeLines,recoverShort);
          if(consensus)RecoverReaderConsensus(frame,recognized,*consensusFirst,*consensusSecond,detector);
          for(auto block:recognized) {
            if((top>0&&block.rect.top<18)||(bottom<height&&block.rect.bottom>frame.height-18))continue;
            int edgeClearance=std::min(top>0?block.rect.top:2000,bottom<height?frame.height-block.rect.bottom:2000);
            OffsetRect(&block.rect,0,top);bool duplicate=false;
            if(!allCandidates)for(auto& old:previous) {RECT overlap;if(IntersectRect(&overlap,&old.first,&block.rect)&&
                (overlap.right-overlap.left)*(overlap.bottom-overlap.top)>.7*std::min(
                  (old.first.right-old.first.left)*(old.first.bottom-old.first.top),(block.rect.right-block.rect.left)*(block.rect.bottom-block.rect.top))) {duplicate=true;break;}}
            if(duplicate)continue;previous.push_back({block.rect,block.text});
            JsonObject row;row.Insert(L"chapter",item.GetNamedValue(L"chapter"));row.Insert(L"image",item.GetNamedValue(L"image"));
            if(allCandidates)row.Insert(L"capture_edge_clearance",JsonValue::CreateNumberValue(edgeClearance));
            row.Insert(L"source",JsonValue::CreateStringValue(block.text));row.Insert(L"cropTop",JsonValue::CreateNumberValue(top));
            row.Insert(L"native_source",JsonValue::CreateStringValue(block.raw_text));
            row.Insert(L"additional_detection",JsonValue::CreateBooleanValue(block.additional_detection));
            row.Insert(L"short_dialogue_recovered",JsonValue::CreateBooleanValue(block.short_dialogue_recovered));
            row.Insert(L"reader_consensus_enabled",JsonValue::CreateBooleanValue(consensus));
            row.Insert(L"paragraph_recovered",JsonValue::CreateBooleanValue(block.paragraph_recovered));
            row.Insert(L"line_completed",JsonValue::CreateBooleanValue(block.line_completed));
            if(consensus) {
              row.Insert(L"before_consensus",JsonValue::CreateStringValue(block.before_consensus));
              row.Insert(L"first_reader",JsonValue::CreateStringValue(block.first_reader));
              row.Insert(L"second_reader",JsonValue::CreateStringValue(block.second_reader));
              row.Insert(L"consensus_recovered",JsonValue::CreateBooleanValue(block.consensus_recovered));
            }
            JsonArray words;
            for(auto& word:block.words){JsonObject entry;entry.Insert(L"text",JsonValue::CreateStringValue(word.second));JsonArray box;
              box.Append(JsonValue::CreateNumberValue(word.first.left));box.Append(JsonValue::CreateNumberValue(word.first.top+top));
              box.Append(JsonValue::CreateNumberValue(word.first.right));box.Append(JsonValue::CreateNumberValue(word.first.bottom+top));
              entry.Insert(L"bounds",box);words.Append(entry);}
            row.Insert(L"native_words",words);
            JsonArray bounds;bounds.Append(JsonValue::CreateNumberValue(block.rect.left));bounds.Append(JsonValue::CreateNumberValue(block.rect.top));
            bounds.Append(JsonValue::CreateNumberValue(block.rect.right));bounds.Append(JsonValue::CreateNumberValue(block.rect.bottom));row.Insert(L"bounds",bounds);
            if(!ocrOnly)try {
              auto found=cache.find(block.text);luma::TranslationResult translated;
              if(found!=cache.end())translated=found->second;
              else {if(!model)model=std::make_unique<luma::LocalTranslationModel>(LocalModelDirectory());translated=model->TranslateDetailed(Utf8FromUtf16(block.text.c_str()));cache[block.text]=translated;}
              row.Insert(L"translation",JsonValue::CreateStringValue(Wide(translated.text)));
              row.Insert(L"retained_original",JsonValue::CreateBooleanValue(translated.retained_original));
              row.Insert(L"sentence_recovered",JsonValue::CreateBooleanValue(translated.sentence_recovered));
              row.Insert(L"question_recovered",JsonValue::CreateBooleanValue(translated.question_recovered));
              row.Insert(L"opening_recovered",JsonValue::CreateBooleanValue(translated.opening_recovered));
              row.Insert(L"tail_recovered",JsonValue::CreateBooleanValue(translated.tail_recovered));
              if(translated.sentence_recovered) {
                row.Insert(L"whole_translation",JsonValue::CreateStringValue(Wide(translated.whole_translation)));
                JsonArray sources,outputs;
                for(const auto& value:translated.sentence_sources)sources.Append(JsonValue::CreateStringValue(Wide(value)));
                for(const auto& value:translated.sentence_translations)outputs.Append(JsonValue::CreateStringValue(Wide(value)));
                row.Insert(L"sentence_sources",sources);row.Insert(L"sentence_translations",outputs);
              }
              if(translated.retained_original)row.Insert(L"reason",JsonValue::CreateStringValue(Wide(translated.reason)));
            } catch(const std::exception& error) {row.Insert(L"error",JsonValue::CreateStringValue(Wide(error.what())));++failures;}
            report<<winrt::to_string(row.Stringify())<<'\n';++regions;
          }
          ++viewports;if(bottom==height)break;
        }
        ++images;report.flush();
      }
      JsonObject summary;summary.Insert(L"images",JsonValue::CreateNumberValue(images));summary.Insert(L"viewports",JsonValue::CreateNumberValue(viewports));
      summary.Insert(L"regions",JsonValue::CreateNumberValue(regions));summary.Insert(L"runtime_errors",JsonValue::CreateNumberValue(failures));
      std::ofstream status(output+".summary.json");status<<winrt::to_string(summary.Stringify());exitCode=0;
    } catch(const winrt::hresult_error& error) {std::ofstream status(output+".error.txt");status<<winrt::to_string(error.message());}
    catch(const std::exception& error) {std::ofstream status(output+".error.txt");status<<error.what();}
    winrt::uninit_apartment();
  });test.join();return exitCode;
}

int ScreenTranslator::ToolbarTest(const std::string& output) {
  using namespace winrt::Windows::Data::Json;
  HWND owner = CreateWindowExW(WS_EX_TOOLWINDOW,L"STATIC",L"Luma toolbar test",WS_OVERLAPPED,0,0,1,1,nullptr,nullptr,GetModuleHandle(nullptr),nullptr);
  JsonObject report;
  {
    ScreenTranslator translator(owner,nullptr);
    // Older clients may still send automatic=true. It must never start OCR.
    translator.Start({{flutter::EncodableValue("automatic"),flutter::EncodableValue(true)}});
    WindowProc(translator.toolbar_,WM_TIMER,1,0);
    report.Insert(L"manualOnly",JsonValue::CreateBooleanValue(!translator.busy_));
    RECT before{}; GetWindowRect(translator.toolbar_,&before);
    report.Insert(L"visible",JsonValue::CreateBooleanValue(IsWindowVisible(translator.toolbar_) != FALSE));
    report.Insert(L"topmost",JsonValue::CreateBooleanValue((GetWindowLongPtr(translator.toolbar_,GWL_EXSTYLE)&WS_EX_TOPMOST) != 0));
    report.Insert(L"clickThrough",JsonValue::CreateBooleanValue((GetWindowLongPtr(translator.overlay_,GWL_EXSTYLE)&WS_EX_TRANSPARENT) != 0));
    auto hit = WindowProc(translator.toolbar_,WM_NCHITTEST,0,MAKELPARAM(before.left+20,before.top+20));
    report.Insert(L"draggable",JsonValue::CreateBooleanValue(hit == HTCAPTION));
    WNDCLASSW fixtureClass{};fixtureClass.hInstance=GetModuleHandle(nullptr);fixtureClass.lpszClassName=L"LumaCaptureFixture";
    fixtureClass.lpfnWndProc=[](HWND window,UINT message,WPARAM w,LPARAM l)->LRESULT {
      if(message==WM_PAINT){PAINTSTRUCT ps{};HDC dc=BeginPaint(window,&ps);RECT area{};GetClientRect(window,&area);
        FillRect(dc,&area,static_cast<HBRUSH>(GetStockObject(WHITE_BRUSH)));Text(dc,L"Hello world",{8,8,176,68},25,RGB(0,0,0));EndPaint(window,&ps);return 0;}
      return DefWindowProc(window,message,w,l);
    };
    RegisterClassW(&fixtureClass);
    HWND fixture=CreateWindowExW(WS_EX_TOPMOST|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE,fixtureClass.lpszClassName,L"",WS_POPUP,
        before.left,before.top,before.right-before.left,before.bottom-before.top,nullptr,nullptr,fixtureClass.hInstance,nullptr);
    ShowWindow(fixture,SW_SHOWNOACTIVATE);UpdateWindow(fixture);
    SetWindowPos(translator.toolbar_,HWND_TOPMOST,0,0,0,0,SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE);DwmFlush();
    auto clean=translator.CaptureFrame();DestroyWindow(fixture);
    int left=static_cast<int>((before.left-clean.desktop.left)*clean.scale),top=static_cast<int>((before.top-clean.desktop.top)*clean.scale);
    int right=std::min(clean.width,static_cast<int>((before.right-clean.desktop.left)*clean.scale));
    int bottom=std::min(clean.height,static_cast<int>((before.bottom-clean.desktop.top)*clean.scale));
    Frame covered{};covered.width=right-left;covered.height=bottom-top;covered.scale=1;covered.desktop={0,0,covered.width,covered.height};
    covered.pixels.resize(static_cast<size_t>(covered.width)*covered.height*4);
    for(int y=0;y<covered.height;++y)std::copy_n(clean.pixels.data()+(static_cast<size_t>(top+y)*clean.width+left)*4,
        static_cast<size_t>(covered.width)*4,covered.pixels.data()+static_cast<size_t>(y)*covered.width*4);
    bool recovered=false;
    std::thread check([&]{winrt::init_apartment(winrt::apartment_type::multi_threaded);
      try{for(const auto& block:Recognize(covered,L"en"))if(block.text.find(L"Hello world")!=std::wstring::npos)recovered=true;}catch(...){}
      winrt::uninit_apartment();});check.join();
    report.Insert(L"captureRecoversTextBehindToolbar",JsonValue::CreateBooleanValue(recovered));
    report.Insert(L"captureRestoresToolbar",JsonValue::CreateBooleanValue(IsWindowVisible(translator.toolbar_)!=FALSE));
    RECT obstacle=before;OffsetRect(&obstacle,-clean.desktop.left,-clean.desktop.top);
    translator.PlaceToolbar(clean.desktop,{obstacle});RECT moved{};GetWindowRect(translator.toolbar_,&moved);RECT overlap{};
    report.Insert(L"toolbarAvoidsRecognizedText",JsonValue::CreateBooleanValue(!IntersectRect(&overlap,&before,&moved)));
    RECT same{},space{0,0,1000,800},position{10,10,194,86};
    report.Insert(L"clearUserPositionPreserved",JsonValue::CreateBooleanValue(ToolbarPosition(position,space,{},same)&&EqualRect(&position,&same)));
    report.Insert(L"noFreePositionDetected",JsonValue::CreateBooleanValue(!ToolbarPosition(position,space,{space},same)));
    translator.watch_motion_=true;
    translator.blocks_.push_back({{10,10,100,40},L"Generated fixture",RGB(255,255,255)});
    WindowProc(translator.toolbar_,WM_ENTERSIZEMOVE,0,0);
    translator.MonitorScreen();
    report.Insert(L"toolbarDragPreservesTranslation",JsonValue::CreateBooleanValue(translator.toolbar_dragging_ && !translator.blocks_.empty()));
    WindowProc(translator.toolbar_,WM_EXITSIZEMOVE,0,0);
    report.Insert(L"toolbarDragRefreshesReference",JsonValue::CreateBooleanValue(!translator.toolbar_dragging_ && translator.motion_reference_.size()==96*64));
    translator.SetWorking(true);
    report.Insert(L"workingAnimation",JsonValue::CreateBooleanValue(translator.animating_));
    int oldGeneration=translator.generation_;
    translator.DismissTranslation();
    report.Insert(L"movementRestoresOriginal",JsonValue::CreateBooleanValue(translator.original_ && translator.blocks_.empty() && !translator.animating_));
    auto stale=new CaptureResult(); stale->generation=oldGeneration;
    stale->blocks.push_back({{10,10,100,40},L"Stale fixture",RGB(255,255,255)});
    WindowProc(translator.toolbar_,kCompleted,0,reinterpret_cast<LPARAM>(stale));
    report.Insert(L"staleResultIgnored",JsonValue::CreateBooleanValue(translator.blocks_.empty()));
    translator.Stop(false);
    report.Insert(L"closed",JsonValue::CreateBooleanValue(!translator.active_ && !IsWindowVisible(translator.toolbar_) && !IsWindowVisible(translator.overlay_)));
  }
  DestroyWindow(owner);
  std::ofstream file(output); file << winrt::to_string(report.Stringify());
  return 0;
}
