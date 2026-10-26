cmake_minimum_required(VERSION 3.18)
project(luma_local_translation LANGUAGES CXX)

include(cmake/translation_core.cmake)

set(LUMA_TOOLS_DEFAULT OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(LUMA_TOOLS_DEFAULT ON)
endif()
option(LUMA_BUILD_TOOLS "Build native evaluation tools and tests" ${LUMA_TOOLS_DEFAULT})
if(LUMA_BUILD_TOOLS)
  include(cmake/benchmark_targets.cmake)
endif()
