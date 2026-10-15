# Anti-REA Transform Engine (LLVM Pass plugin) —— R2
# 构建：cmake -S engine -B engine/build -DLLVM_DIR=<llvm>/lib/cmake/llvm && cmake --build engine/build
# 设计: docs/design/ddd/dd-03-llvm-transforms.md、dd-04-virtualization.md
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
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/vm)

add_llvm_pass_plugin(anti_rea_passes
  passes/anti_rea_passes.cpp
)

# 虚拟机解释器 -> LLVM bitcode（与目标一起链接，见 dd-04）
# 使用 LLVM 自带 clang；若不可用则退化为提示。
find_program(ANTI_REA_CLANG NAMES clang
  HINTS "${LLVM_TOOLS_BINARY_DIR}" "${LLVM_BINARY_DIR}/bin")
if(ANTI_REA_CLANG)
  add_custom_command(
    OUTPUT "${CMAKE_BINARY_DIR}/vm_interp.bc"
    COMMAND "${ANTI_REA_CLANG}" -O2 -emit-llvm -c
            "${CMAKE_CURRENT_SOURCE_DIR}/vm/vm_interp.c"
            -I "${CMAKE_CURRENT_SOURCE_DIR}/vm"
            -o "${CMAKE_BINARY_DIR}/vm_interp.bc"
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/vm/vm_interp.c"
            "${CMAKE_CURRENT_SOURCE_DIR}/vm/vm_isa.h"
    COMMENT "Anti-REA: 构建 VM 解释器 bitcode (vm_interp.bc)")
  add_custom_target(anti_rea_vm ALL DEPENDS "${CMAKE_BINARY_DIR}/vm_interp.bc")
else()
  message(WARNING "Anti-REA: 未找到 clang，跳过 VM 解释器 bitcode 构建")
endif()
