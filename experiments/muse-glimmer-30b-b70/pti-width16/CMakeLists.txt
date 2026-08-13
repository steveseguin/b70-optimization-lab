cmake_minimum_required(VERSION 3.22)
project(muse_pti_width16 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(muse-pti-width16 SHARED pti-width16-collector.cpp)
target_compile_options(muse-pti-width16 PRIVATE -O2)

find_path(PTI_INCLUDE_DIR pti/pti_view.h
    HINTS /opt/intel/oneapi/pti/latest/include /opt/intel/oneapi/pti/1.0/include
    REQUIRED)
find_library(PTI_VIEW_LIBRARY pti_view
    HINTS /opt/intel/oneapi/pti/latest/lib /opt/intel/oneapi/pti/1.0/lib
    REQUIRED)
target_include_directories(muse-pti-width16 PRIVATE ${PTI_INCLUDE_DIR})
target_include_directories(muse-pti-width16 PRIVATE
    /home/steve/src/llama.cpp-muse-100/include
    /home/steve/src/llama.cpp-muse-100/ggml/include)
target_link_libraries(muse-pti-width16 PRIVATE ${PTI_VIEW_LIBRARY} pthread dl)
