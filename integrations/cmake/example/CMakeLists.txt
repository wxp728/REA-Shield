cmake_minimum_required(VERSION 3.16)
project(anti_rea_cmake_example C)

add_executable(app src/app.c)

# 接入 Anti-REA CMake 插件（FR-D2）
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/..")
include(AntiRea)
anti_rea_protect(
  ROOT "${CMAKE_CURRENT_SOURCE_DIR}"
  SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/src/app.c"
  OUT "${CMAKE_CURRENT_BINARY_DIR}/anti-rea"
  SEED 7
  ABORT)
