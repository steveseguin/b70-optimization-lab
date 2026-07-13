cmake_minimum_required(VERSION 3.24)
project(q27_xe2_hot_kernel_module LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(Q27_XE2_DEVICE "bmg-g31" CACHE STRING "Intel GPU AOT device")
set(Q27_XE2_BUILD_ID "prototype-v1" CACHE STRING "Module build identifier")
set(Q27_XE2_TOOLCHAIN_ABI "oneapi-2026.0-sycl-cxx17" CACHE STRING "Strict host/module ABI tag")

set(Q27_SYCL_COMPILE_OPTIONS
    -O3
    -fsycl
    -fsycl-targets=spir64_gen)
set(Q27_SYCL_LINK_OPTIONS
    -fsycl
    -fsycl-targets=spir64_gen
    "SHELL:-Xs \"-device ${Q27_XE2_DEVICE}\"")

add_library(q27_xe2_smoke MODULE module.cpp)
target_compile_options(q27_xe2_smoke PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_xe2_smoke PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_xe2_smoke PRIVATE
    Q27_XE2_BUILD_ID="${Q27_XE2_BUILD_ID}"
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}"
    Q27_XE2_TARGET_ARCH="${Q27_XE2_DEVICE}")
set_target_properties(q27_xe2_smoke PROPERTIES PREFIX "lib" OUTPUT_NAME "q27_xe2_smoke")

add_executable(q27_xe2_loader loader.cpp)
target_compile_options(q27_xe2_loader PRIVATE ${Q27_SYCL_COMPILE_OPTIONS})
target_link_options(q27_xe2_loader PRIVATE ${Q27_SYCL_LINK_OPTIONS})
target_compile_definitions(q27_xe2_loader PRIVATE
    Q27_XE2_TOOLCHAIN_ABI="${Q27_XE2_TOOLCHAIN_ABI}")
target_link_libraries(q27_xe2_loader PRIVATE dl)
