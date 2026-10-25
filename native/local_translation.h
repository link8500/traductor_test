#pragma once
#include <atomic>
#include <array>
#include <cstdint>
#include <cstddef>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace luma {
struct ModelBytes {const void* encoder=nullptr;size_t encoder_size=0;const void* decoder=nullptr;size_t decoder_size=0;};
struct TranslationResult {
  std::string text,raw,prepared,reason,whole_translation;
  std::string opening_source,opening_translation;
  std::string tail_source,tail_translation;
  std::vector<std::string> terminology,source_corrections,sentence_sources,sentence_translations;
  bool retained_original=false,sentence_recovered=false,question_recovered=false,opening_recovered=false,tail_recovered=false;
};
struct RecognizedLine {std::string text;float confidence=0;int left=0,right=0;bool system_agreement=false;};
struct DetectedText {std::array<float,8> corners{};float confidence=0;};
class LocalTextDetector {
 public:
  explicit LocalTextDetector(const std::string& directory,const void* model=nullptr,size_t model_size=0);
  ~LocalTextDetector();
  std::vector<DetectedText> Detect(const uint8_t* bgra,int width,int height,int stride,const std::function<bool()>& cancelled = {});
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
class LocalLineRecognizer {
 public:
  explicit LocalLineRecognizer(const std::string& directory,const void* model=nullptr,size_t model_size=0,
      const void* fallback_model=nullptr,size_t fallback_size=0);
  ~LocalLineRecognizer();
  RecognizedLine Read(const uint8_t* bgra,int width,int height,int stride,int left,int top,int right,int bottom);
  RecognizedLine ReadWithHint(const uint8_t* bgra,int width,int height,int stride,int left,int top,int right,int bottom,const std::string& system_text);
  RecognizedLine ReadQuad(const uint8_t* bgra,int width,int height,int stride,const std::array<float,8>& corners,const std::string& system_text = {});
  RecognizedLine ReadFamilyQuad(const uint8_t* bgra,int width,int height,int stride,const std::array<float,8>& corners,bool secondary);
 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
// The same quantized model, tokenizer and search run on Android and Windows.
class LocalTranslationModel {
 public:
  explicit LocalTranslationModel(const std::string& directory, ModelBytes bytes = {});
  ~LocalTranslationModel();
  LocalTranslationModel(const LocalTranslationModel&) = delete;
  LocalTranslationModel& operator=(const LocalTranslationModel&) = delete;
  std::string Translate(const std::string& text, const std::function<bool()>& cancelled = {});
  TranslationResult TranslateDetailed(const std::string& text, const std::function<bool()>& cancelled = {});
  TranslationResult PrepareInput(const std::string& text) const;
  std::vector<int64_t> Tokenize(const std::string& text) const;
  void Cancel();
  static std::string PrepareSource(const std::string& text);
 private:
  TranslationResult TranslateCoreDetailed(const std::string& text,const std::function<bool()>& cancelled);
  TranslationResult TranslateBaseDetailed(const std::string& text,const std::function<bool()>& cancelled);
  struct Impl;
  std::unique_ptr<Impl> impl_;
};
}
