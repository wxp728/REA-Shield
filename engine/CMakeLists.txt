# Anti-REA Transform Engine (LLVM Pass plugin) —— R1 MVP
# 构建：cmake -S engine -B engine/build -DLLVM_DIR=<llvm>/lib/cmake/llvm && cmake --build engine/build
# 设计: docs/design/ddd/dd-03-llvm-transforms.md
cmake_minimum_required(VERSION 3.16)
project(anti_rea_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(LLVM REQUIRED CONFIG)
message(STATUS "Anti-REA: using LLVM ${LLVM_PACKAGE_VERSION} from ${LLVM_DIR}")

set(LLVM_CMAKE_DIR "${LLVM_DIR}/../cmake")
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")
include(AddLLVM)

add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS})

add_llvm_pass_plugin(anti_rea_passes
  passes/anti_rea_passes.cpp
)
