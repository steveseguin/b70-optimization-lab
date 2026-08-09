cmake_minimum_required(VERSION 3.16)

project(q8_canonical_mmvq_component_gate LANGUAGES CXX)

set(GGML_SOURCE_DIR "" CACHE PATH "llama.cpp source tree containing ggml/include")
set(GGML_LIBRARY_DIR "" CACHE PATH "directory containing the exact libggml*.so runtime set")

if(NOT IS_ABSOLUTE "${GGML_SOURCE_DIR}")
    message(FATAL_ERROR "GGML_SOURCE_DIR must be an absolute path")
endif()
if(NOT IS_ABSOLUTE "${GGML_LIBRARY_DIR}")
    message(FATAL_ERROR "GGML_LIBRARY_DIR must be an absolute path")
endif()

set(GGML_INCLUDE_DIR "${GGML_SOURCE_DIR}/ggml/include")
set(GGML_LIBRARY "${GGML_LIBRARY_DIR}/libggml.so")
set(GGML_BASE_LIBRARY "${GGML_LIBRARY_DIR}/libggml-base.so")

foreach(required_path
        "${GGML_INCLUDE_DIR}/ggml.h"
        "${GGML_INCLUDE_DIR}/ggml-backend.h"
        "${GGML_LIBRARY}"
        "${GGML_BASE_LIBRARY}")
    if(NOT EXISTS "${required_path}")
        message(FATAL_ERROR "required component-gate artifact is missing: ${required_path}")
    endif()
endforeach()

add_executable(q8-canonical-mmvq-component-gate q8-canonical-mmvq-component-gate.cpp)
target_compile_features(q8-canonical-mmvq-component-gate PRIVATE cxx_std_17)
target_compile_options(q8-canonical-mmvq-component-gate PRIVATE -Wall -Wextra -Wpedantic)
target_include_directories(q8-canonical-mmvq-component-gate PRIVATE "${GGML_INCLUDE_DIR}")
target_link_libraries(q8-canonical-mmvq-component-gate PRIVATE
    "${GGML_LIBRARY}"
    "${GGML_BASE_LIBRARY}"
)

# The runner independently checks every resolved ggml object with ldd. Keeping
# the selected library directory in RUNPATH also makes a copied command fail
# against a missing runtime instead of silently selecting a system ggml.
set_target_properties(q8-canonical-mmvq-component-gate PROPERTIES
    BUILD_RPATH "${GGML_LIBRARY_DIR}"
)
