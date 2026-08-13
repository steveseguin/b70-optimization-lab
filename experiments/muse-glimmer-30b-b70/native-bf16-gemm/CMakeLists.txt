cmake_minimum_required(VERSION 3.22)
project(muse_native_bf16_gemm LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(muse-native-bf16-gemm native-bf16-gemm.cpp)
target_compile_options(muse-native-bf16-gemm PRIVATE -O3 -fsycl)
target_link_options(muse-native-bf16-gemm PRIVATE -fsycl)

find_path(DNNL_INCLUDE_DIR oneapi/dnnl/dnnl.hpp
    HINTS /opt/intel/oneapi/dnnl/latest/include /opt/intel/oneapi/dnnl/2026.0/include
    REQUIRED)
find_library(DNNL_LIBRARY dnnl
    HINTS /opt/intel/oneapi/dnnl/latest/lib /opt/intel/oneapi/dnnl/2026.0/lib
    REQUIRED)
target_include_directories(muse-native-bf16-gemm PRIVATE ${DNNL_INCLUDE_DIR})
target_link_libraries(muse-native-bf16-gemm PRIVATE ${DNNL_LIBRARY})
