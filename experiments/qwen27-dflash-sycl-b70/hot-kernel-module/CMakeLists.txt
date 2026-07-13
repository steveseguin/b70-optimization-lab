cmake_minimum_required(VERSION 3.24)
project(q27_xe2_hot_kernel_module LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(Q27_XE2_DEVICE "bmg-g31" CACHE STRING "Intel GPU AOT device")
set(Q27_XE2_BUILD_ID "gdn-qkvzab-folded-gate-v1" CACHE STRING "Module build identifier")
set(Q27_XE2_TOOLCHAIN_ABI "oneapi-2026.0-sycl-cxx17" CACHE STRING "Strict host/module ABI tag")
set(LLAMA_ROOT "/home/steve/src/llama.cpp" CACHE PATH "Protected llama.cpp source used read-only by comparator")
set(LLAMA_BUILD "${LLAMA_ROOT}/build-sycl-b70-qwen36-mtp" CACHE PATH "AOT llama.cpp build used by comparator")

set(Q27_SYCL_COMPILE_OPTIONS
    -O3
    -fsycl
    -fsycl-targets=spir64_gen)
set(Q27_SYCL_LINK_OPTIONS
    -fsycl
    -fsycl-targets=spir64_gen
    "SHELL:-Xs \"-device ${Q27_XE2_DEVICE}\"")

add_library(q27_xe2_module MODULE module.cpp q6_m6_top1_module.cpp gdn_qkvz_m6_module.cpp)
target_compile_options(q27_xe2_module PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_xe2_module PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_xe2_module PRIVATE
    Q27_XE2_BUILD_ID="${Q27_XE2_BUILD_ID}"
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}"
    Q27_XE2_TARGET_ARCH="${Q27_XE2_DEVICE}")
set_target_properties(q27_xe2_module PROPERTIES PREFIX "lib" OUTPUT_NAME "q27_xe2_module")

add_executable(q27_xe2_loader loader.cpp)
target_compile_options(q27_xe2_loader PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_xe2_loader PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_xe2_loader PRIVATE
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}")
target_link_libraries(q27_xe2_loader PRIVATE dl)

add_library(q27_ggml_sycl_runtime SHARED IMPORTED)
set_target_properties(q27_ggml_sycl_runtime PROPERTIES
    IMPORTED_LOCATION "${LLAMA_BUILD}/bin/libggml-sycl.so.0.16.0")

add_executable(q27_q6_module_compare q6_module_compare.cpp)
target_compile_options(q27_q6_module_compare PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_q6_module_compare PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_q6_module_compare PRIVATE
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}"
    GGML_BACKEND_BUILD
    GGML_BACKEND_SHARED
    GGML_SCHED_MAX_COPIES=4
    GGML_SHARED
    GGML_SYCL_DNNL=1
    GGML_SYCL_F16
    GGML_SYCL_GRAPH
    GGML_SYCL_HOST_MEM_FALLBACK
    GGML_SYCL_SUPPORT_LEVEL_ZERO_API
    GGML_SYCL_WARP_SIZE=16
    _GNU_SOURCE
    _XOPEN_SOURCE=600)
target_include_directories(q27_q6_module_compare PRIVATE
    "${LLAMA_ROOT}/ggml/src"
    "${LLAMA_ROOT}/ggml/include"
    "/opt/intel/oneapi/dnnl/2026.0/include"
    "/opt/intel/oneapi/mkl/2026.0/include")
target_link_libraries(q27_q6_module_compare PRIVATE q27_ggml_sycl_runtime dl)
set_target_properties(q27_q6_module_compare PROPERTIES
    BUILD_RPATH "${LLAMA_BUILD}/bin;/opt/intel/oneapi/dnnl/2026.0/lib;/opt/intel/oneapi/mkl/2026.0/lib")

add_executable(q27_gdn_qkvz_module_compare gdn_qkvz_module_compare.cpp)
target_compile_options(q27_gdn_qkvz_module_compare PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_gdn_qkvz_module_compare PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_gdn_qkvz_module_compare PRIVATE
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}"
    GGML_BACKEND_BUILD
    GGML_BACKEND_SHARED
    GGML_SCHED_MAX_COPIES=4
    GGML_SHARED
    GGML_SYCL_DNNL=1
    GGML_SYCL_F16
    GGML_SYCL_GRAPH
    GGML_SYCL_HOST_MEM_FALLBACK
    GGML_SYCL_SUPPORT_LEVEL_ZERO_API
    GGML_SYCL_WARP_SIZE=16
    _GNU_SOURCE
    _XOPEN_SOURCE=600)
target_include_directories(q27_gdn_qkvz_module_compare PRIVATE
    "${LLAMA_ROOT}/ggml/src"
    "${LLAMA_ROOT}/ggml/include"
    "/opt/intel/oneapi/dnnl/2026.0/include"
    "/opt/intel/oneapi/mkl/2026.0/include")
target_link_libraries(q27_gdn_qkvz_module_compare PRIVATE
    q27_ggml_sycl_runtime
    /opt/intel/oneapi/mkl/2026.0/lib/libmkl_sycl_blas.so
    dl)
set_target_properties(q27_gdn_qkvz_module_compare PROPERTIES
    BUILD_RPATH "${LLAMA_BUILD}/bin;/opt/intel/oneapi/dnnl/2026.0/lib;/opt/intel/oneapi/mkl/2026.0/lib")
