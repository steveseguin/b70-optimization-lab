cmake_minimum_required(VERSION 3.22)
project(muse_onednn_operand_layout LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(muse-onednn-operand-layout onednn-operand-layout.cpp)
target_compile_options(muse-onednn-operand-layout PRIVATE -O3 -fsycl)
target_link_options(muse-onednn-operand-layout PRIVATE -fsycl)

find_path(DNNL_INCLUDE_DIR oneapi/dnnl/dnnl.hpp
    HINTS /opt/intel/oneapi/dnnl/latest/include /opt/intel/oneapi/dnnl/2026.0/include
    REQUIRED)
find_library(DNNL_LIBRARY dnnl
    HINTS /opt/intel/oneapi/dnnl/latest/lib /opt/intel/oneapi/dnnl/2026.0/lib
    REQUIRED)
target_include_directories(muse-onednn-operand-layout PRIVATE ${DNNL_INCLUDE_DIR})
target_link_libraries(muse-onednn-operand-layout PRIVATE ${DNNL_LIBRARY})
