cmake_minimum_required(VERSION 3.22)
project(muse_qg_projection_lending LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(muse-qg-projection-lending qg-projection-lending.cpp)
target_compile_options(muse-qg-projection-lending PRIVATE -O3 -fsycl)
target_link_options(muse-qg-projection-lending PRIVATE -fsycl)

find_path(DNNL_INCLUDE_DIR oneapi/dnnl/dnnl.hpp
    HINTS /opt/intel/oneapi/dnnl/latest/include /opt/intel/oneapi/dnnl/2026.0/include
    REQUIRED)
find_library(DNNL_LIBRARY dnnl
    HINTS /opt/intel/oneapi/dnnl/latest/lib /opt/intel/oneapi/dnnl/2026.0/lib
    REQUIRED)
target_include_directories(muse-qg-projection-lending PRIVATE ${DNNL_INCLUDE_DIR})
target_link_libraries(muse-qg-projection-lending PRIVATE ${DNNL_LIBRARY})
