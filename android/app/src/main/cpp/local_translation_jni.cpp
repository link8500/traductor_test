#include <jni.h>
#include <android/asset_manager_jni.h>
#include "local_translation.h"
#include "json.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace {
struct AndroidModel {
  AAsset* encoder=nullptr;AAsset* decoder=nullptr;AAsset* letters=nullptr;AAsset* fallbackLetters=nullptr;AAsset* detection=nullptr;
  std::unique_ptr<luma::LocalTranslationModel> engine;
  std::unique_ptr<luma::LocalLineRecognizer> recognizer;
  std::unique_ptr<luma::LocalTextDetector> detector;std::atomic<uint64_t> cancellation{0};
  ~AndroidModel(){engine.reset();recognizer.reset();detector.reset();if(encoder)AAsset_close(encoder);if(decoder)AAsset_close(decoder);if(letters)AAsset_close(letters);if(fallbackLetters)AAsset_close(fallbackLetters);if(detection)AAsset_close(detection);}
};
luma::LocalTranslationModel* Model(jlong value) {
  if (!value) throw std::runtime_error("El modelo local esta cerrado.");
  return reinterpret_cast<AndroidModel*>(value)->engine.get();
}
std::string Source(JNIEnv* env,jbyteArray input) {
  std::string source(static_cast<size_t>(env->GetArrayLength(input)),'\0');
  env->GetByteArrayRegion(input,0,static_cast<jsize>(source.size()),reinterpret_cast<jbyte*>(source.data()));
  return source;
}
void Error(JNIEnv* env,const std::exception& error) {
  env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),error.what());
}
}
extern "C" JNIEXPORT jlong JNICALL Java_com_example_traductor_LocalMarian_nativeCreate(JNIEnv* env,jobject,jstring directory,jobject assets) {
  const char* chars=env->GetStringUTFChars(directory,nullptr);
  std::string path(chars);env->ReleaseStringUTFChars(directory,chars);
  try {
    auto handle=std::make_unique<AndroidModel>();auto manager=AAssetManager_fromJava(env,assets);
    handle->encoder=AAssetManager_open(manager,"flutter_assets/assets/models/opus-en-es/encoder.onnx",AASSET_MODE_BUFFER);
    handle->decoder=AAssetManager_open(manager,"flutter_assets/assets/models/opus-en-es/decoder.onnx",AASSET_MODE_BUFFER);
    if(!handle->encoder||!handle->decoder)throw std::runtime_error("Faltan los pesos del modelo local en el APK.");
    luma::ModelBytes data{AAsset_getBuffer(handle->encoder),static_cast<size_t>(AAsset_getLength64(handle->encoder)),
                         AAsset_getBuffer(handle->decoder),static_cast<size_t>(AAsset_getLength64(handle->decoder))};
    if(!data.encoder||!data.decoder)throw std::runtime_error("No se pudieron abrir los pesos del modelo local.");
    handle->engine=std::make_unique<luma::LocalTranslationModel>(path,data);
    handle->letters=AAssetManager_open(manager,"flutter_assets/assets/models/opus-en-es/english-ocr.onnx",AASSET_MODE_BUFFER);
    handle->fallbackLetters=AAssetManager_open(manager,"flutter_assets/assets/models/opus-en-es/english-ocr-fallback.onnx",AASSET_MODE_BUFFER);
    if(!handle->letters||!handle->fallbackLetters)throw std::runtime_error("Falta un reconocedor local en el APK.");
    if(!AAsset_getBuffer(handle->letters)||!AAsset_getBuffer(handle->fallbackLetters))throw std::runtime_error("No se pudieron abrir los reconocedores locales.");
    handle->recognizer=std::make_unique<luma::LocalLineRecognizer>(path,AAsset_getBuffer(handle->letters),static_cast<size_t>(AAsset_getLength64(handle->letters)),
        AAsset_getBuffer(handle->fallbackLetters),static_cast<size_t>(AAsset_getLength64(handle->fallbackLetters)));
    handle->detection=AAssetManager_open(manager,"flutter_assets/assets/models/opus-en-es/text-detector.onnx",AASSET_MODE_BUFFER);
    if(!handle->detection)throw std::runtime_error("Falta el detector de texto local en el APK.");
    handle->detector=std::make_unique<luma::LocalTextDetector>(path,AAsset_getBuffer(handle->detection),static_cast<size_t>(AAsset_getLength64(handle->detection)));
    return reinterpret_cast<jlong>(handle.release());
  }
  catch(const std::exception& error){Error(env,error);return 0;}
}
extern "C" JNIEXPORT jbyteArray JNICALL Java_com_example_traductor_LocalMarian_nativeTranslate(JNIEnv* env,jobject,jlong handle,jbyteArray input) {
  try {
    auto translated=Model(handle)->TranslateDetailed(Source(env,input));
    auto result=nlohmann::json{{"translation",translated.text},{"retained_original",translated.retained_original},{"reason",translated.reason}}.dump();
    auto bytes=env->NewByteArray(static_cast<jsize>(result.size()));
    env->SetByteArrayRegion(bytes,0,static_cast<jsize>(result.size()),reinterpret_cast<const jbyte*>(result.data()));return bytes;
  } catch(const std::exception& error){Error(env,error);return nullptr;}
}
extern "C" JNIEXPORT jlongArray JNICALL Java_com_example_traductor_LocalMarian_nativeTokenize(JNIEnv* env,jobject,jlong handle,jbyteArray input) {
  try {
    auto tokens=Model(handle)->Tokenize(Source(env,input));auto result=env->NewLongArray(static_cast<jsize>(tokens.size()));
    env->SetLongArrayRegion(result,0,static_cast<jsize>(tokens.size()),reinterpret_cast<const jlong*>(tokens.data()));return result;
  } catch(const std::exception& error){Error(env,error);return nullptr;}
}
extern "C" JNIEXPORT void JNICALL Java_com_example_traductor_LocalMarian_nativeCancel(JNIEnv*,jobject,jlong handle) {if(handle){++reinterpret_cast<AndroidModel*>(handle)->cancellation;Model(handle)->Cancel();}}
extern "C" JNIEXPORT jbyteArray JNICALL Java_com_example_traductor_LocalMarian_nativeDetect(JNIEnv* env,jobject,jlong handle,jintArray input,jint width,jint height,jintArray existing,jlong expectedGeneration) {
  auto model=reinterpret_cast<AndroidModel*>(handle);if(!model||!model->detector||!model->recognizer)return nullptr;
  if(width<=0||height<=0||width>4096||height>4096||env->GetArrayLength(input)!=static_cast<jlong>(width)*height||env->GetArrayLength(existing)%4) {
    env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),"Invalid detector image");return nullptr;}
  std::vector<jint> known(static_cast<size_t>(env->GetArrayLength(existing)));if(!known.empty())env->GetIntArrayRegion(existing,0,static_cast<jsize>(known.size()),known.data());
  uint64_t generation=static_cast<uint64_t>(expectedGeneration);auto cancelled=[&]{return generation!=model->cancellation;};
  jint* pixels=env->GetIntArrayElements(input,nullptr);if(!pixels)return nullptr;
  nlohmann::json lines=nlohmann::json::array();
  try {
    for(const auto& box:model->detector->Detect(reinterpret_cast<uint8_t*>(pixels),width,height,width*4,cancelled)) {
      if(cancelled())break;
      int left=width,top=height,right=0,bottom=0;
      for(int i=0;i<4;++i){left=std::min(left,static_cast<int>(std::floor(box.corners[i*2])));top=std::min(top,static_cast<int>(std::floor(box.corners[i*2+1])));
        right=std::max(right,static_cast<int>(std::ceil(box.corners[i*2])));bottom=std::max(bottom,static_cast<int>(std::ceil(box.corners[i*2+1])));}
      if(right<=left||bottom<=top)continue;
      bool covered=false;
      for(size_t i=0;i<known.size();i+=4){int iw=std::min(right,known[i+2])-std::max(left,known[i]),ih=std::min(bottom,known[i+3])-std::max(top,known[i+1]);
        if(iw>0&&ih>0&&iw*ih>.5*std::min((right-left)*(bottom-top),(known[i+2]-known[i])*(known[i+3]-known[i+1]))){covered=true;break;}}
      if(covered)continue;
      auto read=model->recognizer->ReadQuad(reinterpret_cast<uint8_t*>(pixels),width,height,width*4,box.corners);
      // DB includes vertical padding around tall decorative letters. Retry
      // that padding only; retain the full word width and require agreement
      // with the first reading instead of accepting a weaker confidence.
      if(read.confidence>=.75f&&read.confidence<.87f&&box.confidence>=.9f&&!cancelled()) {
        auto key=[](const std::string& text){std::string result;for(unsigned char c:text) {
          if(c==' '||c=='\n'||c=='\r'||c=='\t')continue;
          result+=static_cast<char>(c>='a'&&c<='z'?c-'a'+'A':c);
        }return result;};
        for(float factor:{.9f,.8f}) {
          auto tighter=box.corners;
          for(int side=0;side<2;++side)for(int coordinate=0;coordinate<2;++coordinate) {
            int upper=side*2+coordinate,lower=(3-side)*2+coordinate;
            float middle=(box.corners[upper]+box.corners[lower])*.5f;
            tighter[upper]=middle+(box.corners[upper]-middle)*factor;
            tighter[lower]=middle+(box.corners[lower]-middle)*factor;
          }
          if(cancelled())break;
          auto retry=model->recognizer->ReadQuad(reinterpret_cast<uint8_t*>(pixels),width,height,width*4,tighter);
          if(retry.confidence>=.9f&&retry.confidence>read.confidence+.025f&&key(retry.text)==key(read.text)) {read=retry;break;}
        }
      }
      int alphabetic=0;for(char c:read.text)if((c>='a'&&c<='z')||(c>='A'&&c<='Z'))++alphabetic;
      if(read.confidence<.87f||alphabetic<2)continue;
      lines.push_back({{"text",read.text},{"confidence",read.confidence},{"bounds",{left,top,right,bottom}},{"quad",box.corners}});
    }
  }catch(const std::exception& error){env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);Error(env,error);return nullptr;}
  env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);
  auto json=lines.dump();auto bytes=env->NewByteArray(static_cast<jsize>(json.size()));env->SetByteArrayRegion(bytes,0,static_cast<jsize>(json.size()),reinterpret_cast<const jbyte*>(json.data()));return bytes;
}
extern "C" JNIEXPORT jbyteArray JNICALL Java_com_example_traductor_LocalMarian_nativeRecognize(JNIEnv* env,jobject,jlong handle,jintArray input,jint width,jint height) {
  auto model=reinterpret_cast<AndroidModel*>(handle);if(!model||!model->recognizer)return nullptr;
  if(width<=0||height<=0||width>4096||height>4096||env->GetArrayLength(input)!=static_cast<jlong>(width)*height) {env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),"Invalid OCR image size");return nullptr;}
  jint* pixels=env->GetIntArrayElements(input,nullptr);luma::RecognizedLine result;
  try {result=model->recognizer->Read(reinterpret_cast<uint8_t*>(pixels),width,height,width*4,0,0,width,height);}
  catch(const std::exception& error) {env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);Error(env,error);return nullptr;}
  env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);
  auto json=nlohmann::json{{"text",result.text},{"confidence",result.confidence}}.dump();auto bytes=env->NewByteArray(static_cast<jsize>(json.size()));
  env->SetByteArrayRegion(bytes,0,static_cast<jsize>(json.size()),reinterpret_cast<const jbyte*>(json.data()));return bytes;
}
extern "C" JNIEXPORT void JNICALL Java_com_example_traductor_LocalMarian_nativeDestroy(JNIEnv*,jobject,jlong handle) {delete reinterpret_cast<AndroidModel*>(handle);}
extern "C" JNIEXPORT jbyteArray JNICALL Java_com_example_traductor_LocalMarian_nativeRecognizeWithHint(JNIEnv* env,jobject,jlong handle,jintArray input,jint width,jint height,jbyteArray hint) {
  auto model=reinterpret_cast<AndroidModel*>(handle);if(!model||!model->recognizer)return nullptr;
  if(width<=0||height<=0||width>4096||height>4096||env->GetArrayLength(input)!=static_cast<jlong>(width)*height) {env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),"Invalid OCR image size");return nullptr;}
  auto text=Source(env,hint);jint* pixels=env->GetIntArrayElements(input,nullptr);if(!pixels)return nullptr;
  luma::RecognizedLine result;
  try {result=model->recognizer->ReadWithHint(reinterpret_cast<uint8_t*>(pixels),width,height,width*4,0,0,width,height,text);}
  catch(const std::exception& error) {env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);Error(env,error);return nullptr;}
  env->ReleaseIntArrayElements(input,pixels,JNI_ABORT);
  auto json=nlohmann::json{{"text",result.text},{"confidence",result.confidence},{"system_agreement",result.system_agreement}}.dump();
  auto bytes=env->NewByteArray(static_cast<jsize>(json.size()));env->SetByteArrayRegion(bytes,0,static_cast<jsize>(json.size()),reinterpret_cast<const jbyte*>(json.data()));return bytes;
}
