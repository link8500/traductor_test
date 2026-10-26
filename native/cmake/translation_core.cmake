include_guard(GLOBAL)

get_filename_component(LUMA_NATIVE_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

add_library(luma_json INTERFACE)
add_library(luma::json ALIAS luma_json)
target_include_directories(luma_json INTERFACE "${LUMA_NATIVE_ROOT}/third_party/json")

# One engine target for Windows, Android JNI and command-line evaluations.
add_library(luma_translation_core STATIC "${LUMA_NATIVE_ROOT}/local_translation.cpp")
add_library(luma::translation_core ALIAS luma_translation_core)
target_compile_features(luma_translation_core PUBLIC cxx_std_17)
set_target_properties(luma_translation_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(luma_translation_core
  PUBLIC "${LUMA_NATIVE_ROOT}"
  PRIVATE "${LUMA_NATIVE_ROOT}/third_party/onnxruntime/include")
target_link_libraries(luma_translation_core PRIVATE luma::json)

if(COMMAND apply_standard_settings)
  apply_standard_settings(luma_translation_core)
endif()
if(MSVC)
  target_compile_definitions(luma_translation_core PRIVATE NOMINMAX)
  target_compile_options(luma_translation_core PRIVATE /utf-8 /EHsc)
endif()
if(WIN32)
  target_link_libraries(luma_translation_core PRIVATE normaliz)
else()
  target_link_libraries(luma_translation_core PRIVATE ${CMAKE_DL_LIBS})
endif()
