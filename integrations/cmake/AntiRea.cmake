# AntiRea.cmake —— CMake 构建集成（FR-D2）
#
# 用法：
#   list(APPEND CMAKE_MODULE_PATH "<repo>/integrations/cmake")
#   include(AntiRea)
#   anti_rea_protect(ROOT <src-root> SOURCES <f.c> OUT <dir> [SEED n] [ABORT])
#
# 说明：不内嵌引擎，仅在 POST_BUILD 阶段调用集成驱动 scan→plan→protect→verify；
#       ABORT 时验证失败令构建以非零退出（FR-D7）。

set(ANTI_REA_CMAKE_DIR "${CMAKE_CURRENT_LIST_DIR}")

function(anti_rea_protect)
  cmake_parse_arguments(AR "ABORT" "ROOT;OUT;SEED" "SOURCES" ${ARGN})
  if(NOT AR_ROOT)
    set(AR_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
  endif()
  if(NOT AR_OUT)
    set(AR_OUT "${CMAKE_CURRENT_BINARY_DIR}/anti-rea")
  endif()

  set(_driver "${ANTI_REA_CMAKE_DIR}/../anti-rea")
  if(NOT EXISTS "${_driver}")
    set(_driver "${ANTI_REA_CMAKE_DIR}/../anti_rea.py")
  endif()

  set(_args pipeline --root "${AR_ROOT}" --out "${AR_OUT}")
  foreach(_s IN LISTS AR_SOURCES)
    list(APPEND _args --source "${_s}")
  endforeach()
  if(AR_SEED)
    list(APPEND _args --seed "${AR_SEED}")
  endif()
  if(AR_ABORT)
    list(APPEND _args --abort-on-failure)
  endif()

  add_custom_command(
    OUTPUT "${AR_OUT}/verification_report.json"
    COMMAND "${_driver}" ${_args}
    DEPENDS ${AR_SOURCES}
    COMMENT "REA-Shield: 施加保护并验证（FR-D2）"
    VERBATIM)
  add_custom_target(anti_rea_protect ALL
    DEPENDS "${AR_OUT}/verification_report.json")
endfunction()
